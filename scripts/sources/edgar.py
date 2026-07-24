#!/usr/bin/env python3
"""SEC EDGAR sourcing script for the FieldBench corpus.

Fetches real SEC filings end-to-end:
  1. Searches EDGAR's full-text index for filings of a given form type
  2. Looks up authoritative metadata via the company's submission index
  3. Downloads the primary filing document (the actual 10-K/10-Q/8-K)
  4. Sends the raw HTML to a running OCR (docling) and
     saves the returned markdown as a corpus sample
  5. Writes the expected JSON straight from the EDGAR index — that index
     is the authoritative source for filer name, CIK, form type, dates,
     and accession number, so the expected outputs need no extra review

Why parse via fieldbench instead of html2text:
  - The corpus has to test what fieldbench's *production* extract step sees.
    Extract is designed to consume parse-quality markdown (with real
    structural headers from docling), not html2text output (which leaves
    the original HTML's lack of <h1> tags as a flat blob).
  - Going through parse means the corpus markdown matches exactly what
    `fieldbench process` would produce in prod for the same input.
  - Drops html2text as a dep and removes a second markdown converter
    from the codebase.

Key constraints:
  - SEC requires a User-Agent header identifying the requester
  - Rate limit is 10 requests/second; we explicitly pace at >=1s/filing
    (and 0.125s between intra-filing API calls) to stay well under
  - EDGAR does not require authentication
  - Requires a running fieldbench cluster reachable at --fieldbench-server-url
    (default http://127.0.0.1:9401) for the parse step

Dependencies:
  - httpx

Run via uv (no venv to maintain):
  uv run --with httpx \\
    python scripts/sources/edgar.py --form-type 10-K --limit 5

Usage:
  python scripts/sources/edgar.py --form-type 10-K --limit 20
  python scripts/sources/edgar.py --form-type 8-K --limit 50 --start-date 2024-01-01
  python scripts/sources/edgar.py --form-type all --limit 100
  python scripts/sources/edgar.py --form-type 10-K --limit 5 --metadata-only

Form types supported:
  10-K, 10-Q, 8-K, DEF 14A, S-1, 20-F, 6-K, and variants.

References:
  - EDGAR full-text search: https://efts.sec.gov/LATEST/search-index?q=&forms=10-K
  - EDGAR submissions endpoint: https://data.sec.gov/submissions/CIK{cik}.json
  - EDGAR Archives: https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_no_dashes}/{primary_doc}
  - FieldBench parse API: POST /api/parse (multipart file upload, returns {markdown, pages})
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import httpx

CORPUS_ROOT = Path(__file__).resolve().parent.parent.parent
FILINGS_DIR = CORPUS_ROOT / "sec_filings"

USER_AGENT = "FieldBench Corpus bot@getfieldbench.dev"
RATE_LIMIT_DELAY = 0.125  # 8 req/sec, safely under SEC's 10/sec limit
PER_FILING_DELAY = 1.5  # explicit pacing between filings, well above the rate limit floor
DEFAULT_FIELDBENCH_SERVER_URL = "http://127.0.0.1:9401"
PARSE_TIMEOUT = 600.0  # docling can be slow on large filings

SUPPORTED_FORMS = [
    "10-K", "10-K/A",
    "10-Q", "10-Q/A",
    "8-K", "8-K/A",
    "S-1", "S-1/A",
    "DEF 14A",
    "20-F",
    "6-K",
]

# ── HTTP helpers ─────────────────────────────────────────────────


def _client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate"},
        timeout=60.0,
        follow_redirects=True,
    )


def _parse_client() -> httpx.Client:
    """Separate client for the local OCR.

    Different timeout, no SEC user-agent (parse service doesn't care).
    """
    return httpx.Client(timeout=PARSE_TIMEOUT)


def edgar_search(form_type: str, start_date: str | None, end_date: str | None, limit: int, client: httpx.Client) -> list[dict]:
    """Search EDGAR full-text index for filings of a given form type.

    Returns a list of hit dicts with keys: adsh (accession), cik, form, file_date.
    """
    params = {
        "q": "",
        "forms": form_type,
        "dateRange": "custom" if (start_date or end_date) else "",
    }
    if start_date:
        params["startdt"] = start_date
    if end_date:
        params["enddt"] = end_date

    # EDGAR's search endpoint — returns a structured JSON result
    url = "https://efts.sec.gov/LATEST/search-index"

    hits: list[dict] = []
    offset = 0
    page_size = 100

    while len(hits) < limit:
        query_params = {**params, "from": offset}
        resp = client.get(url, params=query_params)
        if resp.status_code != 200:
            print(f"[edgar] Search request failed: {resp.status_code}", file=sys.stderr)
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
                "form": src.get("form"),
                "file_date": src.get("file_date"),
                "display_names": src.get("display_names", []),
            })
            if len(hits) >= limit:
                break

        offset += page_size
        time.sleep(RATE_LIMIT_DELAY)

    return hits


def fetch_submission_index(cik: str, client: httpx.Client) -> dict | None:
    """Fetch a company's submission index from EDGAR's data.sec.gov endpoint.

    This gives us authoritative metadata (name, periods of report, filing dates)
    for all of the company's recent filings.
    """
    padded_cik = cik.zfill(10)
    url = f"https://data.sec.gov/submissions/CIK{padded_cik}.json"
    resp = client.get(url)
    if resp.status_code != 200:
        return None
    return resp.json()


def build_sample_from_submission(cik: str, accession: str, submission: dict) -> dict | None:
    """Extract metadata for a single filing from a company submission index.

    Returned dict includes the schema fields plus `primary_document` (the
    HTML filename of the actual filing on EDGAR), which the fetcher uses to
    pull the real document content.
    """
    filer_name = submission.get("name")
    if not filer_name:
        return None

    recent = submission.get("filings", {}).get("recent", {})
    accessions = recent.get("accessionNumber", [])
    try:
        idx = accessions.index(accession.replace("-", ""))
    except ValueError:
        # Try with original format
        try:
            idx = accessions.index(accession)
        except ValueError:
            return None

    return {
        "filer_name": filer_name,
        "cik": cik.zfill(10),
        "form_type": recent.get("form", [None] * (idx + 1))[idx],
        "filing_date": recent.get("filingDate", [None] * (idx + 1))[idx],
        "period_of_report": recent.get("reportDate", [None] * (idx + 1))[idx] or None,
        "accession_number": accession,
        "primary_document": recent.get("primaryDocument", [None] * (idx + 1))[idx],
    }


def fetch_primary_document(
    cik: str,
    accession: str,
    primary_document: str,
    client: httpx.Client,
) -> tuple[str, str] | None:
    """Fetch the primary filing document from EDGAR Archives.

    Returns a tuple of (raw_html, source_url), or None if the fetch fails.
    The accession number's dashes are stripped to form the directory name.
    """
    cik_int = str(int(cik))  # strip leading zeros for the Archives path
    accession_no_dashes = accession.replace("-", "")
    url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_no_dashes}/{primary_document}"

    resp = client.get(url)
    if resp.status_code != 200:
        print(
            f"[edgar] Primary document fetch failed ({resp.status_code}): {url}",
            file=sys.stderr,
        )
        return None
    return resp.text, url


def parse_via_fieldbench(
    html: str,
    filename: str,
    server_url: str,
    parse_client: httpx.Client,
) -> tuple[str, int] | None:
    """Send raw filing HTML to a running OCR and return markdown.

    The corpus tests how fieldbench's *production* extract step performs on
    real documents. Extract is designed to consume parse-quality
    markdown, so the corpus markdown must come from the same parser
    (docling) the prod pipeline uses — not from a one-off HTML-to-text
    converter that would skip docling's structure-detection logic.

    Returns (markdown, page_count) on success, or None on parse failure.
    """
    files = {"file": (filename, html.encode("utf-8"), "text/html")}
    try:
        resp = parse_client.post(f"{server_url}/api/parse", files=files)
    except httpx.RequestError as exc:
        print(f"[edgar] Parse request failed: {exc}", file=sys.stderr)
        return None

    if resp.status_code != 200:
        try:
            err = resp.json().get("error", resp.text[:200])
        except Exception:
            err = resp.text[:200]
        print(f"[edgar] Parse returned {resp.status_code}: {err}", file=sys.stderr)
        return None

    body = resp.json()
    md = body.get("markdown") or ""
    pages = int(body.get("pages") or 0) or 1
    if not md.strip():
        print(f"[edgar] Parse returned empty markdown for {filename}", file=sys.stderr)
        return None
    return md, pages


def parse_via_local_docling(html: str, filename: str) -> tuple[str, int] | None:
    """Run docling in-process to convert HTML → markdown without the fieldbench cluster.

    Used when --local-parse is set. Same parser as the fieldbench parse
    service (docling DocumentConverter), just invoked directly so
    sourcing works in environments where the ghcr.io parse-base image
    isn't pullable. Imports docling lazily so non-local-parse runs
    don't pay the import cost.

    Returns (markdown, page_count) on success, or None on failure.
    """
    try:
        import io

        from docling.datamodel.base_models import DocumentStream
        from docling.document_converter import DocumentConverter
    except ImportError as exc:
        print(
            f"[edgar] docling not available for --local-parse: {exc}\n"
            f"        Install with: uv run --with docling python scripts/sources/edgar.py ...",
            file=sys.stderr,
        )
        return None

    try:
        stream = DocumentStream(name=filename, stream=io.BytesIO(html.encode("utf-8")))
        converter = DocumentConverter()
        result = converter.convert(stream)
        md = result.document.export_to_markdown()
        pages = len(result.pages) if hasattr(result, "pages") and result.pages else 0
    except Exception as exc:
        print(f"[edgar] Local docling failed on {filename}: {exc}", file=sys.stderr)
        return None

    if not md.strip():
        print(f"[edgar] Local docling returned empty markdown for {filename}", file=sys.stderr)
        return None

    if pages <= 0:
        pages = max(1, len(md) // 3000)
    return md, pages


# ── Sample writer ────────────────────────────────────────────────


def build_metadata_stub_markdown(metadata: dict) -> str:
    """Render a filing's metadata as a short markdown document.

    Used as a fallback when --metadata-only is set or the primary document
    fetch fails. The original 5 hand-crafted samples are also of this
    flavor (varied surface forms over the same metadata).
    """
    form_type = metadata.get("form_type", "Unknown")
    filer_name = metadata.get("filer_name", "Unknown")
    cik = metadata.get("cik", "")
    filing_date = metadata.get("filing_date", "")
    period = metadata.get("period_of_report") or filing_date
    accession = metadata.get("accession_number", "")

    return f"""# Form {form_type}

**UNITED STATES SECURITIES AND EXCHANGE COMMISSION**
Washington, D.C. 20549

---

**Filer:** {filer_name}
**CIK:** {cik}
**Form Type:** {form_type}
**Filing Date:** {filing_date}
**Period of Report:** {period}
**Accession Number:** {accession}

This filing was retrieved from SEC EDGAR and is part of the FieldBench corpus.
"""


def safe_filename(form_type: str, n: int) -> str:
    slug = form_type.lower().replace("/", "_").replace(" ", "_").replace("-", "")
    return f"edgar_{slug}_{n:03d}"


def next_available_index(form_type: str) -> int:
    """Find the lowest unused sample index for this form type.

    Lets us add new samples without colliding with the existing 5
    hand-crafted ones (or with previous batches).
    """
    docs_dir = FILINGS_DIR / "documents"
    n = 1
    while (docs_dir / f"{safe_filename(form_type, n)}.md").exists():
        n += 1
    return n


def load_existing_accessions() -> set[str]:
    """Read every manifest in the corpus and collect known accession numbers.

    EDGAR full-text search will happily hand back the same most-recent
    filing on every call, so we need to remember what we've already
    saved across runs. We source the accession from each manifest's
    explicit `accession_number` field when present, falling back to
    parsing it out of the `source_url` for older manifests that predate
    the explicit field.
    """
    accessions: set[str] = set()
    man_dir = FILINGS_DIR / "manifests"
    if not man_dir.is_dir():
        return accessions
    for path in man_dir.glob("*.json"):
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        acc = data.get("accession_number")
        if not acc:
            # Backwards compat: derive from Archives URL
            # (e.g. .../Archives/edgar/data/1080448/000168316826002795/...)
            url = data.get("source_url") or ""
            import re as _re
            m = _re.search(r"/Archives/edgar/data/\d+/(\d{18})/", url)
            if m:
                raw = m.group(1)
                acc = f"{raw[:10]}-{raw[10:12]}-{raw[12:]}"
        if acc:
            accessions.add(acc)
    return accessions


# Map each form type to the period field that applies to it. Only the
# relevant field is populated in expected.json; the other three are
# dropped entirely (the bench ignores fields not present in expected).
# Registration statements (S-1/A) have no period-of-report concept and
# get no period field at all.
_FORM_TO_PERIOD_FIELD: dict[str, str] = {
    "10-K": "period_fiscal_year_end",
    "10-K/A": "period_fiscal_year_end",
    "10-Q": "period_quarter_end",
    "10-Q/A": "period_quarter_end",
    "8-K": "period_date_of_report",
    "8-K/A": "period_date_of_report",
    "DEF 14A": "period_meeting_date",
    "20-F": "period_fiscal_year_end",
    "6-K": "period_date_of_report",
}


def _build_expected(metadata: dict) -> dict:
    """Project EDGAR-index metadata onto the filing_metadata schema's fields.

    Only fields actually present in the schema and populated for the
    given form type are returned. Everything else (CIK, accession
    number, primary_document) is plumbing and lives in the manifest.
    """
    expected: dict = {
        "filer_name": metadata.get("filer_name"),
        "form_type": metadata.get("form_type"),
        "filing_date": metadata.get("filing_date"),
    }
    period = metadata.get("period_of_report")
    period_field = _FORM_TO_PERIOD_FIELD.get(metadata.get("form_type") or "")
    if period_field and period:
        expected[period_field] = period
    # Drop keys that came back None so the bench doesn't count them
    return {k: v for k, v in expected.items() if v is not None}


def write_sample(
    metadata: dict,
    sample_id: str,
    document_markdown: str,
    source_url: str,
    pages_estimate: int,
) -> None:
    doc_path = FILINGS_DIR / "documents" / f"{sample_id}.md"
    exp_path = FILINGS_DIR / "expected" / f"{sample_id}.expected.json"
    man_path = FILINGS_DIR / "manifests" / f"{sample_id}.json"

    doc_path.write_text(document_markdown)

    expected = _build_expected(metadata)
    exp_path.write_text(json.dumps(expected, indent=2) + "\n")

    form_type = metadata.get("form_type", "")
    filer_name = metadata.get("filer_name", "")
    cik = metadata.get("cik", "")
    accession = metadata.get("accession_number", "")
    manifest = {
        "filename": doc_path.name,
        "source_name": "SEC EDGAR",
        "source_url": source_url,
        "license": "Public Domain (US Government Work)",
        "license_url": "https://www.sec.gov/privacy",
        "attribution": "US Securities and Exchange Commission",
        "original_format": "HTML",
        "r2_url": None,
        "pages": pages_estimate,
        "added_date": "2026-04-12",
        "added_by": "corpus-bootstrap",
        "schema": "sec_filings/schemas/filing_metadata.yaml",
        # Sidecar metadata from the EDGAR index — not in the schema, but
        # load_existing_accessions() reads from here to dedupe across runs
        # and humans can trace any sample back to its EDGAR record.
        "accession_number": accession,
        "cik": cik,
        "notes": (
            f"{form_type} filing for {filer_name} (accession {accession}). "
            f"Document text produced by piping the EDGAR primary HTML through "
            f"fieldbench parse (docling); expected JSON is sourced from the EDGAR "
            f"submission index (authoritative for filer, form type, dates)."
        ),
    }
    man_path.write_text(json.dumps(manifest, indent=2) + "\n")


def estimate_pages_from_markdown(markdown: str) -> int:
    """Fallback page count when parse doesn't supply one (~3000 chars/page)."""
    return max(1, len(markdown) // 3000)


# ── Main ─────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--form-type",
        default="10-K",
        help="Form type to fetch (10-K, 10-Q, 8-K, DEF 14A, etc., or 'all')",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of filings to process (default: 20)",
    )
    parser.add_argument(
        "--start-date",
        help="Earliest filing date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end-date",
        help="Latest filing date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--metadata-only",
        action="store_true",
        help="Skip the primary document fetch and write a synthetic metadata stub instead. "
             "Useful for offline / smoke-test runs.",
    )
    parser.add_argument(
        "--per-filing-delay",
        type=float,
        default=PER_FILING_DELAY,
        help=f"Seconds to sleep between filings (default: {PER_FILING_DELAY})",
    )
    parser.add_argument(
        "--fieldbench-server-url",
        default=DEFAULT_FIELDBENCH_SERVER_URL,
        help=f"FieldBench server URL for the parse step (default: {DEFAULT_FIELDBENCH_SERVER_URL})",
    )
    parser.add_argument(
        "--local-parse",
        action="store_true",
        help=(
            "Run docling in-process instead of calling the OCR. "
            "Use when the cluster isn't running (e.g., ghcr.io parse-base image "
            "can't be pulled). Requires `uv run --with docling`."
        ),
    )
    args = parser.parse_args()

    form_types = SUPPORTED_FORMS if args.form_type == "all" else [args.form_type]

    for sub in ("documents", "expected", "manifests"):
        (FILINGS_DIR / sub).mkdir(parents=True, exist_ok=True)

    seen_accessions = load_existing_accessions()
    if seen_accessions:
        print(f"[edgar] Skipping {len(seen_accessions)} accession(s) already in corpus", file=sys.stderr)

    processed = 0
    skipped = 0
    failed = 0

    with _client() as client, _parse_client() as parse_client:
        if args.local_parse:
            # Lazy-import docling once up front so failures are loud and
            # we don't download HTML we can't parse. An ImportError here
            # kills the run before any SEC traffic.
            try:
                import docling.document_converter  # noqa: F401
            except ImportError:
                print(
                    "[edgar] --local-parse requires docling. Re-run with:\n"
                    "        uv run --with docling python scripts/sources/edgar.py ...",
                    file=sys.stderr,
                )
                return 1
        else:
            # Sanity check: parse service must be reachable up front, otherwise
            # we'd download HTML and lose it.
            try:
                health = parse_client.get(f"{args.fieldbench_server_url}/health", timeout=5)
                if health.status_code != 200:
                    print(
                        f"[edgar] FieldBench server health check failed at {args.fieldbench_server_url}/health "
                        f"(HTTP {health.status_code}). Start a fieldbench cluster first.",
                        file=sys.stderr,
                    )
                    return 1
            except httpx.RequestError as exc:
                print(
                    f"[edgar] Cannot reach fieldbench server at {args.fieldbench_server_url}: {exc}\n"
                    f"        Start a fieldbench cluster first, or pass --fieldbench-server-url.",
                    file=sys.stderr,
                )
                return 1

        for form_type in form_types:
            if processed >= args.limit:
                break

            # Over-fetch from EDGAR so we still hit `limit` after de-duping.
            # Scale with the corpus size so we reliably find unseen filings
            # even when the first several pages are already in the corpus.
            wanted = max(args.limit - processed, 1)
            search_limit = max(wanted * 4, wanted + len(seen_accessions) + 10)
            print(f"[edgar] Searching for {form_type} filings (over-fetching {search_limit} for de-dup)", file=sys.stderr)
            hits = edgar_search(form_type, args.start_date, args.end_date, search_limit, client)
            print(f"[edgar] Found {len(hits)} hits", file=sys.stderr)

            for hit in hits:
                if processed >= args.limit:
                    break

                cik = hit.get("cik")
                accession = hit.get("accession")
                if not cik or not accession:
                    failed += 1
                    continue

                if accession in seen_accessions:
                    skipped += 1
                    continue

                try:
                    submission = fetch_submission_index(cik, client)
                    if not submission:
                        failed += 1
                        continue
                    time.sleep(RATE_LIMIT_DELAY)

                    metadata = build_sample_from_submission(cik, accession, submission)
                    if not metadata:
                        failed += 1
                        continue

                    actual_form = metadata.get("form_type", form_type)
                    n = next_available_index(actual_form)
                    sample_id = safe_filename(actual_form, n)

                    if (FILINGS_DIR / "documents" / f"{sample_id}.md").exists():
                        skipped += 1
                        continue

                    primary_document = metadata.get("primary_document")
                    if args.metadata_only or not primary_document:
                        document_markdown = build_metadata_stub_markdown(metadata)
                        source_url = (
                            f"https://www.sec.gov/cgi-bin/browse-edgar?"
                            f"action=getcompany&CIK={cik}&type={actual_form}"
                        )
                        pages = estimate_pages_from_markdown(document_markdown)
                    else:
                        fetched = fetch_primary_document(cik, accession, primary_document, client)
                        if fetched is None:
                            failed += 1
                            continue
                        raw_html, source_url = fetched

                        if args.local_parse:
                            parsed = parse_via_local_docling(raw_html, primary_document)
                        else:
                            parsed = parse_via_fieldbench(
                                raw_html,
                                primary_document,
                                args.fieldbench_server_url,
                                parse_client,
                            )
                        if parsed is None:
                            failed += 1
                            continue
                        document_markdown, pages = parsed

                    write_sample(metadata, sample_id, document_markdown, source_url, pages)
                    seen_accessions.add(accession)
                    processed += 1
                    print(
                        f"[edgar] ({processed}/{args.limit}) {sample_id} "
                        f"{metadata.get('filer_name')} {actual_form} "
                        f"~{pages}p ({len(document_markdown)} chars)",
                        file=sys.stderr,
                    )

                    time.sleep(args.per_filing_delay)

                except Exception as e:
                    print(f"[edgar] Error on {accession}: {e}", file=sys.stderr)
                    failed += 1

    print(
        f"\n[edgar] Done. Processed: {processed}, Skipped: {skipped}, Failed: {failed}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
