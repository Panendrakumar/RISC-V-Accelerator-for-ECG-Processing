#ifndef VIT_INFERENCE_H
#define VIT_INFERENCE_H

#define ECG_LEN 198
#define RR_LEN 2
#define CLASS_COUNT 5

extern "C" void vit_inference(const float *ecg, const float *rr, float *logits);

#endif  // VIT_INFERENCE_H
