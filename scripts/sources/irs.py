#!/usr/bin/env python3
"""IRS form synthetic generator for the FieldBench corpus.

Generates synthetic IRS tax forms (1099-NEC, W-2) with completely fake data
and perfect deterministic ground truth. Real IRS forms contain PII, so we
avoid them entirely — synthetic data gives us unlimited variety without
privacy concerns.

Why synthetic instead of real:
  - Real tax forms contain SSNs, income, and personal information we cannot
    legally redistribute
  - Synthetic generation produces perfect ground truth (the generator knows
    what it put on the form)
  - We can produce unlimited variety across income brackets, filing statuses,
    and form layouts
  - Deterministic via --seed for reproducibility

Usage:
  python scripts/sources/irs.py --form-type 1099-nec --count 20
  python scripts/sources/irs.py --form-type w2 --count 30 --seed 42
  python scripts/sources/irs.py --form-type all --count 50

Supported form types:
  - 1099-nec : Nonemployee Compensation
  - w2       : Wage and Tax Statement
  - all      : Generate all supported types

Output:
  Each generated form is written as three files in the irs_forms/ category:
    - documents/<name>.md            - the form as markdown
    - expected/<name>.expected.json  - ground truth matching the form exactly
    - manifests/<name>.json          - metadata with synthetic: true flag
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

CORPUS_ROOT = Path(__file__).resolve().parent.parent.parent
IRS_DIR = CORPUS_ROOT / "irs_forms"

# ── Fake data pools ──────────────────────────────────────────────

FIRST_NAMES = [
    "Alex", "Jordan", "Taylor", "Morgan", "Riley", "Casey", "Avery",
    "Jamie", "Quinn", "Reese", "Blake", "Cameron", "Drew", "Emerson",
    "Finley", "Harper", "Kendall", "Logan", "Parker", "Rowan", "Sawyer",
    "Rachel", "David", "Marcus", "Jennifer", "Thomas", "Elena", "Samuel",
]

MIDDLE_INITIALS = ["A", "B", "C", "D", "E", "F", "G", "H", "J", "K", "L", "M", "N", "P", "R", "S", "T", "W"]

LAST_NAMES = [
    "Anderson", "Brown", "Chen", "Davis", "Evans", "Garcia", "Hernandez",
    "Johnson", "Kim", "Lee", "Martinez", "Nguyen", "O'Brien", "Patel",
    "Rodriguez", "Smith", "Thompson", "Vasquez", "Williams", "Zhang",
    "Martinez", "Thompson", "Freelancer",
]

COMPANY_PREFIXES = [
    "Acme", "Summit", "Pacific", "Meridian", "Apex", "Nexus", "Vertex",
    "Horizon", "Crescent", "Pinnacle", "Atlas", "Harbor", "Redwood",
    "Alpine", "Cascade", "Ridgeline", "Northstar", "Keystone", "Ironwood",
]

COMPANY_SUFFIXES = [
    "Consulting LLC", "Digital Strategies, Inc.", "Logistics Inc.",
    "Manufacturing Corp.", "Technologies LLC", "Solutions Group",
    "Partners LP", "Enterprises Inc.", "Holdings LLC", "Industries Inc.",
]

CITIES = [
    ("Portland", "OR", "97201"),
    ("Seattle", "WA", "98101"),
    ("Denver", "CO", "80202"),
    ("Chicago", "IL", "60614"),
    ("San Francisco", "CA", "94111"),
    ("Oakland", "CA", "94605"),
    ("Cleveland", "OH", "44109"),
    ("Akron", "OH", "44313"),
    ("Austin", "TX", "78701"),
    ("Boston", "MA", "02108"),
    ("Miami", "FL", "33101"),
    ("Phoenix", "AZ", "85001"),
]

STREETS = [
    "Business Park Drive", "Mountainview Parkway", "Harbor Way",
    "Industrial Parkway", "Main Street", "Oak Ridge Drive",
    "Elm Street", "Pine Avenue", "Cedar Lane", "Maple Boulevard",
    "First Avenue", "Market Street",
]

# ── Helpers ──────────────────────────────────────────────────────


def rand_name(rng: random.Random) -> str:
    return f"{rng.choice(FIRST_NAMES)} {rng.choice(MIDDLE_INITIALS)}. {rng.choice(LAST_NAMES)}"


def rand_company(rng: random.Random) -> str:
    return f"{rng.choice(COMPANY_PREFIXES)} {rng.choice(COMPANY_SUFFIXES)}"


def rand_address(rng: random.Random) -> tuple[str, str, str, str]:
    """Returns (street, city, state, zip)."""
    street_num = rng.randint(100, 9999)
    street = f"{street_num} {rng.choice(STREETS)}"
    city, state, zipcode = rng.choice(CITIES)
    return street, city, state, zipcode


def rand_ein(rng: random.Random) -> str:
    """Fake EIN in XX-XXXXXXX format."""
    return f"{rng.randint(10, 99)}-{rng.randint(1000000, 9999999)}"


def rand_ssn_masked(rng: random.Random) -> str:
    """Fake SSN with only last 4 digits shown."""
    return f"XXX-XX-{rng.randint(1000, 9999)}"


# ── 1099-NEC generator ───────────────────────────────────────────


def generate_1099_nec(rng: random.Random, n: int) -> tuple[str, dict]:
    """Generate a synthetic 1099-NEC. Returns (markdown, expected)."""
    tax_year = 2024
    payer_name = rand_company(rng)
    payer_tin = rand_ein(rng)
    payer_street, payer_city, payer_state, payer_zip = rand_address(rng)

    recipient_name = rand_name(rng)
    recipient_tin = rand_ssn_masked(rng)
    rec_street, rec_city, rec_state, rec_zip = rand_address(rng)

    compensation = round(rng.uniform(5000, 180000), 2)
    # Most 1099 contractors have zero federal withholding, but sometimes they do
    if rng.random() < 0.3:
        fed_withheld = round(compensation * rng.uniform(0.05, 0.15), 2)
    else:
        fed_withheld = 0.00

    markdown = f"""# Form 1099-NEC — Nonemployee Compensation ({tax_year})

