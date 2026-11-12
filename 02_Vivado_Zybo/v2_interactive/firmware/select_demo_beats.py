"""Pick 16 test-split beats for the switch-selectable FPGA demo.

Switch values 0-8  : the 9 saved golden beats (same as the known-beat self-test).
Switch values 9-15 : extra beats chosen on purpose to include model mistakes
                     and the two other Q beats, so the demo is honest.

For every beat the script records:
  true label (y_test), FP32 checkpoint prediction (baseline_results.json), and
  the Q6.10 software-reference prediction (fixed_point_reference.infer_batch).
The FPGA is checked against the Q6.10 prediction, because the hardware is Q6.10.

Outputs (next to this script):
  demo_beats_data.h   - firmware header (raw signed Q6.10 values)
  demo_beats.json     - human-readable list of the 16 beats

Read-only with respect to the dataset, checkpoint and results files.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SPLIT = ROOT / "04_Model_Software/third_party_models/TinyTransformer/software/consistent_data_splits.npz"
RESULTS = ROOT / "04_Model_Software/third_party_models/TinyTransformer/software/training_attempt_20261024/baseline_results.json"
GOLDEN_JSON = ROOT / "03_HW_SW_Validation/model_export/golden_fp32_samples.json"
GOLDEN_H = ROOT / "03_HW_SW_Validation/vitis_hls/z7_tiny_ecg_vit/golden_test_vectors.h"
FIXED_DIR = ROOT / "03_HW_SW_Validation/vitis_hls/z7_tiny_ecg_vit"
OUT_H = HERE / "demo_beats_data.h"
OUT_JSON = HERE / "demo_beats.json"
NAMES = "NSVFQ"

sys.path.insert(0, str(FIXED_DIR))
import fixed_point_reference as fpr  # noqa: E402


def q610(values) -> list[int]:
    return [int(max(-32768, min(32767, round(float(v) * 1024)))) for v in values]


def golden_header_rows(name: str) -> list[list[float]]:
    src = GOLDEN_H.read_text(encoding="utf-8")
    m = re.search(rf"static const float {name}\[[^;]*?=\s*\{{(.*?)\n\}};", src, flags=re.DOTALL)
    rows = re.findall(r"\{([^{}]+)\}", m.group(1))
    return [[float(x.rstrip("f")) for x in re.findall(r"[-+0-9.eE]+f?", r)] for r in rows]


def main() -> None:
    with np.load(SPLIT) as s:
        x_test, rr_test, y_test = s["X_test"], s["RR_test"], s["y_test"]
    x_test = x_test.reshape(len(y_test), -1)
    fp32_pred = np.asarray(json.loads(RESULTS.read_text())["predictions"], dtype=np.int64)
    golden = json.loads(GOLDEN_JSON.read_text())
    golden_idx = [int(i) for i in golden["test_indices"]]
    if len(fp32_pred) != len(y_test):
        raise SystemExit("Prediction count does not match test split size")

    # Sanity check: golden vectors really are these test rows.
    g_ecg = golden_header_rows("GOLDEN_ECG")
    for k, idx in enumerate(golden_idx):
        if not np.allclose(np.asarray(g_ecg[k]), x_test[idx], atol=1e-4):
            raise SystemExit(f"Golden vector {k} does not match X_test[{idx}]")
        if NAMES[int(y_test[idx])] != golden["true_classes"][k]:
            raise SystemExit(f"Golden vector {k} true label mismatch")
        if NAMES[int(fp32_pred[idx])] != golden["checkpoint_predictions"][k]:
            raise SystemExit(f"Golden vector {k} prediction mismatch")
    print("Golden vectors verified against X_test, y_test and saved predictions.")

    weights = fpr.load_weights()

    def q610_pred(indices: list[int]) -> np.ndarray:
        idx = np.asarray(indices)
        logits = fpr.infer_batch(x_test[idx], rr_test[idx], weights)
        return np.argmax(logits, axis=1)

    # Extra beats: (true, fp32 predicted) categories, mistakes on purpose.
    wanted = [
        ("S", "N", "S beat the model misses (called N)"),
        ("F", "N", "Fusion beat called N"),
        ("V", "F", "V beat called F"),
        ("N", "S", "Normal beat falsely called S"),
        ("V", "N", "V beat called N"),
    ]
    extras: list[tuple[int, str]] = []
    used = set(golden_idx)
    for true_c, pred_c, why in wanted:
        cand = [int(i) for i in np.where((y_test == NAMES.index(true_c)) & (fp32_pred == NAMES.index(pred_c)))[0] if int(i) not in used][:40]
        if not cand:
            print(f"No candidate for {why}; skipped")
            continue
        qp = q610_pred(cand)
        agree = [c for c, p in zip(cand, qp) if int(p) == NAMES.index(pred_c)]
        if not agree:
            print(f"No candidate for {why} where Q6.10 agrees with FP32; skipped")
            continue
        extras.append((agree[0], why))
        used.add(agree[0])
    for i in np.where(y_test == NAMES.index("Q"))[0]:
        if int(i) not in used:
            extras.append((int(i), "Paced/unknown (Q) beat - rare class"))
            used.add(int(i))
    beats = [(i, "golden self-test beat") for i in golden_idx] + extras
    beats = beats[:16]

    idx = [b[0] for b in beats]
    q_pred = q610_pred(idx)
    rows = []
    for sw, ((i, why), qp) in enumerate(zip(beats, q_pred)):
        rows.append({
            "switch": sw, "switch_binary": format(sw, "04b"), "test_index": i,
            "true": NAMES[int(y_test[i])], "fp32_pred": NAMES[int(fp32_pred[i])],
            "q610_pred": NAMES[int(qp)], "note": why,
        })

    n = len(rows)
    lines = [
        "// Generated by select_demo_beats.py. Raw signed Q6.10 values. Do not edit by hand.",
        "#ifndef DEMO_BEATS_DATA_H", "#define DEMO_BEATS_DATA_H", "#include <stdint.h>",
        f"#define DEMO_COUNT {n}u",
        f"static const int16_t demo_ecg_q10[{n}][198] __attribute__((aligned(4))) = {{",
    ]
    for k, r in enumerate(rows):
        vals = q610(x_test[r["test_index"]])
        lines.append(f"  {{ // SW={r['switch_binary']} test#{r['test_index']} true {r['true']}, Q6.10 predicts {r['q610_pred']}")
        lines.append("    " + ",\n    ".join(", ".join(map(str, vals[j:j + 12])) for j in range(0, 198, 12)))
        lines.append("  }" + ("," if k + 1 < n else ""))
    lines.append("};")
    lines.append(f"static const int16_t demo_rr_q10[{n}][2] __attribute__((aligned(4))) = {{")
    lines.append("    " + ",\n    ".join("{%d, %d}" % tuple(q610(rr_test[r["test_index"]])) for r in rows))
    lines.append("};")
    for name, key in (("demo_true_class", "true"), ("demo_fp32_pred", "fp32_pred"), ("demo_q610_pred", "q610_pred")):
        lines.append(f"static const uint8_t {name}[{n}] = {{{', '.join(str(NAMES.index(r[key])) for r in rows)}}};")
    lines.append(f"static const uint16_t demo_test_index[{n}] = {{{', '.join(str(r['test_index']) for r in rows)}}};")
    lines += ["#endif", ""]
    OUT_H.write_text("\n".join(lines), encoding="utf-8")
    OUT_JSON.write_text(json.dumps({
        "note": "Switch-selectable demo beats. FPGA output is checked against q610_pred. Not an accuracy sample.",
        "beats": rows}, indent=2), encoding="utf-8")

    print(f"\nWrote {OUT_H.name} and {OUT_JSON.name} with {n} beats:\n")
    print(" SW    test#   true  FP32  Q6.10  note")
    for r in rows:
        flag = "" if r["fp32_pred"] == r["q610_pred"] else "   <-- FP32 and Q6.10 differ"
        print(f" {r['switch_binary']}  {r['test_index']:6d}    {r['true']}     {r['fp32_pred']}     {r['q610_pred']}    {r['note']}{flag}")


if __name__ == "__main__":
    main()
