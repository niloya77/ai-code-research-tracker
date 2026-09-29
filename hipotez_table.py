"""
H1: Reviewing AI generated code before acceptance -> structural rework (total_lines_changed)
H2: Reviewing AI generated code before acceptance -> total time spent modifying accepted code (total_active_modification_time_s)

Immediate vs Reviewed karsilastirmasi, katilimci bazinda.

Kullanim:  python3 hipotez_table.py
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
        "select": "participant_id,condition,observation_complete,total_lines_changed,total_active_modification_time_s",
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
    print(f"Toplam {len(records)} kayit (immediate + reviewed), H1/H2 katilimci bazinda:\n")

    stats = defaultdict(lambda: {
        "imm_tot": 0, "imm_lines_sum": 0.0, "imm_time_sum": 0.0,
        "rev_tot": 0, "rev_lines_sum": 0.0, "rev_time_sum": 0.0,
    })

    for r in records:
        pid = r["participant_id"]
        cond = r["condition"]
        lines = r.get("total_lines_changed")
        lines_val = float(lines) if lines is not None else 0.0
        time_s = r.get("total_active_modification_time_s")
        time_val = float(time_s) if time_s is not None else 0.0

        prefix = "imm" if cond == "immediate" else "rev"
        stats[pid][f"{prefix}_tot"] += 1
        stats[pid][f"{prefix}_lines_sum"] += lines_val
        stats[pid][f"{prefix}_time_sum"] += time_val

    def fmt_lines(lines_sum, tot):
        return f"{lines_sum:.0f}" if tot else "N/A"

    def fmt_time(time_sum, tot):
        return f"{time_sum:.1f}s" if tot else "N/A"

    def pct_diff(rev, imm):
        if imm == 0:
            return "N/A"
        return f"{((rev - imm) / imm * 100):+.1f}%"

    header = (
        f"{'Participant':<12}"
        f"{'H1 Imm lines':>13}{'H1 Rev lines':>13}{'H1 fark':>10}"
        f"{'H2 Imm timeS':>13}{'H2 Rev timeS':>13}{'H2 fark':>10}"
    )
    print(header)
    print("-" * len(header))

    tot = defaultdict(float)
    for pid in sorted(stats.keys(), key=lambda x: str(x)):
        s = stats[pid]
        for k in s:
            tot[k] += s[k]

        h1_fark = pct_diff(s["rev_lines_sum"], s["imm_lines_sum"]) if s["imm_tot"] and s["rev_tot"] else "N/A"
        h2_fark = pct_diff(s["rev_time_sum"], s["imm_time_sum"]) if s["imm_tot"] and s["rev_tot"] else "N/A"

        print(
            f"{str(pid):<12}"
            f"{fmt_lines(s['imm_lines_sum'], s['imm_tot']):>13}"
            f"{fmt_lines(s['rev_lines_sum'], s['rev_tot']):>13}"
            f"{h1_fark:>10}"
            f"{fmt_time(s['imm_time_sum'], s['imm_tot']):>13}"
            f"{fmt_time(s['rev_time_sum'], s['rev_tot']):>13}"
            f"{h2_fark:>10}"
        )

    print("-" * len(header))
    print(
        f"{'TOPLAM':<12}"
        f"{fmt_lines(tot['imm_lines_sum'], tot['imm_tot']):>13}"
        f"{fmt_lines(tot['rev_lines_sum'], tot['rev_tot']):>13}"
        f"{pct_diff(tot['rev_lines_sum'], tot['imm_lines_sum']):>10}"
        f"{fmt_time(tot['imm_time_sum'], tot['imm_tot']):>13}"
        f"{fmt_time(tot['rev_time_sum'], tot['rev_tot']):>13}"
        f"{pct_diff(tot['rev_time_sum'], tot['imm_time_sum']):>10}"
    )


if __name__ == "__main__":
    main()
