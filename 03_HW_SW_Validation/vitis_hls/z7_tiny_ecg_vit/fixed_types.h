#ifndef FIXED_TYPES_H
#define FIXED_TYPES_H

#include <ap_fixed.h>
#include <ap_int.h>

// Signed Q6.10 format. Inputs are sent as the raw two's-complement 16-bit
// representation; all model activations and weights use the same format.
typedef ap_fixed<16, 6, AP_RND_CONV, AP_SAT> q_t;
typedef ap_fixed<32, 12, AP_RND_CONV, AP_SAT> acc_t;

#endif  // FIXED_TYPES_H
