"""Stream saved MIT-BIH test beats through the Zybo Z7-10 (v2 bitstream) and
measure FPGA predictions over the existing USB/JTAG cable.

The laptop only moves data: every class reported as "FPGA" was computed by the
accelerator on the board and read back from BRAM. Nothing is predicted in Python
except the separately labelled software references used for comparison.

Usage (project venv, board programmed with zybo_vit_v2_interactive.bit):
  python stream_test_beats.py --start 0 --count 50          # quick benchmark
  python stream_test_beats.py --start 0 --count 2000        # larger sample
  python stream_test_beats.py --all                          # entire test split

Sample = test-split rows [start, start+count). The split order is the saved
stratified shuffle, so a contiguous block is not hand-picked; state it as a
sample, never as full-test-set accuracy unless --all completed.

Outputs: 03_HW_SW_Validation/hardware_outputs/fpga_stream/<run>/
  fpga_predictions.csv, summary.json
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score

# Keep the V: drive form of the path (do not resolve()): Vivado's command line
# breaks on the spaces in the real project path.
HERE = Path(__file__).absolute().parent
ROOT = HERE.parents[2]
if " " in str(HERE):
    raise SystemExit("Run this script through the V: drive (subst), e.g. V:\\02_Vivado_Zybo\\v2_interactive\\host\\stream_test_beats.py")
sys.path.insert(0, str(ROOT / "03_HW_SW_Validation/vitis_hls/z7_tiny_ecg_vit"))
import fixed_point_reference as fpr  # noqa: E402

VIVADO = r"C:\Xilinx\Vivado\2023.2\bin\vivado.bat"
LTX = HERE.parent / "ECG_ViT_Zybo_v2/ECG_ViT_Zybo_v2.runs/impl_1/zybo_vit_v2_top.ltx"
ENGINE = HERE / "stream_engine.tcl"
RESULTS = ROOT / "04_Model_Software/third_party_models/TinyTransformer/software/training_attempt_20261024/baseline_results.json"
OUT_BASE = ROOT / "03_HW_SW_Validation/hardware_outputs/fpga_stream"
NAMES = "NSVFQ"
CHUNK = 2000  # beats per Vivado session


def q610_word(a: int, b: int) -> str:
    return f"{((b & 0xFFFF) << 16) | (a & 0xFFFF):08x}"


def to_q610(values) -> list[int]:
    return [int(max(-32768, min(32767, round(float(v) * 1024)))) for v in values]


def tcl_path(p: Path) -> str:
    return str(p).replace("\\", "/")


def run_chunk(indices, x, rr, tmpdir: Path, chunk_no: int, on_result) -> float:
    lines = [f"set ::LTX {{{tcl_path(LTX)}}}", "set ::BEATS {"]
    for i in indices:
        e = to_q610(x[i])
        words = " ".join(q610_word(e[2 * k], e[2 * k + 1]) for k in range(99))
        r = to_q610(rr[i])
        lines.append(f"  {{{i} {{{words}}} {q610_word(r[0], r[1])}}}")
    lines.append("}")
    lines.append(f"source {{{tcl_path(ENGINE)}}}")
    script = tmpdir / f"chunk_{chunk_no:03d}.tcl"
    script.write_text("\n".join(lines) + "\n", encoding="ascii")

    t0 = time.time()
    proc = subprocess.Popen(
        ["cmd", "/c", VIVADO, "-mode", "batch", "-nojournal", "-nolog", "-notrace", "-source", tcl_path(script)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=str(tmpdir),
    )
    for line in proc.stdout:
        line = line.strip()
        if line.startswith(("RESULT", "FAIL", "FATAL", "INFO write_order", "INFO beats")):
            on_result(line)
    proc.wait()
    return time.time() - t0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--count", type=int, default=50)
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()

    with np.load(fpr.SPLIT) as s:
        x, rr, y = s["X_test"], s["RR_test"], s["y_test"]
    x = x.reshape(len(y), -1)
    fp32 = np.asarray(json.loads(RESULTS.read_text())["predictions"], dtype=np.int64)
    start = 0 if args.all else args.start
    stop = len(y) if args.all else min(len(y), args.start + args.count)
    indices = list(range(start, stop))

    run_name = datetime.now().strftime("%Y%m%d_%H%M%S") + f"_{start}_{stop}"
    out_dir = OUT_BASE / run_name
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Streaming test rows {start}..{stop - 1} ({len(indices)} beats) -> {out_dir}")

    fpga: dict[int, tuple[int, int, list[int]]] = {}
    failures: list[str] = []

    def on_result(line: str) -> None:
        parts = line.split()
        if parts[0] == "RESULT":
            idx, cls, cyc = int(parts[1]), int(parts[2]), int(parts[3])
            fpga[idx] = (cls, cyc, [int(v) for v in parts[4:9]])
            if len(fpga) % 25 == 0:
                print(f"  {len(fpga)}/{len(indices)} beats done", flush=True)
        else:
            print("  " + line, flush=True)
            if parts[0] in ("FAIL", "FATAL"):
                failures.append(line)

    wall = 0.0
    for c, k in enumerate(range(0, len(indices), CHUNK)):
        wall += run_chunk(indices[k:k + CHUNK], x, rr, out_dir, c, on_result)
        if any(f.startswith("FATAL") for f in failures):
            break

    done = [i for i in indices if i in fpga]
    if not done:
        raise SystemExit("No FPGA results were returned.")
    idx = np.asarray(done)
    print("Computing Q6.10 software reference for comparison ...")
    q_logits = np.concatenate([fpr.infer_batch(x[idx[k:k + 256]], rr[idx[k:k + 256]], fpr.load_weights()) for k in range(0, len(idx), 256)])
    q_raw = np.rint(q_logits * 1024).astype(np.int64)
    q_pred = np.argmax(q_logits, axis=1)
    f_pred = np.asarray([fpga[i][0] for i in done])
    f_raw = np.asarray([fpga[i][2] for i in done])
    cycles = np.asarray([fpga[i][1] for i in done])
    y_s, fp32_s = y[idx], fp32[idx]

    with (out_dir / "fpga_predictions.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["test_index", "true", "fpga_pred", "q610_pred", "fp32_pred", "fpga_cycles",
                    "fpga_logits_raw", "q610_logits_raw"])
        for k, i in enumerate(done):
            w.writerow([i, NAMES[y_s[k]], NAMES[f_pred[k]], NAMES[q_pred[k]], NAMES[fp32_s[k]], cycles[k],
                        " ".join(map(str, f_raw[k])), " ".join(map(str, q_raw[k]))])

    labels = [0, 1, 2, 3, 4]
    support = {NAMES[c]: int((y_s == c).sum()) for c in labels}
    summary = {
        "what_this_is": ("FPGA (Zybo Z7-10, v2 bitstream) predictions on "
                         + ("the entire" if args.all and len(done) == len(y) else "a sample of the")
                         + " saved beat-level test split. Beats sent over JTAG-to-AXI; class computed by the on-board accelerator."),
        "test_rows": [start, stop - 1],
        "is_full_test_set": bool(args.all and len(done) == len(y)),
        "beats_requested": len(indices),
        "beats_completed": len(done),
        "failures": failures,
        "support": support,
        "fpga_accuracy_vs_true": float(accuracy_score(y_s, f_pred)),
        "fpga_macro_f1_vs_true": float(f1_score(y_s, f_pred, labels=labels, average="macro", zero_division=0)),
        "fpga_confusion_rows_true_cols_pred_NSVFQ": confusion_matrix(y_s, f_pred, labels=labels).tolist(),
        "agreement_fpga_vs_q610_python": float((f_pred == q_pred).mean()),
        "agreement_fpga_vs_fp32_checkpoint": float((f_pred == fp32_s).mean()),
        "fp32_accuracy_on_same_sample": float(accuracy_score(y_s, fp32_s)),
        "q610_python_accuracy_on_same_sample": float(accuracy_score(y_s, q_pred)),
        "max_abs_logit_diff_fpga_vs_q610_python_raw": int(np.abs(f_raw - q_raw).max()),
        "cycles_mean": float(cycles.mean()),
        "cycles_min": int(cycles.min()),
        "cycles_max": int(cycles.max()),
        "latency_ms_mean_at_100MHz": float(cycles.mean() / 1e5),
        "wall_clock_seconds": round(wall, 1),
        "seconds_per_beat_including_jtag": round(wall / len(done), 3),
        "caveats": [
            "Beat-level split, not patient-independent.",
            "Macro-F1 on a sample depends on how many rare-class beats (F, Q) it contains; see support.",
            "Python Q6.10 reference approximates the HLS arithmetic; small raw-logit differences are expected.",
        ],
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"Saved {out_dir}")


if __name__ == "__main__":
    main()
