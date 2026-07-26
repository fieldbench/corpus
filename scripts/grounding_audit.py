#!/usr/bin/env python3
"""Grounding audit: are the fields the frontier models MISS actually in the source?

Tests the over-abstention thesis. For each non-null GT field, check whether its
value is present in the source text ("grounded"). Then, of the fields a model
returned null for (a `miss`), how many were grounded — i.e. genuine
over-abstention (the value was there, the model declined) vs. defensible
(value not in the parsed source).

If frontier-model misses are overwhelmingly grounded across the categories where
gpt-4o-mini wins, the inversion is a real recall/precision behavior difference,
not a GT-anchoring artifact.

Usage:
    python grounding_audit.py --corpus <corpus> \
        --preds gpt-4o=/tmp/fb-live/gpt-4o sonnet=/tmp/fb-live/sonnet \
        --categories medical_records legal_filings contracts
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from fieldbench.scoring import compare_field, is_empty, normalize_date, to_number


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(s).lower()).strip()


def _scalars(v):
    """Flatten a value to its scalar leaves."""
    if isinstance(v, dict):
        for x in v.values():
            yield from _scalars(x)
    elif isinstance(v, list):
        for x in v:
            yield from _scalars(x)
    elif not is_empty(v):
        yield v


def source_numbers(source: str) -> set[float]:
    """Every numeric token in the source, parsed to a rounded float — so a GT
    number can be matched numerically regardless of formatting (commas,
    currency, trailing zeros)."""
    nums = set()
    for tok in re.findall(r"[-+]?\$?\d[\d,]*(?:\.\d+)?", source):
        try:
            nums.add(round(float(tok.replace("$", "").replace(",", "")), 2))
        except ValueError:
            pass
    return nums


def _grounded_scalar(leaf, source: str, nsource: str, snums: set[float]) -> bool:
    # Number: match against parsed source numbers within the scorer's tolerance.
    n = to_number(leaf)
    if n is not None:
        return any(abs(n - x) <= 0.01 for x in snums)
    # Date: try common renderings, else fall back to string match below.
    d = normalize_date(leaf)
    if d:
        y, m, dd = d.split("-")
        renders = [d, f"{int(m)}/{int(dd)}/{y}", f"{m}/{dd}/{y}", f"{int(m)}/{int(dd)}/{y[2:]}"]
        if any(r in source for r in renders):
            return True
    # String: normalized substring (works for text; alphanumerics must appear in order).
    ns = _norm(str(leaf))
    return len(ns) >= 2 and ns in nsource


def grounded(value, source: str, nsource: str, snums: set[float]) -> bool:
    """Type-aware: numbers matched numerically against parsed source numbers,
    dates by rendering, strings by normalized substring. Composite value is
    grounded iff a majority of its scalar leaves are."""
    leaves = list(_scalars(value))
    if not leaves:
        return False
    hits = sum(_grounded_scalar(leaf, source, nsource, snums) for leaf in leaves)
    return hits >= (len(leaves) + 1) // 2


def audit(corpus: Path, category: str, preds: dict[str, Path]) -> dict:
    cat = corpus / category
    per_model = {m: {"miss": 0, "miss_grounded": 0} for m in preds}
    gt_nonnull = 0
    gt_grounded = 0
    universal_miss = 0  # every model returned null for this field
    universal_miss_ungrounded = 0  # ...and the matcher can't find it either = likely coverage gap

    for exp_path in sorted((cat / "expected").glob("*.expected.json")):
        stem = exp_path.name[: -len(".expected.json")]
        doc = cat / "documents" / f"{stem}.md"
        if not doc.exists():
            continue
        source = doc.read_text()
        nsource = _norm(source)
        snums = source_numbers(source)
        expected = json.loads(exp_path.read_text())
        loaded = {m: json.loads((d / f"{stem}.json").read_text()) if (d / f"{stem}.json").exists() else {}
                  for m, d in preds.items()}
        for field, gt in expected.items():
            if is_empty(gt):
                continue
            gt_nonnull += 1
            g = grounded(gt, source, nsource, snums)
            gt_grounded += g
            missed = 0
            for m, pred in loaded.items():
                r = compare_field(field, gt, pred.get(field))
                if r.bucket == "miss":
                    per_model[m]["miss"] += 1
                    per_model[m]["miss_grounded"] += g
                    missed += 1
            if missed == len(loaded):  # no model recovered this field
                universal_miss += 1
                universal_miss_ungrounded += not g
    return {
        "gt_nonnull": gt_nonnull,
        "gt_grounded": gt_grounded,
        "per_model": per_model,
        "universal_miss": universal_miss,
        "universal_miss_ungrounded": universal_miss_ungrounded,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True, type=Path)
    ap.add_argument("--preds", nargs="+", required=True, help="name=dir pairs")
    ap.add_argument("--categories", nargs="+", required=True)
    args = ap.parse_args(argv)
    preds = {p.split("=", 1)[0]: Path(p.split("=", 1)[1]) for p in args.preds}

    print("Coverage probe: fields NO model recovered (universal miss), and of those how many the")
    print("matcher also can't find (likely genuine coverage gap, matcher-independent numerator).\n")
    print(f"{'category':<24}{'GTf':>6}{'univ-miss':>11}{'gap(ungrnd)':>13}{'gap %of GT':>11}")
    for cat in args.categories:
        r = audit(args.corpus, cat, preds)
        n = r["gt_nonnull"] or 1
        um, gap = r["universal_miss"], r["universal_miss_ungrounded"]
        print(f"{cat:<24}{r['gt_nonnull']:>6}{um:>11}{gap:>13}{100*gap/n:>10.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
