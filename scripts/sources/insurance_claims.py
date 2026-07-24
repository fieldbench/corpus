#!/usr/bin/env python3
"""Source insurance claim forms from public government websites.

Downloads FEMA NFIP proof-of-loss forms and state workers compensation
first-report-of-injury forms, parses each PDF through local docling,
and writes into the insurance_claims corpus category.

Usage:
    uv run --with httpx --with docling python scripts/sources/insurance_claims.py
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import httpx

CORPUS_ROOT = Path(__file__).resolve().parent.parent.parent
CLAIMS_DIR = CORPUS_ROOT / "insurance_claims"

SOURCES = [
    # ── FEMA NFIP Proof of Loss ──
    (
        "fema_proof_of_loss_086",
        "https://www.fema.gov/sites/default/files/2020-07/FEMA-Form_086-0-09_proof-of-loss.pdf",
        "proof_of_loss",
        "FEMA Form 086-0-09 — NFIP Proof of Loss",
        "Public domain — US Government work",
    ),
    (
        "fema_proof_of_loss_hpcc",
        "https://www.fema.gov/sites/default/files/documents/fema_hpcc-proof-of-loss-form-english-exp-11.30.2026.pdf",
        "proof_of_loss",
        "FEMA HPCC Proof of Loss (current version)",
        "Public domain — US Government work",
    ),
    # ── Workers Comp First Report of Injury ──
    (
        "wc_froi_texas",
        "https://www.tdi.texas.gov/forms/dwc/dwc001rpt.pdf",
        "first_report_of_injury",
        "Texas DWC Form-001 — First Report of Injury",
        "Public domain — state government form",
    ),
    (
        "wc_froi_federal",
        "https://www.dol.gov/sites/dolgov/files/owcp/dlhwc/ls-202.pdf",
        "first_report_of_injury",
        "DOL Federal LS-202 — Employer's First Report of Injury",
        "Public domain — US Government work",
    ),
    (
        "wc_froi_south_carolina",
        "https://wcc.sc.gov/sites/wcc/files/Documents/Header/Forms/Form12A.pdf",
        "first_report_of_injury",
        "South Carolina WCC Form 12A — First Report of Injury",
        "Public domain — state government form",
    ),
    (
        "wc_froi_virginia",
        "https://workcomp.virginia.gov/sites/default/files/forms/First-Report-of-Injury_0.pdf",
        "first_report_of_injury",
        "Virginia VWC Form #3 — First Report of Injury",
        "Public domain — state government form",
    ),
    (
        "wc_froi_minnesota",
        "https://www.dli.mn.gov/sites/default/files/pdf/fr01.pdf",
        "first_report_of_injury",
        "Minnesota Form FR01 — First Report of Injury",
        "Public domain — state government form",
    ),
    (
        "wc_froi_idaho",
        "https://iic.idaho.gov/wp-content/uploads/2018/01/ic_1_froi.pdf",
        "first_report_of_injury",
        "Idaho IC-1 — First Report of Injury or Illness",
        "Public domain — state government form",
    ),
    (
        "wc_froi_utah",
        "https://laborcommission.utah.gov/wp-content/uploads/2019/11/Form-122-E-Revised-2-2019.pdf",
        "first_report_of_injury",
        "Utah Form 122E — Employer's First Report of Injury",
        "Public domain — state government form",
    ),
    (
        "wc_froi_alabama",
        "https://labor.alabama.gov/docs/forms/wc_froi_new_with_different_margins.pdf",
        "first_report_of_injury",
        "Alabama — Employer's First Report of Injury",
        "Public domain — state government form",
    ),
    (
        "wc_froi_mississippi",
        "https://mwcc.ms.gov/pdf/1streport.pdf",
        "first_report_of_injury",
        "Mississippi MWCC — First Report of Injury or Illness",
        "Public domain — state government form",
    ),
    (
        "wc_froi_texas_spanish",
        "https://www.tdi.texas.gov/forms/dwc/dwc1s.pdf",
        "first_report_of_injury",
        "Texas DWC Form-001S — First Report of Injury (Spanish)",
        "Public domain — state government form",
    ),
]


def download_pdf(url: str, client: httpx.Client) -> bytes | None:
    try:
        resp = client.get(url, follow_redirects=True, timeout=60.0)
        if resp.status_code != 200:
            print(f"HTTP {resp.status_code}", file=sys.stderr)
            return None
        if not resp.content[:5] == b"%PDF-":
            ct = resp.headers.get("content-type", "")
            if "pdf" not in ct:
                print(f"not PDF ({ct})", file=sys.stderr)
                return None
        return resp.content
    except Exception as e:
        print(f"download error: {e}", file=sys.stderr)
        return None


def parse_pdf_local(pdf_bytes: bytes, filename: str) -> str | None:
    import io
    from docling.datamodel.base_models import DocumentStream
    from docling.document_converter import DocumentConverter

    try:
        stream = DocumentStream(name=filename, stream=io.BytesIO(pdf_bytes))
        converter = DocumentConverter()
        result = converter.convert(stream)
        md = result.document.export_to_markdown()
        return md if md.strip() else None
    except Exception as e:
        print(f"docling error: {e}", file=sys.stderr)
        return None


def write_sample(slug, doc_type, markdown, url, source_name, license_note):
    doc_path = CLAIMS_DIR / "documents" / f"{slug}.md"
    exp_path = CLAIMS_DIR / "expected" / f"{slug}.expected.json"
    man_path = CLAIMS_DIR / "manifests" / f"{slug}.json"

    doc_path.write_text(markdown + "\n")
    exp_path.write_text(json.dumps({"_needs_review": True}, indent=2) + "\n")

    manifest = {
        "filename": doc_path.name,
        "source_name": source_name,
        "source_url": url,
        "license": license_note,
        "license_url": None,
        "attribution": source_name,
        "original_format": "PDF (parsed via docling)",
        "r2_url": None,
        "pages": max(1, len(markdown) // 3000),
        "added_date": "2026-04-16",
        "added_by": "accuracy-25",
        "schema": "insurance_claims/schemas/claim_form.yaml",
        "doc_type": doc_type,
        "notes": f"Real {doc_type} form from {source_name}.",
    }
    man_path.write_text(json.dumps(manifest, indent=2) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, default=len(SOURCES))
    args = parser.parse_args()

    try:
        import docling.document_converter  # noqa: F401
    except ImportError:
        print("[claims] docling required. Run with: uv run --with httpx --with docling ...", file=sys.stderr)
        return 1

    for sub in ("documents", "expected", "manifests"):
        (CLAIMS_DIR / sub).mkdir(parents=True, exist_ok=True)

    processed = failed = 0
    with httpx.Client(headers={"User-Agent": "FieldBench Corpus bot@getfieldbench.dev"}) as client:
        for slug, url, doc_type, source_name, license_note in SOURCES:
            if processed >= args.limit:
                break
            if (CLAIMS_DIR / "documents" / f"{slug}.md").exists():
                print(f"[claims] skip {slug} (exists)", file=sys.stderr)
                continue
            print(f"[claims] ({processed + 1}/{args.limit}) {slug} ...", file=sys.stderr, end=" ")
            pdf = download_pdf(url, client)
            if pdf is None:
                failed += 1
                continue
            print(f"{len(pdf)//1024}KB ...", file=sys.stderr, end=" ")
            md = parse_pdf_local(pdf, f"{slug}.pdf")
            if md is None:
                failed += 1
                continue
            write_sample(slug, doc_type, md, url, source_name, license_note)
            processed += 1
            print(f"ok ({len(md)} chars)", file=sys.stderr)
            time.sleep(0.5)

    print(f"\n[claims] Done. Processed: {processed}, Failed: {failed}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
