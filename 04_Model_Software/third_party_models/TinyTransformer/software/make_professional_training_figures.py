"""Export high-resolution, presentation-ready plots from the saved run."""

from __future__ import annotations

import csv
import json
import zipfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import to_rgb
from matplotlib.ticker import PercentFormatter
import numpy as np
import seaborn as sns
from sklearn.metrics import classification_report, confusion_matrix


RUN_DIR = Path(__file__).resolve().parent / "training_attempt_20261024"
FIG_DIR = RUN_DIR / "figures"
RESULTS_PATH = RUN_DIR / "baseline_results.json"
HISTORY_PATH = RUN_DIR / "training_history.json"
CLASS_NAMES = ["N", "S", "V", "F", "Q"]
CLASS_DESCRIPTIONS = {
    "N": "Normal",
    "S": "Supraventricular ectopic",
    "V": "Ventricular ectopic",
    "F": "Fusion",
    "Q": "Unknown / paced",
}

NAVY = "#17324D"
TEAL = "#007C78"
PURPLE = "#6F4E7C"
AMBER = "#E69F00"
CORAL = "#D55E00"
SLATE = "#586776"
GRID = "#D9E1E8"


def save_figure(fig: plt.Figure, name: str) -> None:
    fig.savefig(FIG_DIR / f"{name}.png", dpi=300, bbox_inches="tight", facecolor="white")
    fig.savefig(FIG_DIR / f"{name}.pdf", bbox_inches="tight", facecolor="white")
    plt.close(fig)


def readable_text_color(rgba: tuple[float, ...]) -> str:
    red, green, blue = to_rgb(rgba[:3])
    luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue
    return "#111827" if luminance > 0.58 else "#FFFFFF"


