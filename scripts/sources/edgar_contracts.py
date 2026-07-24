#!/usr/bin/env python3
"""Source material contracts from SEC EDGAR 8-K Exhibit 10 filings.

Searches for 8-K filings, finds their Exhibit 10.x attachments (material
contracts), downloads the exhibit HTML, and parses to markdown via fieldbench.

Unlike sec_filings sourcing, contracts require manual annotation —
the EDGAR index doesn't contain contract terms. This script downloads
and parses the documents; expected JSON must be created by a human
reading each contract.

Usage:
  uv run --with httpx python scripts/sources/edgar_contracts.py --limit 20
  uv run --with httpx python scripts/sources/edgar_contracts.py --limit 100 --local-parse

After running, manually create expected JSON for each document:
  corpus/contracts/expected/<sample_id>.expected.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import httpx

CORPUS_ROOT = Path(__file__).resolve().parent.parent.parent
CONTRACTS_DIR = CORPUS_ROOT / "contracts"

USER_AGENT = "FieldBench Corpus bot@getfieldbench.dev"
RATE_LIMIT_DELAY = 0.125
PER_FILING_DELAY = 1.5
DEFAULT_FIELDBENCH_SERVER_URL = "http://127.0.0.1:9411"
PARSE_TIMEOUT = 600.0


def _client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate"},
        timeout=60.0,
        follow_redirects=True,
    )


def _parse_client() -> httpx.Client:
    return httpx.Client(timeout=PARSE_TIMEOUT)


def search_8k_filings(limit: int, client: httpx.Client) -> list[dict]:
    """Search EDGAR for recent 8-K filings."""
    url = "https://efts.sec.gov/LATEST/search-index"
    hits = []
    offset = 0

    while len(hits) < limit:
        resp = client.get(url, params={
            "q": "exhibit 10",
            "forms": "8-K",
            "from": offset,
        })
        if resp.status_code != 200:
            break

        data = resp.json()
        page_hits = data.get("hits", {}).get("hits", [])
        if not page_hits:
            break

        for hit in page_hits:
            src = hit.get("_source", {})
            hits.append({
                "accession": src.get("adsh") or hit.get("_id", "").split(":")[0],
                "cik": (src.get("ciks", [None]) or [None])[0],
                "file_date": src.get("file_date"),
                "display_names": src.get("display_names", []),
            })
            if len(hits) >= limit:
                break

        offset += 100
        time.sleep(RATE_LIMIT_DELAY)

    return hits


def find_exhibit_10(cik: str, accession: str, client: httpx.Client) -> str | None:
    """Find the Exhibit 10.x document in an 8-K filing's index.

    Returns the filename of the first Exhibit 10 document, or None.
    """
    cik_int = str(int(cik))
    acc_no_dash = accession.replace("-", "")
    url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_no_dash}/index.json"

    resp = client.get(url)
    if resp.status_code != 200:
        return None

    data = resp.json()
    items = data.get("directory", {}).get("item", [])

    candidates = []
    for item in items:
        name = item.get("name", "")
        name_lower = name.lower().replace("-", "").replace("_", "").replace(" ", "")
        desc = (item.get("description") or "").lower()
        size = int(item.get("size") or 0)

        if not name.endswith((".htm", ".html", ".txt")):
            continue
        if name.endswith("-index.html") or name.endswith("-index-headers.html"):
            continue

        # Match exhibit 10.x patterns: ex101, ex10-1, exhibit10, exhibit_10, etc.
        is_exhibit_10 = (
            "ex10" in name_lower
            or re.search(r"exhibit\s*10", desc)
            or re.search(r"ex[\-_]?10[\-_.]?\d", name_lower)
        )
        if is_exhibit_10:
            candidates.append((size, name))

    if not candidates:
        return None

    # Return the largest exhibit (most likely to be the full contract, not a cover page)
    candidates.sort(reverse=True)
    return candidates[0][1]


def fetch_document(cik: str, accession: str, filename: str, client: httpx.Client) -> tuple[str, str] | None:
    """Fetch a document from EDGAR Archives."""
    cik_int = str(int(cik))
    acc_no_dash = accession.replace("-", "")
    url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_no_dash}/{filename}"

    resp = client.get(url)
    if resp.status_code != 200:
        return None
    return resp.text, url


def parse_via_fieldbench(html: str, filename: str, server_url: str, parse_client: httpx.Client) -> tuple[str, int] | None:
    """Parse HTML via OCR."""
    files = {"file": (filename, html.encode("utf-8"), "text/html")}
    try:
        resp = parse_client.post(f"{server_url}/parse", files=files)
    except httpx.RequestError as exc:
        print(f"[contracts] Parse failed: {exc}", file=sys.stderr)
        return None

    if resp.status_code != 200:
        return None

    body = resp.json()
    md = body.get("markdown") or ""
    pages = int(body.get("pages") or 0) or max(1, len(md) // 3000)
    if not md.strip():
        return None
    return md, pages


def parse_via_local_docling(html: str, filename: str) -> tuple[str, int] | None:
    """Parse HTML via local docling."""
    try:
        import io
        from docling.datamodel.base_models import DocumentStream
        from docling.document_converter import DocumentConverter
    except ImportError as exc:
        print(f"[contracts] docling not available: {exc}", file=sys.stderr)
        return None

    try:
        stream = DocumentStream(name=filename, stream=io.BytesIO(html.encode("utf-8")))
        converter = DocumentConverter()
        result = converter.convert(stream)
        md = result.document.export_to_markdown()
        pages = len(result.pages) if hasattr(result, "pages") and result.pages else max(1, len(md) // 3000)
    except Exception as exc:
        print(f"[contracts] Docling failed: {exc}", file=sys.stderr)
        return None

    if not md.strip():
        return None
    return md, pages


def load_existing_accessions() -> set[str]:
    """Load accession numbers already in the contracts corpus."""
    accessions = set()
    man_dir = CONTRACTS_DIR / "manifests"
    if not man_dir.is_dir():
        return accessions
    for path in man_dir.glob("*.json"):
        try:
            data = json.loads(path.read_text())
            acc = data.get("accession_number")
            if acc:
                accessions.add(acc)
        except (json.JSONDecodeError, OSError):
            continue
    return accessions


def write_sample(
    sample_id: str,
    markdown: str,
    source_url: str,
    accession: str,
    cik: str,
    filer_name: str,
    pages: int,
) -> None:
    """Write document, placeholder expected, and manifest."""
    doc_path = CONTRACTS_DIR / "documents" / f"{sample_id}.md"
    exp_path = CONTRACTS_DIR / "expected" / f"{sample_id}.expected.json"
    man_path = CONTRACTS_DIR / "manifests" / f"{sample_id}.json"

    doc_path.write_text(markdown)

    # Placeholder expected — needs manual annotation
    if not exp_path.exists():
        exp_path.write_text(json.dumps({
            "contract_type": None,
            "parties": [],
            "effective_date": None,
            "termination_date": None,
            "governing_law": None,
            "_annotation_status": "needs_review",
        }, indent=2) + "\n")

    manifest = {
        "filename": doc_path.name,
        "source_name": "SEC EDGAR (8-K Exhibit 10)",
        "source_url": source_url,
        "license": "Public Domain (US Government Work)",
        "license_url": "https://www.sec.gov/privacy",
        "attribution": "US Securities and Exchange Commission",
        "original_format": "HTML",
        "r2_url": None,
        "pages": pages,
        "added_date": time.strftime("%Y-%m-%d"),
        "added_by": "edgar-contracts-sourcer",
        "schema": "contracts/schemas/contract.yaml",
        "accession_number": accession,
        "cik": cik,
        "filer_name": filer_name,
        "notes": (
            f"Material contract (Exhibit 10) from {filer_name}'s 8-K filing "
            f"(accession {accession}). Expected JSON needs manual annotation."
        ),
    }
    man_path.write_text(json.dumps(manifest, indent=2) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, default=20, help="Max contracts to fetch")
    parser.add_argument("--fieldbench-server-url", default=DEFAULT_FIELDBENCH_SERVER_URL)
    parser.add_argument("--local-parse", action="store_true", help="Use local docling instead of fieldbench parse")
    args = parser.parse_args()

    for sub in ("documents", "expected", "manifests"):
        (CONTRACTS_DIR / sub).mkdir(parents=True, exist_ok=True)

    seen = load_existing_accessions()
    print(f"[contracts] {len(seen)} existing contracts in corpus")

    # Search for more than we need to account for dedup + missing exhibits
    search_limit = max(args.limit * 5, args.limit + len(seen) + 20)

    with _client() as client, _parse_client() as parse_client:
        if not args.local_parse:
            try:
                health = parse_client.get(f"{args.fieldbench_server_url.rstrip('/')}/health", timeout=5)
                if health.status_code != 200:
                    print(f"[contracts] FieldBench server not healthy", file=sys.stderr)
                    return 1
            except httpx.RequestError:
                print(f"[contracts] Cannot reach fieldbench at {args.fieldbench_server_url}", file=sys.stderr)
                return 1

        print(f"[contracts] Searching for 8-K filings with Exhibit 10...")
        hits = search_8k_filings(search_limit, client)
        print(f"[contracts] Found {len(hits)} 8-K filings")

        processed = 0
        skipped = 0
        failed = 0

        for hit in hits:
            if processed >= args.limit:
                break

            cik = hit.get("cik")
            accession = hit.get("accession")
            if not cik or not accession:
                failed += 1
                continue

            if accession in seen:
                skipped += 1
                continue

            # Find Exhibit 10 in the filing
            time.sleep(RATE_LIMIT_DELAY)
            exhibit = find_exhibit_10(cik, accession, client)
            if not exhibit:
                # Not every 8-K has an Exhibit 10
                continue

            # Fetch the exhibit document
            time.sleep(RATE_LIMIT_DELAY)
            fetched = fetch_document(cik, accession, exhibit, client)
            if not fetched:
                failed += 1
                continue

            raw_html, source_url = fetched

            # Skip very short documents (likely just headers or redirects)
            if len(raw_html) < 500:
                skipped += 1
                continue

            # Parse to markdown
            if args.local_parse:
                parsed = parse_via_local_docling(raw_html, exhibit)
            else:
                parsed = parse_via_fieldbench(raw_html, exhibit, args.fieldbench_server_url, parse_client)

            if not parsed:
                failed += 1
                continue

            markdown, pages = parsed

            # Skip if markdown is too short (failed parse)
            if len(markdown) < 200:
                skipped += 1
                continue

            filer_name = (hit.get("display_names") or ["Unknown"])[0]
            sample_id = f"edgar_contract_{processed + 1:03d}"

            write_sample(
                sample_id=sample_id,
                markdown=markdown,
                source_url=source_url,
                accession=accession,
                cik=cik,
                filer_name=filer_name,
                pages=pages,
            )

            seen.add(accession)
            processed += 1
            print(f"[contracts] ({processed}/{args.limit}) {sample_id}: {filer_name} — {exhibit}")

            time.sleep(PER_FILING_DELAY)

    print(f"\n[contracts] Done: {processed} saved, {skipped} skipped, {failed} failed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
