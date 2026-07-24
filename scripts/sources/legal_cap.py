#!/usr/bin/env python3
"""Source legal filings from the Caselaw Access Project (Harvard).

Downloads court opinions from the Hugging Face dataset
(free-law/Caselaw_Access_Project). No API token needed. CC0 license.

The dataset contains 6.7M cases. We sample diverse cases across:
- Federal district courts (complaints, motions, orders)
- Federal appellate courts (opinions, briefs)
- State supreme courts (opinions)

Usage:
  uv run --with datasets python scripts/sources/legal_cap.py --limit 100

Each document needs manual annotation for ground truth (case number,
court, parties, judge, filing type, date).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

CORPUS_ROOT = Path(__file__).resolve().parent.parent.parent
LEGAL_DIR = CORPUS_ROOT / "legal_filings"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, default=100, help="Max documents to fetch")
    parser.add_argument("--min-length", type=int, default=500, help="Min text length in chars")
    parser.add_argument("--max-length", type=int, default=50000, help="Max text length in chars")
    args = parser.parse_args()

    try:
        from datasets import load_dataset
    except ImportError:
        print("Install datasets: uv run --with datasets python ...", file=sys.stderr)
        return 1

    for sub in ("documents", "expected", "manifests"):
        (LEGAL_DIR / sub).mkdir(parents=True, exist_ok=True)

    # Load dataset in streaming mode to avoid downloading everything
    print("[legal] Loading Caselaw Access Project from Hugging Face (streaming)...")
    # Use the common-pile mirror which is ungated (no auth needed)
    ds = load_dataset("common-pile/caselaw_access_project", split="train", streaming=True)

    processed = 0
    skipped = 0

    # Track courts we've seen to get diversity
    courts_seen: dict[str, int] = {}
    max_per_court = 10  # cap per court for diversity

    for record in ds:
        if processed >= args.limit:
            break

        # Extract text — try different fields (varies by dataset version)
        text = ""
        for field in ["text", "opinion", "plain_text", "html", "content"]:
            val = record.get(field)
            if val and isinstance(val, str) and len(val) > args.min_length:
                text = val
                break

        if not text or len(text) < args.min_length:
            skipped += 1
            continue

        if len(text) > args.max_length:
            skipped += 1
            continue

        # Get metadata
        court = record.get("court", {})
        court_name = ""
        if isinstance(court, dict):
            court_name = court.get("name", "") or court.get("name_abbreviation", "")
        elif isinstance(court, str):
            court_name = court

        # Diversity check
        if court_name in courts_seen and courts_seen[court_name] >= max_per_court:
            skipped += 1
            continue

        case_name = record.get("name", "") or record.get("name_abbreviation", "") or "Unknown"
        decision_date = record.get("decision_date", "") or ""
        docket_number = record.get("docket_number", "") or ""
        citations = record.get("citations", [])
        cite_str = citations[0].get("cite", "") if citations and isinstance(citations[0], dict) else ""

        # Clean HTML if needed
        if text.startswith("<"):
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()

        # Convert to markdown-ish format
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
        markdown += text

        processed += 1
        courts_seen[court_name] = courts_seen.get(court_name, 0) + 1

        sample_id = f"cap_{processed:03d}"

        # Write document
        doc_path = LEGAL_DIR / "documents" / f"{sample_id}.md"
        doc_path.write_text(markdown)

        # Write placeholder expected (needs manual annotation)
        exp_path = LEGAL_DIR / "expected" / f"{sample_id}.expected.json"
        if not exp_path.exists():
            # Pre-fill what we can from metadata
            expected = {
                "case_number": docket_number or None,
                "court": court_name or None,
                "filing_date": decision_date or None,
                "filing_type": "Opinion",  # CAP is mostly opinions
                "plaintiff": None,  # needs manual extraction from case name
                "defendant": None,  # needs manual extraction from case name
                "judge": None,  # needs manual extraction from text
                "_annotation_status": "auto_partial",
            }

            # Try to split case name into plaintiff v defendant
            if " v. " in case_name:
                parts = case_name.split(" v. ", 1)
                expected["plaintiff"] = parts[0].strip()
                expected["defendant"] = parts[1].strip()
            elif " v " in case_name:
                parts = case_name.split(" v ", 1)
                expected["plaintiff"] = parts[0].strip()
                expected["defendant"] = parts[1].strip()

            exp_path.write_text(json.dumps(expected, indent=2) + "\n")

        # Write manifest
        man_path = LEGAL_DIR / "manifests" / f"{sample_id}.json"
        manifest = {
            "filename": doc_path.name,
            "source_name": "Caselaw Access Project (Harvard Law School)",
            "source_url": f"https://case.law/",
            "license": "CC0 (Public Domain)",
            "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
            "attribution": "Caselaw Access Project, Harvard Law School Library Innovation Lab",
            "original_format": "text",
            "r2_url": None,
            "pages": max(1, len(text) // 3000),
            "added_date": time.strftime("%Y-%m-%d"),
            "added_by": "legal-cap-sourcer",
            "schema": "legal_filings/schemas/legal_filing.yaml",
            "case_name": case_name,
            "citation": cite_str,
            "court": court_name,
            "decision_date": decision_date,
            "notes": (
                f"Court opinion: {case_name}. Source: Caselaw Access Project "
                f"(Harvard). Expected JSON auto-filled from metadata where "
                f"possible; judge field needs manual annotation."
            ),
        }
        man_path.write_text(json.dumps(manifest, indent=2) + "\n")

        court_short = court_name[:30] if court_name else "Unknown"
        print(f"[legal] ({processed}/{args.limit}) {sample_id}: {case_name[:50]} ({court_short})")

        if processed % 50 == 0:
            print(f"[legal] Courts represented: {len(courts_seen)}")

    print(f"\n[legal] Done: {processed} saved, {skipped} skipped")
    print(f"[legal] Courts: {len(courts_seen)} unique courts")
    for court, count in sorted(courts_seen.items(), key=lambda x: -x[1])[:10]:
        print(f"  {court}: {count}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
