"""
Katılımcı bazında Immediate / Reviewed blok tablosu.

Kullanım:  python3 participant_table.py
"""
import json
import ssl
import urllib.request
import urllib.parse
from collections import defaultdict

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

SUPABASE_URL = "https://qcyxsuvbcdsxprkzlkkh.supabase.co"
SUPABASE_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFjeXhzdXZiY2RzeHBya3psa2toIiwi"
    "cm9sZSI6ImFub24iLCJpYXQiOjE3Nzk4ODg1MzUsImV4cCI6MjA5NTQ2NDUzNX0"
    ".g52agmYZgdOmDmNreANtCPW-nYYmiBZH9j-KNNX7n-k"
)


def fetch_records():
    params = urllib.parse.urlencode({
        "condition": "in.(reviewed,immediate)",
        "select": "participant_id,condition,observation_complete,proportion_lines_changed",
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


def main():
    records = fetch_records()
    print(f"Toplam {len(records)} kayıt (immediate + reviewed), katılımcı bazında:\n")

    stats = defaultdict(lambda: {
        "imm_tot": 0, "imm_comp": 0, "imm_ncomp": 0, "imm_changed": 0, "imm_prop_sum": 0.0,
        "rev_tot": 0, "rev_comp": 0, "rev_ncomp": 0, "rev_changed": 0, "rev_prop_sum": 0.0,
    })

    for r in records:
        pid = r["participant_id"]
        cond = r["condition"]
        complete = bool(r.get("observation_complete"))
        prop = r.get("proportion_lines_changed")
        prop_val = float(prop) if prop is not None else 0.0
        changed = prop_val > 0

        prefix = "imm" if cond == "immediate" else "rev"
        stats[pid][f"{prefix}_tot"] += 1
        if complete:
            stats[pid][f"{prefix}_comp"] += 1
        else:
            stats[pid][f"{prefix}_ncomp"] += 1
        if changed:
            stats[pid][f"{prefix}_changed"] += 1
        stats[pid][f"{prefix}_prop_sum"] += prop_val

    def chg_pct(changed, tot):
        return f"{(changed / tot * 100):.1f}%" if tot else "N/A"

    def avg_pct(prop_sum, tot):
        return f"{(prop_sum / tot * 100):.1f}%" if tot else "N/A"

    header = (
        f"{'Participant':<12}{'Imm(tot)':>9}{'Imm(comp)':>10}{'Imm(ncomp)':>11}{'Imm hit%':>10}{'Imm avg%':>10}"
        f"{'Rev(tot)':>10}{'Rev(comp)':>10}{'Rev(ncomp)':>11}{'Rev hit%':>10}{'Rev avg%':>10}"
    )
    print(header)
    print("-" * len(header))

    totals = defaultdict(float)
    for pid in sorted(stats.keys(), key=lambda x: (str(x))):
        s = stats[pid]
        for k in ("imm_tot", "imm_comp", "imm_ncomp", "imm_changed", "imm_prop_sum",
                   "rev_tot", "rev_comp", "rev_ncomp", "rev_changed", "rev_prop_sum"):
            totals[k] += s[k]
        print(
            f"{str(pid):<12}{s['imm_tot']:>9}{s['imm_comp']:>10}{s['imm_ncomp']:>11}"
            f"{chg_pct(s['imm_changed'], s['imm_tot']):>10}"
            f"{avg_pct(s['imm_prop_sum'], s['imm_tot']):>10}"
            f"{s['rev_tot']:>10}{s['rev_comp']:>10}{s['rev_ncomp']:>11}"
            f"{chg_pct(s['rev_changed'], s['rev_tot']):>10}"
            f"{avg_pct(s['rev_prop_sum'], s['rev_tot']):>10}"
        )

    print("-" * len(header))
    print(
        f"{'TOPLAM':<12}{int(totals['imm_tot']):>9}{int(totals['imm_comp']):>10}{int(totals['imm_ncomp']):>11}"
        f"{chg_pct(totals['imm_changed'], totals['imm_tot']):>10}"
        f"{avg_pct(totals['imm_prop_sum'], totals['imm_tot']):>10}"
        f"{int(totals['rev_tot']):>10}{int(totals['rev_comp']):>10}{int(totals['rev_ncomp']):>11}"
        f"{chg_pct(totals['rev_changed'], totals['rev_tot']):>10}"
        f"{avg_pct(totals['rev_prop_sum'], totals['rev_tot']):>10}"
    )


if __name__ == "__main__":
    main()
