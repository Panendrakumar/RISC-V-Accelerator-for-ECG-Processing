#include <stdint.h>
#include "demo_model_data.h"

#define HLS_BASE       0x40000000u
#define GPIO_BASE      0x40010000u
#define HLS_CTRL       (*(volatile uint32_t *)(HLS_BASE + 0x00u))
#define HLS_ECG_PTR_LO (*(volatile uint32_t *)(HLS_BASE + 0x10u))
#define HLS_ECG_PTR_HI (*(volatile uint32_t *)(HLS_BASE + 0x14u))
#define HLS_RR_PTR_LO  (*(volatile uint32_t *)(HLS_BASE + 0x1Cu))
#define HLS_RR_PTR_HI  (*(volatile uint32_t *)(HLS_BASE + 0x20u))
#define HLS_OUT_PTR_LO (*(volatile uint32_t *)(HLS_BASE + 0x28u))
#define HLS_OUT_PTR_HI (*(volatile uint32_t *)(HLS_BASE + 0x2Cu))

static volatile int16_t logits_q10[5] = {0, 0, 0, 0, 0};

int main(void)
{
    volatile uint32_t *gpio_data = (volatile uint32_t *)GPIO_BASE;
    uint32_t best = 0;

    // LED[2:0] = 111 while the accelerator is busy.
    *gpio_data = 7u;

    // HLS pointer registers are 64-bit; the PicoRV32 address space is 32-bit.
    HLS_ECG_PTR_LO = (uint32_t)(uintptr_t)demo_ecg_q10;
    HLS_ECG_PTR_HI = 0;
    HLS_RR_PTR_LO = (uint32_t)(uintptr_t)demo_rr_q10;
    HLS_RR_PTR_HI = 0;
    HLS_OUT_PTR_LO = (uint32_t)(uintptr_t)logits_q10;
    HLS_OUT_PTR_HI = 0;

    // ap_start is bit 0 of the HLS ap_ctrl register.
    HLS_CTRL = 1u;
    while ((HLS_CTRL & 0x2u) == 0u) {
        __asm__ volatile ("nop");
    }

    // Argmax on signed Q6.10 logits; scale does not affect the winning class.
    for (uint32_t i = 1; i < 5; ++i) {
        if (logits_q10[i] > logits_q10[best])
            best = i;
    }

    // Binary class+1 on LEDs: N=001, S=010, V=011, F=100, Q=101.
    *gpio_data = best + 1u;
    for (;;) {
        __asm__ volatile ("nop");
    }
}
