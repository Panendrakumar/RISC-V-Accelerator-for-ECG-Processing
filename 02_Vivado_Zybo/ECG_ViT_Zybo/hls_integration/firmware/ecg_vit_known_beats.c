// Known-beat self-test for the PicoRV32 + Q6.10 ECG Transformer accelerator.
//
// For each of the saved golden beats the firmware:
//   1. fills the 5-value output buffer with a marker (so "never written" is detectable),
//   2. points the accelerator at the beat, starts it and waits for "done",
//   3. checks that all 5 outputs were overwritten,
//   4. takes the argmax and compares it with the class the FP32 checkpoint predicts.
//
// LEDs (LD2:LD0 = AXI GPIO, LD3 = CPU trap, driven by hardware):
//   000            gap between beats
//   001 010 011 100 101   predicted class N S V F Q (class index + 1), ~1 s each
//   111 (steady)   all beats passed
//   110 blinking   failure (timeout, outputs not written, or wrong class)
// Press BTN0 (reset) to run the whole test again.
//
// This is a 9-beat self-test, NOT an accuracy measurement.

#include <stdint.h>
#include "known_beats_data.h"

#define HLS_BASE       0x40000000u
#define GPIO_BASE      0x40010000u
#define HLS_CTRL       (*(volatile uint32_t *)(HLS_BASE + 0x00u))
#define HLS_ECG_PTR_LO (*(volatile uint32_t *)(HLS_BASE + 0x10u))
#define HLS_ECG_PTR_HI (*(volatile uint32_t *)(HLS_BASE + 0x14u))
#define HLS_RR_PTR_LO  (*(volatile uint32_t *)(HLS_BASE + 0x1Cu))
#define HLS_RR_PTR_HI  (*(volatile uint32_t *)(HLS_BASE + 0x20u))
#define HLS_OUT_PTR_LO (*(volatile uint32_t *)(HLS_BASE + 0x28u))
#define HLS_OUT_PTR_HI (*(volatile uint32_t *)(HLS_BASE + 0x2Cu))
#define LEDS           (*(volatile uint32_t *)GPIO_BASE)

// Delay lengths are loop counts, not exact times (the CPU runs from BRAM through
// AXI, so a loop iteration costs many clock cycles). If the LEDs change too fast
// or too slow, change these numbers and rebuild.
#define SHOW_ITER    1500000u   // time a class code stays lit
#define GAP_ITER      500000u   // dark gap between beats
#define BLINK_ITER    300000u   // failure blink half-period
#define TIMEOUT_ITER 5000000u   // give up waiting for "done" after this many polls

#define MARKER_BASE 0x5A5Au

static volatile int16_t logits_q10[5] __attribute__((aligned(4))) = {0, 0, 0, 0, 0};

static void delay(uint32_t count)
{
    for (volatile uint32_t i = 0; i < count; ++i) {
    }
}

static void fail_forever(void)
{
    for (;;) {
        LEDS = 6u;  // 110
        delay(BLINK_ITER);
        LEDS = 0u;
        delay(BLINK_ITER);
    }
}

// Returns 0 on success (class in *predicted), 1 on timeout, 2 if outputs not written.
static int run_beat(uint32_t beat, uint32_t *predicted)
{
    for (uint32_t i = 0; i < 5u; ++i)
        logits_q10[i] = (int16_t)(MARKER_BASE + i);

    // HLS pointer registers are 64-bit; the PicoRV32 address space is 32-bit.
    HLS_ECG_PTR_LO = (uint32_t)(uintptr_t)known_ecg_q10[beat];
    HLS_ECG_PTR_HI = 0u;
    HLS_RR_PTR_LO  = (uint32_t)(uintptr_t)known_rr_q10[beat];
    HLS_RR_PTR_HI  = 0u;
    HLS_OUT_PTR_LO = (uint32_t)(uintptr_t)logits_q10;
    HLS_OUT_PTR_HI = 0u;

    HLS_CTRL = 1u;  // ap_start

    // ap_done (bit 1) clears when read, so read the register once per poll.
    uint32_t polls = 0u;
    for (;;) {
        uint32_t ctrl = HLS_CTRL;
        if (ctrl & 0x2u)
            break;
        if (++polls > TIMEOUT_ITER)
            return 1;
    }

    for (uint32_t i = 0; i < 5u; ++i) {
        if (logits_q10[i] == (int16_t)(MARKER_BASE + i))
            return 2;
    }

    uint32_t best = 0u;
    for (uint32_t i = 1; i < 5u; ++i) {
        if (logits_q10[i] > logits_q10[best])
            best = i;
    }
    *predicted = best;
    return 0;
}

int main(void)
{
    LEDS = 0u;
    delay(GAP_ITER);

    for (uint32_t beat = 0; beat < KNOWN_COUNT; ++beat) {
        uint32_t predicted = 0u;
        int status = run_beat(beat, &predicted);
        if (status != 0)
            fail_forever();

        LEDS = predicted + 1u;  // show what the FPGA predicted
        delay(SHOW_ITER);
        LEDS = 0u;
        delay(GAP_ITER);

        if (predicted != known_expected_class[beat])
            fail_forever();
    }

    LEDS = 7u;  // 111 steady = all beats matched
    for (;;) {
        __asm__ volatile ("nop");
    }
}
