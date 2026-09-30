#!/usr/bin/env python3
"""Regenerate Appendix G Table 13 (tab:app-aa) body: per-category (medical_records,
legal_filings), REAL docs, default vs recall prompt, for ALL 9 models.

Reuses intervention_full_stats' per-doc scorer but splits by category.
Row order matches Table 10 (sorted by Delta-acc); gpt-4o-mini last (control, dagger).
Emits longtable rows: model & cat & prompt & acc & match & wrong & miss & halluc & corr-abs.
"""
import json, glob, os, pathlib, sys
sys.path.insert(0, str(pathlib.Path.home() / "dev/fieldbench/fieldbench/src"))
from fieldbench.scoring import compare_field
from fieldbench.corpus import _schema_mappings

CORPUS = pathlib.Path.home() / "dev/fieldbench/corpus"
DATA = pathlib.Path.home() / "dev/fieldbench/data"
cache = {}

# (display, default-dir, recall-dir), order = Table 10 (Delta-acc desc); mini last
MODELS = [
    ("gpt-4o",            "preds-v0.2/gpt-4o",            "preds-antiabstain/gpt-4o"),
    ("Sonnet-4.5",        "preds-v0.2/sonnet-4-5",        "preds-antiabstain/sonnet-4-5"),
    ("gemini-2.5-pro",    "preds-extra/gemini-2.5-pro",   "preds-antiabstain-extra/gemini-2.5-pro"),
    ("deepseek-chat",     "preds-extra/deepseek-chat",    "preds-antiabstain-extra/deepseek-chat"),
    ("qwen-2.5-7b",       "preds-extra/qwen-2.5-7b",      "preds-antiabstain-extra/qwen-2.5-7b"),
    ("gemini-2.5-flash",  "preds-extra/gemini-2.5-flash", "preds-antiabstain-extra/gemini-2.5-flash"),
    ("llama-3.1-8b",      "preds-extra/llama-3.1-8b",     "preds-antiabstain-extra/llama-3.1-8b"),
    ("llama-3.3-70b",     "preds-extra/llama-3.3-70b",    "preds-antiabstain-extra/llama-3.3-70b"),
    ("gpt-4o-mini",       "preds-v0.2/gpt-4o-mini",       "preds-antiabstain/gpt-4o-mini"),
]
CATLABEL = {"medical_records": "medical", "legal_filings": "legal"}

def real_docs(cat):
    o = []
    for man in glob.glob(f"{CORPUS}/{cat}/manifests/*.json"):
        m = json.load(open(man))
        if str(m.get("source", "")) == "real":
            o.append((os.path.basename(man)[:-5], m.get("schema")))
    return sorted(o)

RD = {c: real_docs(c) for c in CATLABEL}

def score(pdir, cat):
    t = {"match": 0, "wrong_value": 0, "miss": 0, "hallucination": 0, "correct_absence": 0}
    for stem, schema in RD[cat]:
        pp = DATA / pdir / f"{stem}.json"
        pred = json.load(open(pp)) if pp.exists() else {}
        exp = json.load(open(f"{CORPUS}/{cat}/expected/{stem}.expected.json"))
        maps = _schema_mappings(CORPUS, schema, cache)
        for f, gt in exp.items():
            t[compare_field(f, gt, pred.get(f), mappings=maps.get(f)).bucket] += 1
    n = sum(t.values()) or 1
    r = lambda k: 100 * t[k] / n
    acc = r("match") + r("correct_absence")
    return acc, r("match"), r("wrong_value"), r("miss"), r("hallucination"), r("correct_absence")

rows = []
for mi, (disp, dd, rr) in enumerate(MODELS):
    tag = "~$\\dagger$" if disp == "gpt-4o-mini" else ""
    for ci, cat in enumerate(CATLABEL):
        for prompt, pdir in [("default", dd), ("recall", rr)]:
            acc, ma, wr, mi_, ha, ca = score(pdir, cat)
            model_cell = f"{disp}{tag}" if (ci == 0 and prompt == "default") else ""
            cat_cell = CATLABEL[cat] if prompt == "default" else ""
            rows.append(f"{model_cell} & {cat_cell} & {prompt} & {acc:.1f} & {ma:.1f} & {wr:.1f} & {mi_:.1f} & {ha:.1f} & {ca:.1f} \\\\")
    if mi != len(MODELS) - 1:
        rows.append("\\addlinespace")

out = pathlib.Path.home() / "dev/fieldbench/paper/appG_body.tex"
out.write_text("\n".join(rows) + "\n")
print(f"wrote {out}: {len(MODELS)} models x 2 cats x 2 prompts")
print("\n--- CONSISTENCY CHECK: gpt-4o/Sonnet/mini vs existing hardcoded App G ---")
EXPECT = {  # from current tab:app-aa
    ("gpt-4o","medical","default"): (58.2,15.8,7.7,34.2,0.0,42.3),
    ("gpt-4o","legal","recall"):    (79.2,77.0,18.2,0.0,2.7,2.2),
    ("Sonnet-4.5","medical","recall"):(66.2,26.0,16.3,15.3,2.2,40.2),
    ("gpt-4o-mini","legal","default"):(86.4,86.0,9.2,0.0,4.4,0.5),
}
dirs = {x[0]: (x[1], x[2]) for x in MODELS}
for (m,c,p),exp in EXPECT.items():
    catk = "medical_records" if c=="medical" else "legal_filings"
    pdir = dirs[m][0] if p=="default" else dirs[m][1]
    got = tuple(round(v,1) for v in score(pdir, catk))
    print(f"  {m:12} {c:8} {p:8} exp={exp} got={got} {'OK' if got==exp else '<-- DIFF'}")