CORRECTED (if checked) [ ]

**PAYER'S name, street address, city or town, state or province, country, ZIP or foreign postal code, and telephone number**

{payer_name}
{payer_street}
{payer_city}, {payer_state} {payer_zip}

**PAYER'S TIN:** {payer_tin}

---

**RECIPIENT'S TIN:** {recipient_tin}

**RECIPIENT'S name**
{recipient_name}

**Street address**
{rec_street}

**City or town, state or province, country, and ZIP or foreign postal code**
{rec_city}, {rec_state} {rec_zip}

---

**Box 1 — Nonemployee compensation:** ${compensation:,.2f}
**Box 2 — Payer made direct sales totaling $5,000 or more:** [ ]
**Box 4 — Federal income tax withheld:** ${fed_withheld:,.2f}

---

Form 1099-NEC (Rev. January {tax_year}) | www.irs.gov/Form1099NEC | Department of the Treasury — Internal Revenue Service
"""

    expected = {
        "payer_name": payer_name,
        "payer_tin": payer_tin,
        "recipient_name": recipient_name,
        "recipient_tin": recipient_tin,
        "nonemployee_compensation": compensation,
        "federal_income_tax_withheld": fed_withheld,
        "tax_year": tax_year,
    }

    return markdown, expected


# ── W-2 generator ────────────────────────────────────────────────


def generate_w2(rng: random.Random, n: int) -> tuple[str, dict]:
    """Generate a synthetic W-2. Returns (markdown, expected)."""
    tax_year = 2024
    employer_name = rand_company(rng)
    employer_ein = rand_ein(rng)
    emp_street, emp_city, emp_state, emp_zip = rand_address(rng)

    employee_name = rand_name(rng)
    employee_ssn = rand_ssn_masked(rng)
    ee_street, ee_city, ee_state, ee_zip = rand_address(rng)

    # Wages between $25K and $220K with realistic withholding ratios
    wages = round(rng.uniform(25000, 220000), 2)

    # Federal tax withholding: progressive rough approximation
    if wages < 50000:
        fed_rate = rng.uniform(0.08, 0.12)
    elif wages < 100000:
        fed_rate = rng.uniform(0.12, 0.16)
    else:
        fed_rate = rng.uniform(0.16, 0.22)
    federal_tax = round(wages * fed_rate, 2)

    # Social security: 6.2% up to $168,600 (2024 wage base)
    ss_wages = min(wages, 168600.00)
    ss_tax = round(ss_wages * 0.062, 2)

    # Medicare: 1.45% on all wages
    medicare_wages = wages
    medicare_tax = round(wages * 0.0145, 2)

    markdown = f"""# Form W-2 — Wage and Tax Statement ({tax_year})

Copy B — To Be Filed With Employee's FEDERAL Tax Return

