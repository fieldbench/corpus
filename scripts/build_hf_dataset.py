#!/usr/bin/env python3
"""Pack the corpus into a single JSONL for HuggingFace `load_dataset`.

One record per document:
  { doc_id, category, source, original_format, document, expected, schema }
`expected` is the ground-truth field map serialized as a JSON string (categories
have different field sets, so a fixed nested schema is not possible).

    python scripts/build_hf_dataset.py -o fieldbench_corpus.jsonl

Then (once you have an HF token) push with the datasets library or
`huggingface-cli upload` — see huggingface/PUSH.md.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(".")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--output", type=Path, default=Path("fieldbench_corpus.jsonl"))
    args = ap.parse_args(argv)

    cats = sorted(p.name for p in ROOT.iterdir() if p.is_dir() and (p / "manifests").is_dir())
    n = 0
    with args.output.open("w") as out:
        for cat in cats:
            for exp_path in sorted((ROOT / cat / "expected").glob("*.expected.json")):
                stem = exp_path.name[: -len(".expected.json")]
                man_path = ROOT / cat / "manifests" / f"{stem}.json"
                doc_path = ROOT / cat / "documents" / f"{stem}.md"
                if not (man_path.exists() and doc_path.exists()):
                    continue
                man = json.loads(man_path.read_text())
                rec = {
                    "doc_id": stem,
                    "category": cat,
                    "source": man.get("source", "unknown"),
                    "original_format": man.get("original_format"),
                    "schema": Path(man.get("schema", "")).name,
                    "document": doc_path.read_text(),
                    "expected": json.dumps(json.loads(exp_path.read_text())),
                }
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                n += 1

    print(f"wrote {n} records to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
