"""
Statistical analysis for "Encouraging Reflection Before Accepting AI Generated Code"
Nil Sila Ulucan — TU Darmstadt

Plan (thesis section 4.2):
  Primary  : Linear Mixed-Effects Model (LME)
  Fallback : Wilcoxon Signed-Rank Test  (if Shapiro-Wilk rejects normality)
  Effect   : Rank biserial correlation (r)
"""

import json
import ssl
import urllib.request
import urllib.parse
from collections import defaultdict

# macOS Python 3 SSL fix
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

# ── Supabase credentials ──────────────────────────────────────────────────────
SUPABASE_URL = "https://qcyxsuvbcdsxprkzlkkh.supabase.co"
SUPABASE_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFjeXhzdXZiY2RzeHBya3psa2toIiwi"
    "cm9sZSI6ImFub24iLCJpYXQiOjE3Nzk4ODg1MzUsImV4cCI6MjA5NTQ2NDUzNX0"
    ".g52agmYZgdOmDmNreANtCPW-nYYmiBZH9j-KNNX7n-k"
)

# ── tiny stats helpers (no numpy required for core logic) ─────────────────────

def median(values):
    s = sorted(values)
    n = len(s)
    mid = n // 2
    return (s[mid - 1] + s[mid]) / 2 if n % 2 == 0 else s[mid]


def mean(values):
    return sum(values) / len(values)


def rank_biserial(w_stat, n):
    """Effect size for Wilcoxon signed-rank: r = 1 - 4W / (n*(n+1))"""
    return 1 - (4 * w_stat) / (n * (n + 1))


# ── Shapiro-Wilk (simplified — uses scipy if available, else skips) ───────────

def shapiro_wilk(data):
    try:
        from scipy.stats import shapiro
        stat, p = shapiro(data)
        return stat, p
    except ImportError:
        return None, None


# ── Wilcoxon Signed-Rank Test ─────────────────────────────────────────────────

def wilcoxon_signed_rank(x, y):
    """
    Paired Wilcoxon signed-rank test.
    Returns (W statistic, p-value, effect size r).
    Uses scipy if available; otherwise raises.
    """
    from scipy.stats import wilcoxon
    differences = [xi - yi for xi, yi in zip(x, y)]
    stat, p = wilcoxon(differences, alternative="two-sided")
    r = rank_biserial(stat, len(differences))
    return stat, p, r


# ── Linear Mixed-Effects Model ────────────────────────────────────────────────

def run_lme(records, outcome_col):
    """
    Linear mixed-effects model:
      outcome ~ condition + (1 | participant_id)
    Returns result summary string.
    """
    try:
        import pandas as pd
        import statsmodels.formula.api as smf

        df = pd.DataFrame(records)
        df["condition_num"] = (df["condition"] == "reviewed").astype(int)
        model = smf.mixedlm(
            f"{outcome_col} ~ condition_num",
            df,
            groups=df["participant_id"]
        )
        result = model.fit(reml=True)
        coef = result.params["condition_num"]
        p    = result.pvalues["condition_num"]
        ci   = result.conf_int().loc["condition_num"]
        return (
            f"  coef={coef:.4f}  95%CI=[{ci[0]:.4f}, {ci[1]:.4f}]  p={p:.4f}"
        )
    except Exception as e:
        return f"  LME failed: {e}"


# ── Supabase fetch ────────────────────────────────────────────────────────────

def fetch_records():
    params = urllib.parse.urlencode({
        "condition": "in.(reviewed,immediate)",
        "observation_complete": "eq.true",
        "select": (
            "participant_id,condition,"
            "proportion_lines_changed,"
            "total_active_modification_time_s,"
            "time_to_first_modification_s,"
            "review_duration_s,"
            "self_reported_confidence,"
            "block_deleted"
        )
    })
    url = f"{SUPABASE_URL}/rest/v1/insertion_records?{params}"
    req = urllib.request.Request(
        url,
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Accept": "application/json",
            "Range": "0-9999",
        }
    )
    with urllib.request.urlopen(req, context=_SSL_CTX) as resp:
        return json.loads(resp.read())


# ── Per-participant aggregation ───────────────────────────────────────────────

def aggregate_per_participant(records, outcome_col):
    """
    For each participant compute median(outcome) separately for each condition.
    Returns (reviewed_list, immediate_list) — only participants with BOTH conditions.
    """
    buckets = defaultdict(lambda: {"reviewed": [], "immediate": []})
    for r in records:
        pid  = r["participant_id"]
        cond = r["condition"]
        val  = r.get(outcome_col)
        if val is not None and cond in ("reviewed", "immediate"):
            buckets[pid][cond].append(float(val))

    reviewed_medians  = []
    immediate_medians = []
    valid_participants = []

    for pid, groups in buckets.items():
        if groups["reviewed"] and groups["immediate"]:
            reviewed_medians.append(median(groups["reviewed"]))
            immediate_medians.append(median(groups["immediate"]))
            valid_participants.append(pid)

    return reviewed_medians, immediate_medians, valid_participants


# ── Analysis for one outcome ──────────────────────────────────────────────────

