// Interactive ECG beat classifier for the Zybo Z7-10 (v2 hardware).
//
// Board controls
//   SW3..SW0  choose a stored beat (0-15, binary, SW0 = least significant bit)
//   BTN1      classify the selected beat on the FPGA accelerator
//   BTN2      (hold) show the TRUE label of the selected beat
//   BTN3      self-test: classify all stored beats, compare with Q6.10 reference
//   BTN0      reset
//
// Display
//   LD2:LD0   class code N=001 S=010 V=011 F=100 Q=101 ; 000 = nothing yet
//   LED6 RGB  class colour N=green S=yellow V=red F=magenta Q=blue
//   LD3       CPU trap (hardware error)
//   Self-test: each class ~0.5 s, then 111 + green = all match ; blinking 110 + red = mismatch
//
// Laptop mailbox (BRAM, read/written by Vivado through JTAG-to-AXI)
//   0x6000 MAGIC   0xEC600002 once firmware is running
//   0x6004 CMD     laptop writes 1 -> classify the beat in HOST_ECG/HOST_RR
//   0x6008 STATUS  0 idle, 1 busy, 2 done, 3 timeout, 4 outputs not written
//   0x600C SEQ     increments after every finished inference (any source)
//   0x6010 CLASS   predicted class index (0..4)
//   0x6014 CYCLES  CPU clock cycles from start to done (100 MHz clock)
//   0x6018 SOURCE  0 = laptop beat, 1..16 = stored beat (switch value + 1)
//   0x6020 LOGITS  five signed 32-bit values (raw Q6.10)
//   0x6100 HOST_ECG  198 x int16 Q6.10 (laptop writes)
//   0x6300 HOST_RR   2 x int16 Q6.10 (laptop writes)
//   0x6400 HLS_OUT   5 x int16 accelerator output buffer

#include <stdint.h>
#include "demo_beats_data.h"

#define HLS_BASE       0x40000000u
#define HLS_CTRL       (*(volatile uint32_t *)(HLS_BASE + 0x00u))
#define HLS_ECG_PTR_LO (*(volatile uint32_t *)(HLS_BASE + 0x10u))
#define HLS_ECG_PTR_HI (*(volatile uint32_t *)(HLS_BASE + 0x14u))
#define HLS_RR_PTR_LO  (*(volatile uint32_t *)(HLS_BASE + 0x1Cu))
#define HLS_RR_PTR_HI  (*(volatile uint32_t *)(HLS_BASE + 0x20u))
#define HLS_OUT_PTR_LO (*(volatile uint32_t *)(HLS_BASE + 0x28u))
#define HLS_OUT_PTR_HI (*(volatile uint32_t *)(HLS_BASE + 0x2Cu))

#define GPIO_OUT (*(volatile uint32_t *)0x40010000u)   // ch1: [2:0] code, [5:3] RGB
#define GPIO_IN  (*(volatile uint32_t *)0x40010008u)   // ch2: [3:0] SW, [7:4] BTN

#define MB_BASE    0x6000u
#define MB(off)    (*(volatile uint32_t *)(MB_BASE + (off)))
#define MB_MAGIC   0x00u
#define MB_CMD     0x04u
#define MB_STATUS  0x08u
#define MB_SEQ     0x0Cu
#define MB_CLASS   0x10u
#define MB_CYCLES  0x14u
#define MB_SOURCE  0x18u
#define MB_LOGITS  0x20u
#define HOST_ECG   ((const int16_t *)0x6100u)
#define HOST_RR    ((const int16_t *)0x6300u)
#define HLS_OUT    ((volatile int16_t *)0x6400u)

#define MAGIC_VALUE 0xEC600002u

#define BTN_RUN   (1u << 1)
#define BTN_TRUE  (1u << 2)
#define BTN_TEST  (1u << 3)

// Loop counts (not exact times). ~1.5M iterations was about 1 s on the board.
// Self-test speed halved on 2026-11-11: ~0.5 s per result + ~0.13 s gap.
#define SHOW_ITER      750000u
#define GAP_ITER       200000u
#define PASS_ITER     4500000u   // final "all matched" display, ~3 s
#define BLINK_ITER     300000u
#define DEBOUNCE_ITER   30000u
#define TIMEOUT_POLLS 5000000u

// RGB bits [5:3] = R,G,B
#define RGB_OFF     0u
#define RGB_RED     (4u << 3)
#define RGB_GREEN   (2u << 3)
#define RGB_BLUE    (1u << 3)
static const uint32_t class_rgb[5] = {
    RGB_GREEN,               // N
    RGB_RED | RGB_GREEN,     // S yellow
    RGB_RED,                 // V
    RGB_RED | RGB_BLUE,      // F magenta
    RGB_BLUE                 // Q
};

static void delay(uint32_t count)
{
    for (volatile uint32_t i = 0; i < count; ++i) {
    }
}

static inline uint32_t rdcycle(void)
{
    uint32_t c;
    __asm__ volatile ("rdcycle %0" : "=r"(c));
    return c;
}

static void show_class(uint32_t cls)
{
    GPIO_OUT = (cls < 5u) ? ((cls + 1u) | class_rgb[cls]) : 0u;
}

static uint32_t buttons(void) { return (GPIO_IN >> 4) & 0xFu; }
static uint32_t switches(void) { return GPIO_IN & 0xFu; }

