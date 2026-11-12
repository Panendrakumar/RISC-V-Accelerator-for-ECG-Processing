# Tiny ECG Transformer Q6.10 implementation for Zybo Z7-10

This folder contains the checkpoint-matched floating-point starter and the
current fixed-point inference implementation for the project's five-class ECG
beat classifier. The selected checkpoint has 6,643 parameters and accepts 198
ECG samples plus two RR features. The class order is `N, S, V, F, Q`.

## Current fixed-point result

`vit_inference_fixed.cpp` uses signed Q6.10 weights and activations, wider
Q12.20 accumulators, and interpolated 257-entry GELU and exponential lookup
tables. Inputs and outputs are raw two's-complement 16-bit values scaled by
1024. Values are rounded to nearest-even and saturated to the Q6.10 range
`[-32, 31.9990234375]`.

The full saved held-out beat split was evaluated with the fixed-point software
reference:

| Measure | Q6.10 result | Original FP32 result |
|---|---:|---:|
| Test beats | 20,136 | 20,136 |
| Accuracy | 98.6393% | 98.6343% |
| Macro-F1 | 0.7243 | 0.7244 |

The HLS C simulation also matched the saved checkpoint prediction on all 9
representative vectors. This is HLS C-level verification, not an RTL simulation
or an FPGA measurement (the measured FPGA result is given below). The test split contains only three Q beats, so its
Q-class F1 is 0.00; the split is beat-level rather than patient-disjoint.

## Zybo Z7-10 HLS estimate

Vitis HLS 2023.2 synthesized the fixed-point top for `xc7z010clg400-1` at a
10 ns target clock. The estimate is standalone, before adding the PicoRV32,
interconnect, and shared memories:

| Resource or speed | HLS estimate | Device share |
|---|---:|---:|
| LUT | 14,107 | 80% |
| BRAM | 56 | 46% |
| DSP | 35 | 43% |
| FF | 7,115 | 20% |
| Estimated latency | 3,102,112 cycles | about 31.0 ms at 100 MHz |
| Estimated Fmax | 136.99 MHz | HLS estimate |

The generated HLS IP has an AXI master data interface and an AXI-Lite control
interface. It is connected to a PicoRV32 AXI wrapper in the Vivado block design;
the complete system fits the Zynq-7010 (evaluation build: 12,816 LUT, 72.8%;
38.5 BRAM tiles, 64.2%; 43 DSP, 53.8%) and meets timing at 100 MHz. The
measured on-board latency is 3,128,915 cycles per beat, within 0.9% of the HLS
estimate.

## Reproduce the full software fixed-point evaluation

From the project root in PowerShell:

```powershell
.venv\Scripts\python.exe 03_HW_SW_Validation\vitis_hls\z7_tiny_ecg_vit\fixed_point_reference.py
```

This reads the active checkpoint export and saved `X_test`, `RR_test`, and
`y_test` arrays. It writes `fixed_point_q6_10_results.json`. It does not train
the model or modify the dataset.

Regenerate the HLS weights and lookup tables with:

```powershell
.venv\Scripts\python.exe 03_HW_SW_Validation\vitis_hls\z7_tiny_ecg_vit\generate_fixed_assets.py
```

## Reproduce HLS C simulation and synthesis

Vitis HLS needs a working path without spaces. Create a temporary `R:` mapping
to the project root, then run this from PowerShell:

```powershell
subst R: "C:\path\to\RISC-V-Based-Configurable-Accelerator-for-ECG-Processing"
Set-Location R:\03_HW_SW_Validation\vitis_hls\z7_tiny_ecg_vit
& "C:\Xilinx\Vitis_HLS\2023.2\bin\vitis_hls.bat" -f .\run_fixed_hls.tcl
```

The Tcl script runs C simulation, C synthesis, and IP export for the Zybo
Z7-10. The generated Vivado IP repository is
`ecg_vit_z7_fixed\solution1\impl\ip`. Do not add the older FP32 HLS IP to the
active Vivado project.

## Hardware result

The IP runs on the Zybo Z7-10 under PicoRV32 control (`02_Vivado_Zybo/ECG_ViT_Zybo/hls_integration/` and `02_Vivado_Zybo/v2_interactive/`). On the board, all 20,136 test beats gave 98.6442% accuracy and macro-F1 0.7244; the FPGA class equals this folder's Python Q6.10 reference class on 99.995% of beats. The Python reference approximates the HLS arithmetic (median logit difference 0.011), so the agreement is close but not bit-exact. Results: `03_HW_SW_Validation/hardware_outputs/fpga_stream/20261110_232934_0_20136/`.

The earlier floating-point HLS trial remains only as a discarded comparison:
it used 17,466 LUT and 100 BRAM18K and did not leave useful capacity for the
CPU system.
