#!/usr/bin/env python3
"""Build the real-document worklist for the full-corpus GT revision pass.

Handles both manifest shapes:
  A) {"filename": "x.md", "schema": ...}                    (older)
  B) {"id": "x", "document": "documents/x.md",
      "expected": "expected/x.expected.json", "schema": ...} (newer, has gt_provenance)

Emits one entry per REAL doc with category/stem and doc/schema/expected paths
(relative to corpus root) plus byte size. Reads manifests + file sizes only;
never opens expected/ payloads.
"""
import json, os, sys, glob

CORPUS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REAL_CATS = ["sec_filings", "receipts", "contracts", "medical_records",
             "legal_filings", "insurance_claims"]

def rel(cat, p):
    """Resolve a manifest path (category-relative or bare) to corpus-root-relative."""
    if not p:
        return None
    return p if p.startswith(f"{cat}/") else os.path.join(cat, p)

out, warn = [], 0
for cat in REAL_CATS:
    for mpath in sorted(glob.glob(os.path.join(CORPUS, cat, "manifests", "*.json"))):
        try:
            m = json.load(open(mpath))
        except Exception as e:
            print(f"  WARN unreadable {mpath}: {e}", file=sys.stderr); warn += 1; continue
        if m.get("source") != "real":
            continue
        base = os.path.splitext(os.path.basename(mpath))[0]
        stem = m.get("id") or (m["filename"][:-3] if m.get("filename", "").endswith(".md")
                               else os.path.splitext(m.get("filename", base))[0]) or base
        doc = rel(cat, m.get("document") or (f"documents/{m['filename']}" if m.get("filename") else f"documents/{stem}.md"))
        exp = rel(cat, m.get("expected") or f"expected/{stem}.expected.json")
        schema = m.get("schema")
        prov = m.get("gt_provenance") or m.get("notes") or ""
        miss = [lbl for lbl, p in (("doc", doc), ("expected", exp), ("schema", schema))
                if not p or not os.path.isfile(os.path.join(CORPUS, p))]
        if miss:
            print(f"  WARN {cat}/{stem} missing {miss}", file=sys.stderr); warn += 1; continue
        out.append({"category": cat, "stem": stem, "doc": doc, "schema": schema,
                    "expected": exp, "bytes": os.path.getsize(os.path.join(CORPUS, doc)),
                    "gt_provenance": prov})

dest = sys.argv[1] if len(sys.argv) > 1 else "/tmp/gtpass_worklist.json"
json.dump(out, open(dest, "w"), indent=0)

print(f"worklist: {len(out)} real docs ({warn} warnings) -> {dest}\n")
print(f"{'category':<20}{'n':>5}{'totalKB':>10}{'avgKB':>8}{'maxKB':>8}{'>40KB':>7}")
for cat in REAL_CATS:
    e = [x for x in out if x["category"] == cat]
    if not e: continue
    b = [x["bytes"] for x in e]
    print(f"{cat:<20}{len(e):>5}{sum(b)//1024:>10}{(sum(b)//len(b))//1024:>8}{max(b)//1024:>8}{sum(1 for x in b if x>40960):>7}")
print(f"\nTOTAL real docs: {len(out)}  total {sum(x['bytes'] for x in out)//1024} KB")
