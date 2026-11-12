// Checkpoint-matched FP32 inference starter for the local Tiny ECG Transformer.
// It is an HLS function, not yet connected to the PicoRV32 memory bus.

#include "vit_inference.h"
#include "active_model_weights.h"
#include <hls_math.h>

namespace {
constexpr int PATCHES = 66;
constexpr int EMBED = 16;
constexpr int HEADS = 8;
constexpr int HEAD_DIM = 2;
constexpr int FF = 128;
constexpr float LN_EPSILON = 1.0e-3f;  // Keras LayerNormalization default.
constexpr float INV_SQRT_HEAD_DIM = 0.7071067811865475f;
constexpr float INV_SQRT_2 = 0.7071067811865475f;

inline float gelu_exact(float x) {
    return 0.5f * x * (1.0f + hls::erff(x * INV_SQRT_2));
}

void layer_norm(const float in[PATCHES][EMBED], float out[PATCHES][EMBED],
                const float gamma[EMBED], const float beta[EMBED]) {
    for (int p = 0; p < PATCHES; ++p) {
        float mean = 0.0f;
        for (int e = 0; e < EMBED; ++e) mean += in[p][e];
        mean /= static_cast<float>(EMBED);

        float variance = 0.0f;
        for (int e = 0; e < EMBED; ++e) {
            const float d = in[p][e] - mean;
            variance += d * d;
        }
        variance /= static_cast<float>(EMBED);
        const float inv_std = 1.0f / hls::sqrtf(variance + LN_EPSILON);
        for (int e = 0; e < EMBED; ++e)
            out[p][e] = (in[p][e] - mean) * inv_std * gamma[e] + beta[e];
    }
}

void dense_patch(const float in[PATCHES][EMBED], float out[PATCHES][FF],
                 const float weights[EMBED * FF], const float bias[FF]) {
    for (int p = 0; p < PATCHES; ++p) {
        for (int j = 0; j < FF; ++j) {
            float sum = bias[j];
            for (int i = 0; i < EMBED; ++i)
                sum += in[p][i] * weights[i * FF + j];
            out[p][j] = gelu_exact(sum);
        }
    }
}

void dense_patch_back(const float in[PATCHES][FF], float out[PATCHES][EMBED],
                      const float weights[FF * EMBED],
                      const float bias[EMBED]) {
    for (int p = 0; p < PATCHES; ++p) {
        for (int j = 0; j < EMBED; ++j) {
            float sum = bias[j];
            for (int i = 0; i < FF; ++i)
                sum += in[p][i] * weights[i * EMBED + j];
            // The selected notebook applies GELU to the second Dense too.
            out[p][j] = gelu_exact(sum);
        }
    }
}
}  // namespace

