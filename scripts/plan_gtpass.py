#!/usr/bin/env python3
"""Plan the GT revision pass: slice large docs and group docs into agent chunks.

- For docs over SLICE_THRESHOLD, write a head+tail excerpt to <scratch>/excerpts/
  (schema fields for sec_filings / contracts live on the cover + signature pages),
  and point the chunk at the excerpt with sliced=true.
- Group docs into chunks bounded by a per-agent byte budget and a doc-count cap,
  never mixing categories (each chunk shares one schema).
- Write chunk_plan.json: [{chunk_id, category, schema, docs:[{stem, read, expected,
  sliced, bytes}]}]. `read` and `expected` are ABSOLUTE paths for the agents.
"""
import json, os, sys

CORPUS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SLICE_THRESHOLD = 40 * 1024
HEAD = {"sec_filings": 12 * 1024, "contracts": 30 * 1024}
TAIL = {"sec_filings": 8 * 1024, "contracts": 15 * 1024}
BYTE_BUDGET = 350 * 1024   # post-slice read bytes per agent
DOC_CAP = 18               # max docs per agent

worklist_path = sys.argv[1]
scratch = sys.argv[2]
plan_path = sys.argv[3]
excerpt_dir = os.path.join(scratch, "excerpts")
wl = json.load(open(worklist_path))

def excerpt(cat, stem, abspath):
    raw = open(abspath, "rb").read()
    h, t = HEAD.get(cat, 12 * 1024), TAIL.get(cat, 8 * 1024)
    head, tail = raw[:h], raw[-t:]
    cut = len(raw) - h - t
    body = (head + f"\n\n...[MIDDLE {cut//1024} KB OF {len(raw)//1024} KB OMITTED — "
            f"this is a head+tail excerpt; if a schema field is not groundable here, "
            f"mark it needs_full_review, do not change it]...\n\n".encode() + tail)
    d = os.path.join(excerpt_dir, cat)
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, f"{stem}.excerpt.md")
    open(p, "wb").write(body)
    return p, len(body)

# Resolve each doc to a read path (excerpt if large) and read-bytes.
docs_by_cat = {}
sliced_n = 0
for e in wl:
    cat, stem = e["category"], e["stem"]
    docabs = os.path.join(CORPUS, e["doc"])
    if e["bytes"] > SLICE_THRESHOLD and cat in HEAD:
        read, rbytes = excerpt(cat, stem, docabs)
        sliced = True; sliced_n += 1
    else:
        read, rbytes = docabs, e["bytes"]
    docs_by_cat.setdefault(cat, []).append({
        "stem": stem, "read": read, "sliced": sliced if e["bytes"] > SLICE_THRESHOLD and cat in HEAD else False,
        "expected": os.path.join(CORPUS, e["expected"]), "bytes": rbytes,
        "schema": os.path.join(CORPUS, e["schema"]), "provenance": e.get("gt_provenance", ""),
    })

# Chunk within each category by byte budget + doc cap.
chunks = []
for cat, docs in docs_by_cat.items():
    docs.sort(key=lambda d: d["stem"])
    cur, cur_b = [], 0
    for d in docs:
        if cur and (cur_b + d["bytes"] > BYTE_BUDGET or len(cur) >= DOC_CAP):
            chunks.append((cat, cur)); cur, cur_b = [], 0
        cur.append(d); cur_b += d["bytes"]
    if cur:
        chunks.append((cat, cur))

plan = []
for i, (cat, docs) in enumerate(chunks):
    schema = docs[0]["schema"]
    plan.append({"chunk_id": f"{cat}-{i:03d}", "category": cat, "schema": schema,
                 "docs": [{k: d[k] for k in ("stem", "read", "expected", "sliced", "bytes")} for d in docs]})

json.dump(plan, open(plan_path, "w"), indent=0)
print(f"chunks: {len(plan)}  (sliced {sliced_n} large docs)  -> {plan_path}\n")
from collections import Counter
c = Counter(p["category"] for p in plan)
dcount = Counter()
for p in plan:
    dcount[p["category"]] += len(p["docs"])
print(f"{'category':<20}{'chunks':>8}{'docs':>7}")
for cat in ["sec_filings","contracts","legal_filings","medical_records","receipts","insurance_claims"]:
    if c[cat]:
        print(f"{cat:<20}{c[cat]:>8}{dcount[cat]:>7}")
print(f"\nTOTAL chunks (= audit agents): {len(plan)}  docs: {sum(dcount.values())}")
