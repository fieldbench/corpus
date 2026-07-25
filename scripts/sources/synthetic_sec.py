#!/usr/bin/env python3
"""Synthetic SEC-filing generator — matched-pair partner for the REAL EDGAR docs.

Purpose: the published corpus has sec_filings as 100% real EDGAR filings. To
measure the synthetic-vs-real accuracy gap *holding category (schema, difficulty
class) constant*, we add templated synthetic filing cover pages against the SAME
`filing_metadata.yaml` schema. Real and synthetic then differ only in
provenance/formatting, not in what is being extracted — the controlled comparison
§6.3 needs.

Deterministic (seeded). Emits documents/<id>.md, expected/<id>.expected.json,
manifests/<id>.json with source=synthetic, license CC0.

    python synthetic_sec.py --out <corpus>/sec_filings --n 40 [--seed N] [--realism {0,1}]

Self-consistency invariant: every non-null ground-truth value appears verbatim
(filer_name) or in a recognizable long-date format ("December 31, 2025") in the
generated document. Only the period_* field that matches the form_type is
populated; the others are null AND no matching period date is written for them.
"""
from __future__ import annotations

import argparse
import json
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 53001  # distinct from other generators

# (form_type enum value, period kind)
#   fye     -> period_fiscal_year_end   (10-K family)
#   qe      -> period_quarter_end       (10-Q family)
#   dor     -> period_date_of_report    (8-K / 6-K families)
#   meeting -> period_meeting_date      (DEF 14A)
#   None    -> no period_* field applies (S-1, 20-F families)
FORM_SPECS = [
    ("10-K", "fye"),
    ("10-K", "fye"),
    ("10-K/A", "fye"),
    ("10-Q", "qe"),
    ("10-Q", "qe"),
    ("10-Q/A", "qe"),
    ("8-K", "dor"),
    ("8-K", "dor"),
    ("8-K/A", "dor"),
    ("6-K", "dor"),
    ("DEF 14A", "meeting"),
    ("DEF 14A", "meeting"),
    ("S-1", None),
    ("S-1/A", None),
    ("20-F", None),
]

# Curated full registrant names — used verbatim in both doc and expected.json.
COMPANIES = [
    "Meridian Dynamics Corporation",
    "Blue Harbor Financial Group, Inc.",
    "Cascade Biosciences, Inc.",
    "Ironwood Industrial Holdings Corp.",
    "Northwind Energy Partners, Inc.",
    "Silverleaf Technologies, Inc.",
    "Granite Peak Resources Corporation",
    "Concordia Health Systems, Inc.",
    "Aurora Semiconductor Corp.",
    "Longbow Capital Group, Inc.",
    "Evergreen Logistics Holdings, Inc.",
    "Summit Ridge Bancorp",
    "Halcyon Therapeutics, Inc.",
    "Pinnacle Aerospace Corporation",
    "Redwood Digital Media, Inc.",
    "Cobalt Ventures Group, Inc.",
    "Sterling Materials Company",
    "Vanguard Robotics Corporation",
    "Crestline Insurance Holdings, Inc.",
    "Talon Software, Inc.",
    "Marlin Offshore Energy Limited",
    "Kingfisher Consumer Brands, Inc.",
    "Obelisk Data Centers Corp.",
    "Solstice Renewable Power, Inc.",
    "Wren & Barlow Holdings plc",
    "Ashford Mining Company",
    "Beacon Point Pharmaceuticals, Inc.",
    "Delphi Analytics Group, Inc.",
    "Fairwind Shipping Company Limited",
    "Zenith Communications Corporation",
]

FIRST = ["James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael",
         "Linda", "David", "Barbara", "William", "Elizabeth", "Richard", "Susan",
         "Joseph", "Margaret", "Thomas", "Karen", "Charles", "Nancy"]
LAST = ["Whitfield", "Alvarez", "Carrington", "Dela Cruz", "Emerson", "Fontaine",
        "Grigsby", "Halloran", "Ishikawa", "Kowalski", "Laurent", "Montoya",
        "Nakamura", "Osei", "Pemberton", "Quintero", "Rasmussen", "Sinclair",
        "Thibault", "Vasquez"]
