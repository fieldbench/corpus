#!/usr/bin/env python3
"""Compute \\iaacontested: annotator agreement with GT on CONTESTED fields.

Contested (per paper 3.4): fields where the frontier models return null and
gpt-4o-mini fills a value. We measure, over the IAA sample, the annotator's
agreement with GT on exactly those (doc,field) pairs. High agreement there
distinguishes genuine over-abstention from an over-populated reference.

  python scripts/iaa_contested.py <annotator_dir> <data_dir>
"""
import json, os, sys
CORPUS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, CORPUS)
from fieldbench.scoring import compare_field, is_empty  # noqa
import yaml

ann_dir = sys.argv[1]
DATA = sys.argv[2]
_ALL_FRONTIER = {"sonnet-4-5": "preds-v0.2/sonnet-4-5", "gpt-4o": "preds-v0.2/gpt-4o",
                 "gemini-2.5-pro": "preds-extra/gemini-2.5-pro"}
_sel = os.environ.get("FRONTIER_MODELS")
FRONTIER = _ALL_FRONTIER if not _sel else {m: _ALL_FRONTIER[m] for m in _sel.split(",")}
MINI = "preds-v0.2/gpt-4o-mini"

schema_cache = {}
def fields_for(cat):
    if cat not in schema_cache:
        # one schema per real category
        sch = {"sec_filings": "filing_metadata", "receipts": "invoice_basic",
               "contracts": "contract", "medical_records": "discharge_summary",
               "legal_filings": "legal_filing", "insurance_claims": "claim_form"}[cat]
        doc = yaml.safe_load(open(os.path.join(CORPUS, cat, "schemas", f"{sch}.yaml")))
        schema_cache[cat] = doc.get("fields", {}) or {}
    return schema_cache[cat]

def load(path):
    return json.load(open(path)) if os.path.isfile(path) else None

def cmp(name, a, b, spec):
    eo = spec.get("options") if str(spec.get("type", "")).lower() == "enum" else None
    mp = spec.get("mappings") if isinstance(spec.get("mappings"), dict) else None
    return compare_field(name, a, b, mappings=mp, enum_options=eo).passed

contested = agree = gt_nonnull = 0
per_cat = {}
examples = []
for fn in sorted(os.listdir(ann_dir)):
    if not fn.endswith(".annotate.json"):
        continue
    t = json.load(open(os.path.join(ann_dir, fn)))
    stem, cat = t["stem"], t["category"]
    ann = t.get("annotation") or {}
    gt = load(os.path.join(CORPUS, cat, "expected", f"{stem}.expected.json"))
    if gt is None:
        continue
    mini = load(os.path.join(DATA, MINI, f"{stem}.json"))
    if mini is None:
        continue
    fr = {m: load(os.path.join(DATA, p, f"{stem}.json")) for m, p in FRONTIER.items()}
    fr = {m: v for m, v in fr.items() if v is not None}
    if not fr:
        continue
    specs = fields_for(cat)
    MODE = os.environ.get("MODE", "mini")  # mini: frontier-null & mini-fills ; gtnn: frontier-null & GT-nonnull
    for name in gt:
        mv = mini.get(name)
        if MODE == "gtnn":
            if is_empty(gt.get(name)):
                continue                   # GT has no value -> not an over-abstention case
        else:
            if is_empty(mv):
                continue                   # mini did not fill
        if not all(is_empty(v.get(name)) for v in fr.values()):
            continue                       # some frontier model filled -> not contested
        # contested field
        contested += 1
        pc = per_cat.setdefault(cat, [0, 0])
        pc[0] += 1
        if not is_empty(gt.get(name)):
            gt_nonnull += 1
        ok = cmp(name, gt.get(name), ann.get(name), specs.get(name) or {})
        agree += ok
        pc[1] += ok
        if len(examples) < 12:
            examples.append({"stem": stem, "field": name, "gt": gt.get(name),
                             "annotator": ann.get(name), "mini": mv, "agree": bool(ok)})

print(f"frontier set: {sorted(FRONTIER)}")
print(f"contested (doc,field) pairs: {contested}")
print(f"  of which GT non-null: {gt_nonnull} ({100*gt_nonnull/contested:.1f}%)" if contested else "")
print(f"annotator agreement on contested: {agree}/{contested} = {100*agree/contested:.1f}%" if contested else "no contested fields")
print("by category (agree/contested):")
for c, (n, a) in sorted(per_cat.items()):
    print(f"  {c:<16}{a}/{n} = {100*a/n:.1f}%")
print("\nexamples:")
for e in examples:
    print(f"  {e['stem']} {e['field']}: gt={json.dumps(e['gt'])[:40]} ann={json.dumps(e['annotator'])[:40]} mini={json.dumps(e['mini'])[:30]} agree={e['agree']}")
