#!/usr/bin/env python3
"""Source legal opinions from case.law API (Caselaw Access Project).

Uses the case.law API directly — no auth needed for case text.
CC0 license.

Usage:
  uv run --with httpx python scripts/sources/legal_caselaw.py --limit 100
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
LEGAL_DIR = CORPUS_ROOT / "legal_filings"
API_BASE = "https://api.case.law/v1"


def search_cases(query: str, jurisdiction: str | None, limit: int, offset: int, client: httpx.Client) -> dict:
    """Search for cases via the case.law API."""
    params = {
        "search": query,
        "page_size": min(limit, 100),
        "offset": offset,
        "full_case": "true",
        "body_format": "text",
    }
    if jurisdiction:
        params["jurisdiction"] = jurisdiction

    resp = client.get(f"{API_BASE}/cases/", params=params)
    if resp.status_code != 200:
        print(f"[legal] Search failed: {resp.status_code}", file=sys.stderr)
        return {"results": []}
    return resp.json()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--min-length", type=int, default=1000)
    parser.add_argument("--max-length", type=int, default=80000)
    args = parser.parse_args()

    for sub in ("documents", "expected", "manifests"):
        (LEGAL_DIR / sub).mkdir(parents=True, exist_ok=True)

    # Load existing to avoid dupes
    existing = set()
    for p in (LEGAL_DIR / "manifests").glob("*.json"):
        try:
            d = json.loads(p.read_text())
            cite = d.get("citation")
            if cite:
                existing.add(cite)
        except (json.JSONDecodeError, OSError):
            pass

    # Diverse search queries to get variety
    queries = [
        ("breach of contract", None),
        ("motion to dismiss", None),
        ("summary judgment", None),
        ("employment discrimination", None),
        ("patent infringement", None),
        ("securities fraud", None),
        ("personal injury negligence", None),
        ("class action", None),
        ("antitrust", None),
        ("insurance coverage", None),
        ("landlord tenant", None),
        ("bankruptcy", None),
        ("copyright infringement", None),
        ("wrongful termination", None),
        ("due process", None),
    ]

    processed = 0
    skipped = 0
    courts_seen: dict[str, int] = {}
    max_per_court = 8

    # Start from where we left off
    start_idx = len(list((LEGAL_DIR / "documents").glob("*.md")))

    with httpx.Client(timeout=30, follow_redirects=True) as client:
        for query, jurisdiction in queries:
            if processed >= args.limit:
                break

            print(f"[legal] Searching: {query}")
            data = search_cases(query, jurisdiction, 20, 0, client)
            results = data.get("results", [])
            print(f"[legal]   Found {len(results)} results")

            for case in results:
                if processed >= args.limit:
                    break

                # Get case text
                casebody = case.get("casebody", {})
                if isinstance(casebody, dict):
                    data_inner = casebody.get("data", {})
                    if isinstance(data_inner, dict):
                        opinions = data_inner.get("opinions", [])
                        text = ""
                        for op in opinions:
                            if isinstance(op, dict):
                                t = op.get("text", "")
                                if t:
                                    text += t + "\n\n"
                    elif isinstance(data_inner, str):
                        text = data_inner
                    else:
                        text = ""
                else:
                    text = str(casebody) if casebody else ""

                if not text or len(text) < args.min_length:
                    skipped += 1
                    continue
                if len(text) > args.max_length:
                    skipped += 1
                    continue

                # Metadata
                case_name = case.get("name", "") or case.get("name_abbreviation", "") or "Unknown"
                court_name = ""
                court_obj = case.get("court", {})
                if isinstance(court_obj, dict):
                    court_name = court_obj.get("name", "") or court_obj.get("name_abbreviation", "")
                elif isinstance(court_obj, str):
                    court_name = court_obj

                decision_date = case.get("decision_date", "") or ""
                docket_number = case.get("docket_number", "") or ""
                citations = case.get("citations", [])
                cite_str = ""
                if citations and isinstance(citations[0], dict):
                    cite_str = citations[0].get("cite", "")

                # Skip dupes
                if cite_str and cite_str in existing:
                    skipped += 1
                    continue

                # Court diversity
                if court_name in courts_seen and courts_seen[court_name] >= max_per_court:
                    skipped += 1
                    continue

                # Build markdown
                markdown = f"# {case_name}\n\n"
                if court_name:
                    markdown += f"**Court:** {court_name}\n\n"
                if docket_number:
                    markdown += f"**Docket Number:** {docket_number}\n\n"
                if decision_date:
                    markdown += f"**Decision Date:** {decision_date}\n\n"
                if cite_str:
                    markdown += f"**Citation:** {cite_str}\n\n"
                markdown += "---\n\n"
                markdown += text.strip()

                processed += 1
                courts_seen[court_name] = courts_seen.get(court_name, 0) + 1
                if cite_str:
                    existing.add(cite_str)

                sample_id = f"cap_{start_idx + processed:03d}"

                # Write document
                (LEGAL_DIR / "documents" / f"{sample_id}.md").write_text(markdown)

                # Expected JSON — auto-fill from metadata
                expected = {
                    "case_number": docket_number or None,
                    "court": court_name or None,
                    "filing_date": decision_date or None,
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
                elif " v " in case_name:
                    parts = case_name.split(" v ", 1)
                    expected["plaintiff"] = parts[0].strip()
                    expected["defendant"] = parts[1].strip()

                (LEGAL_DIR / "expected" / f"{sample_id}.expected.json").write_text(
                    json.dumps(expected, indent=2) + "\n"
                )

                # Manifest
                manifest = {
                    "filename": f"{sample_id}.md",
                    "source_name": "Caselaw Access Project (Harvard Law School)",
                    "source_url": case.get("url", "https://case.law/"),
                    "license": "CC0 (Public Domain)",
                    "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
                    "attribution": "Caselaw Access Project, Harvard Law School Library Innovation Lab",
                    "original_format": "text",
                    "r2_url": None,
                    "pages": max(1, len(text) // 3000),
                    "added_date": time.strftime("%Y-%m-%d"),
                    "added_by": "legal-caselaw-sourcer",
                    "schema": "legal_filings/schemas/legal_filing.yaml",
                    "case_name": case_name,
                    "citation": cite_str,
                    "court": court_name,
                    "decision_date": decision_date,
                }
                (LEGAL_DIR / "manifests" / f"{sample_id}.json").write_text(
                    json.dumps(manifest, indent=2) + "\n"
                )

                court_short = court_name[:40] if court_name else "?"
                print(f"[legal] ({processed}/{args.limit}) {sample_id}: {case_name[:50]} ({court_short})")

            time.sleep(1)  # Rate limit courtesy

    print(f"\n[legal] Done: {processed} saved, {skipped} skipped")
    print(f"[legal] Courts: {len(courts_seen)} unique")
    for court, count in sorted(courts_seen.items(), key=lambda x: -x[1])[:10]:
        print(f"  {court}: {count}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