TITLES = ["Chief Executive Officer", "President", "Chief Financial Officer"]
AUDITORS = ["Deloitte & Touche LLP", "Ernst & Young LLP", "KPMG LLP",
            "PricewaterhouseCoopers LLP", "BDO USA, LLP", "Marcum LLP", "Grant Thornton LLP"]
STATES = ["Delaware", "Nevada", "Maryland", "California", "New York", "Texas", "Colorado"]


def _iso(d: date) -> str:
    return d.isoformat()


def _long(d: date) -> str:
    """Recognizable long date, e.g. 'December 31, 2025' (no zero-padded day)."""
    return f"{d:%B} {d.day}, {d.year}"


def _eom(d: date) -> date:
    """Last day of d's month."""
    if d.month == 12:
        return date(d.year, 12, 31)
    return date(d.year, d.month + 1, 1) - timedelta(days=1)


def _prev_quarter_end(d: date) -> date:
    """Most recent calendar-quarter end strictly before d."""
    q = [date(d.year - 1, 12, 31), date(d.year, 3, 31),
         date(d.year, 6, 30), date(d.year, 9, 30), date(d.year, 12, 31)]
    return [x for x in q if x < d][-1]


def _period_label_clean(kind: str) -> str:
    return {
        "fye": "For the fiscal year ended",
        "qe": "For the quarterly period ended",
        "dor": "Date of Report (Date of earliest event reported)",
        "meeting": "Date of Annual Meeting of Stockholders",
    }[kind]


def _compute(rng: random.Random):
    """Draw a self-consistent set of dates + parties for one filing."""
    form_type, kind = rng.choice(FORM_SPECS)
    filer = rng.choice(COMPANIES)
    officer = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
    title = rng.choice(TITLES)
    state = rng.choice(STATES)
    auditor = rng.choice(AUDITORS)

    filing = date(2026, 1, 1) + timedelta(days=rng.randint(0, 300))

    period = None
    prior = None  # same-field comparative distractor
    if kind == "fye":
        period = _eom(filing - timedelta(days=rng.randint(45, 120)))
        prior = _eom(date(period.year - 1, period.month, 1))
    elif kind == "qe":
        period = _prev_quarter_end(filing - timedelta(days=rng.randint(20, 50)))
        prior = date(period.year - 1, period.month, period.day)
    elif kind == "dor":
        # 8-K event just before filing; 6-K report date at/near filing
        period = filing - timedelta(days=rng.randint(0, 5))
    elif kind == "meeting":
        period = filing + timedelta(days=rng.randint(25, 55))

    extras = {
        "officer": officer,
        "title": title,
        "state": state,
        "auditor": auditor,
        "auditor_date": filing - timedelta(days=rng.randint(1, 15)),
        "incorp_date": filing - timedelta(days=rng.randint(3000, 12000)),
        "orig_filed": filing - timedelta(days=rng.randint(60, 400)),  # /A distractor
        "amend_no": rng.randint(1, 3),
        "record_date": filing - timedelta(days=rng.randint(5, 20)),   # DEF 14A distractor
        "as_of": filing - timedelta(days=rng.randint(5, 30)),         # S-1/20-F distractor
        "prior": prior,
        "commission_file": f"00{rng.randint(1,9)}-{rng.randint(10000,99999)}",
    }
    return form_type, kind, filer, filing, period, extras