def analyse_outcome(records, outcome_col, label):
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")

    rev, imm, pids = aggregate_per_participant(records, outcome_col)
    n = len(pids)

    if n < 3:
        print(f"  Not enough paired participants (n={n}). Need ≥ 3.")
        return

    print(f"  Participants with both conditions : {n}")
    print(f"  Reviewed  — median of medians    : {median(rev):.4f}")
    print(f"  Immediate — median of medians    : {median(imm):.4f}")

    # Differences for normality test
    diffs = [r - i for r, i in zip(rev, imm)]

    # Shapiro-Wilk
    sw_stat, sw_p = shapiro_wilk(diffs)
    if sw_p is not None:
        normal = sw_p > 0.05
        print(f"\n  Shapiro-Wilk  W={sw_stat:.4f}  p={sw_p:.4f}  "
              f"→ {'NORMAL ✓' if normal else 'NOT normal ✗'}")
    else:
        normal = False
        print("\n  Shapiro-Wilk skipped (scipy not installed) → using Wilcoxon")

    # Primary or fallback
    if normal and n >= 10:
        print("\n  → Primary: Linear Mixed-Effects Model")
        print(run_lme(records, outcome_col))
    else:
        print("\n  → Fallback: Wilcoxon Signed-Rank Test")
        try:
            W, p, r = wilcoxon_signed_rank(rev, imm)
            sig = "SIGNIFICANT ✓" if p < 0.05 else "not significant"
            print(f"  W={W:.1f}  p={p:.4f}  r={r:.3f}  → {sig}")
            print(f"  (α = 0.05, two-sided, n={n} pairs)")
        except ImportError:
            print("  scipy not installed. Run:  pip install scipy")


# ── Exploratory: confidence & review duration ─────────────────────────────────

def exploratory_summary(records):
    print(f"\n{'='*60}")
    print("  Exploratory measures")
    print(f"{'='*60}")

    reviewed  = [r for r in records if r["condition"] == "reviewed"]
    immediate = [r for r in records if r["condition"] == "immediate"]

    def safe_mean(lst, col):
        vals = [float(r[col]) for r in lst if r.get(col) is not None]
        return f"{mean(vals):.3f}" if vals else "N/A"

    print(f"  self_reported_confidence  reviewed={safe_mean(reviewed,'self_reported_confidence')}  "
          f"immediate={safe_mean(immediate,'self_reported_confidence')}")
    print(f"  time_to_first_mod (s)     reviewed={safe_mean(reviewed,'time_to_first_modification_s')}  "
          f"immediate={safe_mean(immediate,'time_to_first_modification_s')}")

    rev_dur = [float(r["review_duration_s"]) for r in reviewed if r.get("review_duration_s")]
    if rev_dur:
        print(f"  review_duration_s         mean={mean(rev_dur):.1f}s  median={median(rev_dur):.1f}s")

    deleted_rev = sum(1 for r in reviewed  if r.get("block_deleted"))
    deleted_imm = sum(1 for r in immediate if r.get("block_deleted"))
    print(f"  block_deleted             reviewed={deleted_rev}/{len(reviewed)}  "
          f"immediate={deleted_imm}/{len(immediate)}")


# ── Per-participant summary table ────────────────────────────────────────────

def participant_summary(records):
    print(f"\n{'='*60}")
    print("  Per-Participant Summary")
    print(f"{'='*60}")

    buckets = defaultdict(lambda: {"reviewed": [], "immediate": []})
    for r in records:
        pid  = r["participant_id"]
        cond = r["condition"]
        if cond in ("reviewed", "immediate"):
            buckets[pid][cond].append(r)

    header = (
        f"{'ID':<8} {'rev_n':>5} {'imm_n':>5} "
        f"{'med_prop_rev':>13} {'med_prop_imm':>13} "
        f"{'med_time_rev':>13} {'med_time_imm':>13}"
    )
    print(f"\n  {header}")
    print(f"  {'-'*len(header)}")

    for pid in sorted(buckets.keys()):
        rev = buckets[pid]["reviewed"]
        imm = buckets[pid]["immediate"]

        def med_col(lst, col):
            vals = [float(r[col]) for r in lst if r.get(col) is not None]
            return f"{median(vals):.3f}" if vals else "—"

        print(
            f"  {pid:<8} {len(rev):>5} {len(imm):>5} "
            f"  {med_col(rev,'proportion_lines_changed'):>11} "
            f"  {med_col(imm,'proportion_lines_changed'):>11} "
            f"  {med_col(rev,'total_active_modification_time_s'):>11} "
            f"  {med_col(imm,'total_active_modification_time_s'):>11}"
        )


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("Fetching data from Supabase...")
    try:
        records = fetch_records()
    except Exception as e:
        print(f"Error fetching data: {e}")
        return

    total = len(records)
    reviewed_n  = sum(1 for r in records if r["condition"] == "reviewed")
    immediate_n = sum(1 for r in records if r["condition"] == "immediate")

    print(f"\nTotal records : {total}")
    print(f"  reviewed    : {reviewed_n}")
    print(f"  immediate   : {immediate_n}")

    if total == 0:
        print("No completed observations yet. Run the study first.")
        return

    # Per-participant breakdown
    participant_summary(records)

    # RQ1 — structural rework
    analyse_outcome(
        records,
        outcome_col="proportion_lines_changed",
        label="RQ1 — Proportion of lines changed after acceptance"
    )

    # RQ2 — temporal effort
    analyse_outcome(
        records,
        outcome_col="total_active_modification_time_s",
        label="RQ2 — Total active modification time after acceptance (s)"
    )

    # Exploratory
    exploratory_summary(records)

    print("\nDone.\n")


if __name__ == "__main__":
    main()
