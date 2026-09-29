"""
Tezin 5. bölümü için ek (keşifsel) analizler.
Girdi: participant_records.csv (participant_medians.py üretir)
Kullanım: python3 extended_analysis.py
"""
import warnings
import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy import stats

warnings.filterwarnings("ignore")
df = pd.read_csv("participant_records.csv")
df["pid"] = df["participant_id"].astype(int)
df["rev"] = (df["condition"] == "reviewed").astype(int)
df["changed"] = np.minimum(df["total_lines_changed"], df["original_line_count"])
df["unchanged"] = df["original_line_count"] - df["changed"]
df["touched"] = (df["total_lines_changed"] > 0).astype(int)
df["deleted"] = df["block_deleted"].astype(str).eq("True").astype(int)
df["t"] = df["total_active_modification_time_s"]
R, I = df[df.rev == 1], df[df.rev == 0]


def gee_binom(formula, data, counts=True):
    fam = sm.families.Binomial()
    m = smf.gee(formula, "pid", data, family=fam, cov_struct=sm.cov_struct.Exchangeable()).fit()
    return m


def orci(m, term):
    c, (lo, hi), p = m.params[term], m.conf_int().loc[term], m.pvalues[term]
    return f"coef={c:.3f} OR={np.exp(c):.2f} [{np.exp(lo):.2f},{np.exp(hi):.2f}] p={p:.4f}"


def h(t): print(f"\n=== {t} ===")


h("0. Reproduce")
m = gee_binom("changed + unchanged ~ rev", df.assign(**{"changed + unchanged": 0}) if False else df) if False else None
m = smf.gee("np.column_stack([changed, unchanged]) ~ rev", "pid", df, family=sm.families.Binomial(),
            cov_struct=sm.cov_struct.Exchangeable()).fit()
print("RQ1 GEE", orci(m, "rev"))
m2 = gee_binom("touched ~ rev", df); print("touched GEE", orci(m2, "rev"))
print("touched %", R.touched.mean(), I.touched.mean(), "zero time %", (R.t == 0).mean(), (I.t == 0).mean())

h("1. Conditional on touched (hurdle part 2)")
Rt, It = R[R.touched == 1], I[I.touched == 1]
print("n", len(Rt), len(It))
for col in ["proportion_lines_changed", "t"]:
    print(col, "mean", Rt[col].mean(), It[col].mean(), "median", Rt[col].median(), It[col].median())
dt = df[df.touched == 1]
m = smf.gee("np.column_stack([changed, unchanged]) ~ rev", "pid", dt, family=sm.families.Binomial(),
            cov_struct=sm.cov_struct.Exchangeable()).fit()
print("cond prop GEE", orci(m, "rev"))
dt = dt.assign(logt=np.log1p(dt.t))
m = smf.gee("logt ~ rev", "pid", dt, family=sm.families.Gaussian(), cov_struct=sm.cov_struct.Exchangeable()).fit()
print("cond log1p time GEE coef", m.params["rev"], m.conf_int().loc["rev"].values, m.pvalues["rev"], "ratio", np.exp(m.params["rev"]))

h("2. Time to first modification")
for name, d in [("R", Rt), ("I", It)]:
    x = d.time_to_first_modification_s.dropna()
    print(name, len(x), "median", x.median(), "q1,q3", x.quantile(.25), x.quantile(.75),
          "<60s", (x < 60).mean(), "<1h", (x < 3600).mean(), "<24h", (x < 86400).mean(), ">24h n", (x >= 86400).sum())
print("MWU", stats.mannwhitneyu(Rt.time_to_first_modification_s.dropna(), It.time_to_first_modification_s.dropna()))
dd = df[df.touched == 1].dropna(subset=["time_to_first_modification_s"]).copy()
dd["lttf"] = np.log1p(dd.time_to_first_modification_s)
m = smf.gee("lttf ~ rev", "pid", dd, family=sm.families.Gaussian(), cov_struct=sm.cov_struct.Exchangeable()).fit()
print("ttf GEE", m.params["rev"], m.conf_int().loc["rev"].values, m.pvalues["rev"], "ratio", np.exp(m.params["rev"]))

h("3. Block deletion")
print("deleted", R.deleted.sum(), len(R), I.deleted.sum(), len(I))
try:
    m = gee_binom("deleted ~ rev", df); print("del GEE", orci(m, "rev"))
except Exception as e: print(e)
print("fisher", stats.fisher_exact([[R.deleted.sum(), len(R) - R.deleted.sum()], [I.deleted.sum(), len(I) - I.deleted.sum()]]))
print("deleted by pid", df[df.deleted == 1].groupby(["pid", "condition"]).size().to_dict())

h("4. Review duration (reviewed only)")
rd = R.review_duration_s
print("review dur", rd.describe().to_dict())
print("spearman vs prop", stats.spearmanr(rd, R.proportion_lines_changed), "vs time", stats.spearmanr(rd, R.t),
      "vs touched", stats.spearmanr(rd, R.touched))
