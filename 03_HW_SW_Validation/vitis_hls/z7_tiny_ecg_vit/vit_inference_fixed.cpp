// Q6.10 inference port of the project's saved Tiny ECG Transformer checkpoint.
// It keeps the learned dimensions and weights; nonlinearities use Q6.10 LUTs.

#include "vit_inference_fixed.h"
#include "fixed_model_assets.h"
#include <hls_math.h>

namespace {
constexpr int PATCHES = 66;
constexpr int EMBED = 16;
constexpr int HEADS = 8;
constexpr int HEAD_DIM = 2;
constexpr int FF = 128;
const q_t LN_EPSILON = q_t(0.0009765625);  // Nearest Q6.10 value to 1e-3.
const q_t INV_SQRT_HEAD_DIM = q_t(0.70703125);

q_t decode_q10(ap_int<16> raw) {
    q_t value;
    value.range(15, 0) = raw;
    return value;
}

ap_int<16> encode_q10(q_t value) {
    ap_int<16> raw = value.range(15, 0);
    return raw;
}

q_t gelu_lut(q_t x) {
    if (x <= q_t(-8.0)) return q_t(0.0);
    if (x >= q_t(8.0)) return x;
    acc_t position = acc_t(x + q_t(8.0)) * acc_t(16.0);
    int index = position.to_int();
    if (index < 0) index = 0;
    if (index > 255) index = 255;
    q_t fraction = q_t(position - acc_t(index));
    return q_t(GELU_LUT[index] + fraction * (GELU_LUT[index + 1] - GELU_LUT[index]));
}

q_t exp_lut(q_t x) {
    if (x <= q_t(-12.0)) return q_t(0.0);
    if (x >= q_t(0.0)) return q_t(1.0);
    acc_t position = acc_t(x + q_t(12.0)) * acc_t(21.3330078125);
    int index = position.to_int();
    if (index < 0) index = 0;
    if (index > 255) index = 255;
    q_t fraction = q_t(position - acc_t(index));
    return q_t(EXP_LUT[index] + fraction * (EXP_LUT[index + 1] - EXP_LUT[index]));
}

void layer_norm(const q_t in[PATCHES][EMBED], q_t out[PATCHES][EMBED],
                const q_t gamma[EMBED], const q_t beta[EMBED]) {
    for (int p = 0; p < PATCHES; ++p) {
        acc_t sum = 0;
        for (int e = 0; e < EMBED; ++e) sum += in[p][e];
        q_t mean = q_t(sum / q_t(EMBED));

        acc_t variance_sum = 0;
        for (int e = 0; e < EMBED; ++e) {
            q_t difference = in[p][e] - mean;
            variance_sum += difference * difference;
        }
        q_t variance = q_t(variance_sum / q_t(EMBED));
        q_t root = hls::sqrt(variance + LN_EPSILON);
        q_t inverse_std = q_t(1.0) / root;
        for (int e = 0; e < EMBED; ++e)
            out[p][e] = (in[p][e] - mean) * inverse_std * gamma[e] + beta[e];
    }
}

void dense1(const q_t in[PATCHES][EMBED], q_t out[PATCHES][FF]) {
    for (int p = 0; p < PATCHES; ++p) {
        for (int j = 0; j < FF; ++j) {
            acc_t sum = B_FF1[j];
            for (int i = 0; i < EMBED; ++i)
                sum += in[p][i] * W_FF1[i * FF + j];
            out[p][j] = gelu_lut(q_t(sum));
        }
    }
}

void dense2(const q_t in[PATCHES][FF], q_t out[PATCHES][EMBED]) {
    for (int p = 0; p < PATCHES; ++p) {
        for (int j = 0; j < EMBED; ++j) {
            acc_t sum = B_FF2[j];
            for (int i = 0; i < FF; ++i)
                sum += in[p][i] * W_FF2[i * EMBED + j];
            out[p][j] = gelu_lut(q_t(sum));
        }
    }
}
}  // namespace

