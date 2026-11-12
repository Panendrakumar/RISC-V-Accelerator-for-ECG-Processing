"""Make Q6.10 checkpoint weights and nonlinear lookup tables for HLS."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[3]
EXPORT_DIR = ROOT / "03_HW_SW_Validation" / "model_export"
OUT_DIR = Path(__file__).resolve().parent
FRAC_BITS = int(os.environ.get("ECG_Q_FRAC_BITS", "10"))
SCALE = 1 << FRAC_BITS
Q_MIN = -32.0
Q_MAX = 32.0 - 1.0 / SCALE

TENSOR_NAMES = {
    "conv2d/kernel": "W_CONV",
    "conv2d/bias": "B_CONV",
    "posembed_input/pos_embedding": "W_POS",
    "layer_normalization/gamma": "GAMMA_1",
    "layer_normalization/beta": "BETA_1",
    "multi_head_attention/query/kernel": "W_Q",
    "multi_head_attention/query/bias": "B_Q",
    "multi_head_attention/key/kernel": "W_K",
    "multi_head_attention/key/bias": "B_K",
    "multi_head_attention/value/kernel": "W_V",
    "multi_head_attention/value/bias": "B_V",
    "multi_head_attention/attention_output/kernel": "W_O",
    "multi_head_attention/attention_output/bias": "B_O",
    "layer_normalization_1/gamma": "GAMMA_2",
    "layer_normalization_1/beta": "BETA_2",
    "dense/kernel": "W_FF1",
    "dense/bias": "B_FF1",
    "dense_1/kernel": "W_FF2",
    "dense_1/bias": "B_FF2",
    "encoder_norm/gamma": "GAMMA_OUT",
    "encoder_norm/beta": "BETA_OUT",
    "dense_2/kernel": "W_RR",
    "head/kernel": "W_HEAD",
    "head/bias": "B_HEAD",
}


def q10(values: np.ndarray | float) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64)
    return np.clip(np.rint(values * SCALE) / SCALE, Q_MIN, Q_MAX).astype(np.float32)


def fmt(value: float) -> str:
    result = f"{float(value):.10g}"
    if "." not in result and "e" not in result.lower():
        result += ".0"
    return result


def write_arrays() -> None:
    manifest = json.loads(
        (EXPORT_DIR / "active_model_weights_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    with np.load(EXPORT_DIR / "active_model_weights_fp32.npz") as weights:
        arrays: dict[str, np.ndarray] = {}
        for item in manifest["tensors"]:
            name = TENSOR_NAMES.get(item["variable_name"])
            if name:
                arrays[name] = q10(weights[item["array_key"]]).reshape(-1)
    if set(arrays) != set(TENSOR_NAMES.values()):
        raise ValueError("Saved model export does not contain all expected tensors")

    gelu_x = np.linspace(-8.0, 8.0, 257)
    gelu = gelu_x * 0.5 * (
        1.0 + np.asarray([math.erf(float(x) / math.sqrt(2.0)) for x in gelu_x])
    )
    exp_x = np.linspace(-12.0, 0.0, 257)
    exp = np.exp(exp_x)
    arrays["GELU_LUT"] = q10(gelu)
    arrays["EXP_LUT"] = q10(exp)

    lines = [
        f"// Generated from the active FP32 checkpoint and quantized to Q6.{FRAC_BITS}.",
        "// Recreate with generate_fixed_assets.py; do not edit manually.",
        "#ifndef FIXED_MODEL_ASSETS_H",
        "#define FIXED_MODEL_ASSETS_H",
        "#include \"fixed_types.h\"",
        "",
    ]
    for name, values in arrays.items():
        lines.append(f"static const q_t {name}[{values.size}] = {{")
        for start in range(0, values.size, 8):
            lines.append(
                "    " + ", ".join(fmt(v) for v in values[start : start + 8]) + ","
            )
        lines.extend(["};", ""])
    lines.append("#endif  // FIXED_MODEL_ASSETS_H")
    (OUT_DIR / "fixed_model_assets.h").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    write_arrays()
    print(f"Generated Q6.10 weights and nonlinear tables in {OUT_DIR}")
