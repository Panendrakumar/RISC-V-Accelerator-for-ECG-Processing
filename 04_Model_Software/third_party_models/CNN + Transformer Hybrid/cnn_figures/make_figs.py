from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

HERE = Path(__file__).resolve().parent
df = pd.read_csv(HERE / "CNN_training_history.csv")
CAP = 0.9675
if df[["train_accuracy", "validation_accuracy"]].max().max() > CAP + 1e-12:
    raise ValueError("Accuracy exceeds the documented 96.75% cap.")

INK, MUTE, GRID = "#16324f", "#5b6b7b", "#d9e2ec"
TEAL, PURPLE, ORANGE = "#00796b", "#6b4c7a", "#d95f02"
ep = df["epoch"].to_numpy()

def smooth(y, w=9):
    return pd.Series(y).rolling(w, center=True, min_periods=1).mean().to_numpy()

specs = [
    ("01_training_loss", "train_loss", "Training loss", "Categorical cross-entropy", TEAL, False),
    ("02_validation_loss", "validation_loss", "Validation loss", "Categorical cross-entropy", PURPLE, False),
    ("03_training_accuracy", "train_accuracy", "Training accuracy", "Accuracy", TEAL, True),
    ("04_validation_accuracy", "validation_accuracy", "Validation accuracy", "Accuracy", PURPLE, True),
]

def style(ax, title, ylabel, pct):
    ax.set_title(title, loc="left", fontsize=15, fontweight="bold", color=INK)
    ax.set_xlabel("Epoch", color=MUTE)
    ax.set_ylabel(ylabel, color=MUTE)
    ax.set_xlim(1, int(ep.max()))
    ax.set_xticks([1, 21, 41, 61, 81])
    ax.grid(axis="y", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    for s in ["left", "bottom"]:
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=MUTE)
    if pct:
        ax.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
        ax.set_ylim(0.88, 0.975)
        ax.set_yticks([0.88, 0.90, 0.92, 0.94, 0.96, 0.975])

def draw(ax, col, title, ylabel, color, pct):
    y = df[col].to_numpy()
    if pct:
        ax.plot(ep, y, color=color, lw=1, alpha=0.35, label="Per-epoch value")
        ax.plot(ep, smooth(y), color=color, lw=2.4, label="Smoothed (9-epoch moving avg)")
        ax.legend(frameon=False, loc="lower right", fontsize=9)
    else:
        ax.plot(ep, y, color=color, lw=2.4)
        ax.set_ylim(0, y.max() * 1.05)
        if col == "validation_loss":
            i = int(y.argmin())
            ax.scatter(ep[i], y[i], color=ORANGE, zorder=5)
            ax.annotate(f"min {y[i]:.4f} @ epoch {int(ep[i])}",
                        (ep[i], y[i]), (ep[i] - 45, y[i] + 0.03),
                        arrowprops=dict(arrowstyle="->", color=MUTE), fontsize=9)
    style(ax, title, ylabel, pct)

for name, col, title, ylabel, color, pct in specs:
    fig, ax = plt.subplots(figsize=(7, 4.5))
    draw(ax, col, title, ylabel, color, pct)
    fig.tight_layout()
    fig.savefig(HERE / f"{name}.png", dpi=300)
    fig.savefig(HERE / f"{name}.pdf")
    plt.close(fig)

fig, axes = plt.subplots(2, 2, figsize=(13, 8.5))
fig.suptitle("CNN-Transformer training history", x=0.03, ha="left",
             fontsize=20, fontweight="bold", color=INK)
best_epoch = int(df.loc[df.validation_loss.idxmin(), "epoch"])
fig.text(0.03, 0.925,
         f"Saved run | {len(df)} epochs | min validation loss {df.validation_loss.min():.4f} at epoch {best_epoch}",
         color=MUTE, fontsize=11)
for ax, spec in zip(axes.ravel(), specs):
    draw(ax, spec[1], spec[2], spec[3], spec[4], spec[5])
fig.tight_layout(rect=[0, 0, 1, 0.91])
fig.savefig(HERE / "00_training_history_overview.png", dpi=300)
fig.savefig(HERE / "00_training_history_overview.pdf")
plt.close(fig)
