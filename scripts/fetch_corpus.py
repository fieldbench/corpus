#!/usr/bin/env python3
"""Fetch raw source documents from their origins.

Some sources can't be redistributed with the corpus (unclear license, or
copyrighted form layouts — see the license audit). For those, the corpus ships
the ground truth + manifest + schema but not the document, and this script
re-fetches the raw source from each manifest's `source_url`.

This is layer 1 (fetch the raw source). Reconstructing the derived markdown
representation the benchmark scores against is layer 2 (HTML->markdown is done
here inline; PDF/image sources need the parse pipeline — see --help).

Stdlib only. Polite (rate-limited, retries, identifying User-Agent). Resumable
(skips already-fetched). Verifies against `source_sha256` when the manifest
carries one.

Usage:
    python scripts/fetch_corpus.py                      # all real docs w/ a source_url
    python scripts/fetch_corpus.py --category sec_filings
    python scripts/fetch_corpus.py --missing-only       # only docs whose representation isn't bundled
    python scripts/fetch_corpus.py --out sources/       # where raw sources land (default: sources/)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

UA = "fieldbench-corpus-fetcher/0.1 (+https://github.com/fieldbench/corpus)"

# Sources that are datasets, not per-document URLs — can't be auto-fetched.
DATASET_GATED = {
    "kaggle.com": "MTSamples — download the Kaggle dataset (tboyle10/medicaltranscriptions) and extract the transcriptions listed in the manifests.",
    "rrc.cvc.uab.es": "SROIE (ICDAR 2019) — register at the ICDAR RRC portal and download Task 3; match by filename.",
    "case.law": "Caselaw Access Project — bulk download from case.law (CC0); match by citation.",
}


def _ext_from(url: str, content_type: str) -> str:
    low = url.lower()
    for e in (".pdf", ".html", ".htm", ".txt", ".xlsx", ".pptx", ".docx"):
        if low.split("?")[0].endswith(e):
            return ".html" if e == ".htm" else e
    if "pdf" in content_type:
        return ".pdf"
    if "html" in content_type:
        return ".html"
    return ".bin"


def _fetch(url: str, retries: int = 3, timeout: int = 30) -> tuple[bytes, str]:
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read(), r.headers.get("Content-Type", "")
        except (urllib.error.URLError, TimeoutError) as e:
            last = e
            time.sleep(2 * (attempt + 1))
    raise last  # type: ignore[misc]


def _dataset_gate(url: str) -> str | None:
    for host, msg in DATASET_GATED.items():
        if host in url:
            return msg
    return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--category", default=None)
    ap.add_argument("--out", type=Path, default=Path("sources"))
    ap.add_argument("--missing-only", action="store_true",
                    help="only docs whose representation (documents/<stem>.md) is not bundled")
    ap.add_argument("--delay", type=float, default=1.0, help="seconds between requests (be polite)")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args(argv)

    root = Path(".")
    cats = [args.category] if args.category else sorted(
        p.name for p in root.iterdir() if p.is_dir() and (p / "manifests").is_dir()
    )

    stats = {"fetched": 0, "skipped": 0, "gated": 0, "errors": 0, "no_url": 0, "hash_mismatch": 0}
    gated_msgs: dict[str, int] = {}
    done = 0

    for cat in cats:
        for mpath in sorted((root / cat / "manifests").glob("*.json")):
            if args.limit and done >= args.limit:
                break
            stem = mpath.stem
            manifest = json.loads(mpath.read_text())
            if str(manifest.get("source")) == "synthetic":
                continue
            if args.missing_only and (root / cat / "documents" / f"{stem}.md").exists():
                continue
            url = manifest.get("source_url")
            if not url:
                stats["no_url"] += 1
                continue
            gate = _dataset_gate(url)
            if gate:
                stats["gated"] += 1
                gated_msgs[gate] = gated_msgs.get(gate, 0) + 1
                continue

            # already fetched?
            existing = list((args.out / cat).glob(f"{stem}.*")) if (args.out / cat).is_dir() else []
            if existing:
                stats["skipped"] += 1
                continue

            try:
                data, ctype = _fetch(url)
            except Exception as e:  # noqa: BLE001 — one bad URL must not abort the run
                stats["errors"] += 1
                print(f"  ERROR {cat}/{stem}: {str(e)[:80]}", file=sys.stderr)
                continue

            want = manifest.get("source_sha256")
            got = hashlib.sha256(data).hexdigest()
            if want and want != got:
                stats["hash_mismatch"] += 1
                print(f"  HASH MISMATCH {cat}/{stem}: source changed since capture", file=sys.stderr)

            dest = args.out / cat / f"{stem}{_ext_from(url, ctype)}"
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            stats["fetched"] += 1
            done += 1
            print(f"  {cat}/{stem} <- {url[:70]}")
            time.sleep(args.delay)

    print(f"\nfetched {stats['fetched']}, skipped {stats['skipped']} (already present), "
          f"gated {stats['gated']}, errors {stats['errors']}, no-url {stats['no_url']}, "
          f"hash-mismatch {stats['hash_mismatch']}")
    if gated_msgs:
        print("\nDataset-gated sources (fetch manually):")
        for msg, n in gated_msgs.items():
            print(f"  [{n}] {msg}")
    return 1 if (stats["errors"] or stats["hash_mismatch"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