Rr = R.copy(); Rr["long"] = (Rr.review_duration_s >= Rr.review_duration_s.median()).astype(int)
print(Rr.groupby("long")[["proportion_lines_changed", "t", "touched", "review_duration_s"]].agg(["mean", "median", "count"]))
# within-person: center duration by participant
Rr["rd_c"] = Rr.review_duration_s - Rr.groupby("pid").review_duration_s.transform("mean")
Rr["rd_z"] = Rr.rd_c / Rr.review_duration_s.std()
m = smf.gee("np.column_stack([changed, unchanged]) ~ rd_z", "pid", Rr, family=sm.families.Binomial(),
            cov_struct=sm.cov_struct.Exchangeable()).fit()
print("prop ~ review dur (within, per SD)", orci(m, "rd_z"), "SD=", Rr.review_duration_s.std())
m = gee_binom("touched ~ rd_z", Rr); print("touched ~ review dur", orci(m, "rd_z"))
print("time to accept imm", I.time_to_accept_s.describe().to_dict())

h("5. Confidence")
for name, d in [("R", R), ("I", I)]:
    c = d.self_reported_confidence.dropna()
    print(name, len(c), "mean", c.mean(), "median", c.median(), c.value_counts().sort_index().to_dict())
pc = df.groupby(["pid", "condition"]).self_reported_confidence.mean().unstack()
print(pc.round(2))
pc2 = pc.dropna()
print("wilcoxon conf", stats.wilcoxon(pc2.reviewed, pc2.immediate))
for name, d in [("R", R), ("I", I), ("all", df)]:
    print(name, "spearman conf-prop", stats.spearmanr(d.self_reported_confidence, d.proportion_lines_changed, nan_policy="omit"),
          "conf-touched", stats.spearmanr(d.self_reported_confidence, d.touched, nan_policy="omit"))
df["conf_c"] = df.self_reported_confidence - df.groupby("pid").self_reported_confidence.transform("mean")
m = smf.gee("np.column_stack([changed, unchanged]) ~ rev + conf_c", "pid", df.dropna(subset=["conf_c"]),
            family=sm.families.Binomial(), cov_struct=sm.cov_struct.Exchangeable()).fit()
print("prop ~ rev + conf_c", orci(m, "rev"), "|", orci(m, "conf_c"))
print(df.groupby(["self_reported_confidence", "condition"]).agg(n=("touched", "size"), touched=("touched", "mean"), prop=("proportion_lines_changed", "mean")).round(3))

h("6. Block size")
for name, d in [("R", R), ("I", I)]:
    print(name, d.original_line_count.describe().round(1).to_dict())
print("MWU size", stats.mannwhitneyu(R.original_line_count, I.original_line_count))
df["lsize"] = np.log2(df.original_line_count)
df["lsize_c"] = df.lsize - df.lsize.mean()
m = smf.gee("np.column_stack([changed, unchanged]) ~ rev + lsize_c", "pid", df, family=sm.families.Binomial(),
            cov_struct=sm.cov_struct.Exchangeable()).fit()
print("adj size", orci(m, "rev"), "|", orci(m, "lsize_c"))
m = smf.gee("np.column_stack([changed, unchanged]) ~ rev * lsize_c", "pid", df, family=sm.families.Binomial(),
            cov_struct=sm.cov_struct.Exchangeable()).fit()
print("interaction", orci(m, "rev:lsize_c"))
m = gee_binom("touched ~ rev + lsize_c", df); print("touched adj size", orci(m, "rev"), "|", orci(m, "lsize_c"))
df["sizebin"] = pd.cut(df.original_line_count, [0, 20, 40, 10000], labels=["<=20", "21-40", ">40"])
print(df.groupby(["sizebin", "condition"]).agg(n=("touched", "size"), touched=("touched", "mean"), prop=("proportion_lines_changed", "mean")).round(3))

h("7. Participant review propensity")
pp = df.groupby("pid").agg(n=("rev", "size"), rev_rate=("rev", "mean"))
med = pd.read_csv("participant_medians.csv").set_index("participant_id")
pp["d_prop"] = med.median_prop_changed_reviewed - med.median_prop_changed_immediate
pp["d_time"] = med.median_mod_time_s_reviewed - med.median_mod_time_s_immediate
tp = df.groupby(["pid", "condition"]).touched.mean().unstack()
pp["d_touched"] = tp.reviewed - tp.immediate
print(pp.round(3))
print("rev rate range", pp.rev_rate.min(), pp.rev_rate.max(), "median", pp.rev_rate.median())
print("spearman rev_rate vs d_prop", stats.spearmanr(pp.rev_rate, pp.d_prop), "vs d_touched", stats.spearmanr(pp.rev_rate, pp.d_touched))
print("participants with touched R<I", (pp.d_touched < 0).sum(), ">", (pp.d_touched > 0).sum())
print("wilcoxon touched", stats.wilcoxon(tp.reviewed, tp.immediate))