| Field | Value |
|---|---|
| **a — Employee's social security number** | {employee_ssn} |
| **b — Employer identification number (EIN)** | {employer_ein} |
| **c — Employer's name, address, ZIP** | {employer_name} |
| | {emp_street} |
| | {emp_city}, {emp_state} {emp_zip} |
| **e — Employee's first name and initial. Last name** | {employee_name} |
| | {ee_street} |
| | {ee_city}, {ee_state} {ee_zip} |

---

| Box | Description | Amount |
|---|---|---|
| 1 | Wages, tips, other compensation | ${wages:,.2f} |
| 2 | Federal income tax withheld | ${federal_tax:,.2f} |
| 3 | Social security wages | ${ss_wages:,.2f} |
| 4 | Social security tax withheld | ${ss_tax:,.2f} |
| 5 | Medicare wages and tips | ${medicare_wages:,.2f} |
| 6 | Medicare tax withheld | ${medicare_tax:,.2f} |

---

Form W-2 Wage and Tax Statement ({tax_year})
Department of the Treasury — Internal Revenue Service
"""

    expected = {
        "employer_name": employer_name,
        "employer_ein": employer_ein,
        "employee_name": employee_name,
        "employee_ssn": employee_ssn,
        "wages": wages,
        "federal_income_tax": federal_tax,
        "social_security_wages": ss_wages,
        "social_security_tax": ss_tax,
        "medicare_wages": medicare_wages,
        "medicare_tax": medicare_tax,
        "tax_year": tax_year,
    }

    return markdown, expected


# ── Sample writer ────────────────────────────────────────────────


def write_sample(form_type: str, n: int, markdown: str, expected: dict, schema_name: str) -> str:
    """Write a synthetic sample into the corpus. Returns the sample filename stem."""
    slug = {"1099-nec": "1099nec", "w2": "w2"}.get(form_type, form_type)
    stem = f"synthetic_{slug}_{n:03d}"

    doc_path = IRS_DIR / "documents" / f"{stem}.md"
    exp_path = IRS_DIR / "expected" / f"{stem}.expected.json"
    man_path = IRS_DIR / "manifests" / f"{stem}.json"

    doc_path.write_text(markdown)
    exp_path.write_text(json.dumps(expected, indent=2) + "\n")

    manifest = {
        "filename": doc_path.name,
        "source_name": "Synthetic generator",
        "source_url": None,
        "license": "Apache-2.0",
        "license_url": "https://www.apache.org/licenses/LICENSE-2.0",
        "attribution": "FieldBench corpus contributors",
        "original_format": "markdown",
        "r2_url": None,
        "pages": 1,
        "synthetic": True,
        "added_date": "2026-04-12",
        "added_by": "corpus-bootstrap",
        "schema": f"irs_forms/schemas/{schema_name}",
        "notes": f"Programmatically generated {form_type.upper()} with fictitious data. Ground truth matches generator inputs exactly.",
    }
    man_path.write_text(json.dumps(manifest, indent=2) + "\n")

    return stem


# ── Main ─────────────────────────────────────────────────────────


GENERATORS = {
    "1099-nec": (generate_1099_nec, "form_1099_nec.yaml"),
    "w2": (generate_w2, "form_w2.yaml"),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--form-type",
        choices=["1099-nec", "w2", "all"],
        default="all",
        help="Form type to generate (default: all)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=10,
        help="Number of each form type to generate (default: 10)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing sample files (otherwise skip)",
    )
    args = parser.parse_args()

    for sub in ("documents", "expected", "manifests"):
        (IRS_DIR / sub).mkdir(parents=True, exist_ok=True)

    rng = random.Random(args.seed)

    form_types = list(GENERATORS.keys()) if args.form_type == "all" else [args.form_type]

    total = 0
    for form_type in form_types:
        generator, schema = GENERATORS[form_type]
        for n in range(1, args.count + 1):
            slug = {"1099-nec": "1099nec", "w2": "w2"}.get(form_type, form_type)
            stem = f"synthetic_{slug}_{n:03d}"
            existing = IRS_DIR / "documents" / f"{stem}.md"
            if existing.exists() and not args.overwrite:
                print(f"[irs] Skipping existing {stem}", file=sys.stderr)
                continue

            markdown, expected = generator(rng, n)
            write_sample(form_type, n, markdown, expected, schema)
            total += 1
            print(f"[irs] Generated {stem}", file=sys.stderr)

    print(f"\n[irs] Done. Generated {total} samples.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
