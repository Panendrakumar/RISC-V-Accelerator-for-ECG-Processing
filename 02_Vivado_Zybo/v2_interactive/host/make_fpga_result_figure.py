"""Make a one-page figure from an FPGA streaming run (summary.json + fpga_predictions.csv).

Usage: python make_fpga_result_figure.py <run folder>
Writes fpga_result_figure.png and .pdf into that folder.
"""
import csv
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sklearn.metrics import f1_score, precision_recall_fscore_support

NAMES = "NSVFQ"
run = Path(sys.argv[1])
summary = json.loads((run / "summary.json").read_text())
rows = list(csv.DictReader((run / "fpga_predictions.csv").open()))
y = np.array([NAMES.index(r["true"]) for r in rows])
f = np.array([NAMES.index(r["fpga_pred"]) for r in rows])
q = np.array([NAMES.index(r["q610_pred"]) for r in rows])
s = np.array([NAMES.index(r["fp32_pred"]) for r in rows])
cm = np.array(summary["fpga_confusion_rows_true_cols_pred_NSVFQ"])
labels = list(range(5))

fig = plt.figure(figsize=(13, 6.2))
ax = fig.add_axes([0.04, 0.12, 0.38, 0.72])
norm = cm / np.maximum(cm.sum(axis=1, keepdims=True), 1)
ax.imshow(norm, cmap="Blues", vmin=0, vmax=1)
for i in range(5):
    for j in range(5):
        ax.text(j, i, f"{cm[i, j]}", ha="center", va="center",
                color="white" if norm[i, j] > 0.6 else "black", fontsize=10)
ax.set_xticks(labels, list(NAMES))
ax.set_yticks(labels, list(NAMES))
ax.set_xlabel("FPGA predicted class")
ax.set_ylabel("True class")
ax.set_title("FPGA confusion matrix (counts; colour = row share)")

def acc(p):
    return 100.0 * (p == y).mean()

def mf1(p):
    return f1_score(y, p, labels=labels, average="macro", zero_division=0)

table = [
    ["", "FP32 software", "Q6.10 software", "FPGA (Zybo Z7-10)"],
    ["Accuracy (%)", f"{acc(s):.4f}", f"{acc(q):.4f}", f"{acc(f):.4f}"],
    ["Macro-F1", f"{mf1(s):.4f}", f"{mf1(q):.4f}", f"{mf1(f):.4f}"],
    ["Same class as FPGA (%)", f"{100 * (s == f).mean():.3f}", f"{100 * (q == f).mean():.3f}", "-"],
    ["Mean latency", "-", "-", f"{summary['latency_ms_mean_at_100MHz']:.2f} ms ({summary['cycles_mean']:.0f} cyc)"],
]
per_class = [["Class", "Test beats", "FP32 F1", "Q6.10 F1", "FPGA F1"]]
f1s = [precision_recall_fscore_support(y, p, labels=labels, zero_division=0) for p in (s, q, f)]
for c in labels:
    per_class.append([NAMES[c], f"{f1s[2][3][c]}", f"{f1s[0][2][c]:.3f}", f"{f1s[1][2][c]:.3f}", f"{f1s[2][2][c]:.3f}"])


def draw(rect, data, widths):
    tax = fig.add_axes(rect)
    tax.axis("off")
    t = tax.table(cellText=data, loc="center", cellLoc="center", colWidths=widths)
    t.auto_set_font_size(False)
    t.set_fontsize(9.5)
    t.scale(1, 1.45)
    for (r, c), cell in t.get_celld().items():
        if r == 0 or c == 0:
            cell.set_text_props(weight="bold")


draw([0.47, 0.55, 0.52, 0.32], table, [0.29, 0.21, 0.21, 0.29])
draw([0.53, 0.20, 0.40, 0.32], per_class, [0.14, 0.22, 0.2, 0.2, 0.2])

scope = "entire saved test split" if summary.get("is_full_test_set") else f"test rows {summary['test_rows'][0]}-{summary['test_rows'][1]} (sample)"
fig.suptitle(f"ECG Transformer on Zybo Z7-10: measured FPGA results, {len(rows):,} beats, {scope}", fontsize=13, weight="bold")
fig.text(0.47, 0.12,
         "FPGA classes computed by the on-board Q6.10 accelerator; beats sent from the laptop over JTAG-to-AXI.\n"
         "Beat-level split (records overlap train/test): not patient-independent. Q has very few test beats.\n"
         "Q6.10 software reference approximates the HLS arithmetic; tiny logit differences are expected.",
         fontsize=8.5, va="top")
for ext in ("png", "pdf"):
    fig.savefig(run / f"fpga_result_figure.{ext}", dpi=200 if ext == "png" else None)
print(f"Saved {run / 'fpga_result_figure.png'}")
