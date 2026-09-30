#!/usr/bin/env python3
"""Receipts matched-pair scorer, restricted to the fields real SROIE annotates
(merchant_name, date, total_amount) so real and synthetic are scored over the
SAME field set. Real preds come from the published-corpus v2 run; synthetic from
the matched-stage run, split by realism."""
import os, sys, json, glob
sys.path.insert(0, os.path.expanduser("~/dev/fieldbench/fieldbench/src"))
from pathlib import Path
from fieldbench.scoring import compare_field

FIELDS = ["merchant_name", "date", "total_amount"]
MODELS = ["gpt-4o-mini", "gpt-4o", "sonnet-4-5"]
CORPUS = Path(os.path.expanduser("~/dev/fieldbench/corpus"))
# Real receipt predictions live in preds-v0.2 (the canonical 5-system run);
# preds-v2 lacks the sroie_real_* docs, which silently tanked the real baseline.
REAL_PREDS = Path(os.path.expanduser("~/dev/fieldbench/data/preds-v0.2"))
STAGE = Path(os.path.expanduser("~/dev/fieldbench/data/matched-stage/receipts"))
IS_REAL_RECEIPT = lambda s: s.startswith("sroie")  # real SROIE only, not synth corpus docs

def acc(expected_dir, preds_dir, stem_filter=None):
    passed = total = 0
    for exp_path in sorted(Path(expected_dir).glob("*.expected.json")):
        stem = exp_path.name[:-len(".expected.json")]
        if stem_filter and not stem_filter(stem):
            continue
        exp = json.loads(exp_path.read_text())
        pf = Path(preds_dir) / f"{stem}.json"
        pred = json.loads(pf.read_text()) if pf.exists() else {}
        for f in FIELDS:
            if f not in exp:
                continue
            total += 1
            passed += int(compare_field(f, exp[f], pred.get(f)).passed)
    return 100 * passed / total if total else None, total

print(f"receipts (scored on {FIELDS})")
print(f"{'model':<14}{'real':>8}{'synth r0':>11}{'synth r1':>12}{'gap r0':>9}{'gap r1':>9}")
for m in MODELS:
    real, nr = acc(CORPUS / "receipts" / "expected", REAL_PREDS / m, IS_REAL_RECEIPT)
    r0, _ = acc(STAGE / "expected", STAGE / "preds" / m, lambda s: "-r0-" in s)
    r1, _ = acc(STAGE / "expected", STAGE / "preds" / m, lambda s: "-r1-" in s)
    def f(x): return f"{x:.1f}" if x is not None else "—"
    g0 = f"{r0-real:+.1f}" if (r0 and real) else "—"
    g1 = f"{r1-real:+.1f}" if (r1 and real) else "—"
    print(f"{m:<14}{f(real):>8}{f(r0):>11}{f(r1):>12}{g0:>9}{g1:>9}")
print(f"(real N={nr} field-instances over {FIELDS})")
