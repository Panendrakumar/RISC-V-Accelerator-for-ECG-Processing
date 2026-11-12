#include "vit_inference_fixed.h"
#include "golden_test_vectors.h"
#include <cstdio>

static ap_int<16> encode_input(float value) {
    q_t quantized = q_t(value);
    ap_int<16> raw = quantized.range(15, 0);
    return raw;
}

static q_t decode_output(ap_int<16> raw) {
    q_t value;
    value.range(15, 0) = raw;
    return value;
}

int main() {
    int mismatches = 0;
    for (int sample = 0; sample < GOLDEN_COUNT; ++sample) {
        ap_int<16> ecg[198];
        ap_int<16> rr[2];
        ap_int<16> logits_raw[5];
        for (int i = 0; i < 198; ++i)
            ecg[i] = encode_input(GOLDEN_ECG[sample][i]);
        for (int i = 0; i < 2; ++i)
            rr[i] = encode_input(GOLDEN_RR[sample][i]);

        vit_inference_fixed(ecg, rr, logits_raw);
        int predicted = 0;
        q_t logits[5];
        for (int c = 0; c < 5; ++c) logits[c] = decode_output(logits_raw[c]);
        for (int c = 1; c < 5; ++c)
            if (logits[c] > logits[predicted]) predicted = c;
        std::printf("vector %d expected=%d fixed=%d\n", sample,
                    GOLDEN_EXPECTED_CLASS[sample], predicted);
        if (predicted != GOLDEN_EXPECTED_CLASS[sample]) ++mismatches;
    }
    std::printf("Fixed-point reference mismatches: %d / %d\n", mismatches,
                GOLDEN_COUNT);
    return mismatches == 0 ? 0 : 1;
}
