#!/usr/bin/env python3
"""Three-way concordance: original GT vs human run vs pipeline.

original GT = git HEAD expected/ ; pipeline = working-tree expected/ (batch-1
applied) ; human = exported annotations tsv (doc_id, field, value_json, absent).

Uses the scorer's type-aware compare_field so formatting is not a disagreement.
"""
import json, os, subprocess, sys
from collections import defaultdict

CORPUS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, CORPUS)
from fieldbench.scoring import compare_field  # noqa

import yaml

human_tsv = sys.argv[1]
worklist = json.load(open(sys.argv[2]))
meta = {w["stem"]: w for w in worklist}

# human: (doc,field) -> value  (absent -> None; missing -> None)
human = {}
for line in open(human_tsv):
    parts = line.rstrip("\n").split("\t")
    if len(parts) < 4:
        continue
    doc, field, vj, absent = parts[0], parts[1], parts[2], parts[3]
    human[(doc, field)] = None if absent == "t" else (None if vj == "null" else json.loads(vj))

# schema field specs per category (one schema per real cat)
schema_cache = {}
def fields_for(cat, schema_rel):
    if cat not in schema_cache:
        doc = yaml.safe_load(open(os.path.join(CORPUS, schema_rel)))
        schema_cache[cat] = doc.get("fields", {}) or {}
    return schema_cache[cat]

def head_json(relpath):
    try:
        out = subprocess.run(["git", "-C", CORPUS, "show", f"HEAD:{relpath}"],
                             capture_output=True, text=True, check=True).stdout
        return json.loads(out)
    except Exception:
        return None

def cmp(name, a, b, spec):
    enum_opts = spec.get("options") if str(spec.get("type", "")).lower() == "enum" else None
    maps = spec.get("mappings") if isinstance(spec.get("mappings"), dict) else None
    return compare_field(name, a, b, mappings=maps, enum_options=enum_opts).passed

buckets = defaultdict(int)   # A both-agree, B both-diff, C pipe-only, D human-only, E neither
detail = defaultdict(list)
per_cat = defaultdict(lambda: defaultdict(int))

for stem, w in meta.items():
    cat, exp_rel = w["category"], w["expected"]
    pipe = json.load(open(os.path.join(CORPUS, exp_rel)))
    orig = head_json(exp_rel)
    if orig is None:
        orig = pipe  # new file; treat as unchanged
    specs = fields_for(cat, w["schema"])
    for name in pipe:
        spec = specs.get(name) or {}
        o, p = orig.get(name), pipe.get(name)
        h = human.get((stem, name))
        pipe_changed = not cmp(name, o, p, spec)
        human_changed = not cmp(name, o, h, spec)
        if not pipe_changed and not human_changed:
            buckets["E_neither"] += 1
            continue
        agree_ph = cmp(name, p, h, spec)
        if pipe_changed and human_changed:
            b = "A_both_agree" if agree_ph else "B_both_diff"
        elif pipe_changed and not human_changed:
            b = "C_pipe_only"   # human kept original
        else:
            b = "D_human_only"  # pipeline missed
        buckets[b] += 1
        per_cat[cat][b] += 1
        detail[b].append({"stem": stem, "field": name, "orig": o, "pipe": p, "human": h})

def rate(n, d): return f"{100*n/d:.1f}%" if d else "-"

A, B, C, D = (buckets["A_both_agree"], buckets["B_both_diff"],
              buckets["C_pipe_only"], buckets["D_human_only"])
print("=== THREE-WAY CONCORDANCE (batch-1 pipeline) ===")
print(f"pipeline changed:            {A+B+C}")
print(f"human changed:               {A+B+D}")
print(f"A both agree (same fix):     {A}")
print(f"B both flag, different value:{B}")
print(f"C pipeline only (human kept original): {C}")
print(f"D human only (pipeline missed):        {D}")
print(f"E neither changed:           {buckets['E_neither']}")
print()
print(f"Pipeline changes corroborated by human: {A}/{A+B+C} = {rate(A, A+B+C)}")
print(f"Human changes caught by pipeline:       {A}/{A+B+D} = {rate(A, A+B+D)}")
print(f"Exact-agreement where either flagged:   {A}/{A+B+C+D} = {rate(A, A+B+C+D)}")
print()
print("by category (A/B/C/D):")
for cat in sorted(per_cat):
    pc = per_cat[cat]
    print(f"  {cat:<18} A={pc['A_both_agree']:<4} B={pc['B_both_diff']:<4} C={pc['C_pipe_only']:<4} D={pc['D_human_only']:<4}")

out = sys.argv[3] if len(sys.argv) > 3 else None
if out:
    json.dump({"buckets": dict(buckets), "detail": detail}, open(out, "w"), indent=1, default=str)
    print(f"\ndetail -> {out}")
