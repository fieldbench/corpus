#!/usr/bin/env python3
"""Source insurance documents from publicly available PDFs.

Downloads real insurance policy documents and COIs from government,
university, and insurer websites. Parses each PDF through docling
(local, no fieldbench cluster needed) and writes the result into the
corpus as markdown + manifest.

Expected JSONs are NOT auto-generated — these documents require
manual ground-truth review because there's no authoritative index
(unlike EDGAR for SEC filings). The script writes a placeholder
expected.json with null fields that must be filled in by reading
the parsed markdown.

Usage:
    uv run --with httpx --with docling python scripts/sources/insurance_public.py
    uv run --with httpx --with docling python scripts/sources/insurance_public.py --limit 5
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import httpx

CORPUS_ROOT = Path(__file__).resolve().parent.parent.parent

# Each entry: (id_slug, url, doc_type, source_name, license_note)
SOURCES = [
    # ── CGL / General Liability policies ──
    (
        "sonoma_cgl",
        "https://sonomacounty.gov/Main%20County%20Site/General/Sonoma/Sample%20Dept/Sample%20Dept/Divisions%20and%20Sections/Liability/Services/Help%20Request/Subpages/Help%20Request/_Documents/SampleISO-CGL.pdf",
        "policy",
        "Sonoma County (ISO CG 00 01 CGL form)",
        "Public record — county government website",
    ),
    (
        "abais_gl",
        "https://www.abais.com/docs/default-source/banks/policy-specimen/general-liability-forms-w-dec-coverage-forms-mandatory-endorsements-exclusions.pdf",
        "policy",
        "ABAIS (GL dec + coverage forms + endorsements)",
        "Published specimen policy — insurer website",
    ),
    (
        "nyc_hpd_gl",
        "https://www.nyc.gov/assets/hpd/downloads/pdfs/services/general-liability-insurance-sample.pdf",
        "policy",
        "NYC HPD General Liability sample",
        "Public record — NYC government website",
    ),
    (
        "chubb_bop",
        "https://studio.chubb.com/connect/files/NA_BOP_Sample.pdf",
        "policy",
        "Chubb Businessowners Policy (BOP) sample",
        "Published specimen — insurer website",
    ),
    (
        "insurancebee_cgl",
        "https://www.insurancebee.com/documents/wordings/general-liability-policy-form.pdf",
        "policy",
        "InsuranceBee CGL policy form",
        "Published specimen — insurer website",
    ),
    (
        "ky_psc_liberty_gl_auto",
        "https://psc.ky.gov/pscecf/2022-00035/bob.miller@straightlineky.com/04212022022117/1b_Auto_and_GL_Policy_May2020-May2021.pdf",
        "policy",
        "Kentucky PSC — Liberty Mutual Auto + GL policy",
        "Public record — state regulatory filing",
    ),
    # ── Homeowners ──
    (
        "ok_farmers_ho",
        "https://www.oid.ok.gov/wp-content/uploads/2019/08/Farmers_56-5274ProtectorPlusHO.pdf",
        "policy",
        "Oklahoma DOI — Farmers Protector Plus Homeowners",
        "Public record — state insurance department",
    ),
    (
        "fl_sample_dec",
        "https://www.myfloridacfo.com/docs-sf/consumer-services-libraries/consumerservices-documents/understanding-coverage/sample-declarations-page.pdf",
        "policy",
        "Florida CFO — sample declarations page",
        "Public record — state government website",
    ),
    # ── Endorsements ──
    (
        "nv_cg2026_ai",
        "https://risk.nv.gov/uploadedfiles/risknvgov/content/Contracts/AdditionalInsuredFormCG2026.pdf",
        "endorsement",
        "Nevada Risk Management — CG 20 26 Additional Insured",
        "Public record — state government website",
    ),
    (
        "ny_ogs_commercial_auto",
        "https://ogs.ny.gov/system/files/documents/2021/09/ca-20-48-10-13.pdf",
        "policy",
        "NY OGS — Commercial Auto CA 20 48",
        "Public record — state government website",
    ),
    # ── Workers Comp ──
    (
        "insuranceboard_wc",
        "https://www.insuranceboard.org/wp-content/uploads/dlm_uploads/2019/11/10-sample-workers-compensation-policy.pdf",
        "policy",
        "Insurance Board — sample Workers Comp policy",
        "Published specimen — insurer website",
    ),
    (
        "ca_statefund_wc",
        "https://www.statefundca.com/siteassets/publications/workers-compensation-policy-sample.pdf",
        "policy",
        "CA State Fund — Workers Comp policy sample",
        "Public record — state fund website",
    ),
    # ── COIs (Certificates of Insurance) ──
    (
        "cornell_coi",
        "https://scl.cornell.edu/sites/scl/files/documents/OSFL-coi-%20sample.pdf",
        "coi",
        "Cornell University — sample COI",
        "Published sample — university website",
    ),
    (
        "calstate_coi",
        "https://www.calstate.edu/csu-system/doing-business-with-the-csu/capital-planning-design-construction/operations-center/Documents/meas/parc-insurance.pdf",
        "coi",
        "Cal State — construction project COI",
        "Public record — state university website",
    ),
    (
        "gatech_coi",
        "https://facilities.gatech.edu/sites/default/files/sample_coi_-general_consultant_contract_-_final.pdf",
        "coi",
        "Georgia Tech — consultant contract COI sample",
        "Published sample — university website",
    ),
    (
        "niu_coi",
        "https://www.niu.edu/risk-management/_files/niu-general-insurance-certificate.pdf",
        "coi",
        "Northern Illinois University — general insurance COI",
        "Published sample — university website",
    ),
    (
        "ucf_coi",
        "https://www.ucf.edu/downtown/wp-content/blogs.dir/21/files/2020/02/document-sample-certificate-of-liability-insurance.pdf",
        "coi",
        "UCF — sample certificate of liability insurance",
        "Published sample — university website",
    ),
    # ── Additional gov sources ──
    (
        "dc_ho_dec",
        "https://disb.dc.gov/sites/default/files/dc/sites/disb/publication/attachments/Declaration%20Page%20Sample%20Homeowners%2012.pdf",
        "policy",
        "DC DISB — homeowners declarations page sample",
        "Public record — DC government website",
    ),
    (
        "md_ho_dec",
        "https://insurance.maryland.gov/Consumer/Documents/publications/understandinghodeclarationspage.pdf",
        "policy",
        "Maryland Insurance Admin — understanding HO declarations",
        "Public record — state government website",
    ),
    (
        "ok_auto_dec",
        "https://www.oid.ok.gov/wp-content/uploads/2024/04/UnderstandingYourAutoPolicyDeclarations.pdf",
        "policy",
        "Oklahoma DOI — auto policy declarations guide",
        "Public record — state insurance department",
    ),
    (
        "nyc_dot_ai_endorsements",
        "https://www.nyc.gov/html/dot/downloads/pdf/additonal-insured-endorsements-sample.pdf",
        "endorsement",
        "NYC DOT — additional insured endorsement samples",
        "Public record — NYC government website",
    ),
    (
        "houston_sample_endorsements",
        "https://www.houstontx.gov/bizwithhou/forms/Sample_Insurance_Endorsements.pdf",
        "endorsement",
        "City of Houston — sample insurance endorsements",
        "Public record — city government website",
    ),
    # ── Additional real COIs from government sources ──
    (
        "nyc_buildings_coi",
        "https://www.nyc.gov/assets/buildings/pdf/acord_cert_of_ins_sample.pdf",
        "coi",
        "NYC Dept of Buildings — ACORD COI sample",
        "Public record — NYC government website",
    ),
    (
        "la_city_coi",
        "https://cao.lacity.gov/risk/ACORD25-CityofLA.pdf",
        "coi",
        "City of Los Angeles — ACORD 25 COI",
        "Public record — city government website",
    ),
    (
        "ks_kdhe_coi",
        "https://www.kdhe.ks.gov/DocumentCenter/View/5571/INS100---Certificate-of-Liability-Insurance-PDF",
        "coi",
        "Kansas KDHE — Certificate of Liability Insurance",
        "Public record — state government website",
    ),
    (
        "miami_dade_coi",
        "https://www.miamidade.gov/Apps/RER/CLRA/media/SampleCertificate.pdf",
        "coi",
        "Miami-Dade County — sample ACORD certificate",
        "Public record — county government website",
    ),
    (
        "nj_eda_coi",
        "https://www.njeda.gov/wp-content/uploads/2024/10/Certificate-of-Liability-Insurance-Sample-_-TLS-12-1.pdf",
        "coi",
        "New Jersey EDA — Certificate of Liability Insurance",
        "Public record — state authority website",
    ),
    (
        "stpaul_coi",
        "https://www.stpaul.gov/sites/default/files/2024-02/NSTAR2023_SampleInsuranceCertificate_rev.pdf",
        "coi",
        "City of Saint Paul — ACORD certificate example",
        "Public record — city government website",
    ),
    (
        "larimer_coi",
        "https://www.larimer.gov/sites/default/files/uploads/2021/certificate_of_insurance_example_certificate_-_coi.pdf",
        "coi",
        "Larimer County CO — COI example",
        "Public record — county government website",
    ),
    (
        "michigan_dot_coi",
        "https://www.michigan.gov/-/media/Project/Websites/MDOT/Travel/Mobility/Rail/State-Owned-Rail/ACORD-Form-Sample.pdf",
        "coi",
        "Michigan DOT — ACORD form sample",
        "Public record — state DOT website",
    ),
    (
        "texas_rrc_coi",
        "https://www.rrc.texas.gov/media/kh2p1ugz/acord25_-certificate-of-insurance.pdf",
        "coi",
        "Texas Railroad Commission — ACORD 25 COI",
        "Public record — state commission website",
    ),
    (
        "seattle_coi",
        "https://www.seattle.gov/documents/Departments/DEEL/FundingOpportunities/RFIs/2025/2025%20YMH%20Evaluation%20RFI/Sample%20Insurance%20Coverage%20-%20Acord%20Certificate%20and%20Additional%20Insured.pdf",
        "coi",
        "City of Seattle — ACORD certificate + additional insured",
        "Public record — city government website",
    ),
    (
        "oklahoma_coi",
        "https://oklahoma.gov/content/dam/ok/en/cib/documents/your-industry/sampleinsurance.pdf",
        "coi",
        "Oklahoma CIB — sample insurance certificate",
        "Public record — state government website",
    ),
    (
        "temecula_coi",
        "https://temeculaca.gov/DocumentCenter/View/14593/Sample-Insurance-Certificate",
        "coi",
        "City of Temecula CA — sample insurance certificate",
        "Public record — city government website",
    ),
    (
        "nevada_coi_endorsements",
        "https://risk.nv.gov/uploadedfiles/risknvgov/content/Contracts/CertOfInsAndEndorsementSamples.pdf",
        "coi",
        "Nevada Risk Management — COI + endorsement samples",
        "Public record — state government website",
    ),
    (
        "arizona_coi",
        "https://staterisk.az.gov/sites/default/files/2022-04/COI%20Sample%20Form%20with%20HoverOver%20Instructions_1_0.pdf",
        "coi",
        "Arizona Risk Management — COI sample form",
        "Public record — state government website",
    ),
    (
        "edmond_ok_coi",
        "https://www.edmondok.gov/DocumentCenter/View/2783/Certificates-of-Insurance-example-",
        "coi",
        "City of Edmond OK — COI example",
        "Public record — city government website",
    ),
]


def download_pdf(url: str, client: httpx.Client) -> bytes | None:
    try:
        resp = client.get(url, follow_redirects=True, timeout=60.0)
        if resp.status_code != 200:
            print(f"  HTTP {resp.status_code}", file=sys.stderr)
            return None
        content_type = resp.headers.get("content-type", "")
        if "pdf" not in content_type and not resp.content[:5] == b"%PDF-":
            print(f"  not a PDF ({content_type})", file=sys.stderr)
            return None
        return resp.content
    except Exception as e:
        print(f"  download error: {e}", file=sys.stderr)
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
        print(f"  docling error: {e}", file=sys.stderr)
        return None


def write_sample(
    slug: str,
    doc_type: str,
    markdown: str,
    url: str,
    source_name: str,
    license_note: str,
    target_dir: Path,
) -> None:
    (target_dir / "documents").mkdir(parents=True, exist_ok=True)
    (target_dir / "expected").mkdir(parents=True, exist_ok=True)
    (target_dir / "manifests").mkdir(parents=True, exist_ok=True)

    doc_path = target_dir / "documents" / f"{slug}.md"
    exp_path = target_dir / "expected" / f"{slug}.expected.json"
    man_path = target_dir / "manifests" / f"{slug}.json"

    doc_path.write_text(markdown + "\n")

    # Placeholder expected — needs manual review
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
        "added_by": "accuracy-23",
        "schema": (
            "insurance_certificates/schemas/certificate_of_liability.yaml"
            if doc_type == "coi"
            else "insurance_policies/schemas/policy_declarations.yaml"
        ),
        "doc_type": doc_type,
        "notes": f"Real {doc_type} document sourced from {source_name}. Expected JSON needs manual ground-truth review.",
    }
    man_path.write_text(json.dumps(manifest, indent=2) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, default=len(SOURCES), help="Max documents to process")
    args = parser.parse_args()

    try:
        import docling.document_converter  # noqa: F401
    except ImportError:
        print(
            "[insurance] docling required. Run with:\n"
            "  uv run --with httpx --with docling python scripts/sources/insurance_public.py",
            file=sys.stderr,
        )
        return 1

    processed = 0
    failed = 0

    with httpx.Client(headers={"User-Agent": "FieldBench Corpus bot@getfieldbench.dev"}) as client:
        for slug, url, doc_type, source_name, license_note in SOURCES:
            if processed >= args.limit:
                break

            # Route COIs to insurance_certificates, policies to insurance_policies
            if doc_type == "coi":
                target_dir = CORPUS_ROOT / "insurance_certificates"
            else:
                target_dir = CORPUS_ROOT / "insurance_policies"

            doc_path = target_dir / "documents" / f"{slug}.md"
            if doc_path.exists():
                print(f"[insurance] skip {slug} (exists)", file=sys.stderr)
                continue

            print(f"[insurance] ({processed + 1}/{args.limit}) {slug} ...", file=sys.stderr, end=" ")

            pdf = download_pdf(url, client)
            if pdf is None:
                failed += 1
                continue

            print(f"{len(pdf) // 1024}KB ...", file=sys.stderr, end=" ")

            md = parse_pdf_local(pdf, f"{slug}.pdf")
            if md is None:
                failed += 1
                continue

            write_sample(slug, doc_type, md, url, source_name, license_note, target_dir)
            processed += 1
            print(f"ok ({len(md)} chars)", file=sys.stderr)

            time.sleep(0.5)

    print(f"\n[insurance] Done. Processed: {processed}, Failed: {failed}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
