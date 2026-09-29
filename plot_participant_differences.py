"""
Figure 5: katılımcı bazında Reviewed vs. Immediate medyanları.
Her katılımcı ayrı bir satır (dumbbell): 11 kişinin hepsi ayrı görünür.
Girdi: participant_medians.csv (participant_medians.py üretir)

Kullanım:  python3 plot_participant_differences.py [çıktı.pdf]
"""
import csv
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

GREEN, RED, GRAY, INK = "#2e7d4f", "#b8434e", "#8a8a8a", "#333333"
OUT = sys.argv[1] if len(sys.argv) > 1 else "participant_differences.pdf"

rows = sorted(csv.DictReader(open("participant_medians.csv")), key=lambda r: int(r["participant_id"]))
n = len(rows)


def panel(ax, key_imm, key_rev, scale, xlabel, title, unit):
    for y, r in enumerate(rows):
        imm, rev = float(r[key_imm]) * scale, float(r[key_rev]) * scale
        color = GREEN if rev < imm else RED if rev > imm else GRAY
        ax.plot([imm, rev], [y, y], color=color, lw=2.2, zorder=2, solid_capstyle="round")
        ax.plot(imm, y, "o", ms=7, mfc="white", mec=INK, mew=1.3, zorder=3, clip_on=False)
        ax.plot(rev, y, "o", ms=7, mfc=color, mec="white", mew=1, zorder=4, clip_on=False)

    # * = Reviewed medyanı 0; açıklama Figure 5 alt yazısında
    ax.set_yticks(range(n), [f"P{r['participant_id']}" + ("*" if float(r[key_rev]) == 0 else "")
                             for r in rows])
    ax.set_ylim(n - 0.5, -0.5)
    ax.set_xlim(left=0)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:.0f}{unit}"))
    ax.set_xlabel(xlabel)
    ax.set_title(title, fontsize=10)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="x", color="#eeeeee", lw=0.6, zorder=0)


fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 4.8))
panel(a1, "median_prop_changed_immediate", "median_prop_changed_reviewed", 100,
      "Median proportion of lines changed", "Proportion of lines changed", "%")
panel(a2, "median_mod_time_s_immediate", "median_mod_time_s_reviewed", 1,
      "Median active modification time (s)", "Active modification time", "")

fig.suptitle(f"Individual participant differences (n={n}): Reviewed vs. Immediate", fontsize=11)
fig.legend(handles=[
    Line2D([], [], ls="", marker="o", mfc="white", mec=INK, mew=1.3, label="Immediate"),
    Line2D([], [], ls="", marker="o", mfc=INK, mec="white", label="Reviewed (color = direction)"),
    Line2D([], [], color=GREEN, lw=2.2, label="Reviewed < Immediate (expected)"),
    Line2D([], [], color=RED, lw=2.2, label="Reviewed > Immediate (reversed)"),
    Line2D([], [], color=GRAY, marker="o", lw=2.2, label="No difference"),
], loc="lower center", ncol=5, frameon=False, fontsize=8)
fig.tight_layout(rect=(0, 0.06, 1, 1))
fig.savefig(OUT)
fig.savefig(OUT.rsplit(".", 1)[0] + ".png", dpi=130)
print("saved", OUT)
