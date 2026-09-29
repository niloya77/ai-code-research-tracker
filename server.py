"""
Local analysis API server for AI Tracker dashboard.
Run: python3 server.py
Then open dashboard.html in browser.
"""

import json, ssl, time, threading, urllib.request, urllib.parse
from collections import defaultdict
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

SUPABASE_URL = "https://qcyxsuvbcdsxprkzlkkh.supabase.co"
SUPABASE_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFjeXhzdXZiY2RzeHBya3psa2toIiwi"
    "cm9sZSI6ImFub24iLCJpYXQiOjE3Nzk4ODg1MzUsImV4cCI6MjA5NTQ2NDUzNX0"
    ".g52agmYZgdOmDmNreANtCPW-nYYmiBZH9j-KNNX7n-k"
)


_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE




SEVEN_DAYS_MS = 7 * 24 * 60 * 60 * 1000

EXCLUDED_PARTICIPANTS = {"ss"}


def mark_expired_complete():
    """7 günü geçmiş tüm accepted kayıtları observation_complete=true yap."""
    cutoff = int(time.time() * 1000) - SEVEN_DAYS_MS
    params = urllib.parse.urlencode({
        "condition": "in.(reviewed,immediate)",
        "acceptance_timestamp": f"lt.{cutoff}",
        "observation_complete": "eq.false",
    })
    url = f"{SUPABASE_URL}/rest/v1/insertion_records?{params}"
    data = json.dumps({"observation_complete": True}).encode()
    req = urllib.request.Request(url, data=data, headers={
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }, method="PATCH")
    try:
        with urllib.request.urlopen(req, context=_SSL_CTX) as resp:
            updated = json.loads(resp.read())
            if updated:
                print(f"[AutoMark] {len(updated)} kayıt observation_complete=True yapıldı.")
    except Exception as e:
        print(f"[AutoMark] Hata: {e}")


def _auto_mark_loop():
    while True:
        mark_expired_complete()
        time.sleep(3600)


def fetch_records(participant_id=None):
    query = {
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
    }
    if participant_id:
        query["participant_id"] = f"eq.{participant_id}"
    params = urllib.parse.urlencode(query)
    url = f"{SUPABASE_URL}/rest/v1/insertion_records?{params}"
    req = urllib.request.Request(url, headers={
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Accept": "application/json",
        "Range": "0-9999",
    })
    with urllib.request.urlopen(req, context=_SSL_CTX) as resp:
        records = json.loads(resp.read())
    return [r for r in records if r.get("participant_id") not in EXCLUDED_PARTICIPANTS]


def median(values):
    s = sorted(values)
    n = len(s)
    mid = n // 2
    return (s[mid - 1] + s[mid]) / 2 if n % 2 == 0 else s[mid]


def mean(values):
    return sum(values) / len(values)


def aggregate_per_participant(records, col):
    buckets = defaultdict(lambda: {"reviewed": [], "immediate": []})
    for r in records:
        val = r.get(col)
        if val is not None and r["condition"] in ("reviewed", "immediate"):
            buckets[r["participant_id"]][r["condition"]].append(float(val))

    rev, imm, pids = [], [], []
    for pid, g in buckets.items():
        if g["reviewed"] and g["immediate"]:
            rev.append(mean(g["reviewed"]))
            imm.append(mean(g["immediate"]))
            pids.append(pid)
    return rev, imm, pids


def run_lme(records, outcome_col):
    import pandas as pd
    import statsmodels.formula.api as smf

    df = pd.DataFrame(records)
    df["condition_num"] = (df["condition"] == "reviewed").astype(int)
    df[outcome_col] = pd.to_numeric(df[outcome_col], errors="coerce")
    df = df.dropna(subset=[outcome_col])

    model = smf.mixedlm(
        f"{outcome_col} ~ condition_num",
        df,
        groups=df["participant_id"]
    )
    result = model.fit(reml=True)
    if not result.converged:
        raise RuntimeError("LME did not converge")
    coef = float(result.params["condition_num"])
    p    = float(result.pvalues["condition_num"])
    ci   = result.conf_int().loc["condition_num"]
    return {
        "coef": round(coef, 4),
        "ci_low": round(float(ci[0]), 4),
        "ci_high": round(float(ci[1]), 4),
        "p": round(p, 4),
        "significant": p < 0.05,
    }


