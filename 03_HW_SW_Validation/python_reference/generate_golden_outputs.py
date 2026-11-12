"""Export real FP32 checkpoint examples for later software/RTL comparison.

The checkpoint's recorded predictions are paired with the preserved test split.
This prepares reference vectors; it does not run the model, quantize it, or
claim FPGA results.
"""

import argparse
import json
from pathlib import Path

import numpy as np

from active_model_reference import CHECKPOINT, CLASS_ORDER, MODEL_DIR, PROJECT_ROOT


RESULTS = CHECKPOINT.with_name("baseline_results.json")
SPLIT_ARCHIVE = MODEL_DIR / "consistent_data_splits.npz"
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "03_HW_SW_Validation"
    / "model_export"
    / "golden_fp32_samples.npz"
)


def select_representative_indices(y_true, y_pred, per_class):
    """Select correctly classified examples where possible, otherwise one miss."""
    selected = []
    for class_index in range(len(CLASS_ORDER)):
        members = np.flatnonzero(y_true == class_index)
        correct = members[y_pred[members] == class_index]
        chosen = correct[:per_class]
        if len(chosen) == 0 and len(members):
            chosen = members[:1]
        selected.extend(int(i) for i in chosen)
    return np.asarray(selected, dtype=np.int64)


def export_samples(output_path: Path, per_class: int):
    with np.load(SPLIT_ARCHIVE) as archive:
        required = {"X_test", "RR_test", "y_test"}
        missing = required.difference(archive.files)
        if missing:
            raise ValueError(f"Test split archive is missing: {sorted(missing)}")
        x_test = np.asarray(archive["X_test"], dtype=np.float32)
        rr_test = np.asarray(archive["RR_test"], dtype=np.float32)
        y_true = np.asarray(archive["y_test"], dtype=np.int64)

    results = json.loads(RESULTS.read_text(encoding="utf-8"))
    y_pred = np.asarray(results["predictions"], dtype=np.int64)
    if len(y_pred) != len(y_true):
        raise ValueError(
            f"Saved predictions ({len(y_pred)}) do not match test split ({len(y_true)})."
        )
    if x_test.shape[1] != 198 or rr_test.shape[1] != 2:
        raise ValueError(f"Unexpected input shapes: ECG {x_test.shape}, RR {rr_test.shape}")

    indices = select_representative_indices(y_true, y_pred, per_class)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        output_path,
        test_indices=indices,
        ecg_samples=x_test[indices],
        rr_features=rr_test[indices],
        true_class_indices=y_true[indices],
        predicted_class_indices=y_pred[indices],
    )
    manifest_path = output_path.with_suffix(".json")
    manifest = {
        "source_checkpoint": str(CHECKPOINT),
        "source_results": str(RESULTS),
        "source_split": str(SPLIT_ARCHIVE),
        "source_accuracy": results.get("test_accuracy"),
        "source_macro_f1": results.get("f1_macro"),
        "classes_in_output_order": list(CLASS_ORDER),
        "input_shapes": {"ecg_samples": [198], "rr_features": [2]},
        "sample_count": int(len(indices)),
        "test_indices": indices.tolist(),
        "true_classes": [CLASS_ORDER[int(i)] for i in y_true[indices]],
        "checkpoint_predictions": [CLASS_ORDER[int(i)] for i in y_pred[indices]],
        "quantized": False,
        "note": "FP32 reference vectors only; not hardware outputs or INT8 accuracy evidence.",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return output_path, manifest_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--per-class", type=int, default=2)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.per_class < 1:
        parser.error("--per-class must be at least 1")
    output, manifest = export_samples(args.output, args.per_class)
    print(f"Prepared FP32 reference vectors: {output}")
    print(f"Vector manifest: {manifest}")
    print("These are checkpoint predictions, not quantized or FPGA results.")


if __name__ == "__main__":
    main()