extern "C" void vit_inference_fixed(const ap_int<16> *ecg_q10,
                                    const ap_int<16> *rr_q10,
                                    ap_int<16> *logits_q10) {
#pragma HLS INTERFACE m_axi port=ecg_q10 offset=slave bundle=gmem depth=198
#pragma HLS INTERFACE m_axi port=rr_q10 offset=slave bundle=gmem depth=2
#pragma HLS INTERFACE m_axi port=logits_q10 offset=slave bundle=gmem depth=5
#pragma HLS INTERFACE s_axilite port=ecg_q10 bundle=control
#pragma HLS INTERFACE s_axilite port=rr_q10 bundle=control
#pragma HLS INTERFACE s_axilite port=logits_q10 bundle=control
#pragma HLS INTERFACE s_axilite port=return bundle=control

    q_t patches[PATCHES][EMBED];
    q_t norm1[PATCHES][EMBED];
    q_t q[PATCHES][HEADS][HEAD_DIM];
    q_t k[PATCHES][HEADS][HEAD_DIM];
    q_t v[PATCHES][HEADS][HEAD_DIM];
    q_t attended[PATCHES][EMBED];
    q_t residual1[PATCHES][EMBED];
    q_t norm2[PATCHES][EMBED];
    q_t hidden[PATCHES][FF];
    q_t projected[PATCHES][EMBED];
    q_t residual2[PATCHES][EMBED];
    q_t norm_out[PATCHES][EMBED];

    for (int p = 0; p < PATCHES; ++p) {
        for (int e = 0; e < EMBED; ++e) {
            acc_t sum = B_CONV[e];
            for (int tap = 0; tap < 3; ++tap)
                sum += decode_q10(ecg_q10[p * 3 + tap]) * W_CONV[tap * EMBED + e];
            patches[p][e] = q_t(sum) + W_POS[p * EMBED + e];
        }
    }

    layer_norm(patches, norm1, GAMMA_1, BETA_1);

    for (int p = 0; p < PATCHES; ++p) {
        for (int h = 0; h < HEADS; ++h) {
            for (int d = 0; d < HEAD_DIM; ++d) {
                acc_t qs = B_Q[h * HEAD_DIM + d];
                acc_t ks = B_K[h * HEAD_DIM + d];
                acc_t vs = B_V[h * HEAD_DIM + d];
                for (int e = 0; e < EMBED; ++e) {
                    int wi = (e * HEADS + h) * HEAD_DIM + d;
                    qs += norm1[p][e] * W_Q[wi];
                    ks += norm1[p][e] * W_K[wi];
                    vs += norm1[p][e] * W_V[wi];
                }
                q[p][h][d] = q_t(qs);
                k[p][h][d] = q_t(ks);
                v[p][h][d] = q_t(vs);
            }
        }
    }

    for (int p = 0; p < PATCHES; ++p)
        for (int e = 0; e < EMBED; ++e) attended[p][e] = 0;

    for (int h = 0; h < HEADS; ++h) {
        for (int qp = 0; qp < PATCHES; ++qp) {
            q_t scores[PATCHES];
            q_t maximum = q_t(-32.0);
            for (int kp = 0; kp < PATCHES; ++kp) {
                acc_t dot = 0;
                for (int d = 0; d < HEAD_DIM; ++d)
                    dot += q[qp][h][d] * k[kp][h][d];
                scores[kp] = q_t(q_t(dot) * INV_SQRT_HEAD_DIM);
                if (scores[kp] > maximum) maximum = scores[kp];
            }
            q_t exponents[PATCHES];
            acc_t denominator = 0;
            for (int kp = 0; kp < PATCHES; ++kp) {
                exponents[kp] = exp_lut(scores[kp] - maximum);
                denominator += exponents[kp];
            }
            // denominator can be as large as 66; preserve it in acc_t before
            // division because Q6.10 saturates above 31.999.
            q_t inv_denominator = q_t(acc_t(1.0) / denominator);
            for (int d = 0; d < HEAD_DIM; ++d) {
                acc_t context = 0;
                for (int kp = 0; kp < PATCHES; ++kp)
                    context += (exponents[kp] * inv_denominator) * v[kp][h][d];
                int concat = h * HEAD_DIM + d;
                for (int e = 0; e < EMBED; ++e)
                    attended[qp][e] += q_t(context) * W_O[concat * EMBED + e];
            }
        }
    }

    for (int p = 0; p < PATCHES; ++p)
        for (int e = 0; e < EMBED; ++e)
            residual1[p][e] = attended[p][e] + B_O[e] + patches[p][e];

    layer_norm(residual1, norm2, GAMMA_2, BETA_2);
    dense1(norm2, hidden);
    dense2(hidden, projected);
    for (int p = 0; p < PATCHES; ++p)
        for (int e = 0; e < EMBED; ++e)
            residual2[p][e] = projected[p][e] + residual1[p][e];
    layer_norm(residual2, norm_out, GAMMA_OUT, BETA_OUT);

    q_t pooled[EMBED];
    for (int e = 0; e < EMBED; ++e) {
        acc_t sum = 0;
        for (int p = 0; p < PATCHES; ++p) sum += norm_out[p][e];
        // PATCHES=66 is outside Q6.10's range. Divide in the wider type.
        pooled[e] = q_t(sum / acc_t(PATCHES));
    }

    q_t combined[18];
    for (int e = 0; e < EMBED; ++e) combined[e] = pooled[e];
    q_t rr0 = decode_q10(rr_q10[0]);
    q_t rr1 = decode_q10(rr_q10[1]);
    combined[16] = rr0 * W_RR[0] + rr1 * W_RR[2];
    combined[17] = rr0 * W_RR[1] + rr1 * W_RR[3];

    for (int c = 0; c < 5; ++c) {
        acc_t sum = B_HEAD[c];
        for (int i = 0; i < 18; ++i) sum += combined[i] * W_HEAD[i * 5 + c];
        logits_q10[c] = encode_q10(q_t(sum));
    }
}