def _render_clean(form_type, kind, filer, filing, period, extras) -> str:
    """Realism 0 — cover page with one labeled fact per line. Trivially extractable;
    the conventional-synthetic extreme."""
    lines = [
        "**U.S. SECURITIES AND EXCHANGE COMMISSION**", "",
        "**Washington, D.C. 20549**", "",
        f"**FORM {form_type}**", "",
        f"**{filer.upper()}**", "",
        "(Exact name of registrant as specified in its charter)", "",
        f"**Filer:** {filer}",
        f"**Form Type:** {form_type}",
        f"**Filing Date:** {_long(filing)}",
    ]
    if kind is not None:
        lines.append(f"**{_period_label_clean(kind)}:** {_long(period)}")
    lines += [
        f"**State of incorporation:** {extras['state']}",
        f"**Commission file number:** {extras['commission_file']}",
        "",
        "**SIGNATURES**",
        "",
        "Pursuant to the requirements of the Securities Exchange Act of 1934, "
        "this report has been signed below by the following duly authorized "
        "officer of the registrant on the date indicated.",
        "",
        f"Dated: {_long(filing)}   By: /s/ {extras['officer']}",
        f"Name: {extras['officer']}",
        f"Title: {extras['title']}",
        "",
    ]
    return "\n".join(lines) + "\n"


def _render_realistic(rng, form_type, kind, filer, filing, period, extras) -> str:
    """Realism 1 — facts embedded in a dense EDGAR-style cover-page narrative with
    distractor dates (comparative period, auditor signing date, incorporation date,
    original-filing date on amendments, record date on proxies). No per-field labels
    for the answers; filing_date lives in the signature/mailing block, the one
    relevant period date lives in cover-page prose. The over-abstention / distractor
    test."""
    officer, title = extras["officer"], extras["title"]
    state, auditor = extras["state"], extras["auditor"]
    is_amend = form_type.endswith("/A")
    base_form = form_type[:-2] if is_amend else form_type
    is_6k = base_form == "6-K"

    parts = [
        "**UNITED STATES SECURITIES AND EXCHANGE COMMISSION**", "",
        "Washington, D.C. 20549", "",
    ]

    # 6-K foreign-private-issuer bare-date cover convention.
    if is_6k:
        parts += [
            "**FORM 6-K**", "",
            "Report of Foreign Private Issuer Pursuant to Rule 13a-16 or "
            "15d-16(a) of the Securities Exchange Act of 1934", "",
            f"{_long(period)}", "",  # bare standalone report date
            f"**{filer}**", "",
            f"(Commission File Number: {extras['commission_file']})", "",
        ]
    else:
        parts += [f"**FORM {base_form}**"]
        if is_amend:
            parts += ["", f"**Amendment No. {extras['amend_no']}**"]
        parts += [
            "",
            f"**{filer}**", "",
            "(Exact name of registrant as specified in its charter)", "",
            f"Incorporated in the State of {state} on "
            f"{_long(extras['incorp_date'])}. Commission file number "
            f"{extras['commission_file']}.", "",
        ]

    # Explanatory note on amendments (original-filing date is a distractor).
    if is_amend:
        parts += [
            "EXPLANATORY NOTE", "",
            f"This Amendment No. {extras['amend_no']} amends the report on Form "
            f"{base_form} originally filed with the Commission on "
            f"{_long(extras['orig_filed'])}. This Amendment is being filed solely "
            f"to correct certain disclosures and does not otherwise modify the "
            f"registrant's previously reported results.", "",
        ]

    # Period prose (only the field that matches the form type).
    if kind == "fye":
        parts += [
            f"This Annual Report on Form {base_form} is filed for the fiscal year "
            f"ended {_long(period)}. The accompanying financial statements present "
            f"comparative results for the fiscal year ended {_long(extras['prior'])}. "
            f"The report of the registrant's independent registered public accounting "
            f"firm, {auditor}, is dated {_long(extras['auditor_date'])}.", "",
        ]
    elif kind == "qe":
        parts += [
            f"The accompanying unaudited condensed financial statements of the "
            f"registrant are presented for the quarterly period ended "
            f"{_long(period)}, together with comparative figures for the quarterly "
            f"period ended {_long(extras['prior'])}. These interim statements were "
            f"reviewed by {auditor} as of {_long(extras['auditor_date'])}.", "",
        ]
    elif kind == "dor" and not is_6k:
        parts += [
            f"Date of Report (Date of earliest event reported): {_long(period)}. "
            f"The registrant is furnishing this Current Report to disclose the "
            f"matters described in the Items below, which occurred on the date of "
            f"the earliest event reported above.", "",
        ]
    elif kind == "meeting":
        parts += [
            "NOTICE OF ANNUAL MEETING OF STOCKHOLDERS", "",
            f"The Annual Meeting of Stockholders of {filer} will be held on "
            f"{period:%A}, {_long(period)} at 10:00 a.m., local time. Only "
            f"stockholders of record at the close of business on "
            f"{_long(extras['record_date'])} are entitled to notice of and to vote "
            f"at the meeting. These proxy materials were first made available to "
            f"stockholders on or about {_long(filing)}.", "",
        ]
    elif kind is None:
        # S-1 / 20-F: no period_* field applies — deliberately no fiscal/quarter/
        # event/meeting date in the body. Only an unrelated as-of share-count date.
        parts += [
            f"As of {_long(extras['as_of'])}, the registrant had outstanding the "
            f"shares of common stock described under Capitalization. This is a "
            f"distractor date and does not correspond to any period of report.", "",
        ]

    # Signature / filing-date block. DEF 14A uses the mailing date (already above),
    # so no officer signature block for proxies.
    if kind != "meeting":
        parts += [
            "**SIGNATURES**", "",
            "Pursuant to the requirements of the Securities Exchange Act of 1934, "
            "the registrant has duly caused this report to be signed on its behalf "
            "by the undersigned, thereunto duly authorized.", "",
            f"By: /s/ {officer}", "",
            f"{officer}, {title}", "",
            f"Dated: {_long(filing)}", "",
        ]

    return "\n".join(parts) + "\n"


