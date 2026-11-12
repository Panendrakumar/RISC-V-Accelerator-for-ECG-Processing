"""Evaluate a software Q6.10 approximation of the active checkpoint.

This uses quantized checkpoint weights, Q6.10 layer outputs, and the same GELU
and exp lookup tables generated for ``vit_inference_fixed.cpp``. It is a
software accuracy estimate; HLS C simulation and board results are reported
separately.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

import numpy as np
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score


ROOT = Path(__file__).resolve().parents[3]
EXPORT = ROOT / "03_HW_SW_Validation" / "model_export"
SPLIT = (
    ROOT / "04_Model_Software" / "third_party_models" / "TinyTransformer"
    / "software" / "consistent_data_splits.npz"
)
FRAC_BITS = int(os.environ.get("ECG_Q_FRAC_BITS", "10"))
OUT = Path(__file__).resolve().parent / f"fixed_point_q6_{FRAC_BITS}_results.json"
SCALE = float(1 << FRAC_BITS)
QMIN = -32.0
QMAX = 32.0 - 1.0 / SCALE
EPS_Q = np.rint(1.0e-3 * SCALE) / SCALE
INV_SQRT2_Q = np.rint((1.0 / math.sqrt(2.0)) * SCALE) / SCALE
INV_SQRT2 = float(INV_SQRT2_Q)
ACC_SCALE = float(1 << 20)  # fractional precision of ap_fixed<32,12>
ACC_MIN = -2048.0
ACC_MAX = 2048.0 - 1.0 / ACC_SCALE


def q(value):
    return np.clip(np.rint(np.asarray(value) * SCALE) / SCALE, QMIN, QMAX)


def acc_q(value):
    return np.clip(np.rint(np.asarray(value) * ACC_SCALE) / ACC_SCALE, ACC_MIN, ACC_MAX)


def load_weights():
    z = np.load(EXPORT / "active_model_weights_fp32.npz")
    m = json.loads((EXPORT / "active_model_weights_manifest.json").read_text())
    by_name = {
        item["variable_name"]: q(z[item["array_key"]])
        for item in m["tensors"]
    }
    return {
        "conv": by_name["conv2d/kernel"].reshape(3, 16),
        "conv_b": by_name["conv2d/bias"],
        "pos": by_name["posembed_input/pos_embedding"].reshape(66, 16),
        "g1": by_name["layer_normalization/gamma"],
        "b1": by_name["layer_normalization/beta"],
        "qk": by_name["multi_head_attention/query/kernel"],
        "qb": by_name["multi_head_attention/query/bias"],
        "kk": by_name["multi_head_attention/key/kernel"],
        "kb": by_name["multi_head_attention/key/bias"],
        "vk": by_name["multi_head_attention/value/kernel"],
        "vb": by_name["multi_head_attention/value/bias"],
        "ok": by_name["multi_head_attention/attention_output/kernel"],
        "ob": by_name["multi_head_attention/attention_output/bias"],
        "g2": by_name["layer_normalization_1/gamma"],
        "b2": by_name["layer_normalization_1/beta"],
        "ff1": by_name["dense/kernel"],
        "ff1b": by_name["dense/bias"],
        "ff2": by_name["dense_1/kernel"],
        "ff2b": by_name["dense_1/bias"],
        "go": by_name["encoder_norm/gamma"],
        "bo": by_name["encoder_norm/beta"],
        "rr": by_name["dense_2/kernel"],
        "head": by_name["head/kernel"],
        "headb": by_name["head/bias"],
    }


_gelu_x = np.linspace(-8.0, 8.0, 257)
_gelu_table = q(
    _gelu_x * 0.5 * (1.0 + np.asarray([math.erf(float(x) / math.sqrt(2.0)) for x in _gelu_x]))
)
_exp_table = q(np.exp(np.linspace(-12.0, 0.0, 257)))


def lut(x, lo, hi, table, intervals):
    x = np.asarray(x)
    clipped = np.clip(x, lo, hi)
    # LUT positions span 0..256 and do not fit in q_t (Q6.x). The C++ HLS
    # implementation computes this position in the wider accumulator type.
    pos = acc_q((clipped - lo) * q(intervals / (hi - lo)))
    idx = np.clip(np.trunc(pos).astype(np.int32), 0, intervals - 1)
    frac = q(pos - idx)
    return q(table[idx] + frac * (table[idx + 1] - table[idx]))


def gelu(x):
    y = lut(x, -8.0, 8.0, _gelu_table, 256)
    return np.where(x <= -8.0, 0.0, np.where(x >= 8.0, x, y))


def exp_softmax(scores):
    maximum = np.max(scores, axis=-1, keepdims=True)
    delta = q(scores - maximum)
    ex = lut(delta, -12.0, 0.0, _exp_table, 256)
    ex = np.where(delta <= -12.0, 0.0, np.where(delta >= 0.0, 1.0, ex))
    den = acc_q(np.sum(ex, axis=-1, keepdims=True, dtype=np.float64))
    # Keep the denominator in the wider accumulator format: softmax row sums
    # can exceed the Q6.10 range (+32), so quantizing the sum first would
    # saturate it and produce probabilities whose total is greater than one.
    inv = q(1.0 / den)
    return ex * inv


def layer_norm(x, gamma, beta):
    mean = q(acc_q(np.sum(x, axis=-1, keepdims=True, dtype=np.float64)) / 16.0)
    difference = q(x - mean)
    variance_sum = acc_q(np.sum(difference * difference, axis=-1, keepdims=True, dtype=np.float64))
    variance = q(variance_sum / 16.0)
    root = q(np.sqrt(q(variance + EPS_Q)))
    inv = q(1.0 / root)
    return q(difference * inv * gamma + beta)


def infer_batch(ecg, rr, w, trace=False):
    def report(name, values):
        if trace:
            first = np.asarray(values)[0]
            print(
                f"{name:12s} min={first.min(): .6f} max={first.max(): .6f} "
                f"mean={first.mean(): .6f} std={first.std(): .6f}",
                flush=True,
            )

    batch = ecg.shape[0]
    x = q(ecg.astype(np.float32))
    report("input", x)
    patches = q(np.einsum("bpk,ke->bpe", x.reshape(batch, 66, 3), w["conv"], optimize=True) + w["conv_b"])
    patches = q(patches + w["pos"])
    report("patches", patches)

    norm1 = layer_norm(patches, w["g1"], w["b1"])
    report("norm1", norm1)
    qv = q(np.einsum("bpe,ehd->bphd", norm1, w["qk"], optimize=True) + w["qb"])
    kv = q(np.einsum("bpe,ehd->bphd", norm1, w["kk"], optimize=True) + w["kb"])
    vv = q(np.einsum("bpe,ehd->bphd", norm1, w["vk"], optimize=True) + w["vb"])
    report("qkv", np.concatenate([qv.reshape(batch, 66, 16), kv.reshape(batch, 66, 16), vv.reshape(batch, 66, 16)], axis=1))
    scores = q(np.einsum("bqhd,bkhd->bhqk", qv, kv, optimize=True))
    scores = q(scores * INV_SQRT2)
    report("scores", scores)
    attention = exp_softmax(scores)
    report("attention", attention)
    context = q(acc_q(np.einsum("bhqk,bkhd->bqhd", attention, vv, optimize=True)))
    report("context", context)

    attended = np.zeros((batch, 66, 16), dtype=np.float64)
    for h in range(8):
        for d in range(2):
            product = q(context[:, :, h, d, None]) * w["ok"][h, d, :]
            attended = q(attended + product)
    report("attended", attended)
    residual1 = q(attended + w["ob"] + patches)
    report("residual1", residual1)

    norm2 = layer_norm(residual1, w["g2"], w["b2"])
    report("norm2", norm2)
    hidden = gelu(q(np.einsum("bpe,ef->bpf", norm2, w["ff1"], optimize=True) + w["ff1b"]))
    report("hidden", hidden)
    projected = gelu(q(np.einsum("bpf,fe->bpe", hidden, w["ff2"], optimize=True) + w["ff2b"]))
    report("projected", projected)
    residual2 = q(projected + residual1)
    report("residual2", residual2)
    final = layer_norm(residual2, w["go"], w["bo"])
    report("final", final)
    pooled = q(acc_q(np.sum(final, axis=1, dtype=np.float64)) / 66.0)
    report("pooled", pooled)

    rr_embed = q(np.einsum("br,re->be", q(rr), w["rr"], optimize=True))
    combined = np.concatenate([pooled, rr_embed], axis=1)
    logits = q(np.einsum("bi,ic->bc", combined, w["head"], optimize=True) + w["headb"])
    report("logits", logits)
    return logits


def main():
    with np.load(SPLIT) as split:
        x_test = split["X_test"]
        rr_test = split["RR_test"]
        y_true = split["y_test"]
    weights = load_weights()
    predictions = []
    batch_size = 32
    for start in range(0, len(y_true), batch_size):
        end = min(start + batch_size, len(y_true))
        predictions.extend(np.argmax(infer_batch(x_test[start:end], rr_test[start:end], weights), axis=1))
        if (start // batch_size) % 100 == 0:
            print(f"Q6.{FRAC_BITS} reference: {end:,}/{len(y_true):,}", flush=True)
    y_pred = np.asarray(predictions, dtype=np.int64)
    result = {
        "format": f"Q6.{FRAC_BITS} weights and activations with Q12.20 accumulators",
        "test_count": int(len(y_true)),
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=[0, 1, 2, 3, 4]).tolist(),
        "classes": ["N", "S", "V", "F", "Q"],
        "note": "Software fixed-point approximation only; it is not an FPGA measurement.",
    }
    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()
