# Training figures and test outputs

This folder contains exportable 300 dpi PNG files and vector PDF copies of the
training curves and test evaluation figures.

## Verified test counts

- Correct predictions on the confusion-matrix diagonal: 19,861 of 20,136
- Test accuracy: 98.634287%
- Macro-F1: 0.724389
- True-class supports in order N, S, V, F, Q: 18,015, 556, 1,401, 161, 3
- Diagonal counts in order N, S, V, F, Q: 17,892, 487, 1,358, 124, 0

The raw-count confusion matrix labels each cell with the exact count and the
percentage of that true-class row. Correct predictions are on the main
diagonal. The normalized matrix uses each true-class support as its row total.
Colors use a dark-to-bright viridis scale with automatic white/black annotation
text for contrast.

The saved evaluation split is stratified by beat, not by patient/record. The Q
class has only three test beats and received F1 = 0.000; interpret accuracy
alongside the per-class chart and CSV.

## Files

- `00_training_history_overview` â€” combined training/validation overview.
- `01` to `04` â€” separate training loss, validation loss, training accuracy,
  and validation accuracy plots.
- `05` â€” raw count confusion matrix.
- `06` â€” row-normalized confusion matrix.
- `07` â€” per-class precision, recall, and F1 chart.
- `per_class_metrics.csv`, `overall_metrics.csv` â€” exact tabular metrics.


Epoch-by-epoch data for the four learning curves is in ../training_history.csv (100 epochs).

