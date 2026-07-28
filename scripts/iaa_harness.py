#!/usr/bin/env python3
"""Inter-annotator agreement (IAA) harness for the FieldBench corpus.

Measures how much a second, independent annotator agrees with the existing
ground truth — the number that establishes the corpus's GT trustworthiness.

    # 1. draw a stratified sample of REAL docs and emit blind annotation templates
    python scripts/iaa_harness.py sample --n 60 --out iaa/ --exclude insurance_claims

    # 2. annotator 2 fills each iaa/<stem>.annotate.json (WITHOUT looking at GT)

    # 3. score agreement against the existing ground truth
    python scripts/iaa_harness.py score --dir iaa/

    # 3b. or score two annotators against each other (no ground truth involved)
    python scripts/iaa_harness.py score --dir iaa_annotator_a/ --against iaa_annotator_b/

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


def _real_docs(category: str | None, exclude: set[str] | None = None):
    cats = [category] if category else sorted(
        p.name for p in ROOT.iterdir() if p.is_dir() and (p / "manifests").is_dir()
    )
    if exclude:
        cats = [c for c in cats if c not in exclude]
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
    exclude = {c.strip() for c in (args.exclude or "").split(",") if c.strip()}
    for cat, stem, m in _real_docs(args.category, exclude):
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


def _annotation(path: Path) -> dict:
    return (json.loads(path.read_text()).get("annotation")) or {}


def cmd_score(args) -> int:
    cache: dict = {}
    total = agree = 0
    per_cat = defaultdict(lambda: [0, 0])  # [agree, total]
    enum_pairs = defaultdict(list)  # field_name -> [(ref_label, ann_label)]
    disagreements = []
    scored_docs = 0
    skipped = []
    ref_name = "annotator_b" if args.against else "gt"

    for tmpl_path in sorted(args.dir.glob("*.annotate.json")):
        t = json.loads(tmpl_path.read_text())
        stem, cat = t["stem"], t["category"]
        ann2 = t.get("annotation") or {}
        if all(is_empty(v) for v in ann2.values()):
            continue  # not yet annotated
        # The field set is ALWAYS the ground-truth key list, even when scoring
        # annotator-vs-annotator. That keeps A-vs-GT, B-vs-GT and A-vs-B over
        # identical fields, so the three agreement rates compare directly.
        gt = json.loads((ROOT / cat / "expected" / f"{stem}.expected.json").read_text())
        if args.against:
            ref_path = args.against / tmpl_path.name
            if not ref_path.exists():
                skipped.append(f"{stem}: no counterpart in {args.against}")
                continue
            ref = _annotation(ref_path)
            if all(is_empty(v) for v in ref.values()):
                skipped.append(f"{stem}: counterpart not yet annotated")
                continue
        else:
            ref = gt
        fields = _schema_fields(json.loads((ROOT / cat / "manifests" / f"{stem}.json").read_text()), cache)
        scored_docs += 1
        for name in gt:
            ref_val = ref.get(name)
            a2 = ann2.get(name)
            spec = fields.get(name) or {}
            enum_opts = spec.get("options") if str(spec.get("type", "")).lower() == "enum" else None
            maps = spec.get("mappings") if isinstance(spec.get("mappings"), dict) else None
            r = compare_field(name, ref_val, a2, mappings=maps, enum_options=enum_opts)
            ok = r.passed
            total += 1
            agree += ok
            per_cat[cat][1] += 1
            per_cat[cat][0] += ok
            if str(spec.get("type", "")).lower() == "enum" or spec.get("options"):
                enum_pairs[name].append((json.dumps(ref_val), json.dumps(a2)))
            if not ok:
                disagreements.append({"doc": stem, "field": name, ref_name: ref_val, "annotator2": a2})

    if total == 0:
        print("error: no filled annotations found in", args.dir, file=sys.stderr)
        return 2

    kappas = {k: _cohen_kappa(v) for k, v in enum_pairs.items()}
    kappas = {k: v for k, v in kappas.items() if v is not None}
    report = {
        "comparison": f"{args.dir} vs {args.against}" if args.against else f"{args.dir} vs ground truth",
        "scored_docs": scored_docs,
        "fields_compared": total,
        "agreement_rate": round(agree / total, 4),
        "by_category": {c: round(a / n, 4) for c, (a, n) in sorted(per_cat.items())},
        "enum_field_cohen_kappa": {k: round(v, 4) for k, v in sorted(kappas.items())},
        "mean_enum_kappa": round(sum(kappas.values()) / len(kappas), 4) if kappas else None,
        "n_disagreements": len(disagreements),
    }
    print(json.dumps(report, indent=2))
    if skipped:
        print(f"\nskipped {len(skipped)} doc(s):", file=sys.stderr)
        for s in skipped:
            print(f"  {s}", file=sys.stderr)
    if args.disagreements:
        print("\n=== disagreements (for adjudication) ===", file=sys.stderr)
        label = "B" if args.against else "GT"
        for d in disagreements:
            print(f"  [{d['doc']}] {d['field']}: {label}={d[ref_name]!r}  A2={d['annotator2']!r}", file=sys.stderr)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample", help="draw a stratified real-doc sample + emit blind templates")
    s.add_argument("--n", type=int, default=60)
    s.add_argument("--out", type=Path, default=Path("iaa"))
    s.add_argument("--category", default=None)
    s.add_argument(
        "--exclude",
        default=None,
        help="comma-separated categories to leave out of the sample. Use for pools that "
        "carry no IAA signal — e.g. insurance_claims, whose real docs are blank form "
        "templates with nothing to extract but form_type.",
    )
    s.add_argument("--seed", type=int, default=20260724)
    s.set_defaults(func=cmd_sample)
    sc = sub.add_parser("score", help="compare filled annotations to GT; report agreement + kappa")
    sc.add_argument("--dir", type=Path, default=Path("iaa"))
    sc.add_argument(
        "--against",
        type=Path,
        default=None,
        help="score --dir against a SECOND annotator's dir instead of the ground truth, "
        "giving annotator-vs-annotator agreement. Fields compared are still the GT key "
        "list, so the rate is directly comparable to the vs-GT runs.",
    )
    sc.add_argument("--disagreements", action="store_true", help="list every disagreement for adjudication")
    sc.set_defaults(func=cmd_score)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
