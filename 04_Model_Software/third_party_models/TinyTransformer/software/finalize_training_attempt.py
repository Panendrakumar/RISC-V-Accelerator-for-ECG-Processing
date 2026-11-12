"""Finalize plots and integrity metadata for the completed single run."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
from sklearn.metrics import classification_report, confusion_matrix


RUN_DIR = Path(__file__).resolve().parent / "training_attempt_20261024"
RESULTS_PATH = RUN_DIR / "baseline_results.json"
HISTORY_PATH = RUN_DIR / "training_history.json"
MANIFEST_PATH = RUN_DIR / "training_attempt_manifest.json"
WEIGHTS_PATH = RUN_DIR / "baseline_ecg_transformer.weights.h5"
CLASSES = ["N", "S", "V", "F", "Q"]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    results = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    history = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    y_true = np.asarray(results["true_labels"], dtype=np.int64)
    y_pred = np.asarray(results["predictions"], dtype=np.int64)
    cm = confusion_matrix(y_true, y_pred, labels=list(range(len(CLASSES))))
    report = classification_report(
        y_true,
        y_pred,
        labels=list(range(len(CLASSES))),
        target_names=CLASSES,
        output_dict=True,
        zero_division=0,
    )
    results["class_order"] = CLASSES
    results["confusion_matrix"] = cm.tolist()
    results["classification_report_by_class"] = {
        name: report[name] for name in CLASSES
    }
    results["test_class_counts"] = {
        name: int(np.sum(y_true == index)) for index, name in enumerate(CLASSES)
    }
    results["predicted_class_counts"] = {
        name: int(np.sum(y_pred == index)) for index, name in enumerate(CLASSES)
    }
    results["checkpoint_file"] = WEIGHTS_PATH.name
    results["checkpoint_sha256"] = sha256_file(WEIGHTS_PATH)
    RESULTS_PATH.write_text(json.dumps(results, indent=2), encoding="utf-8")

    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    for axis, metric, title in [
        (axes[0, 0], "loss", "Training loss"),
        (axes[0, 1], "val_loss", "Validation loss"),
        (axes[1, 0], "accuracy", "Training accuracy"),
        (axes[1, 1], "val_accuracy", "Validation accuracy"),
    ]:
        axis.plot(history["epochs"], history[metric])
        axis.set_title(title)
        axis.set_xlabel("Epoch")
        axis.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(RUN_DIR / "baseline_training_history.png", dpi=180)
    plt.close(fig)

    fig, axis = plt.subplots(figsize=(7, 6))
    sns.heatmap(
        cm,
        annot=True,
        fmt="d",
        cmap="Blues",
        xticklabels=CLASSES,
        yticklabels=CLASSES,
        ax=axis,
    )
    axis.set_title(f"Test confusion matrix | accuracy {results['test_accuracy']:.2%}")
    axis.set_xlabel("Predicted class")
    axis.set_ylabel("True class")
    fig.tight_layout()
    fig.savefig(RUN_DIR / "baseline_confusion_matrix.png", dpi=180)
    plt.close(fig)

    manifest.pop("failed_at_utc", None)
    manifest.pop("error_type", None)
    manifest.pop("error", None)
    manifest.update({
        "status": "completed",
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "best_validation_epoch": results["best_validation_epoch"],
        "best_validation_accuracy": results["best_validation_accuracy"],
        "test_accuracy": results["test_accuracy"],
        "test_macro_f1": results["f1_macro"],
        "training_seconds": results["training_seconds"],
        "weights_sha256": sha256_file(WEIGHTS_PATH),
        "postprocessing_note": (
            "Training and test evaluation completed and were saved. The original "
            "interactive chart display was interrupted after it blocked; both "
            "plots were regenerated with a noninteractive backend."
        ),
    })
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(json.dumps({
        "status": manifest["status"],
        "test_accuracy": results["test_accuracy"],
        "macro_f1": results["f1_macro"],
        "best_validation_accuracy": results["best_validation_accuracy"],
        "best_validation_epoch": results["best_validation_epoch"],
        "per_class": results["classification_report_by_class"],
        "confusion_matrix": cm.tolist(),
        "checkpoint_sha256": results["checkpoint_sha256"],
    }, indent=2))


if __name__ == "__main__":
    main()