h("8. Temporal")
df["ts"] = pd.to_datetime(df.insertion_timestamp, unit="ms")
print("range", df.ts.min(), df.ts.max())
df["rank"] = df.groupby("pid").insertion_timestamp.rank(pct=True)
df["half"] = np.where(df["rank"] <= 0.5, "first", "second")
print(df.groupby("half").agg(n=("rev", "size"), rev_rate=("rev", "mean")).round(3))
print(df.groupby(["half", "condition"]).agg(n=("touched", "size"), touched=("touched", "mean"), prop=("proportion_lines_changed", "mean"), t=("t", "mean")).round(3))
df["rank_c"] = df["rank"] - 0.5
m = gee_binom("rev ~ rank_c", df); print("review rate over time", orci(m, "rank_c"))
m = smf.gee("np.column_stack([changed, unchanged]) ~ rev * rank_c", "pid", df, family=sm.families.Binomial(),
            cov_struct=sm.cov_struct.Exchangeable()).fit()
print("rev", orci(m, "rev"), "| time", orci(m, "rank_c"), "| int", orci(m, "rev:rank_c"))
cs = df.groupby("pid").self_reported_confidence.apply(lambda s: s.nunique())
print("distinct conf values per pid", cs.to_dict())
fl = df.sort_values("insertion_timestamp").groupby("pid").apply(lambda g: (g.self_reported_confidence.iloc[len(g)//2:].nunique(), g.self_reported_confidence.iloc[:len(g)//2].nunique()))
print("conf unique first/second half", fl.to_dict())

h("9. Sensitivity: leave-one-participant-out")
res = []
for p in sorted(df.pid.unique()):
    d = df[df.pid != p]
    m = smf.gee("np.column_stack([changed, unchanged]) ~ rev", "pid", d, family=sm.families.Binomial(),
                cov_struct=sm.cov_struct.Exchangeable()).fit()
    m2 = gee_binom("touched ~ rev", d)
    res.append((p, np.exp(m.params.rev), m.pvalues.rev, np.exp(m2.params.rev), m2.pvalues.rev))
r = pd.DataFrame(res, columns=["out", "OR", "p", "OR_t", "p_t"]); print(r.round(3))
print("OR range", r.OR.min(), r.OR.max(), "max p", r.p.max(), "| touched OR range", r.OR_t.min(), r.OR_t.max(), "max p", r.p_t.max())
# independence working corr
m = smf.gee("np.column_stack([changed, unchanged]) ~ rev", "pid", df, family=sm.families.Binomial(),
            cov_struct=sm.cov_struct.Independence()).fit()
print("indep corr", orci(m, "rev"))
# excluding deleted blocks
d = df[df.deleted == 0]
m = smf.gee("np.column_stack([changed, unchanged]) ~ rev", "pid", d, family=sm.families.Binomial(),
            cov_struct=sm.cov_struct.Exchangeable()).fit()
print("excl deleted", orci(m, "rev"), "n", len(d))
# excluding participants with <5 reviewed
few = df.groupby("pid").rev.sum(); keep = few[few >= 5].index
d = df[df.pid.isin(keep)]
m = smf.gee("np.column_stack([changed, unchanged]) ~ rev", "pid", d, family=sm.families.Binomial(),
            cov_struct=sm.cov_struct.Exchangeable()).fit()
print("only pids with >=5 reviewed", list(keep), orci(m, "rev"), "n", len(d))
# RQ2 with means instead of medians
pm = df.groupby(["pid", "condition"]).t.mean().unstack()
print("wilcoxon means time", stats.wilcoxon(pm.reviewed, pm.immediate), (pm.reviewed < pm.immediate).sum())
pm2 = df.groupby(["pid", "condition"]).proportion_lines_changed.mean().unstack()
print("wilcoxon means prop", stats.wilcoxon(pm2.reviewed, pm2.immediate), (pm2.reviewed < pm2.immediate).sum())
# RQ2 trial level GEE on log1p time
df["logt"] = np.log1p(df.t)
m = smf.gee("logt ~ rev", "pid", df, family=sm.families.Gaussian(), cov_struct=sm.cov_struct.Exchangeable()).fit()
print("log1p time GEE", m.params.rev, m.conf_int().loc["rev"].values, m.pvalues.rev, "ratio", np.exp(m.params.rev))
m = smf.gee("t ~ rev", "pid", df, family=sm.families.Tweedie(var_power=1.5), cov_struct=sm.cov_struct.Exchangeable()).fit()
print("tweedie time GEE", m.params.rev, m.conf_int().loc["rev"].values, m.pvalues.rev, "ratio", np.exp(m.params.rev))
