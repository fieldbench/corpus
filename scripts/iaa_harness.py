#!/usr/bin/env python3
"""Inter-annotator agreement (IAA) harness for the FieldBench corpus.

Measures how much a second, independent annotator agrees with the existing
ground truth — the number that establishes the corpus's GT trustworthiness.

    # 1. draw a stratified sample of REAL docs and emit blind annotation templates
    python scripts/iaa_harness.py sample --n 60 --out iaa/

    # 2. annotator 2 fills each iaa/<stem>.annotate.json (WITHOUT looking at GT)

    # 3. score agreement against the existing ground truth
    python scripts/iaa_harness.py score --dir iaa/

Synthetic documents are excluded by default — their GT is correct by construction,
so they carry no IAA signal. Real-document GT is what needs validating.

Requires the canonical scorer for type-aware comparison:  pip install fieldbench
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

try:
    import yaml
except ImportError:
    print("error: pyyaml required (pip install pyyaml)", file=sys.stderr)
    raise

try:
    from fieldbench.scoring import compare_field, is_empty
except ImportError:
    print("error: fieldbench required for type-aware comparison (pip install fieldbench)", file=sys.stderr)
    raise

ROOT = Path(".")


def _real_docs(category: str | None):
    cats = [category] if category else sorted(
        p.name for p in ROOT.iterdir() if p.is_dir() and (p / "manifests").is_dir()
    )
    for cat in cats:
        for mpath in sorted((ROOT / cat / "manifests").glob("*.json")):
            m = json.loads(mpath.read_text())
            if m.get("source") == "real":
                stem = mpath.stem
                exp = ROOT / cat / "expected" / f"{stem}.expected.json"
                if exp.exists():
                    yield cat, stem, m


def _schema_fields(manifest: dict, cache: dict) -> dict:
    ref = manifest.get("schema")
    if not ref:
        return {}
    if ref not in cache:
        try:
            cache[ref] = (yaml.safe_load((ROOT / ref).read_text()) or {}).get("fields") or {}
        except Exception:  # noqa: BLE001
            cache[ref] = {}
    return cache[ref]


def cmd_sample(args) -> int:
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    by_cat = defaultdict(list)
    for cat, stem, m in _real_docs(args.category):
        by_cat[cat].append((stem, m))
    if not by_cat:
        print("error: no real documents found", file=sys.stderr)
        return 2

    rng = random.Random(args.seed)
    for docs in by_cat.values():
        rng.shuffle(docs)
    # round-robin across categories until n reached (stratified)
    order = sorted(by_cat)
    picked = []
    i = 0
    while len(picked) < args.n and any(by_cat[c] for c in order):
        c = order[i % len(order)]
        if by_cat[c]:
            picked.append((c, *by_cat[c].pop()))
        i += 1

    cache: dict = {}
    worklist = []
    for cat, stem, m in picked:
        fields = _schema_fields(m, cache)
        template = {
            "stem": stem,
            "category": cat,
            "document": f"{cat}/documents/{stem}.md",
            "instructions": "Read the document, then fill each value with what the document says, "
            "or null if the field is not present. Do NOT open the ground truth. Save this file in place.",
            "annotation": {name: None for name in fields},
        }
        (out / f"{stem}.annotate.json").write_text(json.dumps(template, indent=2) + "\n")
        worklist.append({"stem": stem, "category": cat})

    (out / "worklist.json").write_text(json.dumps(worklist, indent=2) + "\n")
    print(f"wrote {len(picked)} blind annotation templates to {out}/ "
          f"({', '.join(f'{c}:{sum(1 for x in picked if x[0]==c)}' for c in order if any(x[0]==c for x in picked))})")
    print("Annotator 2: fill each <stem>.annotate.json, then run `score`.", file=sys.stderr)
    return 0


def _cohen_kappa(pairs: list[tuple[str, str]]) -> float | None:
    """Cohen's kappa over (annotator1, annotator2) categorical labels."""
    n = len(pairs)
    if n == 0:
        return None
    agree = sum(a == b for a, b in pairs) / n
    c1 = Counter(a for a, _ in pairs)
    c2 = Counter(b for _, b in pairs)
    pe = sum((c1[k] / n) * (c2[k] / n) for k in set(c1) | set(c2))
    return None if pe >= 1.0 else (agree - pe) / (1 - pe)


def cmd_score(args) -> int:
    cache: dict = {}
    total = agree = 0
    per_cat = defaultdict(lambda: [0, 0])  # [agree, total]
    enum_pairs = defaultdict(list)  # field_name -> [(gt_label, ann2_label)]
    disagreements = []
    scored_docs = 0

    for tmpl_path in sorted(args.dir.glob("*.annotate.json")):
        t = json.loads(tmpl_path.read_text())
        stem, cat = t["stem"], t["category"]
        ann2 = t.get("annotation") or {}
        if all(is_empty(v) for v in ann2.values()):
            continue  # not yet annotated
        gt = json.loads((ROOT / cat / "expected" / f"{stem}.expected.json").read_text())
        fields = _schema_fields(json.loads((ROOT / cat / "manifests" / f"{stem}.json").read_text()), cache)
        scored_docs += 1
        for name, gt_val in gt.items():
            a2 = ann2.get(name)
            r = compare_field(name, gt_val, a2)
            ok = r.passed
            total += 1
            agree += ok
            per_cat[cat][1] += 1
            per_cat[cat][0] += ok
            spec = fields.get(name) or {}
            if str(spec.get("type", "")).lower() == "enum" or spec.get("options"):
                enum_pairs[name].append((json.dumps(gt_val), json.dumps(a2)))
            if not ok:
                disagreements.append({"doc": stem, "field": name, "gt": gt_val, "annotator2": a2})

    if total == 0:
        print("error: no filled annotations found in", args.dir, file=sys.stderr)
        return 2

    kappas = {k: _cohen_kappa(v) for k, v in enum_pairs.items()}
    kappas = {k: v for k, v in kappas.items() if v is not None}
    report = {
        "scored_docs": scored_docs,
        "fields_compared": total,
        "agreement_rate": round(agree / total, 4),
        "by_category": {c: round(a / n, 4) for c, (a, n) in sorted(per_cat.items())},
        "enum_field_cohen_kappa": {k: round(v, 4) for k, v in sorted(kappas.items())},
        "mean_enum_kappa": round(sum(kappas.values()) / len(kappas), 4) if kappas else None,
        "n_disagreements": len(disagreements),
    }
    print(json.dumps(report, indent=2))
    if args.disagreements:
        print("\n=== disagreements (for adjudication) ===", file=sys.stderr)
        for d in disagreements:
            print(f"  [{d['doc']}] {d['field']}: GT={d['gt']!r}  A2={d['annotator2']!r}", file=sys.stderr)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample", help="draw a stratified real-doc sample + emit blind templates")
    s.add_argument("--n", type=int, default=60)
    s.add_argument("--out", type=Path, default=Path("iaa"))
    s.add_argument("--category", default=None)
    s.add_argument("--seed", type=int, default=20260724)
    s.set_defaults(func=cmd_sample)
    sc = sub.add_parser("score", help="compare filled annotations to GT; report agreement + kappa")
    sc.add_argument("--dir", type=Path, default=Path("iaa"))
    sc.add_argument("--disagreements", action="store_true", help="list every disagreement for adjudication")
    sc.set_defaults(func=cmd_score)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
