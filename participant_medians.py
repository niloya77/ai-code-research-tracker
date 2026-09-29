"""
Her katılımcı için Reviewed / Immediate medyanları (proportion changed, modification time)
ve ham kayıtları CSV olarak çıkarır. 'ss' test kullanıcısı hariç (293 kayıt, 11 katılımcı).

Kullanım:  python3 participant_medians.py
Çıktı:     participant_medians.csv, participant_records.csv
"""
import csv
import json
import urllib.request
import urllib.parse
from collections import defaultdict

from analysis import SUPABASE_URL, SUPABASE_KEY, _SSL_CTX, median

EXCLUDE = {"ss"}
FIELDS = [
    "participant_id", "condition", "record_id", "file_name", "insertion_timestamp",
    "original_line_count", "total_lines_changed", "proportion_lines_changed",
    "total_active_modification_time_s", "time_to_first_modification_s",
    "review_duration_s", "time_to_accept_s", "self_reported_confidence",
    "block_deleted", "observation_complete",
]


def fetch_records():
    params = urllib.parse.urlencode({
        "condition": "in.(reviewed,immediate)",
        "select": ",".join(FIELDS),
    })
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/insertion_records?{params}",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Accept": "application/json",
            "Range": "0-9999",
        },
    )
    with urllib.request.urlopen(req, context=_SSL_CTX) as resp:
        return [r for r in json.loads(resp.read()) if r["participant_id"] not in EXCLUDE]


def med(recs, col):
    vals = [float(r[col]) for r in recs if r.get(col) is not None]
    return round(median(vals), 4) if vals else None


def main():
    records = fetch_records()
    records.sort(key=lambda r: (int(r["participant_id"]), r["condition"], r["insertion_timestamp"] or ""))

    with open("participant_records.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(records)

    buckets = defaultdict(lambda: {"reviewed": [], "immediate": []})
    for r in records:
        buckets[r["participant_id"]][r["condition"]].append(r)

    rows = []
    for pid in sorted(buckets, key=int):
        rev, imm = buckets[pid]["reviewed"], buckets[pid]["immediate"]
        rows.append({
            "participant_id": pid,
            "n_reviewed": len(rev),
            "n_immediate": len(imm),
            "median_prop_changed_reviewed": med(rev, "proportion_lines_changed"),
            "median_prop_changed_immediate": med(imm, "proportion_lines_changed"),
            "median_mod_time_s_reviewed": med(rev, "total_active_modification_time_s"),
            "median_mod_time_s_immediate": med(imm, "total_active_modification_time_s"),
        })

    with open("participant_medians.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    fmt = lambda v: "—" if v is None else f"{v:.3f}"
    print(f"{len(records)} kayıt, {len(rows)} katılımcı\n")
    print(f"{'ID':<4}{'n_rev':>6}{'n_imm':>6}{'prop_rev':>10}{'prop_imm':>10}{'time_rev':>10}{'time_imm':>10}")
    for r in rows:
        print(f"{r['participant_id']:<4}{r['n_reviewed']:>6}{r['n_immediate']:>6}"
              f"{fmt(r['median_prop_changed_reviewed']):>10}{fmt(r['median_prop_changed_immediate']):>10}"
              f"{fmt(r['median_mod_time_s_reviewed']):>10}{fmt(r['median_mod_time_s_immediate']):>10}")


if __name__ == "__main__":
    main()
