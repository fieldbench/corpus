#!/usr/bin/env python3
"""Document-level bootstrap CIs for FieldBench headline claims (corpus v0.3).

Reproduces the confidence intervals in the paper: 1000 resamples with replacement
over documents, seed 42, 95% percentile intervals. Point estimates are exact
(whole corpus); CIs are bootstrap estimates. Paired comparisons resample document
indices once per iteration and apply to both systems.

Run: fieldbench/.venv/bin/python data/bootstrap_ci.py
"""
from __future__ import annotations
import sys, json, glob, os, pathlib
sys.path.insert(0, "fieldbench/src")
import numpy as np
from fieldbench.corpus import score_corpus, _schema_mappings
from fieldbench.scoring import compare_field

CORPUS = pathlib.Path("corpus")
N, SEED = 1000, 42
MODELS = ["gpt-4o-mini", "gpt-4o", "sonnet-4-5"]
cache = {}

# per-doc (passed, fields) vectors for each system, overall and per (category, real)
DOCS = {m: score_corpus(CORPUS, pathlib.Path(f"data/preds-v0.2/{m}"))[0] for m in MODELS}

def vecs(model, cat=None, real_only=False, restrict=None):
    """Return arrays (passed, fields) per document."""
    P, F = [], []
    for d in DOCS[model]:
        if cat and d.category != cat:
            continue
        if real_only and d.source != "real":
            continue
        p = t = 0
        for r in d.fields:
            if restrict and r.field_name not in restrict:
                continue
            t += 1; p += int(r.passed)
        if t:
            P.append(p); F.append(t)
    return np.array(P), np.array(F)

def boot_acc(P, F, rng):
    idx = rng.integers(0, len(P), size=len(P))
    return 100 * P[idx].sum() / F[idx].sum()

def ci_single(P, F):
    rng = np.random.default_rng(SEED)
    s = np.array([boot_acc(P, F, rng) for _ in range(N)])
    return round(np.percentile(s, 2.5), 1), round(np.percentile(s, 97.5), 1)

def ci_margin(Pa, Fa, Pb, Fb):
    """Paired: same resampled doc indices for both systems. Assumes aligned docs."""
    rng = np.random.default_rng(SEED)
    diffs = []
    n = len(Pa)
    for _ in range(N):
        idx = rng.integers(0, n, size=n)
        a = 100 * Pa[idx].sum() / Fa[idx].sum()
        b = 100 * Pb[idx].sum() / Fb[idx].sum()
        diffs.append(a - b)
    diffs = np.array(diffs)
    return (round(diffs.mean(), 1), round(np.percentile(diffs, 2.5), 1),
            round(np.percentile(diffs, 97.5), 1), round(100 * (diffs > 0).mean()))

RESTR = {"merchant_name", "date", "total_amount"}
print("=== Table 4: overall accuracy CI ===")
for m in MODELS:
    P, F = vecs(m)
    print(f"  {m:12} {100*P.sum()/F.sum():.1f}  95% CI {ci_single(P, F)}")

print("\n=== §6.1 overall margins (paired) ===")
Pm, Fm = vecs("gpt-4o-mini"); Pg, Fg = vecs("gpt-4o"); Ps, Fs = vecs("sonnet-4-5")
print(f"  mini - gpt-4o : {ci_margin(Pm,Fm,Pg,Fg)}   (mean, lo, hi, %win)")
print(f"  mini - sonnet : {ci_margin(Pm,Fm,Ps,Fs)}")

print("\n=== §6.1 per-category winning margins (real docs; receipts restricted) ===")
def catvec(m, cat, restrict=None): return vecs(m, cat=cat, real_only=True, restrict=restrict)
for cat, a, b, lbl in [("medical_records","gpt-4o-mini","gpt-4o","clinical mini-vs-4o"),
                       ("legal_filings","gpt-4o-mini","gpt-4o","legal mini-vs-4o"),
                       ("contracts","gpt-4o-mini","gpt-4o","contracts mini-vs-4o"),
                       ("sec_filings","sonnet-4-5","gpt-4o-mini","sec sonnet-vs-mini"),
                       ("receipts","sonnet-4-5","gpt-4o-mini","receipts sonnet-vs-mini")]:
    rz = RESTR if cat == "receipts" else None
    Pa, Fa = catvec(a, cat, rz); Pb, Fb = catvec(b, cat, rz)
    print(f"  {lbl:22} {ci_margin(Pa,Fa,Pb,Fb)}")