extern "C" void vit_inference(const float *ecg, const float *rr,
                              float *logits) {
#pragma HLS INTERFACE m_axi port=ecg offset=slave bundle=gmem depth=198
#pragma HLS INTERFACE m_axi port=rr offset=slave bundle=gmem depth=2
#pragma HLS INTERFACE m_axi port=logits offset=slave bundle=gmem depth=5
#pragma HLS INTERFACE s_axilite port=ecg bundle=control
#pragma HLS INTERFACE s_axilite port=rr bundle=control
#pragma HLS INTERFACE s_axilite port=logits bundle=control
#pragma HLS INTERFACE s_axilite port=return bundle=control

    float patches[PATCHES][EMBED];
    float norm1[PATCHES][EMBED];
    float q[PATCHES][HEADS][HEAD_DIM];
    float k[PATCHES][HEADS][HEAD_DIM];
    float v[PATCHES][HEADS][HEAD_DIM];
    float attended[PATCHES][EMBED];
    float residual1[PATCHES][EMBED];
    float norm2[PATCHES][EMBED];
    float hidden[PATCHES][FF];
    float projected[PATCHES][EMBED];
    float residual2[PATCHES][EMBED];
    float norm_out[PATCHES][EMBED];

    // Conv2D kernel (3,1), stride (3,1), valid padding -> 66 x 16.
    for (int p = 0; p < PATCHES; ++p) {
        for (int e = 0; e < EMBED; ++e) {
            float sum = B_CONV[e];
            for (int tap = 0; tap < 3; ++tap)
                sum += ecg[p * 3 + tap] * W_CONV[tap * EMBED + e];
            patches[p][e] = sum + W_POS[p * EMBED + e];
        }
    }

    layer_norm(patches, norm1, GAMMA_1, BETA_1);

    // Keras MultiHeadAttention: Q/K/V projections, scaled dot-product,
    // softmax over key positions, concatenate heads, output projection.
    for (int p = 0; p < PATCHES; ++p) {
        for (int h = 0; h < HEADS; ++h) {
            for (int d = 0; d < HEAD_DIM; ++d) {
                float qs = B_Q[h * HEAD_DIM + d];
                float ks = B_K[h * HEAD_DIM + d];
                float vs = B_V[h * HEAD_DIM + d];
                for (int e = 0; e < EMBED; ++e) {
                    const int wi = (e * HEADS + h) * HEAD_DIM + d;
                    qs += norm1[p][e] * W_Q[wi];
                    ks += norm1[p][e] * W_K[wi];
                    vs += norm1[p][e] * W_V[wi];
                }
                q[p][h][d] = qs;
                k[p][h][d] = ks;
                v[p][h][d] = vs;
            }
        }
    }

    for (int p = 0; p < PATCHES; ++p) {
        for (int e = 0; e < EMBED; ++e) attended[p][e] = 0.0f;
    }

    for (int h = 0; h < HEADS; ++h) {
        for (int qp = 0; qp < PATCHES; ++qp) {
            float scores[PATCHES];
            float maximum = -3.402823466e+38f;
            for (int kp = 0; kp < PATCHES; ++kp) {
                float dot = 0.0f;
                for (int d = 0; d < HEAD_DIM; ++d)
                    dot += q[qp][h][d] * k[kp][h][d];
                scores[kp] = dot * INV_SQRT_HEAD_DIM;
                if (scores[kp] > maximum) maximum = scores[kp];
            }
            float denominator = 0.0f;
            for (int kp = 0; kp < PATCHES; ++kp) {
                scores[kp] = hls::expf(scores[kp] - maximum);
                denominator += scores[kp];
            }
            for (int d = 0; d < HEAD_DIM; ++d) {
                float context = 0.0f;
                for (int kp = 0; kp < PATCHES; ++kp)
                    context += (scores[kp] / denominator) * v[kp][h][d];
                const int concat = h * HEAD_DIM + d;
                for (int e = 0; e < EMBED; ++e)
                    attended[qp][e] += context * W_O[concat * EMBED + e];
            }
        }
    }

    for (int p = 0; p < PATCHES; ++p) {
        for (int e = 0; e < EMBED; ++e)
            residual1[p][e] = attended[p][e] + B_O[e] + patches[p][e];
    }

    layer_norm(residual1, norm2, GAMMA_2, BETA_2);
    dense_patch(norm2, hidden, W_FF1, B_FF1);
    dense_patch_back(hidden, projected, W_FF2, B_FF2);
    for (int p = 0; p < PATCHES; ++p)
        for (int e = 0; e < EMBED; ++e)
            residual2[p][e] = projected[p][e] + residual1[p][e];

    layer_norm(residual2, norm_out, GAMMA_OUT, BETA_OUT);

    float pooled[EMBED];
    for (int e = 0; e < EMBED; ++e) {
        float sum = 0.0f;
        for (int p = 0; p < PATCHES; ++p) sum += norm_out[p][e];
        pooled[e] = sum / static_cast<float>(PATCHES);
    }

    float combined[18];
    for (int e = 0; e < EMBED; ++e) combined[e] = pooled[e];
    for (int j = 0; j < 2; ++j)
        combined[EMBED + j] = rr[0] * W_RR[j] + rr[1] * W_RR[2 + j];

    for (int c = 0; c < CLASS_COUNT; ++c) {
        float sum = B_HEAD[c];
        for (int i = 0; i < 18; ++i) sum += combined[i] * W_HEAD[i * 5 + c];
        logits[c] = sum;
    }
}
