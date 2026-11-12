# ECG Transformer software reference

This folder holds the software reference used by the ECG accelerator project. The active notebook builds the compact 1-D ECG Transformer named `build_baseline_ViT()` and evaluates saved weights. One authorized training attempt is complete; the notebook itself remains **inference only** and will not train again.

## Model and input contract

- Dataset: MIT-BIH Arrhythmia Database
- Classes, in output order: `N`, `S`, `V`, `F`, `Q`
- Beat input: 198 ECG samples from the slice `[R-99 : R+99]`: 99 samples before the R peak, the R-peak sample, and 98 after (`half_window = 99`, end-exclusive slice)
- Rhythm input: pre-RR and post-RR intervals in seconds
- Signal preparation: 0.5–40 Hz, order-5 Butterworth filtering, followed by per-record normalization
- Model: 1-D convolutional patch embedding, one Transformer encoder, RR feature branch, five-class output
- Reference dimensions: 8 attention heads, embedding 16, key dimension 2 per head, FFN 128, 6,643 parameters
- Split: stratified beat-level 70%/10%/20%, seed 42

The notebook calls the builder `build_baseline_ViT`, but it classifies ECG time-series; it does not process images.

## Run the inference-only notebook

From the project root in PowerShell:

```powershell
Set-Location "04_Model_Software/third_party_models/TinyTransformer/software"
& "../../../../.venv/Scripts/python.exe" -m jupyter notebook "Baseline Tiny Transformer (Software).ipynb"
```

Run all cells. The final cell loads `training_attempt_20261024/baseline_ecg_transformer.weights.h5` and evaluates against the preserved `consistent_data_splits.npz`. Its results and plots are in `training_attempt_20261024/`. If weights are absent, the notebook stops. Its training function is deliberately disabled.

## Current local result

The single training attempt completed for 100 epochs with early stopping, saving the best validation checkpoint at epoch 75. On the preserved test split it scored **98.63% accuracy** and **0.724 macro-F1**. Q-class F1 was 0.00 with only three Q test beats. The split contains 100,674 beats overall, including only 15 `Q` beats, and allows beats from the same record in different partitions; it is not patient-independent.

The upstream repository reports 98.83% for its baseline; the original paper separately reports 98.97% for its 8-bit evaluation. These are reference results, not local measurements. The local result is 98.63% (98.6343%) and must be reported with its split and classwise limitations.

## Fixed-point and FPGA results from this checkpoint

The same checkpoint was converted to Q6.10 fixed point (`03_HW_SW_Validation/vitis_hls/z7_tiny_ecg_vit/`): 98.6393% accuracy, macro-F1 0.7243 on the same test split. Running on the Digilent Zybo Z7-10 under PicoRV32 control, the accelerator classified all 20,136 test beats with 98.6442% accuracy and macro-F1 0.7244 at 31.29 ms per beat (`03_HW_SW_Validation/hardware_outputs/fpga_stream/20261110_232934_0_20136/`). These are separate measurements from the floating-point result above.

The parent-folder files `baseline_ecg_transformer.weights.h5` and `baseline_results.json` belong to the earlier 41.68% run. Use the checkpoint and results inside `training_attempt_20261024/` for the current software reference.

See [INFERENCE_ONLY_SETUP.md](INFERENCE_ONLY_SETUP.md) for the full setup and reporting rules, and [inference_config.json](inference_config.json) for the machine-readable input and evaluation configuration.
