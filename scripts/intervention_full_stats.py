#!/usr/bin/env python3
"""Full per-model stats for the 9-model over-abstention + intervention tables.

For each of the 9 models, over REAL medical_records + legal_filings docs:
  - default prompt:  acc, miss%, wrong%, halluc%  (all rates over ALL slots)
  - recall prompt:   acc, miss%, wrong%, halluc%
  - grounded%:       share of the default-prompt misses that are recoverable in source
  - Dacc + paired document-level bootstrap 95% CI (1000 resamples, seed 42)

acc = (match + correct_absence) / all_slots  (matches paper convention).
Run: fieldbench/.venv/bin/python data/intervention_full_stats.py
"""
from __future__ import annotations
import sys, json, glob, os, pathlib
sys.path.insert(0, "fieldbench/src")
sys.path.insert(0, "corpus/scripts")
import numpy as np
from fieldbench.scoring import compare_field, is_empty
from fieldbench.corpus import _schema_mappings
from grounding_audit import grounded, source_numbers, _norm

CORPUS = pathlib.Path("corpus")
CATS = ["medical_records", "legal_filings"]
N, SEED = 1000, 42
cache = {}

MODELS = [
    ("gpt-4o-mini",      "preds-v0.2/gpt-4o-mini",        "preds-antiabstain/gpt-4o-mini"),
    ("gpt-4o",           "preds-v0.2/gpt-4o",             "preds-antiabstain/gpt-4o"),
    ("sonnet-4-5",       "preds-v0.2/sonnet-4-5",         "preds-antiabstain/sonnet-4-5"),
    ("llama-3.1-8b",     "preds-extra/llama-3.1-8b",      "preds-antiabstain-extra/llama-3.1-8b"),
    ("llama-3.3-70b",    "preds-extra/llama-3.3-70b",     "preds-antiabstain-extra/llama-3.3-70b"),
    ("qwen-2.5-7b",      "preds-extra/qwen-2.5-7b",       "preds-antiabstain-extra/qwen-2.5-7b"),
    ("deepseek-chat",    "preds-extra/deepseek-chat",     "preds-antiabstain-extra/deepseek-chat"),
    ("gemini-2.5-flash", "preds-extra/gemini-2.5-flash",  "preds-antiabstain-extra/gemini-2.5-flash"),
    ("gemini-2.5-pro",   "preds-extra/gemini-2.5-pro",    "preds-antiabstain-extra/gemini-2.5-pro"),
]

def real_docs(cat):
    o = []
    for man in glob.glob(f"corpus/{cat}/manifests/*.json"):
        m = json.load(open(man))
        if str(m.get("source", "")) == "real":
            o.append((os.path.basename(man)[:-5], m.get("schema")))
    return sorted(o)

RD = {c: real_docs(c) for c in CATS}
# cache source text + grounding inputs per doc
SRC = {}
for cat in CATS:
    for stem, _ in RD[cat]:
        src = (CORPUS / cat / "documents" / f"{stem}.md").read_text()
        SRC[(cat, stem)] = (src, _norm(src), source_numbers(src))

DOCLIST = [(cat, stem, schema) for cat in CATS for stem, schema in RD[cat]]

def per_doc(pdir, want_grounded=False):
    """Return list over docs of dict(passed, total, miss, wrong, halluc, cabs, miss_grounded)."""
    out = []
    for cat, stem, schema in DOCLIST:
        pp = f"data/{pdir}/{stem}.json"
        pred = json.load(open(pp)) if os.path.exists(pp) else {}
        exp = json.load(open(f"corpus/{cat}/expected/{stem}.expected.json"))
        maps = _schema_mappings(CORPUS, schema, cache)
        src, nsrc, snums = SRC[(cat, stem)]
        d = dict(passed=0, total=0, miss=0, wrong=0, halluc=0, cabs=0, miss_grounded=0)
        for f, gt in exp.items():
            b = compare_field(f, gt, pred.get(f), mappings=maps.get(f)).bucket
            d["total"] += 1
            if b == "match":
                d["passed"] += 1
            elif b == "correct_absence":
                d["passed"] += 1; d["cabs"] += 1
            elif b == "miss":
                d["miss"] += 1
                if want_grounded and not is_empty(gt) and grounded(gt, src, nsrc, snums):
                    d["miss_grounded"] += 1
            elif b == "wrong_value":
                d["wrong"] += 1
            elif b == "hallucination":
                d["halluc"] += 1
        out.append(d)
    return out

def totals(docs):
    T = {k: sum(x[k] for x in docs) for k in ("passed", "total", "miss", "wrong", "halluc", "miss_grounded")}
    n = T["total"] or 1
    return dict(acc=100*T["passed"]/n, miss=100*T["miss"]/n, wrong=100*T["wrong"]/n,
                halluc=100*T["halluc"]/n,
                grounded=(100*T["miss_grounded"]/T["miss"] if T["miss"] else float("nan")),
                misscount=T["miss"])

def paired_ci(dd, dr):
    """dd, dr: per-doc lists (default, recall), aligned. Return (mean, lo, hi, %win) of recall-default acc."""
    Pd = np.array([x["passed"] for x in dd]); Fd = np.array([x["total"] for x in dd])
    Pr = np.array([x["passed"] for x in dr]); Fr = np.array([x["total"] for x in dr])
    rng = np.random.default_rng(SEED); n = len(Pd); diffs = []
    for _ in range(N):
        idx = rng.integers(0, n, size=n)
        a = 100*Pr[idx].sum()/Fr[idx].sum()
        b = 100*Pd[idx].sum()/Fd[idx].sum()
        diffs.append(a-b)
    diffs = np.array(diffs)
    return round(diffs.mean(),1), round(np.percentile(diffs,2.5),1), round(np.percentile(diffs,97.5),1), round(100*(diffs>0).mean())

print(f"{'model':17}{'d_acc':>7}{'d_miss':>7}{'d_wrng':>7}{'d_hal':>6}{'grnd%':>7} | "
      f"{'r_acc':>7}{'r_miss':>7}{'r_wrng':>7}{'r_hal':>6} | {'Dacc':>6} {'95% CI':>16} {'%win':>5}")
rows = []
for name, dd_dir, rr_dir in MODELS:
    dd = per_doc(dd_dir, want_grounded=True)
    dr = per_doc(rr_dir, want_grounded=False)
    D = totals(dd); R = totals(dr)
    mean, lo, hi, win = paired_ci(dd, dr)
    rows.append((name, D, R, mean, lo, hi, win))
    print(f"{name:17}{D['acc']:7.1f}{D['miss']:7.1f}{D['wrong']:7.1f}{D['halluc']:6.1f}{D['grounded']:7.1f} | "
          f"{R['acc']:7.1f}{R['miss']:7.1f}{R['wrong']:7.1f}{R['halluc']:6.1f} | "
          f"{mean:+6.1f} [{lo:+.1f},{hi:+.1f}] {win:4d}%")
