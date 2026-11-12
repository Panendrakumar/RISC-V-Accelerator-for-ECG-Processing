#include "vit_inference.h"
#include "golden_test_vectors.h"
#include <cstdio>

int main() {
    int failures = 0;
    for (int sample = 0; sample < GOLDEN_COUNT; ++sample) {
        float ecg[ECG_LEN];
        float rr[RR_LEN];
        float logits[CLASS_COUNT] = {};
        for (int i = 0; i < ECG_LEN; ++i) ecg[i] = GOLDEN_ECG[sample][i];
        for (int i = 0; i < RR_LEN; ++i) rr[i] = GOLDEN_RR[sample][i];

        vit_inference(ecg, rr, logits);
        int predicted = 0;
        for (int c = 1; c < CLASS_COUNT; ++c)
            if (logits[c] > logits[predicted]) predicted = c;
        std::printf("vector %d true=%d reference=%d HLS-C=%d\n", sample,
                    GOLDEN_TRUE_CLASS[sample],
                    GOLDEN_EXPECTED_CLASS[sample], predicted);
        if (predicted != GOLDEN_EXPECTED_CLASS[sample]) ++failures;
    }
    std::printf("Reference-class mismatches: %d / %d\n", failures,
                GOLDEN_COUNT);
    return failures == 0 ? 0 : 1;
}
