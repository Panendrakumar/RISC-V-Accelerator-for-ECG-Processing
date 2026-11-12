"""Measure checkpoint-weight Q6.10 with FP32 activations (diagnostic only)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import accuracy_score, f1_score

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fixed_point_reference as fixed  # noqa: E402


def main() -> None:
    weights = fixed.load_weights()  # q() is still enabled: quantize weights.
    fixed.q = lambda value: np.asarray(value, dtype=np.float64)  # type: ignore[assignment]
    split_path = fixed.SPLIT
    with np.load(split_path) as split:
        x_test, rr_test, y_true = split["X_test"], split["RR_test"], split["y_test"]

    predictions: list[int] = []
    for start in range(0, len(y_true), 32):
        end = min(start + 32, len(y_true))
        out = fixed.infer_batch(x_test[start:end], rr_test[start:end], weights)
        predictions.extend(np.argmax(out, axis=1).tolist())
        if start % 3200 == 0:
            print(f"Weight-only Q6.10: {end:,}/{len(y_true):,}", flush=True)

    predicted = np.asarray(predictions)
    result = {
        "weights": "Q6.10",
        "activations": "float64 software arithmetic",
        "test_count": int(len(y_true)),
        "accuracy": float(accuracy_score(y_true, predicted)),
        "macro_f1": float(f1_score(y_true, predicted, average="macro", zero_division=0)),
        "note": "Diagnostic software result only; not an FPGA measurement.",
    }
    output = HERE / "weight_only_q610_results.json"
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    print(f"Saved: {output}")


if __name__ == "__main__":
    main()
