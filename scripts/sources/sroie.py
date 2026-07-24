#!/usr/bin/env python3
"""SROIE dataset sourcing script for the FieldBench corpus.

Fetches receipts from the SROIE (Scanned Receipt OCR and Information Extraction)
dataset, converts them to FieldBench corpus format, and writes them into the invoices
category.

SROIE is an ICDAR 2019 competition dataset containing receipt images and
annotated ground truth for four fields: company, date, address, total.

Dataset:
  - Official: https://rrc.cvc.uab.es/?ch=13 (requires registration)
  - Mirror: https://github.com/zzzDavid/ICDAR-2019-SROIE (Task 3 annotations)

Why we use SROIE:
  - Pre-annotated ground truth means no manual review needed for these fields
  - Receipt images exercise OCR and layout analysis
  - Diverse retailers from Singapore give variety beyond US-centric data

Prerequisites:
  - FieldBench parse service running at http://127.0.0.1:9411/parse
    (or pass --parse-url to override)
  - httpx installed

Usage:
  python scripts/sources/sroie.py --limit 20
  python scripts/sources/sroie.py --parse-url http://localhost:9411/parse --limit 50
  python scripts/sources/sroie.py --dataset-path ./sroie-dataset/

Steps the script performs:
  1. Download the SROIE Task 3 dataset (images + JSON annotations)
  2. For each receipt image, POST it to FieldBench parse service to get markdown
  3. Load the SROIE JSON annotation for that receipt
  4. Convert SROIE field names to FieldBench invoice_basic schema:
       - company -> merchant_name
       - date -> date (normalized to YYYY-MM-DD)
       - total -> total_amount
       - address stays as context only (not in our schema)
  5. Write document, expected JSON, and manifest to the corpus
  6. Skip receipts that already exist (idempotent)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import zipfile
from pathlib import Path

import httpx

CORPUS_ROOT = Path(__file__).resolve().parent.parent.parent
INVOICES_DIR = CORPUS_ROOT / "invoices"

# Mirror of SROIE Task 3 (information extraction) — the only task with
# ground truth annotations we can use for validation.
SROIE_ZIP_URL = (
    "https://github.com/zzzDavid/ICDAR-2019-SROIE/archive/refs/heads/master.zip"
)

DEFAULT_PARSE_URL = "http://127.0.0.1:9411/parse"


def _normalize_date(value: str) -> str | None:
    """Convert a SROIE date string to YYYY-MM-DD. Returns None if unparseable."""
    if not value:
        return None
    value = value.strip()

    # Already ISO
    match = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", value)
    if match:
        y, m, d = match.groups()
        return f"{y}-{m.zfill(2)}-{d.zfill(2)}"

    # DD/MM/YYYY or DD-MM-YYYY (common in SROIE)
    match = re.match(r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})", value)
    if match:
        d, m, y = match.groups()
        if len(y) == 2:
            y = "20" + y
        return f"{y}-{m.zfill(2)}-{d.zfill(2)}"

    return None


def _normalize_total(value: str) -> float | None:
    """Parse a SROIE total string to a float. Returns None if unparseable."""
    if value is None:
        return None
    cleaned = re.sub(r"[^\d.,\-]", "", str(value))
    if not cleaned:
        return None
    # Assume period is decimal separator (SROIE uses periods)
    cleaned = cleaned.replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def download_dataset(dest: Path) -> Path:
    """Download and extract the SROIE dataset. Returns the extracted root directory."""
    if dest.exists() and any(dest.iterdir()):
        print(f"[sroie] Dataset already downloaded at {dest}", file=sys.stderr)
        return dest

    dest.mkdir(parents=True, exist_ok=True)
    zip_path = dest / "sroie.zip"
    print(f"[sroie] Downloading dataset from {SROIE_ZIP_URL}", file=sys.stderr)

    with httpx.stream("GET", SROIE_ZIP_URL, follow_redirects=True, timeout=600.0) as resp:
        resp.raise_for_status()
        with open(zip_path, "wb") as f:
            for chunk in resp.iter_bytes(chunk_size=1024 * 1024):
                f.write(chunk)

    print(f"[sroie] Extracting to {dest}", file=sys.stderr)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(dest)

    zip_path.unlink()
    return dest


def find_task3_pairs(dataset_root: Path) -> list[tuple[Path, Path]]:
    """Find all (image, annotation JSON) pairs in the SROIE dataset.

    The zzzDavid mirror stores images in `data/img/NNN.jpg` and Task 3
    key-value annotations in `data/key/NNN.json`, matched by numeric
    stem. Falls back to looking for `.txt` or `.json` files co-located
    with images for other mirror layouts.
    """
    pairs: list[tuple[Path, Path]] = []

    # Primary layout: data/key/*.json + data/img/*.jpg (zzzDavid mirror)
    key_dirs = list(dataset_root.rglob("data/key"))
    img_dirs = list(dataset_root.rglob("data/img"))
    if key_dirs and img_dirs:
        key_dir = key_dirs[0]
        img_dir = img_dirs[0]
        for ann in sorted(key_dir.glob("*.json")):
            image = img_dir / f"{ann.stem}.jpg"
            if not image.exists():
                image = img_dir / f"{ann.stem}.png"
            if image.exists():
                pairs.append((image, ann))
        if pairs:
            return pairs

    # Fallback: .txt or .json co-located with images
    candidates = list(dataset_root.rglob("*.jpg")) + list(dataset_root.rglob("*.png"))
    for image in candidates:
        for suffix in (".json", ".txt"):
            ann = image.with_suffix(suffix)
            if ann.exists():
                try:
                    content = ann.read_text(encoding="utf-8", errors="replace")
                    if '"company"' in content or "company:" in content.lower():
                        pairs.append((image, ann))
                        break
                except Exception:
                    continue

    return pairs


def parse_sroie_annotation(txt_path: Path) -> dict:
    """Parse a SROIE annotation file into a dict.

    SROIE annotations come in two formats depending on the mirror:
      1. JSON: {"company": "...", "date": "...", "address": "...", "total": "..."}
      2. Key-value lines: company:XXX\\ndate:XXX\\naddress:XXX\\ntotal:XXX

    Returns a dict with normalized keys.
    """
    content = txt_path.read_text(encoding="utf-8", errors="replace").strip()
    if not content:
        return {}

    # Try JSON first
    if content.startswith("{"):
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

    # Fall back to key:value format
    result: dict = {}
    for line in content.splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            result[key.strip().lower()] = value.strip()

    return result


def parse_image_to_markdown(image_path: Path, parse_url: str, client: httpx.Client) -> str:
    """POST an image to FieldBench's parse service and return the markdown output."""
    with open(image_path, "rb") as f:
        files = {"file": (image_path.name, f, "image/jpeg")}
        resp = client.post(parse_url, files=files, timeout=300.0)

    resp.raise_for_status()
    data = resp.json()
    return data.get("markdown", "")


