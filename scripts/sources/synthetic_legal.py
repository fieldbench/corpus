#!/usr/bin/env python3
"""Synthetic court-filing generator — matched-pair partner for the REAL
CourtListener/Caselaw legal_filings docs.

Purpose: the published corpus has legal_filings as 100% real (appellate opinions,
motions, orders scraped from public case law). To measure the synthetic-vs-real
accuracy gap *holding category (schema, difficulty class) constant*, we add
templated synthetic filings against the SAME `legal_filing.yaml` schema. Real and
synthetic then differ only in provenance/formatting, not in what is being
extracted — the controlled comparison the paper needs.

Deterministic (seeded). Emits documents/<id>.md, expected/<id>.expected.json,
manifests/<id>.json with source=synthetic, license CC0.

    python synthetic_legal.py --out <corpus>/legal_filings --n 40 [--seed N] [--realism {0,1}]
"""
from __future__ import annotations

import argparse
import json
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 51001  # distinct from other generators

FIRST = ["James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael",
         "Linda", "David", "Barbara", "William", "Elizabeth", "Richard", "Susan",
         "Joseph", "Margaret", "Thomas", "Dorothy", "Charles", "Nancy",
         "Daniel", "Karen", "Matthew", "Sandra", "Anthony", "Ashley", "Mark",
         "Kimberly", "Steven", "Donna", "Paul", "Carol", "Andrew", "Ruth"]
LAST = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
        "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
        "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
        "Trask", "Goodwin", "Wallace", "Merrill", "Koelsch", "Kilkenny", "Ely",
        "Ferguson", "Whitaker", "Reinhardt", "Kozinski", "Fletcher", "Bybee"]

# (company-name stem, suffix) pools for corporate parties
CO_STEMS = ["Northstar", "Bluewater", "Summit", "Pioneer", "Redwood", "Anchor",
            "Vanguard", "Cascade", "Meridian", "Ironclad", "Everest", "Sterling",
            "Beacon", "Cornerstone", "Highland", "Longview", "Crestline"]
CO_KINDS = ["Logistics", "Industries", "Holdings", "Technologies", "Capital",
            "Manufacturing", "Partners", "Systems", "Properties", "Financial"]
CO_SUFFIX = ["Inc.", "LLC", "Corp.", "Co.", "L.P.", "Ltd."]

GOVERNMENT = ["United States of America", "State of California",
              "People of the State of New York", "Commonwealth of Massachusetts",
              "State of Texas", "State of Washington"]

# (court name, level) — level drives docket format + judge style
COURTS = [
    ("United States Court of Appeals, Ninth Circuit", "appellate"),
    ("United States Court of Appeals, Second Circuit", "appellate"),
    ("United States Court of Appeals, Fifth Circuit", "appellate"),
    ("United States Court of Appeals, District of Columbia Circuit", "appellate"),
    ("United States District Court for the Southern District of New York", "district"),
    ("United States District Court for the Northern District of California", "district"),
    ("United States District Court for the District of Massachusetts", "district"),
    ("United States District Court for the Eastern District of Virginia", "district"),
    ("Superior Court of California, County of Los Angeles", "state"),
    ("Supreme Court of the State of New York, County of Kings", "state"),
    ("Circuit Court of Cook County, Illinois", "state"),
]

# Filing-type enum value -> candidate document titles. The correct enum keyword
# leads each title; other type keywords are avoided so the title is unambiguous.
TYPE_TITLES = {
    "Opinion": ["OPINION OF THE COURT", "PER CURIAM OPINION", "OPINION"],
    "Complaint": ["COMPLAINT FOR DAMAGES", "COMPLAINT FOR BREACH OF CONTRACT",
                  "VERIFIED COMPLAINT"],
    "Motion": ["MOTION TO DISMISS", "MOTION FOR SUMMARY JUDGMENT",
               "MOTION TO COMPEL DISCOVERY"],
    "Brief": ["APPELLANT'S OPENING BRIEF", "BRIEF FOR THE APPELLEE",
              "BRIEF IN SUPPORT"],
    "Order": ["ORDER", "SCHEDULING ORDER", "ORDER TO SHOW CAUSE"],
    "Memorandum": ["MEMORANDUM OF LAW IN SUPPORT", "MEMORANDUM IN OPPOSITION",
                   "MEMORANDUM OF POINTS AND AUTHORITIES"],
    "Declaration": ["DECLARATION IN SUPPORT", "DECLARATION OF COUNSEL"],
    "Stipulation": ["STIPULATION OF DISMISSAL", "JOINT STIPULATION"],
    "Answer": ["ANSWER AND AFFIRMATIVE DEFENSES", "ANSWER TO COMPLAINT"],
    "Other": ["NOTICE OF APPEAL", "PETITION FOR WRIT OF CERTIORARI",
              "NOTICE OF REMOVAL"],
}
FILING_TYPES = list(TYPE_TITLES.keys())


