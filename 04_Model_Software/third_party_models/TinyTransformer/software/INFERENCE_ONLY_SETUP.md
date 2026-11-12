# ECG Transformer inference setup

## What this runs

The notebook builds the compact 1-D ECG Transformer defined by `build_baseline_ViT()`. It reads one annotated beat at a time, uses a 198-sample waveform from the slice `[R-99 : R+99]` (99 samples before the R peak, the peak, 98 after) plus pre-RR and post-RR values, and predicts one AAMI class: `N`, `S`, `V`, `F`, or `Q`.

The notebook configuration matches the reference baseline dimensions: 8 attention heads, 16-dimensional embedding, key dimension 2 per head, one encoder layer, FFN dimension 128, and 6,643 parameters. The model runs on an ECG sequence. “ViT” is the notebook's builder name; this is not an image model.

## Run without training

From the project root, open the notebook with the existing environment:

```powershell
Set-Location "04_Model_Software/third_party_models/TinyTransformer/software"
& "../../../../.venv/Scripts/python.exe" -m jupyter notebook "Baseline Tiny Transformer (Software).ipynb"
```

Run the notebook cells in order. The final cell only loads `training_attempt_20261024/baseline_ecg_transformer.weights.h5` and evaluates it. The training function is disabled, and the notebook stops with a clear error if the weights file is missing. It reuses `consistent_data_splits.npz` rather than deleting or recreating the split cache.

The pipeline uses the selected 44 MIT-BIH records, bandpass filtering from 0.5–40 Hz, per-record normalization, the AAMI five-class mapping, and a stratified beat-level split of 70% training, 10% validation, and 20% testing. Training examples are used only to preserve the notebook's split; the inference-only run does not train on them.

## Current workspace result

The split cache contains 100,674 beats: `N=90,070`, `V=7,008`, `S=2,779`, `F=802`, and `Q=15`. Its test partition contains 20,136 beats, including only 3 `Q` beats.

One authorized training attempt completed for 100 epochs with early stopping. Its best checkpoint was selected at epoch 75 using validation accuracy. On the preserved test split it achieved **98.63% accuracy** and **0.724 macro-F1**. The Q-class F1 is **0.00**, with only three Q beats in the test set. The split is beat-level, so beats from one record can occur in both train and test partitions.

The current checkpoint and full metrics are in `training_attempt_20261024/`. The earlier 41.68% result remains in the parent folder as a historical result. The run manifest records the split archive SHA-256 and current checkpoint SHA-256.

## Compare local and published results

The upstream repository reports 98.83% for its baseline. The original paper separately reports 98.97% for its own INT8 evaluation. This project's measured 98.63% is from a local training run and the local saved beat-level split. Do not substitute either published number for the measured result, and do not change labels, discard difficult classes, or adjust metrics.

## Reporting rule

Keep these results separate:

- **Reference:** 98.83% reported by the downloaded repository.
- **Local software:** 98.63% accuracy and 0.724 macro-F1 from the one completed training attempt; Q F1 is 0.00 with support 3.
- **Quantized software:** 98.6393% accuracy, macro-F1 0.7243 (Q6.10 reference, `03_HW_SW_Validation/vitis_hls/z7_tiny_ecg_vit/fixed_point_q6_10_results.json`).
- **FPGA (Zybo Z7-10, measured on the board):** 98.6442% accuracy, macro-F1 0.7244 on all 20,136 test beats; 31.29 ms per beat at 100 MHz (`03_HW_SW_Validation/hardware_outputs/fpga_stream/20261110_232934_0_20136/summary.json`).

Accuracy alone can hide poor performance on rare classes. Report macro-F1, per-class precision/recall/F1, the confusion matrix, and the split protocol alongside accuracy. This is a research classifier, not a clinical diagnostic device.

## Print the current test accuracy in a terminal

From the project root in PowerShell, run:

```powershell
& ".\.venv\Scripts\python.exe" ".\04_Model_Software\third_party_models\TinyTransformer\software\show_test_accuracy.py"
```

This command loads the saved 6,643-parameter checkpoint and the preserved test split, runs inference, and prints accuracy, macro-F1, and the per-class report. It does not train, download data, recreate the split, generate plots, or overwrite the saved results. The expected saved-split result is **98.6343% accuracy** and **0.724389 macro-F1**.