def add_line_chart(
    epochs: np.ndarray,
    values: np.ndarray,
    *,
    title: str,
    ylabel: str,
    color: str,
    name: str,
    is_accuracy: bool = False,
    is_validation_accuracy: bool = False,
) -> None:
    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.plot(
        epochs,
        values,
        color=color,
        linewidth=2.6,
        marker="o",
        markersize=3.2,
        markevery=8,
        label=title,
        zorder=3,
    )
    if is_accuracy:
        ax.yaxis.set_major_formatter(PercentFormatter(xmax=1.0, decimals=0))
        lower = 0.90 if not is_validation_accuracy else 0.94
        ax.set_ylim(lower, 1.005)
    else:
        ax.set_ylim(bottom=0)
    if is_validation_accuracy:
        ax.axhline(
            0.98,
            color=AMBER,
            linewidth=2.0,
            linestyle=(0, (5, 3)),
            label="98% target",
            zorder=2,
        )
        best_epoch = int(np.argmax(values))
        best_value = float(values[best_epoch])
        ax.scatter([epochs[best_epoch]], [best_value], s=76, color=CORAL, edgecolor="white", linewidth=1.2, zorder=5)
        ax.annotate(
            f"Best: {best_value:.2%}\nEpoch {int(epochs[best_epoch])}",
            xy=(epochs[best_epoch], best_value),
            xytext=(-78, -48),
            textcoords="offset points",
            fontsize=10,
            color=NAVY,
            arrowprops={"arrowstyle": "->", "color": SLATE, "lw": 1.1},
            bbox={"boxstyle": "round,pad=0.35", "facecolor": "white", "edgecolor": GRID, "alpha": 0.98},
        )
    ax.set_title(title, loc="left", color=NAVY, pad=15, fontweight="bold")
    ax.set_xlabel("Epoch", color=SLATE, labelpad=8)
    ax.set_ylabel(ylabel, color=SLATE, labelpad=8)
    ax.set_xlim(1, int(epochs[-1]))
    ax.set_xticks(np.arange(1, int(epochs[-1]) + 1, 10))
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.grid(axis="x", visible=False)
    ax.tick_params(colors=SLATE)
    ax.legend(frameon=False, loc="best")
    fig.text(
        0.01,
        0.01,
        "Tiny ECG Transformer baseline | 6,643 parameters | 100 epochs completed",
        color=SLATE,
        fontsize=9,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    save_figure(fig, name)


def main() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "axes.titlesize": 16,
        "axes.labelsize": 11,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "legend.fontsize": 10,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.edgecolor": GRID,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.facecolor": "white",
    })

    results = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    history = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    epochs = np.asarray(history["epochs"], dtype=int)
    metric_values = {key: np.asarray(history[key], dtype=float) for key in ["loss", "val_loss", "accuracy", "val_accuracy"]}
    if any(len(values) != len(epochs) for values in metric_values.values()):
        raise ValueError("Saved training curves have inconsistent epoch counts")

    y_true = np.asarray(results["true_labels"], dtype=int)
    y_pred = np.asarray(results["predictions"], dtype=int)
    cm = confusion_matrix(y_true, y_pred, labels=list(range(len(CLASS_NAMES))))
    support = cm.sum(axis=1)
    total = int(cm.sum())
    correct = int(np.trace(cm))
    accuracy = correct / total
    if total != 20136 or correct != 19861:
        raise ValueError(f"Unexpected saved test counts: {correct}/{total}")
    if abs(accuracy - float(results["test_accuracy"])) > 1e-12:
        raise ValueError("Confusion-matrix accuracy does not match the saved result")
    if support.tolist() != [18015, 556, 1401, 161, 3]:
        raise ValueError(f"Unexpected test class supports: {support.tolist()}")

    report = classification_report(
        y_true,
        y_pred,
        labels=list(range(len(CLASS_NAMES))),
        target_names=CLASS_NAMES,
        output_dict=True,
        zero_division=0,
    )
    saved_report = results.get("classification_report_by_class", {})
    for class_name in CLASS_NAMES:
        if class_name not in saved_report:
            raise ValueError(f"Saved result is missing class metrics for {class_name}")
        for metric in ("precision", "recall", "f1-score"):
            if abs(float(report[class_name][metric]) - float(saved_report[class_name][metric])) > 1e-12:
                raise ValueError(f"Metric mismatch for {class_name} {metric}")

    # Four separate, high-resolution training and validation figures.
    add_line_chart(epochs, metric_values["loss"], title="Training loss", ylabel="Categorical cross-entropy", color=TEAL, name="01_training_loss")
    add_line_chart(epochs, metric_values["val_loss"], title="Validation loss", ylabel="Categorical cross-entropy", color=PURPLE, name="02_validation_loss")
    add_line_chart(epochs, metric_values["accuracy"], title="Training accuracy", ylabel="Accuracy", color=TEAL, name="03_training_accuracy", is_accuracy=True)
    add_line_chart(epochs, metric_values["val_accuracy"], title="Validation accuracy", ylabel="Accuracy", color=PURPLE, name="04_validation_accuracy", is_accuracy=True, is_validation_accuracy=True)

    # Combined overview for slide use.
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    overview = [
        (axes[0, 0], "loss", "Training loss", TEAL, False),
        (axes[0, 1], "val_loss", "Validation loss", PURPLE, False),
        (axes[1, 0], "accuracy", "Training accuracy", TEAL, True),
        (axes[1, 1], "val_accuracy", "Validation accuracy", PURPLE, True),
    ]
    for ax, key, title, color, is_accuracy in overview:
        ax.plot(epochs, metric_values[key], color=color, lw=2.2, marker="o", ms=2.6, markevery=10)
        ax.set_title(title, loc="left", color=NAVY, fontweight="bold")
        ax.set_xlabel("Epoch", color=SLATE)
        ax.set_xlim(1, int(epochs[-1]))
        ax.set_xticks(np.arange(1, int(epochs[-1]) + 1, 20))
        ax.grid(axis="y", color=GRID, linewidth=0.8)
        ax.tick_params(colors=SLATE)
        if is_accuracy:
            ax.set_ylabel("Accuracy", color=SLATE)
            ax.yaxis.set_major_formatter(PercentFormatter(xmax=1.0, decimals=0))
            ax.set_ylim(0.90 if key == "accuracy" else 0.94, 1.005)
        else:
            ax.set_ylabel("Categorical cross-entropy", color=SLATE)
            ax.set_ylim(bottom=0)
        if key == "val_accuracy":
            ax.axhline(0.98, color=AMBER, lw=1.8, linestyle=(0, (5, 3)), label="98% target")
            ax.legend(frameon=False, loc="lower right")
            best_idx = int(np.argmax(metric_values[key]))
            ax.scatter([epochs[best_idx]], [metric_values[key][best_idx]], s=60, color=CORAL, edgecolor="white", linewidth=1.0, zorder=5)
            ax.annotate(f"{metric_values[key][best_idx]:.2%} at epoch {epochs[best_idx]}", (epochs[best_idx], metric_values[key][best_idx]), xytext=(-110, -32), textcoords="offset points", fontsize=9, arrowprops={"arrowstyle": "->", "color": SLATE})
    fig.suptitle("Tiny ECG Transformer training history", x=0.07, ha="left", fontsize=20, color=NAVY, fontweight="bold")
    fig.text(0.07, 0.925, "Saved run | 6,643 parameters | best validation accuracy 98.71% at epoch 75", color=SLATE, fontsize=10)
    fig.tight_layout(rect=(0.04, 0.03, 0.98, 0.90))
    save_figure(fig, "00_training_history_overview")

    # Raw count confusion matrix. Each cell shows count and percentage of its
    # true-class row. Contrast-aware annotation colors remain legible on both
    # dark and bright parts of the viridis scale.
    cmap = plt.get_cmap("viridis")
    vmax = max(1, int(cm.max()))
    fig, ax = plt.subplots(figsize=(8.8, 7.0))
    image = ax.imshow(cm, cmap=cmap, vmin=0, vmax=vmax, aspect="equal")
    ax.set_xticks(np.arange(len(CLASS_NAMES)), labels=CLASS_NAMES)
    ax.set_yticks(np.arange(len(CLASS_NAMES)), labels=[f"{name}  (n={count:,})" for name, count in zip(CLASS_NAMES, support)])
    ax.set_xlabel("Predicted class", labelpad=10, color=SLATE)
    ax.set_ylabel("True class", labelpad=10, color=SLATE)
    ax.set_title("Test confusion matrix — beat counts", loc="left", color=NAVY, pad=18, fontweight="bold")
    ax.text(0, 1.02, f"Diagonal = correct: {correct:,}/{total:,} | Accuracy: {accuracy:.2%}", transform=ax.transAxes, color=SLATE, fontsize=10)
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            pct = 100.0 * cm[i, j] / support[i] if support[i] else 0.0
            color = readable_text_color(cmap(float(cm[i, j]) / vmax))
            ax.text(j, i, f"{cm[i, j]:,}\n{pct:.1f}%", ha="center", va="center", color=color, fontsize=11, fontweight="bold")
    ax.set_xticks(np.arange(-0.5, len(CLASS_NAMES), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(CLASS_NAMES), 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=2.0)
    ax.tick_params(which="minor", bottom=False, left=False)
    cbar = fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Number of test beats", color=SLATE)
    fig.tight_layout()
    save_figure(fig, "05_test_confusion_matrix_counts")

    # Row-normalized confusion matrix to compare recall across imbalanced
    # classes while retaining the exact count in each cell.
    row_normalized = np.divide(cm, support[:, None], out=np.zeros_like(cm, dtype=float), where=support[:, None] != 0)
    fig, ax = plt.subplots(figsize=(8.8, 7.0))
    image = ax.imshow(row_normalized, cmap="viridis", vmin=0, vmax=1, aspect="equal")
    ax.set_xticks(np.arange(len(CLASS_NAMES)), labels=CLASS_NAMES)
    ax.set_yticks(np.arange(len(CLASS_NAMES)), labels=[f"{name}  (n={count:,})" for name, count in zip(CLASS_NAMES, support)])
    ax.set_xlabel("Predicted class", labelpad=10, color=SLATE)
    ax.set_ylabel("True class", labelpad=10, color=SLATE)
    ax.set_title("Test confusion matrix — normalized by true class", loc="left", color=NAVY, pad=18, fontweight="bold")
    ax.text(0, 1.02, "Each row sums to 100%; values show row percentage and count", transform=ax.transAxes, color=SLATE, fontsize=10)
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            color = readable_text_color(cmap(float(row_normalized[i, j])))
            ax.text(j, i, f"{row_normalized[i, j]:.1%}\n({cm[i, j]:,})", ha="center", va="center", color=color, fontsize=10.5, fontweight="bold")
    ax.set_xticks(np.arange(-0.5, len(CLASS_NAMES), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(CLASS_NAMES), 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=2.0)
    ax.tick_params(which="minor", bottom=False, left=False)
    cbar = fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Share of true-class beats", color=SLATE)
    cbar.ax.yaxis.set_major_formatter(PercentFormatter(xmax=1.0, decimals=0))
    fig.tight_layout()
    save_figure(fig, "06_test_confusion_matrix_row_normalized")

    # Precision, recall and F1 chart for the five classes.
    metrics = ["precision", "recall", "f1-score"]
    metric_colors = [TEAL, AMBER, NAVY]
    x = np.arange(len(CLASS_NAMES))
    width = 0.23
    fig, ax = plt.subplots(figsize=(10, 6.2))
    for metric_idx, (metric, color) in enumerate(zip(metrics, metric_colors)):
        values = np.asarray([report[name][metric] for name in CLASS_NAMES])
        offsets = (metric_idx - 1) * width
        bars = ax.bar(x + offsets, values, width=width, color=color, label=metric.replace("-score", ""), edgecolor="white", linewidth=0.7, zorder=3)
        for bar, value in zip(bars, values):
            y = value + 0.025 if value > 0 else 0.02
            ax.text(bar.get_x() + bar.get_width() / 2, y, f"{value:.3f}", ha="center", va="bottom", color=NAVY, fontsize=8.5, rotation=90 if value < 0.15 else 0)
    ax.set_xticks(x, labels=[f"{name}\n{CLASS_DESCRIPTIONS[name]}" for name in CLASS_NAMES])
    ax.set_ylabel("Score", color=SLATE)
    ax.set_ylim(0, 1.12)
    ax.set_title("Per-class test performance", loc="left", color=NAVY, pad=16, fontweight="bold")
    ax.text(0, 1.01, "Macro-F1 = 0.724 | Q has 3 test beats and F1 = 0.000", transform=ax.transAxes, color=SLATE, fontsize=10)
    ax.grid(axis="y", color=GRID, linewidth=0.8, zorder=0)
    ax.legend(frameon=False, ncol=3, loc="upper right")
    ax.tick_params(axis="x", colors=SLATE, labelsize=9)
    fig.tight_layout()
    save_figure(fig, "07_per_class_test_metrics")

    # Export exact tabular values alongside the charts.
    with (FIG_DIR / "per_class_metrics.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["class", "description", "support", "precision", "recall", "f1"])
        for name, count in zip(CLASS_NAMES, support):
            writer.writerow([name, CLASS_DESCRIPTIONS[name], int(count), report[name]["precision"], report[name]["recall"], report[name]["f1-score"]])
    with (FIG_DIR / "overall_metrics.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["metric", "value"])
        writer.writerow(["test_accuracy", accuracy])
        writer.writerow(["test_correct", correct])
        writer.writerow(["test_total", total])
        writer.writerow(["test_errors", total - correct])
        writer.writerow(["macro_f1", results["f1_macro"]])
        writer.writerow(["weighted_f1", results["f1_weighted"]])
        writer.writerow(["best_validation_accuracy", results["best_validation_accuracy"]])
        writer.writerow(["best_validation_epoch", results["best_validation_epoch"]])

    readme = f"""# Training figures and test outputs

This folder contains exportable 300 dpi PNG files and vector PDF copies of the
training curves and test evaluation figures.

## Verified test counts

- Correct predictions on the confusion-matrix diagonal: {correct:,} of {total:,}
- Test accuracy: {accuracy:.6%}
- Macro-F1: {float(results['f1_macro']):.6f}
- True-class supports in order N, S, V, F, Q: {', '.join(f'{v:,}' for v in support)}
- Diagonal counts in order N, S, V, F, Q: {', '.join(f'{int(v):,}' for v in np.diag(cm))}

The raw-count confusion matrix labels each cell with the exact count and the
percentage of that true-class row. Correct predictions are on the main
diagonal. The normalized matrix uses each true-class support as its row total.
Colors use a dark-to-bright viridis scale with automatic white/black annotation
text for contrast.

The saved evaluation split is stratified by beat, not by patient/record. The Q
class has only three test beats and received F1 = 0.000; interpret accuracy
alongside the per-class chart and CSV.

## Files

- `00_training_history_overview` — combined training/validation overview.
- `01` to `04` — separate training loss, validation loss, training accuracy,
  and validation accuracy plots.
- `05` — raw count confusion matrix.
- `06` — row-normalized confusion matrix.
- `07` — per-class precision, recall, and F1 chart.
- `per_class_metrics.csv`, `overall_metrics.csv` — exact tabular metrics.
"""
    (FIG_DIR / "README.md").write_text(readme, encoding="utf-8")

    zip_path = RUN_DIR / "ecg_training_outputs_20261024.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(FIG_DIR.iterdir()):
            if path.is_file():
                archive.write(path, arcname=f"figures/{path.name}")
        for path in [RESULTS_PATH, HISTORY_PATH, RUN_DIR / "training_attempt_manifest.json"]:
            if path.is_file():
                archive.write(path, arcname=path.name)

    print(json.dumps({
        "figure_directory": str(FIG_DIR),
        "zip_path": str(zip_path),
        "figure_file_count": len(list(FIG_DIR.iterdir())),
        "correct_predictions_diagonal": [int(value) for value in np.diag(cm)],
        "correct_total": correct,
        "test_total": total,
        "accuracy": accuracy,
        "macro_f1": results["f1_macro"],
    }, indent=2))


if __name__ == "__main__":
    main()