def _iso(d: date) -> str:
    return d.isoformat()


def _long(d: date) -> str:
    """February 12, 1973 — full month, no leading zero on day."""
    return f"{d.strftime('%B')} {d.day}, {d.year}"


def _abbr(d: date) -> str:
    """Feb. 12, 1973 — abbreviated month, caselaw-reporter style."""
    return f"{d.strftime('%b')}. {d.day}, {d.year}"


def _company(rng) -> str:
    name = f"{rng.choice(CO_STEMS)} {rng.choice(CO_KINDS)}"
    suf = rng.choice(CO_SUFFIX)
    # a comma before Inc./LLC etc. reads like a real corporate name
    return f"{name}, {suf}" if rng.random() < 0.6 else f"{name} {suf}"


def _party(rng) -> str:
    r = rng.random()
    if r < 0.30:
        return rng.choice(GOVERNMENT)
    if r < 0.65:
        return _company(rng)
    return f"{rng.choice(FIRST)} {rng.choice(LAST)}"


def _panel(rng) -> str:
    """Three-judge appellate panel, uppercase surnames: 'TRASK, GOODWIN and WALLACE'."""
    names = rng.sample(LAST, k=3)
    up = [n.upper() for n in names]
    return f"{up[0]}, {up[1]} and {up[2]}"


def _single_judge(rng) -> str:
    return f"{rng.choice(FIRST)} {rng.choice(LAST)}"


def _case_number(rng, level: str) -> str:
    if level == "appellate":
        yy = rng.randint(70, 99) if rng.random() < 0.5 else rng.randint(10, 24)
        return f"No. {yy}-{rng.randint(1000, 9999)}"
    if level == "district":
        yy = rng.randint(18, 24)
        kind = rng.choice(["cv", "cr"])
        return f"No. {rng.randint(1, 5)}:{yy:02d}-{kind}-{rng.randint(1000, 99999):05d}"
    # state
    style = rng.random()
    if style < 0.5:
        return f"Civil Action No. 20{rng.randint(18, 24)}-{rng.randint(1000, 9999):04d}"
    return f"Case No. {rng.randint(10, 24)}-{rng.randint(10000, 99999)}"


def _render_clean(rng, court, level, case_number, filing_date, filing_type, title,
                  plaintiff, defendant, judge):
    """Realism 0 — templated, one labeled fact per line. Trivially extractable;
    the conventional-synthetic extreme."""
    lines = [
        f"# {title}", "",
        f"**Court:** {court}",
        f"**Case Number:** {case_number}",
        f"**Filing Type:** {filing_type}",
        f"**Plaintiff:** {plaintiff}",
        f"**Defendant:** {defendant}",
        f"**Filing Date:** {_long(filing_date)}",
        f"**Judge:** {judge}", "",
        "## Caption",
        f"{plaintiff}, Plaintiff, v. {defendant}, Defendant.", "",
        "## Nature of Filing",
        f"This is a {filing_type.lower()} filed in {court}. "
        f"The above-captioned matter, bearing case number {case_number}, "
        f"came before the court on {_long(filing_date)}.",
    ]
    return "\n".join(lines) + "\n"