def make_doc(rng: random.Random, idx: int, realism: int = 0) -> tuple[str, dict, dict]:
    form_type, kind, filer, filing, period, extras = _compute(rng)

    stem = f"synth-sec-r{realism}-{idx:03d}"
    if realism == 0:
        doc = _render_clean(form_type, kind, filer, filing, period, extras)
    else:
        doc = _render_realistic(rng, form_type, kind, filer, filing, period, extras)

    expected = {
        "filer_name": filer,
        "form_type": form_type,
        "filing_date": _iso(filing),
        "period_fiscal_year_end": _iso(period) if kind == "fye" else None,
        "period_quarter_end": _iso(period) if kind == "qe" else None,
        "period_date_of_report": _iso(period) if kind == "dor" else None,
        "period_meeting_date": _iso(period) if kind == "meeting" else None,
    }
    manifest = {
        "id": stem,
        "source_name": "Synthetic generator (synthetic_sec.py)",
        "source_url": None,
        "license": "CC0-1.0",
        "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
        "schema": "sec_filings/schemas/filing_metadata.yaml",
        "document": f"documents/{stem}.md",
        "expected": f"expected/{stem}.expected.json",
        "attribution": "Synthetic — no real company or filing data.",
        "license_basis": "Machine-generated synthetic document; released CC0.",
        "source": "synthetic",
    }
    return doc, expected, manifest


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, type=Path, help="sec_filings category dir")
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--start", type=int, default=0, help="starting index (append)")
    ap.add_argument("--realism", type=int, default=0, choices=[0, 1],
                    help="0=clean templated cover page, 1=prose-embedded with distractors")
    args = ap.parse_args(argv)

    rng = random.Random(args.seed + args.realism)
    for sub in ("documents", "expected", "manifests"):
        (args.out / sub).mkdir(parents=True, exist_ok=True)

    for i in range(args.start, args.start + args.n):
        doc, expected, manifest = make_doc(rng, i, args.realism)
        stem = manifest["id"]
        (args.out / "documents" / f"{stem}.md").write_text(doc)
        (args.out / "expected" / f"{stem}.expected.json").write_text(
            json.dumps(expected, indent=2) + "\n")
        (args.out / "manifests" / f"{stem}.json").write_text(
            json.dumps(manifest, indent=2) + "\n")
    print(f"wrote {args.n} synthetic SEC filings (realism={args.realism}) to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
