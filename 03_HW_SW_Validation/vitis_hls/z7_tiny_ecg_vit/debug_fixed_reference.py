"""Print layer ranges for a few fixed-point vs unrounded reference vectors."""

from __future__ import annotations

import numpy as np

import fixed_point_reference as fixed


def main() -> None:
    weights = fixed.load_weights()
    vectors = np.load(fixed.EXPORT / "golden_fp32_samples.npz")
    print("Fixed activation arithmetic:")
    fixed_logits = fixed.infer_batch(
        vectors["ecg_samples"], vectors["rr_features"], weights, trace=True
    )
    print("fixed classes:", np.argmax(fixed_logits, axis=1))
    fixed.q = lambda value: np.asarray(value, dtype=np.float64)  # type: ignore[assignment]
    print("Unrounded activations (same Q6 weights, LUT tables):")
    float_logits = fixed.infer_batch(
        vectors["ecg_samples"], vectors["rr_features"], weights, trace=True
    )
    print("unrounded classes:", np.argmax(float_logits, axis=1))
    print("checkpoint classes:", vectors["predicted_class_indices"])


if __name__ == "__main__":
    main()
