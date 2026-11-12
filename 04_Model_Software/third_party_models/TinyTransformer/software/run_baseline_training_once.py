"""Run one audited training attempt for the Tiny ECG Transformer baseline.

This script reuses the model, preprocessing, split, dataset, and evaluation
definitions in the adjacent notebook. It always trains from a fresh
initialization, preserves the existing split archive, and writes every output
to training_attempt_20261024/ so the old checkpoint and results stay intact.

The attempt guard prevents a second run from overwriting or silently repeating
this authorized attempt. Remove the run directory only if a future user
explicitly authorizes another attempt.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Keep post-training plots headless so a GUI window cannot block completion.
os.environ.setdefault("MPLBACKEND", "Agg")

import nbformat


SOFTWARE_DIR = Path(__file__).resolve().parent
NOTEBOOK_PATH = SOFTWARE_DIR / "Baseline Tiny Transformer (Software).ipynb"
RUN_DIR = SOFTWARE_DIR / "training_attempt_20261024"
MANIFEST_PATH = RUN_DIR / "training_attempt_manifest.json"
SPLIT_PATH = SOFTWARE_DIR / "consistent_data_splits.npz"
WEIGHTS_PATH = RUN_DIR / "baseline_ecg_transformer.weights.h5"
RESULTS_PATH = RUN_DIR / "baseline_results.json"


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    if not NOTEBOOK_PATH.is_file():
        raise FileNotFoundError(f"Notebook not found: {NOTEBOOK_PATH}")
    if not SPLIT_PATH.is_file():
        raise FileNotFoundError(
            f"Preserved split archive not found: {SPLIT_PATH}. "
            "This run will not recreate or replace the split."
        )
    if MANIFEST_PATH.exists():
        raise RuntimeError(
            f"The authorized training attempt has already started: {MANIFEST_PATH}"
        )

    RUN_DIR.mkdir(parents=True, exist_ok=False)
    os.chdir(SOFTWARE_DIR)

    # Load only notebook definitions; skip notebook shell commands and its
    # inference-only main cell. This keeps the project notebook inference-only.
    notebook = nbformat.read(NOTEBOOK_PATH, as_version=4)
    namespace: dict = {"__name__": "ecg_training_attempt"}
    definition_cell_indices = (3, 4, 5, 6, 7, 9, 10)
    for cell_index in definition_cell_indices:
        cell = notebook.cells[cell_index]
        if cell.cell_type == "code":
            exec(compile(cell.source, f"notebook_cell_{cell_index}", "exec"), namespace)

    np = namespace["np"]
    tf = namespace["tf"]
    config = namespace["config"]
    config.learning_rate = 2e-3
    config.epochs = 100
    config.patience = 25
    config.batch_size = 128
    config.random_seed = 42
    config.baseline_weights = str(WEIGHTS_PATH)
    config.baseline_results = str(RESULTS_PATH)

    np.random.seed(config.random_seed)
    tf.keras.utils.set_random_seed(config.random_seed)

    # Set a fixed shuffle seed in the dataset pipeline, without touching the
    # saved train/validation/test membership.
    split_data = np.load(SPLIT_PATH, allow_pickle=False)
    expected_keys = {
        "X_train", "X_val", "X_test", "y_train", "y_val", "y_test",
        "RR_train", "RR_val", "RR_test",
    }
    missing_keys = sorted(expected_keys.difference(split_data.files))
    if missing_keys:
        raise ValueError(f"Split archive is missing arrays: {missing_keys}")
    data = {key: split_data[key] for key in sorted(expected_keys)}
    split_data.close()

    x_train, x_val, x_test = data["X_train"], data["X_val"], data["X_test"]
    y_train, y_val, y_test = data["y_train"], data["y_val"], data["y_test"]
    rr_train, rr_val, rr_test = data["RR_train"], data["RR_val"], data["RR_test"]
    if len(x_train) != len(y_train) or len(x_val) != len(y_val) or len(x_test) != len(y_test):
        raise ValueError("Split archive has mismatched ECG and label lengths")

    train_ds, val_ds = namespace["create_datasets"](
        x_train, rr_train, y_train, x_val, rr_val, y_val, config.batch_size
    )
    test_ds = namespace["create_test_dataset"](
        x_test, rr_test, y_test, config.batch_size
    )
    model = namespace["build_baseline_ViT"]()
    parameter_count = int(model.count_params())
    if parameter_count != 6643:
        raise RuntimeError(
            f"Expected the selected 6,643-parameter model; built {parameter_count:,}."
        )

    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=config.learning_rate),
        loss=tf.keras.losses.CategoricalCrossentropy(from_logits=True),
        metrics=["accuracy"],
    )
    callbacks = [
        tf.keras.callbacks.ModelCheckpoint(
            str(WEIGHTS_PATH),
            monitor="val_accuracy",
            save_best_only=True,
            save_weights_only=True,
            mode="max",
            verbose=1,
        ),
        tf.keras.callbacks.EarlyStopping(
            monitor="val_accuracy",
            patience=config.patience,
            restore_best_weights=True,
            mode="max",
            verbose=1,
        ),
        tf.keras.callbacks.ReduceLROnPlateau(
            monitor="val_loss",
            factor=0.5,
            patience=10,
            min_lr=1e-7,
            verbose=1,
        ),
    ]

    started_at = datetime.now(timezone.utc).isoformat()
    attempt_manifest = {
        "attempt": 1,
        "status": "running",
        "started_at_utc": started_at,
        "notebook": NOTEBOOK_PATH.name,
        "training_from_scratch": True,
        "training_configuration": {
            "epochs_max": config.epochs,
            "batch_size": config.batch_size,
            "learning_rate": config.learning_rate,
            "early_stopping_patience": config.patience,
            "random_seed": config.random_seed,
            "monitor": "validation accuracy",
            "class_weighting": "not applied; matches upstream baseline training code",
            "parameters": parameter_count,
        },
        "saved_split": {
            "file": SPLIT_PATH.name,
            "sha256": sha256_file(SPLIT_PATH),
            "train_beats": int(len(y_train)),
            "validation_beats": int(len(y_val)),
            "test_beats": int(len(y_test)),
            "protocol": "stratified beat-level 70/10/20; same saved membership",
        },
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "tensorflow": tf.__version__,
            "devices": [str(device) for device in tf.config.list_physical_devices()],
        },
        "output_weights": str(WEIGHTS_PATH.relative_to(SOFTWARE_DIR)),
        "output_results": str(RESULTS_PATH.relative_to(SOFTWARE_DIR)),
    }
    write_json(MANIFEST_PATH, attempt_manifest)

    try:
        print("Starting the one authorized training attempt from fresh weights.", flush=True)
        print(f"Model parameters: {parameter_count:,}", flush=True)
        print(f"Saved split SHA-256: {attempt_manifest['saved_split']['sha256']}", flush=True)
        print(
            f"Train/validation/test beats: {len(y_train):,}/{len(y_val):,}/{len(y_test):,}",
            flush=True,
        )
        start_clock = time.monotonic()
        history = model.fit(
            train_ds,
            epochs=config.epochs,
            validation_data=val_ds,
            callbacks=callbacks,
            verbose=2,
        )
        elapsed_seconds = time.monotonic() - start_clock

        if not WEIGHTS_PATH.is_file():
            raise RuntimeError("Training ended without a best-validation checkpoint")
        model.load_weights(str(WEIGHTS_PATH))
        results = namespace["evaluate_baseline_model"](model, test_ds, y_test)
        val_accuracy = [float(value) for value in history.history.get("val_accuracy", [])]
        best_epoch = int(np.argmax(val_accuracy) + 1) if val_accuracy else None
        results.update({
            "attempt": 1,
            "training_attempt_directory": RUN_DIR.name,
            "training_from_scratch": True,
            "best_validation_epoch": best_epoch,
            "best_validation_accuracy": max(val_accuracy) if val_accuracy else None,
            "epochs_completed": len(history.epoch),
            "training_seconds": elapsed_seconds,
            "random_seed": config.random_seed,
            "split_sha256": attempt_manifest["saved_split"]["sha256"],
            "split_protocol": "stratified beat-level 70/10/20; saved split preserved",
            "target_accuracy": 0.98,
        })
        write_json(RESULTS_PATH, results)
        write_json(RUN_DIR / "training_history.json", {
            "epochs": [int(epoch + 1) for epoch in history.epoch],
            **{
                metric: [float(value) for value in values]
                for metric, values in history.history.items()
            },
        })
        namespace["plot_baseline_training_history"](
            history, str(RUN_DIR / "baseline_training_history.png")
        )
        namespace["plot_baseline_confusion_matrix"](
            results, str(RUN_DIR / "baseline_confusion_matrix.png")
        )

        attempt_manifest.update({
            "status": "completed",
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "epochs_completed": len(history.epoch),
            "best_validation_epoch": best_epoch,
            "best_validation_accuracy": max(val_accuracy) if val_accuracy else None,
            "test_accuracy": results["test_accuracy"],
            "test_macro_f1": results["f1_macro"],
            "training_seconds": elapsed_seconds,
            "weights_sha256": sha256_file(WEIGHTS_PATH),
        })
        write_json(MANIFEST_PATH, attempt_manifest)

        print("\nONE TRAINING ATTEMPT COMPLETE", flush=True)
        print(f"Best validation accuracy: {results['best_validation_accuracy']:.4%}", flush=True)
        print(f"Test accuracy:            {results['test_accuracy']:.4%}", flush=True)
        print(f"Test macro-F1:            {results['f1_macro']:.4f}", flush=True)
        print(f"Results: {RESULTS_PATH}", flush=True)
        print(f"Weights: {WEIGHTS_PATH}", flush=True)
        print(f"Manifest: {MANIFEST_PATH}", flush=True)
        return 0
    except BaseException as exc:
        attempt_manifest.update({
            "status": "failed_after_start",
            "failed_at_utc": datetime.now(timezone.utc).isoformat(),
            "error_type": type(exc).__name__,
            "error": str(exc),
        })
        write_json(MANIFEST_PATH, attempt_manifest)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