def _render_realistic(rng, court, level, case_number, filing_date, filing_type, title,
                      plaintiff, defendant, judge):
    """Realism 1 — facts embedded in dense caselaw-reporter prose with distractors:
    an 'argued' date before the decided date, attorney names that are not parties,
    a magistrate judge distinct from the presiding judge, and appellee/appellant
    role labels. Every ground-truth value is present and recoverable, just unlabeled."""
    # --- distractors ---
    argued = filing_date - timedelta(days=rng.randint(20, 120))   # distractor date
    citation = f"{rng.randint(200, 620)} F.{rng.choice(['2d', '3d', 'Supp.'])} {rng.randint(1, 999)}"  # distractor number
    atty_p = f"{rng.choice(FIRST)} {rng.choice(LAST)}"            # distractor person
    atty_d = f"{rng.choice(FIRST)} {rng.choice(LAST)}"            # distractor person
    magistrate = f"{rng.choice(FIRST)} {rng.choice(LAST)}"        # distractor judge

    if level == "appellate":
        p_role, d_role = "Plaintiff-Appellee", "Defendant-Appellant"
        judge_line = f"Before {judge}, Circuit Judges."
        court_disp = court
    else:
        p_role, d_role = "Plaintiff", "Defendant"
        judge_line = f"Before the Honorable {judge}, presiding."
        court_disp = court

    caption = f"{plaintiff}, {p_role}, v. {defendant}, {d_role}."

    para = (
        f"{caption} {case_number}. {court_disp}. {_abbr(filing_date)}. "
        f"Argued and submitted {_abbr(argued)}; decided {_abbr(filing_date)}. "
        f"Reported at {citation}. "
        f"{atty_p}, for the plaintiff; {atty_d}, for the defendant. "
        f"{judge_line} "
        f"The matter had earlier been referred to Magistrate Judge {magistrate} "
        f"for a report and recommendation, which the court now adopts in part. "
        f"This {filing_type.lower()} comes before {court_disp} on the pleadings "
        f"filed of record. Comes now the plaintiff, {plaintiff}, and respectfully "
        f"states as follows. The court, having reviewed the submissions in case "
        f"number {case_number}, and being fully advised, enters the following. "
        f"WHEREFORE, for the foregoing reasons, the relief requested is addressed "
        f"herein. Dated {_long(filing_date)}."
    )
    return f"# {title}\n\n{para}\n"


def make_doc(rng: random.Random, idx: int, realism: int = 0) -> tuple[str, dict, dict]:
    court, level = rng.choice(COURTS)
    case_number = _case_number(rng, level)
    filing_date = date(1970, 1, 1) + timedelta(days=rng.randint(0, 20000))
    filing_type = rng.choice(FILING_TYPES)
    title = rng.choice(TYPE_TITLES[filing_type])

    plaintiff = _party(rng)
    defendant = _party(rng)
    while defendant == plaintiff:
        defendant = _party(rng)

    judge = _panel(rng) if level == "appellate" else _single_judge(rng)

    stem = f"synth-legal-r{realism}-{idx:03d}"
    render = _render_clean if realism == 0 else _render_realistic
    doc = render(rng, court, level, case_number, filing_date, filing_type, title,
                 plaintiff, defendant, judge)

    expected = {
        "case_number": case_number,
        "court": court,
        "filing_date": _iso(filing_date),
        "filing_type": filing_type,
        "plaintiff": plaintiff,
        "defendant": defendant,
        "judge": judge,
    }
    manifest = {
        "id": stem,
        "source_name": "Synthetic generator (synthetic_legal.py)",
        "source_url": None,
        "license": "CC0-1.0",
        "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
        "schema": "legal_filings/schemas/legal_filing.yaml",
        "document": f"documents/{stem}.md",
        "expected": f"expected/{stem}.expected.json",
        "attribution": "Synthetic — no real case data.",
        "license_basis": "Machine-generated synthetic document; released CC0.",
        "source": "synthetic",
    }
    return doc, expected, manifest


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, type=Path, help="legal_filings category dir")
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--start", type=int, default=0, help="starting index (append)")
    ap.add_argument("--realism", type=int, default=0, choices=[0, 1],
                    help="0=clean templated, 1=prose-embedded with distractors")
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
    print(f"wrote {args.n} synthetic court filings to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