def parse_image_local(image_path: Path) -> str:
    """Run docling in-process to convert a receipt image to markdown.

    Same approach as edgar.py --local-parse: import docling lazily,
    hand it the image, and export to markdown. Works for JPG/PNG
    receipt images without a running fieldbench cluster.
    """
    from docling.document_converter import DocumentConverter

    converter = DocumentConverter()
    result = converter.convert(str(image_path))
    return result.document.export_to_markdown()


def convert_to_fieldbench_format(sroie_annotation: dict) -> dict:
    """Convert a SROIE annotation dict to a FieldBench invoice_basic expected output."""
    return {
        "merchant_name": sroie_annotation.get("company") or None,
        "date": _normalize_date(sroie_annotation.get("date", "")),
        "total_amount": _normalize_total(sroie_annotation.get("total", "")),
        "subtotal": None,
        "tax": None,
        "currency": "SGD",  # SROIE is Singaporean, default SGD
        "items": None,
    }


def write_sample(
    receipt_id: str,
    markdown: str,
    expected: dict,
    source_image: str,
) -> None:
    """Write a SROIE receipt into the corpus as document, expected, and manifest."""
    doc_path = INVOICES_DIR / "documents" / f"sroie_{receipt_id}.md"
    exp_path = INVOICES_DIR / "expected" / f"sroie_{receipt_id}.expected.json"
    man_path = INVOICES_DIR / "manifests" / f"sroie_{receipt_id}.json"

    doc_path.write_text(markdown + "\n")
    exp_path.write_text(json.dumps(expected, indent=2) + "\n")

    manifest = {
        "filename": doc_path.name,
        "source_name": "SROIE Dataset (ICDAR 2019)",
        "source_url": "https://rrc.cvc.uab.es/?ch=13",
        "license": "CC BY 4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "attribution": "ICDAR 2019 Robust Reading Challenge on SROIE",
        "original_format": "JPEG image (OCR)",
        "original_image": source_image,
        "r2_url": None,
        "pages": 1,
        "added_date": "2026-04-12",
        "added_by": "corpus-bootstrap",
        "schema": "invoices/schemas/invoice_basic.yaml",
        "notes": "Singaporean receipt from SROIE Task 3. Ground truth from dataset annotations (company, date, total). Subtotal, tax, and line items left null — SROIE doesn't annotate them.",
    }
    man_path.write_text(json.dumps(manifest, indent=2) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of receipts to process (default: 20)",
    )
    parser.add_argument(
        "--parse-url",
        default=DEFAULT_PARSE_URL,
        help=f"FieldBench parse service URL (default: {DEFAULT_PARSE_URL})",
    )
    parser.add_argument(
        "--dataset-path",
        type=Path,
        default=CORPUS_ROOT / ".sroie-cache",
        help="Path to download and cache the SROIE dataset",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Skip download and use an already-extracted dataset at --dataset-path",
    )
    parser.add_argument(
        "--local-parse",
        action="store_true",
        help=(
            "Run docling in-process instead of calling the OCR. "
            "Use when the cluster isn't running. Requires `uv run --with docling`."
        ),
    )
    args = parser.parse_args()

    # Ensure target dirs exist
    for sub in ("documents", "expected", "manifests"):
        (INVOICES_DIR / sub).mkdir(parents=True, exist_ok=True)

    # Download dataset
    if not args.skip_download:
        download_dataset(args.dataset_path)

    # Find all annotated receipts
    pairs = find_task3_pairs(args.dataset_path)
    if not pairs:
        print(
            f"[sroie] No annotated receipts found in {args.dataset_path}. "
            f"Check that the dataset download extracted correctly.",
            file=sys.stderr,
        )
        return 1

    print(f"[sroie] Found {len(pairs)} annotated receipts", file=sys.stderr)

    # Process receipts
    processed = 0
    skipped = 0
    failed = 0

    if args.local_parse:
        try:
            import docling.document_converter  # noqa: F401
        except ImportError:
            print(
                "[sroie] --local-parse requires docling. Re-run with:\n"
                "        uv run --with docling python scripts/sources/sroie.py ...",
                file=sys.stderr,
            )
            return 1

    with httpx.Client() as client:
        for i, (image, txt) in enumerate(pairs):
            if processed >= args.limit:
                break

            receipt_id = image.stem
            doc_path = INVOICES_DIR / "documents" / f"sroie_{receipt_id}.md"
            if doc_path.exists():
                skipped += 1
                continue

            try:
                annotation = parse_sroie_annotation(txt)
                if not annotation or "company" not in annotation:
                    failed += 1
                    continue

                if args.local_parse:
                    markdown = parse_image_local(image)
                else:
                    markdown = parse_image_to_markdown(image, args.parse_url, client)

                if not markdown.strip():
                    print(f"[sroie] Empty markdown for {receipt_id}", file=sys.stderr)
                    failed += 1
                    continue

                expected = convert_to_fieldbench_format(annotation)
                write_sample(receipt_id, markdown, expected, image.name)

                processed += 1
                print(f"[sroie] ({processed}/{args.limit}) {receipt_id}", file=sys.stderr)

                if not args.local_parse:
                    time.sleep(0.5)

            except httpx.HTTPError as e:
                print(f"[sroie] HTTP error on {receipt_id}: {e}", file=sys.stderr)
                failed += 1
            except Exception as e:
                print(f"[sroie] Error on {receipt_id}: {e}", file=sys.stderr)
                failed += 1

    print(
        f"\n[sroie] Done. Processed: {processed}, Skipped: {skipped}, Failed: {failed}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
