#!/usr/bin/env python3
"""Score staged matched-pair categories, split by realism level (from stem), and
print the real-vs-synthetic gradient table.

Real baselines come from the published-corpus v2 run (by_category). Synthetic
accuracy is computed here per (model, realism) from the staging predictions.

Usage: score_gradient.py <category> [<category> ...]
"""
import os, sys, glob, json
sys.path.insert(0, os.path.expanduser("~/dev/fieldbench/fieldbench/src"))
from pathlib import Path
from fieldbench.corpus import score_corpus

STAGE = Path(os.path.expanduser("~/dev/fieldbench/data/matched-stage"))
MODELS = ["gpt-4o-mini", "gpt-4o", "sonnet-4-5"]

# Real per-category accuracy, recomputed live from the current corpus + preds
# (was hardcoded to the pre-fix results-canonical-v2 numbers, which went stale
# after the GT corrections + scorer 0.2.0->0.2.1). Compute once here.
_REAL_PREDS = Path(os.path.expanduser("~/dev/fieldbench/data/preds-v0.2"))
def _real_baseline(cat):
    # real-docs-only (source=='real'), to match Table 5 / the matched-pair design
    real_stems = {
        os.path.basename(f)[: -len(".json")]
        for f in glob.glob(f"corpus/{cat}/manifests/*.json")
        if json.load(open(f)).get("source") == "real"
    }
    out = {}
    for m in MODELS:
        docs, _ = score_corpus(Path("corpus"), _REAL_PREDS / m, category=cat)
        docs = [d for d in docs if d.stem in real_stems]
        p = sum(f.passed for d in docs for f in d.fields)
        n = sum(1 for d in docs for f in d.fields)
        out[m] = round(100 * p / n, 1) if n else None
    return out
REAL = {c: _real_baseline(c) for c in ["medical_records", "legal_filings", "contracts", "sec_filings"]}

def realism_of(stem: str) -> str:
    if "-r0-" in stem: return "synth r0 (clean)"
    if "-r1-" in stem: return "synth r1 (realistic)"
    return "synth"

def acc_by_realism(cat, model):
    preds = STAGE / cat / "preds" / model
    if not preds.exists():
        return {}
    docs, missing = score_corpus(STAGE, preds, category=cat)
    agg = {}
    for d in docs:
        k = realism_of(d.stem)
        p, f = agg.get(k, (0, 0))
        agg[k] = (p + sum(int(r.passed) for r in d.fields), f + len(d.fields))
    return {k: 100 * p / f if f else 0.0 for k, (p, f) in agg.items()}, missing

for cat in sys.argv[1:]:
    print(f"\n===== {cat} =====")
    print(f"{'model':<14}{'real':>8}{'synth r0':>11}{'synth r1':>12}{'gap r0':>9}{'gap r1':>9}")
    for m in MODELS:
        res = acc_by_realism(cat, m)
        if not res:
            print(f"{m:<14}  (no preds yet)"); continue
        by, missing = res
        real = REAL.get(cat, {}).get(m)
        r0 = by.get("synth r0 (clean)"); r1 = by.get("synth r1 (realistic)")
        def f(x): return f"{x:.1f}" if x is not None else "—"
        g0 = f"{r0-real:+.1f}" if (r0 is not None and real is not None) else "—"
        g1 = f"{r1-real:+.1f}" if (r1 is not None and real is not None) else "—"
        miss = f"  [missing {missing}]" if missing else ""
        print(f"{m:<14}{f(real):>8}{f(r0):>11}{f(r1):>12}{g0:>9}{g1:>9}{miss}")
