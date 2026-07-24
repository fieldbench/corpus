#!/usr/bin/env python3
"""Source legal opinions from CourtListener public search results.

Uses the public search API (no auth needed) to find cases, then
fetches the public opinion pages to get full text.

Usage:
  uv run --with httpx --with beautifulsoup4 python scripts/sources/legal_cl_scrape.py --limit 90
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import httpx

CORPUS_ROOT = Path(__file__).resolve().parent.parent.parent
LEGAL_DIR = CORPUS_ROOT / "legal_filings"
SEARCH_URL = "https://www.courtlistener.com/api/rest/v4/search/"


def search_opinions(query: str, client: httpx.Client, token: str, page_size: int = 20, page: int = 1) -> list[dict]:
    """Search CourtListener for opinions with text available."""
    resp = client.get(SEARCH_URL, params={
        "q": query,
        "type": "o",
        "page_size": page_size,
        "page": page,
        "filed_after": "2010-01-01",  # Recent cases more likely to have text
        "order_by": "score desc",
    }, headers={"Accept": "application/json"})
    if resp.status_code != 200:
        return []
    data = resp.json()
    return data.get("results", [])


def fetch_opinion_text(cluster_id: str, client: httpx.Client, token: str) -> str | None:
    """Fetch full opinion text via CourtListener API."""
    headers = {"Authorization": f"Token {token}"}
    resp = client.get(
        f"https://www.courtlistener.com/api/rest/v4/clusters/{cluster_id}/",
        headers=headers,
    )
    if resp.status_code != 200:
        return None

    cluster = resp.json()
    sub_opinions = cluster.get("sub_opinions", [])
    if not sub_opinions:
        return None

    # Fetch the first sub-opinion's text
    for sub_url in sub_opinions:
        time.sleep(0.3)
        resp2 = client.get(sub_url, headers=headers)
        if resp2.status_code != 200:
            continue
        opinion = resp2.json()
        # Try text fields in order of preference
        for field in ["plain_text", "html_with_citations", "html"]:
            text = opinion.get(field, "")
            if text and len(text) > 200:
                # Strip HTML if needed
                if field.startswith("html"):
                    text = re.sub(r"<[^>]+>", " ", text)
                    text = re.sub(r"\s+", " ", text).strip()
                return text

    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=90)
    parser.add_argument("--token", type=str, default=os.environ.get("COURTLISTENER_TOKEN", ""), help="CourtListener API token")
    args = parser.parse_args()

    if not args.token:
        print("[legal] Set --token or COURTLISTENER_TOKEN env var", file=sys.stderr)
        return 1

    for sub in ("documents", "expected", "manifests"):
        (LEGAL_DIR / sub).mkdir(parents=True, exist_ok=True)

    existing_count = len(list((LEGAL_DIR / "documents").glob("*.md")))
    print(f"[legal] Starting from {existing_count} existing docs")

    queries = [
        "breach of contract damages",
        "motion to dismiss failure to state",
        "summary judgment standard",
        "employment discrimination title VII",
        "patent claim construction",
        "securities fraud 10b-5",
        "personal injury negligence",
        "class action certification",
        "antitrust monopoly",
        "insurance bad faith",
        "landlord tenant eviction",
        "bankruptcy discharge",
        "copyright fair use",
        "wrongful termination",
        "due process fourteenth amendment",
        "medical malpractice standard of care",
        "trade secret misappropriation",
        "product liability defect",
    ]

    processed = 0
    courts_seen: dict[str, int] = {}
    max_per_court = 6

    with httpx.Client(timeout=30, follow_redirects=True) as client:
        for query in queries:
            if processed >= args.limit:
                break

            print(f"\n[legal] Searching: {query}")
            # Fetch multiple pages to get enough docs with text
            all_results = []
            for page in range(1, 4):  # up to 3 pages
                results = search_opinions(query, client, args.token, page_size=20, page=page)
                all_results.extend(results)
                if len(results) < 20:
                    break
                time.sleep(0.5)
            print(f"[legal]   {len(all_results)} results")

            for r in all_results:
                if processed >= args.limit:
                    break

                case_name = r.get("caseName", "") or "Unknown"
                court = r.get("court", "") or ""
                date = r.get("dateFiled", "") or ""
                docket = r.get("docketNumber", "") or ""
                abs_url = r.get("absolute_url", "")
                citation = ""
                cites = r.get("citation", [])
                if isinstance(cites, list) and cites:
                    citation = cites[0] if isinstance(cites[0], str) else ""
                elif isinstance(cites, str):
                    citation = cites

                # Court diversity
                if court in courts_seen and courts_seen[court] >= max_per_court:
                    continue

                cluster_id = r.get("cluster_id")
                if not cluster_id:
                    continue

                # Fetch full opinion text via API
                text = fetch_opinion_text(str(cluster_id), client, args.token)
                if not text or len(text) < 500:
                    continue

                # Too long = skip (probably a whole docket page)
                if len(text) > 100000:
                    continue

                processed += 1
                courts_seen[court] = courts_seen.get(court, 0) + 1

                idx = existing_count + processed
                sample_id = f"cap_{idx:03d}"

                # Build markdown
                markdown = f"# {case_name}\n\n"
                if court:
                    markdown += f"**Court:** {court}\n\n"
                if docket:
                    markdown += f"**Docket Number:** {docket}\n\n"
                if date:
                    markdown += f"**Decision Date:** {date}\n\n"
                if citation:
                    markdown += f"**Citation:** {citation}\n\n"
                markdown += "---\n\n"
                markdown += text

                (LEGAL_DIR / "documents" / f"{sample_id}.md").write_text(markdown)

                expected = {
                    "case_number": docket or None,
                    "court": court or None,
                    "filing_date": date or None,
                    "filing_type": "Opinion",
                    "plaintiff": None,
                    "defendant": None,
                    "judge": None,
                    "_annotation_status": "auto_partial",
                }
                if " v. " in case_name:
                    parts = case_name.split(" v. ", 1)
                    expected["plaintiff"] = parts[0].strip()
                    expected["defendant"] = parts[1].strip()

                (LEGAL_DIR / "expected" / f"{sample_id}.expected.json").write_text(
                    json.dumps(expected, indent=2) + "\n"
                )

                manifest = {
                    "filename": f"{sample_id}.md",
                    "source_name": "CourtListener",
                    "source_url": f"https://www.courtlistener.com/opinion/{cluster_id}/",
                    "license": "Public Domain (US Court Opinions)",
                    "attribution": "Free Law Project / CourtListener",
                    "original_format": "HTML",
                    "pages": max(1, len(text) // 3000),
                    "added_date": time.strftime("%Y-%m-%d"),
                    "added_by": "legal-cl-sourcer",
                    "schema": "legal_filings/schemas/legal_filing.yaml",
                    "case_name": case_name,
                    "citation": citation,
                    "court": court,
                }
                (LEGAL_DIR / "manifests" / f"{sample_id}.json").write_text(
                    json.dumps(manifest, indent=2) + "\n"
                )

                print(f"[legal] ({processed}/{args.limit}) {sample_id}: {case_name[:50]} ({court[:30]})")
                time.sleep(1)  # Be nice to CourtListener

    print(f"\n[legal] Done: {processed} saved")
    print(f"[legal] Courts: {len(courts_seen)} unique")
    return 0


if __name__ == "__main__":
    sys.exit(main())
