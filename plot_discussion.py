"""
Discussion bölümü grafikleri (Figure 7, Figure 8).
Girdi: participant_records.csv
Kullanım: python3 plot_discussion.py <çıktı klasörü>
"""
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REV, IMM, INK = "#2e7d4f", "#8a8a8a", "#333333"
OUT = sys.argv[1] if len(sys.argv) > 1 else "."

df = pd.read_csv("participant_records.csv")
df["touched"] = (df.total_lines_changed > 0).astype(int)
R, I = df[df.condition == "reviewed"], df[df.condition == "immediate"]


def clean(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


# Figure 7: dağılım (sıfır yığılması + değiştirilenlerin dağılımı)
fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 4), gridspec_kw={"width_ratios": [1, 1.6]})
labels = ["Reviewed", "Immediate"]
zero = [100 * (1 - R.touched.mean()), 100 * (1 - I.touched.mean())]
some = [100 - z for z in zero]
y = [1, 0]
a1.barh(y, zero, color="#d9d9d9", height=0.55, label="Not modified after acceptance")
a1.barh(y, some, left=zero, color=[REV, IMM], height=0.55, label="Modified")
for yi, z, n in zip(y, zero, [len(R), len(I)]):
    a1.text(z / 2, yi, f"{z:.0f}%", ha="center", va="center", fontsize=9, color=INK)
    a1.text(z + (100 - z) / 2, yi, f"{100 - z:.0f}%", ha="center", va="center", fontsize=9, color="white")
a1.set_yticks(y, [f"{l}\n(n={n})" for l, n in zip(labels, [len(R), len(I)])])
a1.set_xlim(0, 100)
a1.set_xlabel("Share of accepted blocks (%)")
a1.set_title("(a) Was the block modified at all?", fontsize=10)
a1.tick_params(axis="y", length=0)
clean(a1)

bins = np.linspace(0, 1, 11)
for d, c, l in [(R, REV, "Reviewed"), (I, IMM, "Immediate")]:
    x = d[d.touched == 1].proportion_lines_changed.clip(upper=1)
    w = np.ones(len(x)) * 100 / len(x)
    a2.hist(x, bins=bins, weights=w, histtype="step", lw=2, color=c, label=f"{l} (n={len(x)}, median {x.median() * 100:.0f}%)")
a2.set_xlabel("Proportion of lines changed (modified blocks only)")
a2.set_ylabel("Share of modified blocks (%)")
a2.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v * 100:.0f}%"))
a2.set_title("(b) If modified: how much?", fontsize=10)
a2.legend(frameon=False, fontsize=8)
clean(a2)
fig.tight_layout()
fig.savefig(f"{OUT}/rework_decomposition.pdf")
fig.savefig(f"{OUT}/rework_decomposition.png", dpi=130)

# Figure 8: güven puanına göre 'hiç değiştirildi mi'
fig, ax = plt.subplots(figsize=(7.5, 3.8))
g = df.dropna(subset=["self_reported_confidence"]).groupby(["self_reported_confidence", "condition"]).touched.agg(["mean", "size", "sum"]).reset_index()
levels = sorted(g.self_reported_confidence.unique())
x = np.arange(len(levels))
for off, cond, c in [(-0.2, "reviewed", REV), (0.2, "immediate", IMM)]:
    s = g[g.condition == cond].set_index("self_reported_confidence").reindex(levels)
    ax.bar(x + off, s["mean"] * 100, width=0.38, color=c, label=cond.capitalize(), zorder=2)
    for xi, (m, n, k) in zip(x + off, s[["mean", "size", "sum"]].values):
        ax.text(xi, m * 100 + 2, f"{m * 100:.0f}%\n({int(k)}/{int(n)})", ha="center", fontsize=7.5, color=INK)
ax.set_xticks(x, [f"{int(l)}" for l in levels])
ax.set_xlabel("Self-reported confidence in the acceptance decision (1 = low, 5 = high)")
ax.set_ylabel("Blocks modified after acceptance (%)")
ax.set_ylim(0, 105)
ax.grid(axis="y", color="#eeeeee", lw=0.6, zorder=0)
ax.legend(frameon=False, fontsize=8, loc="upper right", ncol=2)
clean(ax)
fig.tight_layout()
fig.savefig(f"{OUT}/confidence_rework.pdf")
fig.savefig(f"{OUT}/confidence_rework.png", dpi=130)
print("saved")

# Figure: ilk düzenlemeye kadar geçen sürenin kümülatif dağılımı
fig, ax = plt.subplots(figsize=(7.5, 3.6))
for d, c, l in [(R, REV, "Reviewed"), (I, IMM, "Immediate")]:
    x = np.sort(d[d.touched == 1].time_to_first_modification_s.dropna().values)
    y = np.arange(1, len(x) + 1) / len(x) * 100
    ax.step(np.maximum(x, 1), y, where="post", color=c, lw=2, label=f"{l} (n={len(x)})")
for s, name in [(60, "1 min"), (3600, "1 h"), (86400, "1 day"), (604800, "7 days")]:
    ax.axvline(s, color="#cccccc", lw=0.8, ls="--", zorder=0)
    ax.text(s * 1.1, 3, name, fontsize=8, color="#666666")
ax.set_xscale("log")
ax.set_xlim(1, 604800 * 1.2)
ax.set_ylim(0, 100)
ax.set_xlabel("Time from acceptance to first modification (s, log scale)")
ax.set_ylabel("Cumulative share of modified blocks (%)")
ax.legend(frameon=False, fontsize=8, loc="upper left")
clean(ax)
fig.tight_layout()
fig.savefig(f"{OUT}/time_to_first_mod.pdf")
fig.savefig(f"{OUT}/time_to_first_mod.png", dpi=130)
print("saved ttf")
