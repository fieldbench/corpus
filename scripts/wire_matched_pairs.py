#!/usr/bin/env python3
"""Wire the matched-pair synthetic documents into the corpus.

For five real-only categories, this regenerates synthetic documents against the
*same schema* as the real ones, at two realism levels (0 = clean templated,
1 = realistic prose with distractors), making each category dual-source so the
synthetic-vs-real accuracy gap can be measured holding category constant (see the
matched-pair analysis in the accompanying paper).

Deterministic: the generators are seeded, so re-running reproduces byte-identical
documents. Each generated manifest is tagged `matched_pair: true` and
`synthetic_realism: {0,1}` so the subset is filterable and never silently pooled
with the organic synthetic documents.

By default only the **realistic** level (realism 1) is written into the corpus.
The clean/templated level (realism 0) is a strawman baseline for the synthetic-
realism gradient analysis; it is trivially extractable (~100% for every model) and
would only pad the synthetic share, so it is not part of the benchmark. Pass
`--include-clean` to also emit realism 0 for reproducing the full gradient.

Usage:
    python3 scripts/wire_matched_pairs.py                  # realistic synth only (benchmark)
    python3 scripts/wire_matched_pairs.py --include-clean  # + clean level (analysis)
    python3 scripts/wire_matched_pairs.py --n 40           # docs per realism level
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
GEN = ROOT / "scripts" / "sources"

# category -> generator module file
CATS = {
    "medical_records": "synthetic_medical.py",
    "legal_filings": "synthetic_legal.py",
    "contracts": "synthetic_contracts.py",
    "sec_filings": "synthetic_sec.py",
    "receipts": "synthetic_receipts.py",
}


def _load_main(pyfile: pathlib.Path):
    spec = importlib.util.spec_from_file_location(pyfile.stem, pyfile)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.main


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40, help="docs per realism level per category")
    ap.add_argument("--include-clean", action="store_true",
                    help="also emit realism-0 (clean strawman) for gradient analysis")
    args = ap.parse_args()
    levels = (0, 1) if args.include_clean else (1,)

    for cat, genfile in CATS.items():
        outdir = ROOT / cat
        main_fn = _load_main(GEN / genfile)
        for realism in levels:
            main_fn(["--out", str(outdir), "--n", str(args.n), "--realism", str(realism)])
        # tag every matched-pair manifest so the subset is filterable
        tagged = 0
        for mf in (outdir / "manifests").glob("synth-*-r*-*.json"):
            m = json.loads(mf.read_text())
            if m.get("source") != "synthetic":
                continue
            realism = 1 if "-r1-" in mf.name else 0
            m["matched_pair"] = True
            m["synthetic_realism"] = realism
            mf.write_text(json.dumps(m, indent=2) + "\n")
            tagged += 1
        print(f"{cat}: wired {tagged} matched-pair synthetic docs "
              f"(alongside real docs), 2 realism levels")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
