"""Run the saved ECG Transformer on the saved MIT-BIH test split and print metrics.

This is inference-only. It executes the import/config/data/model/evaluation cells
from the active notebook so the terminal uses the same preprocessing and model.
It does not train, recreate the split, download data, save results, or make plots.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
SOFTWARE_DIR = Path(__file__).resolve().parent
NOTEBOOK_PATH = SOFTWARE_DIR / "Baseline Tiny Transformer (Software).ipynb"
EXPECTED_PARAMETERS = 6643
EXPECTED_TEST_BEATS = 20136


def main() -> int:
    if not NOTEBOOK_PATH.is_file():
        raise FileNotFoundError(f"Active inference notebook not found: {NOTEBOOK_PATH}")

    os.chdir(SOFTWARE_DIR)
    notebook = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    namespace: dict[str, object] = {"__name__": "terminal_inference"}

    # These notebook cells contain imports, configuration, cached split loading,
    # model construction, input batching, and inference metrics. The training cell
    # and interactive plotting cells are deliberately not executed.
    cells = notebook.get("cells", [])
    for index in (3, 4, 5, 6, 7, 9):
        if index >= len(cells) or cells[index].get("cell_type") != "code":
            raise RuntimeError(f"Expected inference code cell {index} is missing.")
        source = "".join(cells[index].get("source", []))
        compile(source, f"{NOTEBOOK_PATH.name}:cell-{index}", "exec")
        exec(source, namespace)

    config = namespace["config"]
    checkpoint = SOFTWARE_DIR / config.baseline_weights
    split_file = SOFTWARE_DIR / config.splits_file
    if not checkpoint.is_file():
        raise FileNotFoundError(f"Saved model weights not found: {checkpoint}")
    if not split_file.is_file():
        raise FileNotFoundError(f"Saved test split not found: {split_file}")

    print("ECG TRANSFORMER - SAVED TEST SET EVALUATION")
    print("Inference only: no training, downloads, plots, or result-file changes.")
    print(f"Checkpoint: {checkpoint.relative_to(SOFTWARE_DIR)}")
    print(f"Saved split: {split_file.name}")

    data = namespace["create_consistent_data_splits"]()
    X_train, X_val, X_test, y_train, y_val, y_test, RR_train, RR_val, RR_test = data
    del X_train, X_val, y_train, y_val, RR_train, RR_val
    if len(y_test) != EXPECTED_TEST_BEATS:
        raise RuntimeError(
            f"Unexpected saved test size: {len(y_test)}; expected {EXPECTED_TEST_BEATS}."
        )

    model = namespace["build_baseline_ViT"]()
    parameter_count = model.count_params()
    if parameter_count != EXPECTED_PARAMETERS:
        raise RuntimeError(
            f"Model has {parameter_count:,} parameters; expected {EXPECTED_PARAMETERS:,}."
        )
    model.load_weights(str(checkpoint))

    test_ds = namespace["create_test_dataset"](
        X_test, RR_test, y_test, config.batch_size
    )
    results = namespace["evaluate_baseline_model"](model, test_ds, y_test)

    predictions = results["predictions"]
    correct = sum(int(pred == true) for pred, true in zip(predictions, y_test))
    accuracy = correct / len(y_test)
    macro_f1 = float(results["f1_macro"])
    print("\n" + "=" * 58)
    print(f"FINAL TEST ACCURACY : {accuracy:.4%} ({correct:,} / {len(y_test):,})")
    print(f"MACRO-F1            : {macro_f1:.6f}")
    print(f"MODEL PARAMETERS    : {parameter_count:,}")
    print("TRAINING PERFORMED  : No")
    print("=" * 58)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

