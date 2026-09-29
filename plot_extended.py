"""
Figure 6: (a) haftalık inceleme oranı, (b) katılımcı bazında 'kabulden sonra hiç değiştirildi mi' oranı.
Girdi: participant_records.csv
Kullanım: python3 plot_extended.py [çıktı.pdf]
"""
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.lines import Line2D

GREEN, RED, GRAY, INK, BAR = "#2e7d4f", "#b8434e", "#8a8a8a", "#333333", "#4a6fa5"
OUT = sys.argv[1] if len(sys.argv) > 1 else "extended_figure.pdf"

df = pd.read_csv("participant_records.csv")
df["rev"] = (df.condition == "reviewed").astype(int)
df["touched"] = (df.total_lines_changed > 0).astype(int)
df["week"] = ((df.insertion_timestamp - df.insertion_timestamp.min()) // (7 * 86400e3)).astype(int) + 1

fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 4.6), gridspec_kw={"width_ratios": [1, 1.25]})

wk = df.groupby("week").agg(n=("rev", "size"), rate=("rev", "mean"))
a1.bar(wk.index, wk.rate * 100, width=0.6, color=BAR, zorder=2)
for w, r in wk.iterrows():
    a1.text(w, r.rate * 100 + 2, f"{r.rate * 100:.0f}%", ha="center", fontsize=9, color=INK)
a1.set_xticks(wk.index, [f"Week {w}\n(n={int(r.n)})" for w, r in wk.iterrows()])
a1.tick_params(axis="x", length=0)
a1.set_ylim(0, 100)
a1.set_ylabel("Share of accepted blocks reviewed (%)")
a1.set_title("(a) Review rate over the study period", fontsize=10)

tp = df.groupby(["participant_id", "condition"]).touched.mean().unstack() * 100
tp = tp.sort_index()
n = len(tp)
for y, (pid, r) in enumerate(tp.iterrows()):
    imm, rev = r.immediate, r.reviewed
    color = GREEN if rev < imm else RED if rev > imm else GRAY
    a2.plot([imm, rev], [y, y], color=color, lw=2.2, zorder=2, solid_capstyle="round")
    a2.plot(imm, y, "o", ms=7, mfc="white", mec=INK, mew=1.3, zorder=3, clip_on=False)
    a2.plot(rev, y, "o", ms=7, mfc=color, mec="white", mew=1, zorder=4, clip_on=False)
a2.set_yticks(range(n), [f"P{p}" for p in tp.index])
a2.set_ylim(n - 0.5, -0.5)
a2.set_xlim(0, 100)
a2.set_xlabel("Blocks modified at all after acceptance (%)")
a2.set_title("(b) Modified at all, per participant", fontsize=10)
a2.tick_params(axis="y", length=0)
a2.spines["left"].set_visible(False)

for ax in (a1, a2):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
a1.grid(axis="y", color="#eeeeee", lw=0.6, zorder=0)
a2.grid(axis="x", color="#eeeeee", lw=0.6, zorder=0)

fig.legend(handles=[
    Line2D([], [], ls="", marker="o", mfc="white", mec=INK, mew=1.3, label="Immediate"),
    Line2D([], [], ls="", marker="o", mfc=INK, mec="white", label="Reviewed (color = direction)"),
    Line2D([], [], color=GREEN, lw=2.2, label="Reviewed < Immediate"),
    Line2D([], [], color=RED, lw=2.2, label="Reviewed > Immediate"),
], loc="lower right", bbox_to_anchor=(0.99, 0), ncol=4, frameon=False, fontsize=8)
fig.tight_layout(rect=(0, 0.06, 1, 1))
fig.savefig(OUT)
fig.savefig(OUT.rsplit(".", 1)[0] + ".png", dpi=130)
print("saved", OUT)