def run_wilcoxon(rev, imm):
    from scipy.stats import wilcoxon as scipy_wilcoxon
    diffs = [r - i for r, i in zip(rev, imm)]
    stat, p = scipy_wilcoxon(diffs, alternative="two-sided")
    n = sum(1 for d in diffs if d != 0)  # scipy drops zero-diffs (zero_method='wilcox') before ranking
    r = 1 - (4 * stat) / (n * (n + 1))
    return {
        "W": round(float(stat), 1),
        "p": round(float(p), 4),
        "r": round(float(r), 3),
        "n": n,
        "significant": float(p) < 0.05,
    }


def run_shapiro(rev, imm):
    from scipy.stats import shapiro
    diffs = [r - i for r, i in zip(rev, imm)]
    stat, p = shapiro(diffs)
    return {"stat": round(float(stat), 4), "p": round(float(p), 4), "normal": float(p) > 0.05}


def analyse(records, col):
    rev, imm, pids = aggregate_per_participant(records, col)
    n = len(pids)
    result = {"n_pairs": n, "col": col}

    if n < 3:
        result["error"] = f"Not enough paired participants (n={n}, need ≥3)"
        return result

    result["mean_reviewed"]  = round(mean(rev), 4)
    result["mean_immediate"] = round(mean(imm), 4)

    try:
        sw = run_shapiro(rev, imm)
        result["shapiro"] = sw
        normal = sw["normal"] and n >= 10
    except Exception as e:
        result["shapiro"] = {"error": str(e)}
        normal = False

    if normal:
        try:
            result["method"] = "LME"
            result["lme"] = run_lme(records, col)
        except Exception as e:
            result["method"] = "LME_failed"
            result["lme_error"] = str(e)
            result["wilcoxon"] = run_wilcoxon(rev, imm)
    else:
        result["method"] = "Wilcoxon"
        try:
            result["wilcoxon"] = run_wilcoxon(rev, imm)
        except Exception as e:
            result["wilcoxon_error"] = str(e)

    return result


@app.route("/api/analysis")
def analysis():
    participant_id = request.args.get("participant_id") or None
    try:
        records = fetch_records(participant_id)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    reviewed  = [r for r in records if r["condition"] == "reviewed"]
    immediate = [r for r in records if r["condition"] == "immediate"]

    def safe_mean(lst, col):
        vals = [float(r[col]) for r in lst if r.get(col) is not None]
        return round(sum(vals) / len(vals), 3) if vals else None

    rev_durs = [float(r["review_duration_s"]) for r in reviewed if r.get("review_duration_s")]

    return jsonify({
        "total": len(records),
        "reviewed_n": len(reviewed),
        "immediate_n": len(immediate),
        "rq1": analyse(records, "proportion_lines_changed"),
        "rq2": analyse(records, "total_active_modification_time_s"),
        "exploratory": {
            "confidence_reviewed":  safe_mean(reviewed,  "self_reported_confidence"),
            "confidence_immediate": safe_mean(immediate, "self_reported_confidence"),
            "time_to_first_mod_reviewed":  safe_mean(reviewed,  "time_to_first_modification_s"),
            "time_to_first_mod_immediate": safe_mean(immediate, "time_to_first_modification_s"),
            "review_duration_mean":   round(sum(rev_durs) / len(rev_durs), 1) if rev_durs else None,
            "review_duration_median": round(median(rev_durs), 1) if rev_durs else None,
            "block_deleted_reviewed":  sum(1 for r in reviewed  if r.get("block_deleted")),
            "block_deleted_immediate": sum(1 for r in immediate if r.get("block_deleted")),
        }
    })


if __name__ == "__main__":
    # Başlangıçta ve her saat 7 günü biten kayıtları otomatik tamamla
    t = threading.Thread(target=_auto_mark_loop, daemon=True)
    t.start()

    print("AI Tracker Analysis API → http://localhost:5050")
    app.run(port=5050, debug=False)
