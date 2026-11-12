#ifndef VIT_INFERENCE_FIXED_H
#define VIT_INFERENCE_FIXED_H

#include "fixed_types.h"

extern "C" void vit_inference_fixed(const ap_int<16> *ecg_q10,
                                    const ap_int<16> *rr_q10,
                                    ap_int<16> *logits_q10);

#endif  // VIT_INFERENCE_FIXED_H
