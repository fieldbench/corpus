#!/usr/bin/env python3
"""Apply verified GT corrections to expected/ files, preserving per-file JSON
formatting so the diff shows only value changes. Writes a change report.

  python scripts/apply_gtpass.py <confirmed.json> <worklist.json> <report.md>

- Per-curiam judge fixes (PER_CURIAM_NULL) are overridden to null (convention).
- HOLD entries are skipped (left for targeted follow-up).
"""
import json, os, sys

CORPUS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PER_CURIAM_NULL = {"cap_001","cap_002","cap_003","cap_004","cap_005",
                   "cap_008","cap_009","cap_046","cap_057","cap_058"}
HOLD = set()

confirmed = json.load(open(sys.argv[1]))
wl = json.load(open(sys.argv[2]))
report_path = sys.argv[3]
meta = {w["stem"]: w for w in wl}

def detect_ascii(raw_bytes):
    try:
        raw_bytes.decode("ascii"); return True
    except UnicodeDecodeError:
        return False

applied, held, missing = [], [], []
# group by expected file so multiple field fixes to one doc are one write
by_file = {}
for c in confirmed:
    stem, field = c["stem"], c["field"]
    if (stem, field) in HOLD:
        held.append((stem, field, "held for follow-up")); continue
    if stem not in meta:
        missing.append((stem, field, "stem not in worklist")); continue
    if stem in PER_CURIAM_NULL and field == "judge":
        val = None
    else:
        val = json.loads(c["corrected_json"])
    by_file.setdefault(stem, []).append((field, val, c.get("evidence", "")))

for stem, changes in by_file.items():
    path = os.path.join(CORPUS, meta[stem]["expected"])
    raw = open(path, "rb").read()
    ascii_ok = detect_ascii(raw)
    trailing_nl = raw.endswith(b"\n")
    obj = json.loads(raw)
    for field, val, ev in changes:
        old = obj.get(field, "<<absent>>")
        obj[field] = val
        applied.append({"category": meta[stem]["category"], "stem": stem,
                        "field": field, "old": old, "new": val, "evidence": ev})
    out = json.dumps(obj, indent=2, ensure_ascii=ascii_ok)
    if trailing_nl:
        out += "\n"
    open(path, "w").write(out)

# report
from collections import defaultdict
byc = defaultdict(lambda: defaultdict(list))
for a in applied:
    byc[a["category"]][a["field"]].append(a)
with open(report_path, "w") as f:
    f.write(f"# GT revision pass — applied changes\n\n")
    f.write(f"Applied {len(applied)} field corrections across "
            f"{len(by_file)} documents. Held {len(held)}. Missing {len(missing)}.\n\n")
    for cat in sorted(byc):
        n = sum(len(v) for v in byc[cat].values())
        f.write(f"## {cat} ({n})\n\n")
        for field in sorted(byc[cat]):
            f.write(f"### {field} ({len(byc[cat][field])})\n\n")
            for a in byc[cat][field]:
                ev = a["evidence"].replace("\n", " ")[:160]
                f.write(f"- **{a['stem']}**: `{json.dumps(a['old'])}` -> "
                        f"`{json.dumps(a['new'])}`\n  - _{ev}_\n")
            f.write("\n")
    if held:
        f.write(f"## HELD (needs follow-up)\n\n")
        for s, fld, why in held:
            f.write(f"- {s}.{fld} — {why}\n")

print(f"applied {len(applied)} changes to {len(by_file)} files; held {len(held)}; missing {len(missing)}")
print(f"report -> {report_path}")
if missing:
    print("MISSING:", missing)
