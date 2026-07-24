#!/usr/bin/env python3
"""Source legal opinions from CourtListener opinions API.

Browses recent opinions via the API, fetches text + cluster metadata.
Requires a free CourtListener API token.

Usage:
  uv run --with httpx python scripts/sources/legal_cl_opinions.py --limit 90 --token TOKEN
"""

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
API_BASE = "https://www.courtlistener.com/api/rest/v4"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=90)
    parser.add_argument("--token", type=str, default=os.environ.get("COURTLISTENER_TOKEN", ""))
    parser.add_argument("--min-length", type=int, default=1000)
    parser.add_argument("--max-length", type=int, default=60000)
    args = parser.parse_args()

    if not args.token:
        print("Set --token or COURTLISTENER_TOKEN", file=sys.stderr)
        return 1

    for sub in ("documents", "expected", "manifests"):
        (LEGAL_DIR / sub).mkdir(parents=True, exist_ok=True)

    existing_count = len(list((LEGAL_DIR / "documents").glob("*.md")))
    existing_ids = set()
    for p in (LEGAL_DIR / "manifests").glob("*.json"):
        try:
            d = json.loads(p.read_text())
            oid = d.get("opinion_id")
            if oid:
                existing_ids.add(str(oid))
        except (json.JSONDecodeError, OSError):
            pass

    print(f"[legal] {existing_count} existing docs, {len(existing_ids)} known opinion IDs")

    headers = {"Authorization": f"Token {args.token}"}
    processed = 0
    courts_seen: dict[str, int] = {}
    max_per_court = 8
    page_url = f"{API_BASE}/opinions/?page_size=20&order_by=-date_created"

    def api_get(client, url):
        """GET with retry on 429."""
        for attempt in range(4):
            resp = client.get(url, headers=headers)
            if resp.status_code != 429:
                return resp
            delay = 2 ** (attempt + 1)  # 2, 4, 8, 16 seconds
            print(f"[legal] Rate limited, waiting {delay}s...")
            time.sleep(delay)
        return resp

    with httpx.Client(timeout=30, follow_redirects=True) as client:
        while processed < args.limit and page_url:
            resp = api_get(client, page_url)
            if resp.status_code != 200:
                print(f"[legal] API error: {resp.status_code}")
                break

            data = resp.json()
            opinions = data.get("results", [])
            page_url = data.get("next")

            for op in opinions:
                if processed >= args.limit:
                    break

                op_id = str(op.get("id", ""))
                if op_id in existing_ids:
                    continue

                # Get text
                text = op.get("plain_text", "") or ""
                if not text:
                    html = op.get("html_with_citations", "") or op.get("html", "") or ""
                    if html:
                        text = re.sub(r"<[^>]+>", " ", html)
                        text = re.sub(r"\s+", " ", text).strip()

                if len(text) < args.min_length or len(text) > args.max_length:
                    continue

                # Fetch cluster for case metadata
                cluster_url = op.get("cluster", "")
                if not cluster_url:
                    continue

                time.sleep(2)  # Stay well under rate limit
                cluster_resp = api_get(client, cluster_url)
                if cluster_resp.status_code != 200:
                    continue

                cluster = cluster_resp.json()
                case_name = cluster.get("case_name", "") or cluster.get("case_name_full", "") or "Unknown"
                date_filed = cluster.get("date_filed", "") or ""
                docket_url = cluster.get("docket", "")

                # Get court info from docket
                court_name = ""
                docket_number = ""
                if docket_url:
                    time.sleep(2)
                    docket_resp = api_get(client, docket_url)
                    if docket_resp.status_code == 200:
                        docket = docket_resp.json()
                        docket_number = docket.get("docket_number", "") or ""
                        court_url = docket.get("court", "")
                        if court_url:
                            # Extract court name from URL or fetch
                            court_id = court_url.rstrip("/").split("/")[-1]
                            court_name = court_id.replace("-", " ").title()

                # Court diversity
                if court_name in courts_seen and courts_seen[court_name] >= max_per_court:
                    continue

                processed += 1
                courts_seen[court_name] = courts_seen.get(court_name, 0) + 1
                existing_ids.add(op_id)

                idx = existing_count + processed
                sample_id = f"cap_{idx:03d}"

                # Build markdown
                markdown = f"# {case_name}\n\n"
                if court_name:
                    markdown += f"**Court:** {court_name}\n\n"
                if docket_number:
                    markdown += f"**Docket Number:** {docket_number}\n\n"
                if date_filed:
                    markdown += f"**Decision Date:** {date_filed}\n\n"
                markdown += "---\n\n"
                markdown += text.strip()

                (LEGAL_DIR / "documents" / f"{sample_id}.md").write_text(markdown)

                # Expected
                expected = {
                    "case_number": docket_number or None,
                    "court": court_name or None,
                    "filing_date": date_filed or None,
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

                # Manifest
                manifest = {
                    "filename": f"{sample_id}.md",
                    "source_name": "CourtListener",
                    "source_url": f"https://www.courtlistener.com/opinion/{op_id}/",
                    "license": "Public Domain (US Court Opinions)",
                    "attribution": "Free Law Project / CourtListener",
                    "original_format": "text",
                    "pages": max(1, len(text) // 3000),
                    "added_date": time.strftime("%Y-%m-%d"),
                    "added_by": "legal-cl-opinions-sourcer",
                    "schema": "legal_filings/schemas/legal_filing.yaml",
                    "opinion_id": op_id,
                    "case_name": case_name,
                    "court": court_name,
                }
                (LEGAL_DIR / "manifests" / f"{sample_id}.json").write_text(
                    json.dumps(manifest, indent=2) + "\n"
                )

                print(f"[legal] ({processed}/{args.limit}) {sample_id}: {case_name[:50]} ({court_name[:30]})")

            time.sleep(3)  # Between pages

    print(f"\n[legal] Done: {processed} saved")
    print(f"[legal] Courts: {len(courts_seen)} unique")
    for court, count in sorted(courts_seen.items(), key=lambda x: -x[1])[:10]:
        print(f"  {court}: {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
