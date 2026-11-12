"""Export the saved local checkpoint's tensors for hardware-port work.

This exports the trained FP32 tensors and a shape/name manifest. It does not
quantize them or claim hardware accuracy; activation calibration and the
integer reference are separate stages.
"""

import argparse
import json
from pathlib import Path

import numpy as np

from active_model_reference import (
    CHECKPOINT,
    CLASS_ORDER,
    ECG_SAMPLES,
    EXPECTED_PARAMETER_COUNT,
    MLP_DIM,
    NUM_HEADS,
    NUM_PATCHES,
    RR_FEATURES,
    build_active_model,
)


def export_weights(checkpoint: Path, output_dir: Path) -> tuple[Path, Path]:
    model = build_active_model()
    if model.count_params() != EXPECTED_PARAMETER_COUNT:
        raise RuntimeError(
            f"Model parameter count mismatch: {model.count_params()} vs "
            f"{EXPECTED_PARAMETER_COUNT}"
        )
    model.load_weights(checkpoint)

    output_dir.mkdir(parents=True, exist_ok=True)
    arrays = {}
    tensor_manifest = []
    for layer_index, layer in enumerate(model.layers):
        for tensor_index, value in enumerate(layer.get_weights()):
            key = f"layer_{layer_index:02d}_tensor_{tensor_index:02d}"
            value = np.asarray(value, dtype=np.float32)
            arrays[key] = value
            variable = layer.weights[tensor_index]
            tensor_manifest.append(
                {
                    "array_key": key,
                    "layer_index": layer_index,
                    "layer_name": layer.name,
                    "layer_type": layer.__class__.__name__,
                    "variable_name": getattr(variable, "path", variable.name),
                    "shape": list(value.shape),
                    "dtype": "float32",
                }
            )

    weights_path = output_dir / "active_model_weights_fp32.npz"
    manifest_path = output_dir / "active_model_weights_manifest.json"
    np.savez_compressed(weights_path, **arrays)
    manifest = {
        "model_name": "Local Tiny ECG Transformer baseline",
        "checkpoint": str(checkpoint),
        "parameter_count": model.count_params(),
        "classes_in_output_order": list(CLASS_ORDER),
        "input": {
            "ecg_samples": ECG_SAMPLES,
            "rr_features": RR_FEATURES,
            "sampling_rate_hz": 360,
            "patch_count": NUM_PATCHES,
        },
        "architecture": {
            "attention_heads": NUM_HEADS,
            "key_dimension_per_head": 2,
            "embedding_dimension": 16,
            "feed_forward_dimension": MLP_DIM,
            "encoder_layers": 1,
            "convolution_kernel": 3,
            "convolution_stride": 3,
        },
        "quantization": {
            "status": "not_quantized",
            "note": "Use this FP32 export as source data; calibrate activation scales before integer deployment.",
        },
        "tensors": tensor_manifest,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return weights_path, manifest_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=CHECKPOINT)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "model_export",
    )
    args = parser.parse_args()
    weights_path, manifest_path = export_weights(args.checkpoint, args.output_dir)
    print(f"Exported trained FP32 tensors: {weights_path}")
    print(f"Tensor manifest: {manifest_path}")
    print("No training or quantization was performed.")


if __name__ == "__main__":
    main()
