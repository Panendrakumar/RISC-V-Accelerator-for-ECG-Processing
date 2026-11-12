# RISC-V-Based Configurable Accelerator for ECG Processing

Updated: 2026-11-11

The project classifies individual MIT-BIH heartbeats into five AAMI classes (`N`, `S`, `V`, `F`, `Q`) with a compact 1-D ECG Transformer, and runs the inference on a Digilent Zybo Z7-10 (Zynq-7010, `xc7z010clg400-1`) in a fixed-point accelerator controlled by a PicoRV32 RISC-V softcore. The notebook builder is named `build_baseline_ViT()`, but the model processes a 1-D ECG time series, not an image.

## Model and data

- Input per beat: 198 ECG samples taken with the slice `[R-99 : R+99]` (99 samples before the R peak, the R-peak sample, and 98 after) plus two RR-interval features (pre-RR and post-RR, seconds).
- Preprocessing: 0.5–40 Hz fifth-order Butterworth band-pass, per-record z-score normalization, 360 Hz.
- Model: Conv1D patch embedding (kernel 3, stride 3, 66 tokens, 16-dim), learned positions, one pre-norm encoder block with 8 heads (key dim 2) and a 128-unit GELU FFN, RR branch, five logits. 6,643 parameters.
- Dataset: 44 selected MIT-BIH records, 100,674 beats (N 90,070; S 2,779; V 7,008; F 802; Q 15).
- Split: stratified **beat-level** 70/10/20, seed 42: 70,471 train, 10,067 validation, 20,136 test (N 18,015; S 556; V 1,401; F 161; Q 3). Beats from one record can appear in more than one partition, so this is **not** a patient-independent evaluation.

## Measured results (all on the same 20,136-beat test split)

| Stage | Accuracy | Macro-F1 | Evidence |
|---|---:|---:|---|
| FP32 software (TensorFlow checkpoint) | 98.6343% (19,861 correct) | 0.724389 | `04_Model_Software/third_party_models/TinyTransformer/software/training_attempt_20261024/baseline_results.json` |
| Q6.10 fixed-point software reference (Python) | 98.6393% | 0.7243 | `03_HW_SW_Validation/vitis_hls/z7_tiny_ecg_vit/fixed_point_q6_10_results.json` |
| **FPGA, Zybo Z7-10 (measured on the board)** | **98.6442% (19,863 correct)** | **0.7244** | `03_HW_SW_Validation/hardware_outputs/fpga_stream/20261110_232934_0_20136/summary.json` |

- The FPGA class equals the Q6.10 software class on 99.995% of beats (1 beat differs) and the FP32 class on 99.970% (6 beats differ). The two-beat accuracy difference is fixed-point rounding, not an improvement over software.
- Q has only 3 test beats and F1 = 0.00 in all three stages. Report accuracy together with macro-F1 and per-class results.
- On-board latency (PicoRV32 `rdcycle`, start to done): mean 3,128,915 cycles = **31.29 ms per beat at 100 MHz** (range 3,128,910–3,128,998). The JTAG transfer used for testing (about 82 ms per beat) is not part of this figure.
- Evaluation build after implementation: 12,816 LUTs (72.8%), 15,597 FFs (44.3%), 38.5 BRAM tiles (64.2%), 43 DSPs (53.8%); timing met at 100 MHz (WNS +0.193 ns, WHS +0.018 ns).
- Board self-tests: known-beat firmware reproduced 9/9 golden classes; the interactive build matched the Q6.10 reference on 16/16 stored beats (including 7 deliberate model mistakes).
- Published results (upstream repository 98.83%, original Tiny Transformer paper 98.97%) are reference numbers from other protocols, not this project's measurements.

## Where things are

| Purpose | Path |
|---|---|
| Software notebook (inference-only) | `04_Model_Software/third_party_models/TinyTransformer/software/Baseline Tiny Transformer (Software).ipynb` |
| Trained checkpoint and metrics | `04_Model_Software/third_party_models/TinyTransformer/software/training_attempt_20261024/` |
| Saved split | `04_Model_Software/third_party_models/TinyTransformer/software/consistent_data_splits.npz` |
| Weight export and golden vectors | `03_HW_SW_Validation/model_export/` |
| Q6.10 reference and Vitis HLS source | `03_HW_SW_Validation/vitis_hls/z7_tiny_ecg_vit/` |
| v1 Vivado project (single-beat and known-beat demos) | `02_Vivado_Zybo/ECG_ViT_Zybo/` |
| v2 interactive / evaluation build (switches, buttons, RGB, JTAG-to-AXI) | `02_Vivado_Zybo/v2_interactive/` |
| Ready-to-program demo bitstreams | `02_Vivado_Zybo/demo_bitstreams/`, `02_Vivado_Zybo/v2_interactive/zybo_vit_v2_interactive.bit` |
| Full FPGA test run (predictions, summary, figure) | `03_HW_SW_Validation/hardware_outputs/fpga_stream/20261110_232934_0_20136/` |
| Demo checklist | `DOWNLOAD_AND_DEMO_CHECKLIST.md` |

The `CNN + Transformer Hybrid` and `ResNET` folders under `04_Model_Software/third_party_models/` hold separate comparison models; they are not the deployed model.

## Run the software notebook (no training)

```powershell
Set-Location "04_Model_Software/third_party_models/TinyTransformer/software"
& "../../../../.venv/Scripts/python.exe" -m jupyter notebook "Baseline Tiny Transformer (Software).ipynb"
```

Or print the test metrics directly from the project root:

```powershell
.\.venv\Scripts\python.exe .\04_Model_Software\third_party_models\TinyTransformer\software\show_test_accuracy.py
```

## Board demo and FPGA evaluation

See `02_Vivado_Zybo/v2_interactive/README.md` for the board controls, the rebuild commands and the command that streams test beats from the laptop to the board. Vivado and the streaming script need the project mapped to a drive letter without spaces:

```powershell
subst V: "<path-to-your-repo-folder>"
```

The mapping disappears after a restart; run the command again before using Vivado or the scripts.

## Limitations

- Beat-level split, not patient-independent; results are not evidence of performance on unseen patients.
- Severe class imbalance; Q has 3 test beats.
- R peaks and RR features come from the database annotations. There is no live ECG sensor or automatic R-peak detector; test beats reach the board over JTAG from the laptop.
- The Python Q6.10 reference approximates the HLS arithmetic; FPGA logits are close to it (median difference 11 LSB = 0.011) but not bit-exact.
- Research prototype, not a medical device.

## References

- [Busia et al., A Tiny Transformer for Low-Power Arrhythmia Classification on Microcontrollers](https://arxiv.org/abs/2402.10748)
- [Upstream Tiny Transformer FPGA repository](https://github.com/MostafaElsharkawy92/FPGA-based-Tiny-Transformer-model-for-ECG-Arrythmia-Classification)
- [PicoRV32](https://github.com/YosysHQ/picorv32)
- [Digilent Zybo Z7 reference manual](https://digilent.com/reference/programmable-logic/zybo-z7/reference-manual)