// Runs one inference. Returns 0 and fills *cls on success, else an error code (3 or 4).
static uint32_t run_inference(const int16_t *ecg, const int16_t *rr, uint32_t source, uint32_t *cls)
{
    for (uint32_t i = 0; i < 5u; ++i)
        HLS_OUT[i] = (int16_t)(0x5A5A + i);   // marker: detects "never written"

    MB(MB_STATUS) = 1u;
    MB(MB_SOURCE) = source;
    HLS_ECG_PTR_LO = (uint32_t)(uintptr_t)ecg;
    HLS_ECG_PTR_HI = 0u;
    HLS_RR_PTR_LO  = (uint32_t)(uintptr_t)rr;
    HLS_RR_PTR_HI  = 0u;
    HLS_OUT_PTR_LO = (uint32_t)(uintptr_t)HLS_OUT;
    HLS_OUT_PTR_HI = 0u;

    uint32_t t0 = rdcycle();
    HLS_CTRL = 1u;                              // ap_start
    uint32_t polls = 0u;
    for (;;) {
        if (HLS_CTRL & 0x2u)                    // ap_done (clear-on-read)
            break;
        if (++polls > TIMEOUT_POLLS) {
            MB(MB_STATUS) = 3u;
            return 3u;
        }
    }
    uint32_t t1 = rdcycle();

    for (uint32_t i = 0; i < 5u; ++i) {
        if (HLS_OUT[i] == (int16_t)(0x5A5A + i)) {
            MB(MB_STATUS) = 4u;
            return 4u;
        }
    }

    uint32_t best = 0u;
    for (uint32_t i = 0; i < 5u; ++i) {
        int16_t v = HLS_OUT[i];
        MB(MB_LOGITS + 4u * i) = (uint32_t)(int32_t)v;
        if (i > 0u && v > HLS_OUT[best])
            best = i;
    }
    MB(MB_CLASS) = best;
    MB(MB_CYCLES) = t1 - t0;
    MB(MB_SEQ) = MB(MB_SEQ) + 1u;
    MB(MB_STATUS) = 2u;
    *cls = best;
    return 0u;
}

static void blink_error(uint32_t times)
{
    for (uint32_t k = 0; k < times; ++k) {
        GPIO_OUT = 6u | RGB_RED;
        delay(BLINK_ITER);
        GPIO_OUT = 0u;
        delay(BLINK_ITER);
    }
}

// BTN3: classify every stored beat and compare with the Q6.10 software reference.
static void self_test(void)
{
    uint32_t ok = 1u;
    for (uint32_t b = 0; b < DEMO_COUNT; ++b) {
        uint32_t cls = 0u;
        if (run_inference(demo_ecg_q10[b], demo_rr_q10[b], b + 1u, &cls) != 0u) {
            ok = 0u;
            break;
        }
        show_class(cls);
        delay(SHOW_ITER);
        GPIO_OUT = 0u;
        delay(GAP_ITER);
        if (cls != demo_q610_pred[b]) {
            ok = 0u;
            break;
        }
    }
    if (ok) {
        GPIO_OUT = 7u | RGB_GREEN;      // all stored beats matched the Q6.10 reference
        delay(PASS_ITER);
    } else {
        blink_error(8u);
    }
    GPIO_OUT = 0u;
}

int main(void)
{
    MB(MB_CMD) = 0u;
    MB(MB_STATUS) = 0u;
    MB(MB_SEQ) = 0u;
    MB(MB_MAGIC) = MAGIC_VALUE;
    GPIO_OUT = 0u;

    uint32_t prev_btn = buttons();
    uint32_t prev_sw = switches();
    uint32_t last_cls = 0xFFu;               // 0xFF = nothing classified yet

    for (;;) {
        // 1. Laptop request has priority.
        if (MB(MB_CMD) == 1u) {
            MB(MB_CMD) = 0u;
            uint32_t cls;
            if (run_inference(HOST_ECG, HOST_RR, 0u, &cls) == 0u) {
                last_cls = cls;
                show_class(cls);
            } else {
                blink_error(2u);
                last_cls = 0xFFu;
            }
            continue;
        }

        uint32_t sw = switches();
        uint32_t btn = buttons();
        uint32_t pressed = btn & ~prev_btn;

        // New beat selected: clear the display so the next result is clearly new.
        if (sw != prev_sw) {
            last_cls = 0xFFu;
            GPIO_OUT = 0u;
        }

        if (pressed & BTN_RUN) {
            delay(DEBOUNCE_ITER);
            if (sw < DEMO_COUNT) {
                uint32_t cls;
                if (run_inference(demo_ecg_q10[sw], demo_rr_q10[sw], sw + 1u, &cls) == 0u) {
                    last_cls = cls;
                    show_class(cls);
                } else {
                    blink_error(2u);
                    last_cls = 0xFFu;
                }
            } else {
                blink_error(1u);                // no beat stored for this switch value
            }
        } else if (btn & BTN_TRUE) {
            // While held: true label, LEDs only, RGB off (so it is clearly not a prediction).
            GPIO_OUT = (sw < DEMO_COUNT) ? (demo_true_class[sw] + 1u) : 0u;
        } else if (prev_btn & BTN_TRUE) {
            // Released: go back to the prediction.
            if (last_cls < 5u) show_class(last_cls); else GPIO_OUT = 0u;
        } else if (pressed & BTN_TEST) {
            delay(DEBOUNCE_ITER);
            self_test();
            last_cls = 0xFFu;
        }

        prev_btn = btn;
        prev_sw = sw;
        delay(DEBOUNCE_ITER / 4u);
    }
}
