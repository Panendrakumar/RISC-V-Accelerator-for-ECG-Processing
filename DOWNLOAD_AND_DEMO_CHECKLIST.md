# Demo checklist

Updated: 2026-11-11

## What to state

- Task: classify one annotated MIT-BIH heartbeat into N, S, V, F or Q.
- Input: 198 ECG samples (`[R-99 : R+99]`: 99 before the R peak, the peak, 98 after) plus pre-RR and post-RR.
- Model: compact 1-D ECG Transformer, 6,643 parameters (notebook builder `build_baseline_ViT()`; it is not an image ViT).
- Hardware: Digilent Zybo Z7-10, PicoRV32 RISC-V softcore in programmable logic controlling a Vitis HLS Q6.10 inference IP over AXI; built with Vivado 2023.2.

## Measured numbers (same 20,136-beat beat-level test split)

| | Accuracy | Macro-F1 |
|---|---:|---:|
| FP32 software | 98.6343% | 0.724389 |
| Q6.10 software reference | 98.6393% | 0.7243 |
| FPGA on the Zybo Z7-10 | 98.6442% | 0.7244 |

- FPGA vs Q6.10 software: same class on 99.995% of beats; FPGA vs FP32: 99.970%.
- Latency on the board: 3,128,915 cycles = 31.29 ms per beat at 100 MHz.
- Resources (evaluation build): 72.8% LUT, 44.3% FF, 64.2% BRAM, 53.8% DSP; timing met at 100 MHz.
- Caveats to say every time: the split is beat-level (not patient-independent); Q has only 3 test beats and F1 = 0; the board receives stored test beats from the laptop, not a live ECG.
- Upstream 98.83% and paper 98.97% are other people's results, not ours.

## Before the demo

1. Connect the Zybo Z7-10 to the laptop with its USB-JTAG cable and switch the board on (same setup as the earlier demos).
2. Open PowerShell and map the project drive:

   ```powershell
   subst V: "<path-to-your-repo-folder>"
   ```

3. Open Vivado 2023.2 → **Open Hardware Manager** → **Open Target** → **Auto Connect**.
4. **Program Device** with `V:\02_Vivado_Zybo\v2_interactive\zybo_vit_v2_interactive.bit` (leave the probes file empty unless you will stream beats; then use `V:\02_Vivado_Zybo\v2_interactive\ECG_ViT_Zybo_v2\ECG_ViT_Zybo_v2.runs\impl_1\zybo_vit_v2_top.ltx`).
5. Check the green DONE LED is on.

## Board demo (v2 interactive bitstream)

| Control | Action |
|---|---|
| SW3..SW0 | pick stored beat 0–15 (switch up = 1) |
| BTN1 | classify the selected beat on the FPGA |
| BTN2 (hold) | show the true label of the selected beat |
| BTN3 | self-test of all 16 stored beats |
| BTN0 | reset |

LD2:LD0: N=001, S=010, V=011, F=100, Q=101; RGB: N green, S yellow, V red, F magenta, Q blue; LD3 = CPU trap. Self-test ends with 111 + green when all 16 match the Q6.10 reference. The beat table is in `02_Vivado_Zybo/v2_interactive/README.md`; beats 9–15 are deliberate model mistakes and must not be used to estimate accuracy.

Fallback: `02_Vivado_Zybo/demo_bitstreams/zybo_vit_known_beats.bit` runs the 9-beat known-beat self-test (LED sequence N,N,S,S,V,V,F,F,N, then 111).

## Optional: stream test beats live

With the v2 bitstream and its `.ltx` programmed, close Hardware Manager, then:

```powershell
V:\.venv\Scripts\python.exe V:\02_Vivado_Zybo\v2_interactive\host\stream_test_beats.py --start 0 --count 50
```

A 50-beat run takes about 5 s plus Vivado start-up. The full split (`--all`) took about 27 minutes. Results go to `03_HW_SW_Validation/hardware_outputs/fpga_stream/<run>/`. A partial run is a sample; only the `--all` run gives the FPGA test accuracy.

## Files to show

- Notebook and checkpoint: `04_Model_Software/third_party_models/TinyTransformer/software/`
- Q6.10 reference and HLS: `03_HW_SW_Validation/vitis_hls/z7_tiny_ecg_vit/`
- Implementation reports: `02_Vivado_Zybo/v2_interactive/reports/`
- Full FPGA run and figure: `03_HW_SW_Validation/hardware_outputs/fpga_stream/20261110_232934_0_20136/`

## Explain the RISC-V role

The PicoRV32 runs firmware from BRAM. It reads the switches and buttons, writes the beat and RR addresses into the accelerator's control registers, starts it, polls for done, reads the five logits, picks the largest, drives the LEDs and stores the class and cycle count in a result mailbox in BRAM. The Transformer arithmetic runs in the HLS accelerator, not on the CPU. The RISC-V does not change accuracy.

## References

- [Original Tiny Transformer paper](https://arxiv.org/abs/2402.10748)
- [Upstream Tiny Transformer FPGA repository](https://github.com/MostafaElsharkawy92/FPGA-based-Tiny-Transformer-model-for-ECG-Arrythmia-Classification)
- [PicoRV32 source](https://github.com/YosysHQ/picorv32)
- [Digilent Zybo Z7 reference manual](https://digilent.com/reference/programmable-logic/zybo-z7/reference-manual)
