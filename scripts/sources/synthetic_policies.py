#!/usr/bin/env python3
"""Synthetic insurance policy declarations page generator for the FieldBench
validation corpus.

Generates 50 synthetic policy declarations pages in markdown format with
known ground-truth expected JSON outputs and manifest files.

Distribution across policy types (50 total):
  - Commercial General Liability:  7 docs
  - Businessowners:                6 docs
  - Workers Compensation:          6 docs
  - Commercial Auto:               6 docs
  - Homeowners:                    6 docs
  - Commercial Property:           6 docs
  - Umbrella/Excess:               5 docs
  - Professional Liability:        5 docs
  - Other:                         3 docs

Layout mix:
  - Table layout (structured rows)
  - Key-value pairs (label: value)
  - Narrative format (prose paragraphs)

Uses a fixed random seed (20260416) for reproducibility.
No external dependencies — stdlib only.

Usage:
  python scripts/sources/synthetic_policies.py
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

CORPUS_ROOT = Path(__file__).resolve().parent.parent.parent
POLICIES_DIR = CORPUS_ROOT / "insurance_policies"

SEED = 20260416

# ---------------------------------------------------------------------------
# Data pools
# ---------------------------------------------------------------------------

INSURERS = [
    "Evergreen Mutual Insurance Company",
    "Pacific Crest Casualty",
    "Continental Shield Insurance Co.",
    "Liberty Bell Underwriters",
    "Golden Gate Assurance Corp.",
    "Appalachian Fidelity Mutual",
    "Midwest Indemnity Holdings",
    "Pinnacle Specialty Insurance",
    "Tidewater Surety & Casualty",
    "Sterling National Insurance Co.",
    "Atlantic Coast Mutual",
    "Keystone Indemnity Group",
    "Mountain West Casualty Co.",
    "Northern Lights Insurance Corp.",
    "Compass Rose Specialty",
    "Riverdale Insurance Exchange",
    "Beacon Hill Mutual",
    "Ironbridge Excess Carriers Ltd.",
    "Sentry Pointe Casualty Group",
    "Harvest Plains Insurance Co.",
]

COMMERCIAL_INSUREDS = [
    ("Atlas Framing & Construction LLC", "221 Industrial Park Drive, Lakeland, FL 33805"),
    ("Meridian Mechanical Services Inc.", "4400 Commerce Drive, Indianapolis, IN 46268"),
    ("Silverline Electrical Contractors", "1800 N. Highland Avenue, Los Angeles, CA 90028"),
    ("Brookfield Property Management Group", "350 Madison Avenue, 8th Floor, New York, NY 10017"),
    ("Clearwater Environmental Solutions", "600 N. Pine Island Road, Fort Lauderdale, FL 33324"),
    ("Granite Peak General Contractors", "7700 Mineral Drive, Suite 200, Coeur d'Alene, ID 83815"),
    ("Suncoast Roofing & Waterproofing", "2901 Gandy Boulevard, St. Petersburg, FL 33702"),
    ("Cascade Plumbing & HVAC Inc.", "15200 NE 8th Street, Suite 300, Bellevue, WA 98007"),
    ("Prairie Home Builders LLC", "1100 N. Meridian Street, Oklahoma City, OK 73107"),
    ("Summit Landscaping & Excavation", "4500 W. Colfax Avenue, Denver, CO 80204"),
    ("Iron Horse Steel Erectors Inc.", "8200 Lehigh Avenue, Morton Grove, IL 60053"),
    ("Bayou City Demolition Services", "3200 Westheimer Road, Houston, TX 77098"),
    ("Cornerstone Civil Engineering PC", "90 State Street, Suite 700, Albany, NY 12207"),
    ("Redline Fire Protection Corp.", "1650 Borel Place, Suite 200, San Mateo, CA 94402"),
    ("Valley Forge Painting Contractors", "450 Lancaster Avenue, Wayne, PA 19087"),
    ("Northern Star Telecom Services", "2700 University Avenue, Minneapolis, MN 55414"),
    ("Coastal Crane & Rigging LLC", "5100 Port Road, Savannah, GA 31415"),
    ("Westridge Concrete Foundations", "3300 S. Figueroa Street, Los Angeles, CA 90007"),
    ("Evergreen Site Development Corp.", "1400 NW Compton Drive, Portland, OR 97209"),
    ("Continental Scaffolding Inc.", "600 N. Michigan Avenue, Suite 800, Chicago, IL 60611"),
    ("Pinecrest Medical Group PA", "2200 Mercy Drive, Suite 101, Orlando, FL 32808"),
    ("Harborview Consulting Engineers", "155 Federal Street, 3rd Floor, Boston, MA 02110"),
    ("Apex Industrial Welding LLC", "8900 Steel Road, Gary, IN 46402"),
    ("Trident Marine Services Inc.", "700 Harbor Boulevard, Weehawken, NJ 07086"),
    ("Lone Star Paving & Excavation", "5500 Burnet Road, Austin, TX 78756"),
]

PERSONAL_INSUREDS = [
    ("James R. Patterson", "142 Oakwood Lane, Naperville, IL 60540"),
    ("Maria C. Gutierrez", "8731 Sunset Drive, Phoenix, AZ 85018"),
    ("Robert & Linda Chen", "305 Willowbrook Court, Raleigh, NC 27607"),
    ("Patricia M. O'Brien", "22 Harbor View Terrace, Marblehead, MA 01945"),
    ("David K. Nakamura", "4200 Laurel Canyon Blvd, Studio City, CA 91604"),
    ("Sandra L. Williams", "1509 Magnolia Street, Savannah, GA 31401"),
    ("Thomas & Emily Richardson", "67 Briarcliff Road, Montclair, NJ 07042"),
    ("Angela D. Foster", "3801 Lake Shore Drive, Apt 1204, Chicago, IL 60613"),
    ("Michael S. Petrov", "910 Elm Street, Boulder, CO 80302"),
    ("Christine A. Morales", "2415 Peachtree Road NE, Atlanta, GA 30305"),
]

PROFESSIONAL_INSUREDS = [
    ("Whitfield, Crane & Associates LLP", "1200 K Street NW, Suite 800, Washington, DC 20005"),
    ("Eastlake Architecture + Design PC", "440 N. Wells Street, Chicago, IL 60654"),
    ("Bridgewater Financial Advisors Inc.", "One Liberty Plaza, 42nd Floor, New York, NY 10006"),
    ("Cascade Wealth Management LLC", "900 SW Fifth Avenue, Suite 2000, Portland, OR 97204"),
    ("Piedmont Healthcare Consulting Group", "3344 Peachtree Road NE, Atlanta, GA 30326"),
    ("Sierra Technical Engineering PC", "1500 Solano Avenue, Albany, CA 94706"),
    ("Northshore Accounting Services PA", "200 International Drive, Portsmouth, NH 03801"),
    ("Horizon Legal Group PLLC", "800 Nicollet Mall, Suite 2700, Minneapolis, MN 55402"),
]

# Endorsement form libraries per policy type
ENDORSEMENTS = {
    "Commercial General Liability": [
        ("CG 00 01 04 13", "Commercial General Liability Coverage Form"),
        ("CG 20 10 04 13", "Additional Insured - Owners, Lessees or Contractors"),
        ("CG 20 37 04 13", "Additional Insured - Owners, Lessees or Contractors - Completed Operations"),
        ("CG 24 04 05 09", "Waiver of Transfer of Rights of Recovery Against Others to Us"),
        ("CG 25 03 05 09", "Designated Construction Project(s) General Aggregate Limit"),
        ("CG 21 39 10 93", "Contractual Liability Limitation"),
        ("CG 21 47 12 07", "Employment-Related Practices Exclusion"),
        ("IL 00 21 09 08", "Nuclear Energy Liability Exclusion Endorsement"),
    ],
    "Businessowners": [
        ("BP 00 03 01 10", "Businessowners Coverage Form"),
        ("BP 04 02 01 10", "Protective Safeguards"),
        ("BP 04 53 01 06", "Exclusion of Certified Acts of Terrorism"),
        ("BP 05 17 01 10", "Employment Practices Liability"),
        ("BP 12 01 01 10", "Business Liability Coverage Form"),
        ("IL 00 17 11 98", "Common Policy Conditions"),
    ],
    "Workers Compensation": [
        ("WC 00 00 00 C", "Workers Compensation and Employers Liability Insurance Policy"),
        ("WC 00 03 13", "Waiver of Our Right to Recover from Others Endorsement"),
        ("WC 00 04 06 14", "Experience Rating Modification Factor Endorsement"),
        ("WC 04 03 06", "Waiver of Our Right to Recover from Others"),
        ("WC 42 03 04 B", "State Special Endorsement"),
        ("WC 42 06 01", "Voluntary Compensation Endorsement"),
    ],
    "Commercial Auto": [
        ("CA 00 01 10 13", "Business Auto Coverage Form"),
        ("CA 00 09 10 13", "Business Auto Physical Damage Coverage Form"),
        ("CA 04 44 10 13", "Additional Insured - Lessor"),
        ("CA 20 48 02 99", "Designated Insured for Covered Autos Liability Coverage"),
        ("CA 99 54 03 15", "Truckers Coverage Form"),
        ("IL 00 03 09 08", "Calculation of Premium"),
    ],
    "Homeowners": [
        ("HO 00 03 05 11", "Special Form"),
        ("HO 04 10 05 11", "Additional Interests - Residence Premises"),
        ("HO 04 61 05 11", "Scheduled Personal Property Endorsement"),
        ("HO 04 90 05 11", "Personal Property Replacement Cost Loss Settlement"),
        ("HO 05 24 05 11", "Broadened Residence Premises Definition"),
    ],
    "Commercial Property": [
        ("CP 00 10 10 12", "Building and Personal Property Coverage Form"),
        ("CP 00 30 10 12", "Business Income (and Extra Expense) Coverage Form"),
        ("CP 00 90 07 88", "Commercial Property Conditions"),
        ("CP 01 40 07 06", "Exclusion of Loss Due to Virus or Bacteria"),
        ("CP 10 30 10 12", "Causes of Loss - Special Form"),
        ("IL 00 17 11 98", "Common Policy Conditions"),
    ],
    "Umbrella/Excess": [
        ("UMB 001 01 15", "Commercial Umbrella Coverage Form"),
        ("UMB 003 01 15", "Schedule of Underlying Insurance"),
        ("UMB 005 01 15", "Self-Insured Retention Endorsement"),
        ("UMB 010 01 15", "Exclusion - Professional Liability"),
        ("UMB 012 01 15", "Exclusion - Pollution Liability"),
    ],
    "Professional Liability": [
        ("PL 00 01 01 18", "Professional Liability Coverage Form"),
        ("PL 00 02 01 18", "Supplemental Payments Endorsement"),
        ("PL 04 01 01 18", "Extended Reporting Period Endorsement"),
        ("PL 05 01 01 18", "Deductible Liability Insurance"),
        ("PL 06 01 01 18", "Exclusion - Bodily Injury and Property Damage"),
    ],
    "Other": [
        ("IL 00 17 11 98", "Common Policy Conditions"),
        ("IL 00 21 09 08", "Nuclear Energy Liability Exclusion Endorsement"),
        ("IL 09 52 01 15", "Terrorism Risk Insurance Program Endorsement"),
    ],
}

# Coverage breakdowns for premium sub-lines
CGL_COVERAGES = [
    "Premises/Operations",
    "Products/Completed Operations",
    "Personal & Advertising Injury",
    "Medical Payments",
    "Damage to Premises Rented to You",
]

BOP_COVERAGES = [
    "Building Coverage",
    "Business Personal Property",
    "Business Income & Extra Expense",
    "Liability Coverage",
    "Medical Payments",
]

WC_COVERAGES = [
    "Workers Compensation Premium",
    "Employers Liability",
    "USL&H Coverage",
]

CA_COVERAGES = [
    "Liability Coverage",
    "Physical Damage - Comprehensive",
    "Physical Damage - Collision",
    "Medical Payments",
    "Uninsured Motorist",
]

HO_COVERAGES = [
    "Dwelling (Coverage A)",
    "Other Structures (Coverage B)",
    "Personal Property (Coverage C)",
    "Loss of Use (Coverage D)",
    "Personal Liability (Coverage E)",
    "Medical Payments (Coverage F)",
]

CP_COVERAGES = [
    "Building Coverage",
    "Business Personal Property",
    "Business Income",
    "Extra Expense",
    "Inland Marine",
]

UMBRELLA_COVERAGES = [
    "Umbrella Liability Premium",
]

PL_COVERAGES = [
    "Professional Liability Premium",
    "Supplemental Payments",
]

COVERAGE_BREAKDOWN_MAP = {
    "Commercial General Liability": CGL_COVERAGES,
    "Businessowners": BOP_COVERAGES,
    "Workers Compensation": WC_COVERAGES,
    "Commercial Auto": CA_COVERAGES,
    "Homeowners": HO_COVERAGES,
    "Commercial Property": CP_COVERAGES,
    "Umbrella/Excess": UMBRELLA_COVERAGES,
    "Professional Liability": PL_COVERAGES,
    "Other": ["General Coverage Premium"],
}

# Premium ranges by policy type (min, max)
PREMIUM_RANGES = {
    "Commercial General Liability": (2500, 75000),
    "Businessowners": (1500, 25000),
    "Workers Compensation": (3000, 500000),
    "Commercial Auto": (2000, 100000),
    "Homeowners": (500, 8000),
    "Commercial Property": (3000, 150000),
    "Umbrella/Excess": (2000, 50000),
    "Professional Liability": (3000, 80000),
    "Other": (1000, 30000),
}

# Each-occurrence / general aggregate limit pools by type
OCCURRENCE_LIMITS = {
    "Commercial General Liability": [500000, 1000000, 2000000, 5000000],
    "Businessowners": [300000, 500000, 1000000, 2000000],
    "Workers Compensation": [500000, 1000000],
    "Commercial Auto": [500000, 1000000, 2000000],
    "Homeowners": [100000, 300000, 500000],
    "Commercial Property": [500000, 1000000, 2000000, 5000000, 10000000],
    "Umbrella/Excess": [1000000, 2000000, 5000000, 10000000],
    "Professional Liability": [1000000, 2000000, 5000000],
    "Other": [500000, 1000000, 2000000],
}

AGGREGATE_LIMITS = {
    "Commercial General Liability": [1000000, 2000000, 4000000, 10000000],
    "Businessowners": [600000, 1000000, 2000000, 4000000],
    "Workers Compensation": None,  # WC doesn't use general aggregate
    "Commercial Auto": None,  # Auto typically doesn't have aggregate
    "Homeowners": None,  # Homeowners doesn't use aggregate
    "Commercial Property": [1000000, 2000000, 5000000, 10000000],
    "Umbrella/Excess": [2000000, 5000000, 10000000],
    "Professional Liability": [2000000, 5000000, 10000000],
    "Other": [1000000, 2000000, 4000000],
}

# Policy number prefix patterns
POLICY_PREFIXES = {
    "Commercial General Liability": ["CGL", "GL", "GLP"],
    "Businessowners": ["BOP", "BPP", "BOW"],
    "Workers Compensation": ["WC", "WCP", "WCA"],
    "Commercial Auto": ["CA", "BAP", "CAP"],
    "Homeowners": ["HO", "HOM", "HPP"],
    "Commercial Property": ["CPP", "CPR", "FPP"],
    "Umbrella/Excess": ["CU", "UMB", "XS"],
    "Professional Liability": ["PL", "PLI", "EO"],
    "Other": ["MIS", "SPL", "GEN"],
}

# "Other" sub-types for variety
OTHER_SUBTYPES = [
    "Inland Marine",
    "Employment Practices Liability",
    "Cyber Liability",
]

# Date display format variations
DATE_FORMATS = [
    lambda m, d, y: f"{m:02d}/{d:02d}/{y}",          # 01/15/2026
    lambda m, d, y: f"{m:02d}-{d:02d}-{y}",          # 01-15-2026
    lambda m, d, y: _month_name(m) + f" {d}, {y}",   # January 15, 2026
    lambda m, d, y: f"{_month_abbr(m)} {d}, {y}",    # Jan 15, 2026
]

_MONTHS_FULL = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
_MONTHS_ABBR = [
    "", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]


def _month_name(m: int) -> str:
    return _MONTHS_FULL[m]


def _month_abbr(m: int) -> str:
    return _MONTHS_ABBR[m]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_policy_number(policy_type: str, rng: random.Random) -> str:
    prefix = rng.choice(POLICY_PREFIXES[policy_type])
    digits = rng.randint(1000000, 9999999)
    sep = rng.choice(["", "-", " "])
    suffix = rng.choice(["", "", "", f"-{rng.randint(0, 9):02d}"])
    return f"{prefix}{sep}{digits}{suffix}"


def _eff_exp_dates(rng: random.Random) -> tuple[str, str, int, int, int]:
    """Return (eff_iso, exp_iso, month, day, year) for a 1-year policy."""
    year = rng.choice([2024, 2025, 2025, 2026, 2026])
    month = rng.randint(1, 12)
    day = rng.randint(1, 28)
    eff_iso = f"{year}-{month:02d}-{day:02d}"
    exp_iso = f"{year + 1}-{month:02d}-{day:02d}"
    return eff_iso, exp_iso, month, day, year


def _format_date(month: int, day: int, year: int, fmt_fn) -> str:
    return fmt_fn(month, day, year)


def _fmt_amount(val: int | float) -> str:
    if isinstance(val, float):
        return f"${val:,.2f}"
    return f"${val:,}"


def _pick_premium(policy_type: str, rng: random.Random) -> int:
    lo, hi = PREMIUM_RANGES[policy_type]
    # Round to nearest 50 for realism
    raw = rng.randint(lo, hi)
    return round(raw / 50) * 50


def _pick_occurrence_limit(policy_type: str, rng: random.Random) -> int | None:
    limits = OCCURRENCE_LIMITS.get(policy_type)
    if not limits:
        return None
    return rng.choice(limits)


def _pick_aggregate_limit(policy_type: str, rng: random.Random, occurrence: int | None) -> int | None:
    agg_pool = AGGREGATE_LIMITS.get(policy_type)
    if agg_pool is None:
        return None
    # Aggregate should be >= occurrence
    candidates = [a for a in agg_pool if occurrence is None or a >= occurrence]
    if not candidates:
        candidates = agg_pool
    return rng.choice(candidates)


def _pick_endorsements(policy_type: str, rng: random.Random) -> list[tuple[str, str]]:
    pool = ENDORSEMENTS.get(policy_type, ENDORSEMENTS["Other"])
    n = rng.randint(2, min(len(pool), 6))
    return rng.sample(pool, n)


def _make_coverage_breakdown(policy_type: str, total_premium: int, rng: random.Random) -> list[tuple[str, int]]:
    """Split total premium across sub-coverage lines."""
    lines = COVERAGE_BREAKDOWN_MAP.get(policy_type, ["Premium"])
    if len(lines) == 1:
        return [(lines[0], total_premium)]
    # Random split
    weights = [rng.random() + 0.1 for _ in lines]
    total_w = sum(weights)
    amounts = [round((w / total_w) * total_premium / 50) * 50 for w in weights]
    # Adjust last to match total
    amounts[-1] = total_premium - sum(amounts[:-1])
    return list(zip(lines, amounts))


# ---------------------------------------------------------------------------
# Layout: TABLE
# ---------------------------------------------------------------------------

def _render_table_layout(
    insurer: str,
    insured_name: str,
    insured_addr: str,
    policy_number: str,
    policy_type: str,
    eff_display: str,
    exp_display: str,
    total_premium: int,
    occurrence_limit: int | None,
    aggregate_limit: int | None,
    endorsements: list[tuple[str, str]] | None,
    coverage_breakdown: list[tuple[str, int]] | None,
    rng: random.Random,
) -> str:
    lines = []

    # Vary insurer presentation to match real policy formats
    insurer_style = rng.choice(["labeled_table", "heading_plus_label", "underwritten"])
    if insurer_style == "labeled_table":
        # Insurer as a row in the declarations table
        lines.append("## POLICY DECLARATIONS")
        lines.append("")
        lines.append("| Field | Value |")
        lines.append("|---|---|")
        lines.append(f"| Insurance Company | {insurer} |")
    elif insurer_style == "heading_plus_label":
        lines.append(f"## {insurer.upper()}")
        lines.append("")
        lines.append("## POLICY DECLARATIONS")
        lines.append("")
        lines.append("| Field | Value |")
        lines.append("|---|---|")
    else:
        lines.append("## POLICY DECLARATIONS")
        lines.append("")
        lines.append(f"Underwritten by: {insurer}")
        lines.append("")
        lines.append("| Field | Value |")
        lines.append("|---|---|")

    lines.append(f"| Policy Number | {policy_number} |")
    lines.append(f"| Policy Type | {policy_type} |")
    lines.append(f"| Named Insured | {insured_name} |")
    lines.append(f"| Mailing Address | {insured_addr} |")
    lines.append(f"| Policy Period | {eff_display} to {exp_display} |")
    lines.append(f"| Effective Date | {eff_display} |")
    lines.append(f"| Expiration Date | {exp_display} |")
    lines.append("")

    # Limits table
    lines.append("### LIMITS OF INSURANCE")
    lines.append("")
    lines.append("| Coverage | Limit |")
    lines.append("|---|---|")
    if occurrence_limit is not None:
        lines.append(f"| Each Occurrence Limit | {_fmt_amount(occurrence_limit)} |")
    if aggregate_limit is not None:
        lines.append(f"| General Aggregate Limit | {_fmt_amount(aggregate_limit)} |")
    if policy_type == "Commercial General Liability":
        prod_agg = aggregate_limit if aggregate_limit else 2000000
        lines.append(f"| Products-Completed Operations Aggregate | {_fmt_amount(prod_agg)} |")
        pai = occurrence_limit if occurrence_limit else 1000000
        lines.append(f"| Personal & Advertising Injury | {_fmt_amount(pai)} |")
        dmg = rng.choice([50000, 100000, 300000, 500000])
        lines.append(f"| Damage to Premises Rented to You | {_fmt_amount(dmg)} |")
        med = rng.choice([5000, 10000])
        lines.append(f"| Medical Expense (Any One Person) | {_fmt_amount(med)} |")
    elif policy_type == "Workers Compensation":
        lines.append("| Workers Compensation | Statutory |")
        el = occurrence_limit or 1000000
        lines.append(f"| E.L. Each Accident | {_fmt_amount(el)} |")
        lines.append(f"| E.L. Disease - Policy Limit | {_fmt_amount(el)} |")
        lines.append(f"| E.L. Disease - Each Employee | {_fmt_amount(el)} |")
    lines.append("")

    # Premium
    lines.append("### PREMIUM SUMMARY")
    lines.append("")
    if coverage_breakdown:
        lines.append("| Coverage | Premium |")
        lines.append("|---|---|")
        for cov_name, cov_amt in coverage_breakdown:
            lines.append(f"| {cov_name} | {_fmt_amount(cov_amt)} |")
        lines.append(f"| **Total Premium** | **{_fmt_amount(total_premium)}** |")
    else:
        lines.append(f"Total Annual Premium: {_fmt_amount(total_premium)}")
    lines.append("")

    # Endorsements
    if endorsements:
        lines.append("### SCHEDULE OF FORMS AND ENDORSEMENTS")
        lines.append("")
        lines.append("| Form Number | Title |")
        lines.append("|---|---|")
        for form_no, title in endorsements:
            lines.append(f"| {form_no} | {title} |")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Layout: KEY-VALUE
# ---------------------------------------------------------------------------

def _render_kv_layout(
    insurer: str,
    insured_name: str,
    insured_addr: str,
    policy_number: str,
    policy_type: str,
    eff_display: str,
    exp_display: str,
    total_premium: int,
    occurrence_limit: int | None,
    aggregate_limit: int | None,
    endorsements: list[tuple[str, str]] | None,
    coverage_breakdown: list[tuple[str, int]] | None,
    rng: random.Random,
) -> str:
    lines = []

    # Header style variations — match real policy formats
    style = rng.choice(["insurer_field", "issued_by", "heading_with_field"])
    if style == "insurer_field":
        lines.append("## DECLARATIONS PAGE")
        lines.append("")
        lines.append(f"**Insurance Company:** {insurer}")
        lines.append("")
    elif style == "issued_by":
        lines.append("## Declarations Page")
        lines.append("")
        lines.append(f"Issued by: {insurer}")
        lines.append("")
    else:
        lines.append(f"## {insurer.upper()}")
        lines.append("")
        lines.append("## DECLARATIONS PAGE")
        lines.append("")
        lines.append(f"**Insurer:** {insurer}")
        lines.append("")

    lines.append(f"**Policy Number:** {policy_number}")
    lines.append("")
    lines.append(f"**Named Insured:** {insured_name}")
    lines.append(f"**Mailing Address:** {insured_addr}")
    lines.append("")
    lines.append(f"**Policy Type:** {policy_type}")
    lines.append("")

    # Date display variation
    sep = rng.choice(["to", "through", "-"])
    lines.append(f"**Policy Period:** {eff_display} {sep} {exp_display}")
    lines.append(f"**Effective Date:** {eff_display}")
    lines.append(f"**Expiration Date:** {exp_display}")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("### Limits of Insurance")
    lines.append("")
    if occurrence_limit is not None:
        lines.append(f"**Each Occurrence Limit:** {_fmt_amount(occurrence_limit)}")
    if aggregate_limit is not None:
        lines.append(f"**General Aggregate Limit:** {_fmt_amount(aggregate_limit)}")

    if policy_type == "Commercial General Liability":
        prod_agg = aggregate_limit if aggregate_limit else 2000000
        lines.append(f"**Products-Completed Operations Aggregate:** {_fmt_amount(prod_agg)}")
        pai = occurrence_limit if occurrence_limit else 1000000
        lines.append(f"**Personal & Advertising Injury:** {_fmt_amount(pai)}")
        dmg = rng.choice([50000, 100000, 300000, 500000])
        lines.append(f"**Damage to Premises Rented to You:** {_fmt_amount(dmg)}")
        med = rng.choice([5000, 10000])
        lines.append(f"**Medical Expense (Any One Person):** {_fmt_amount(med)}")
    elif policy_type == "Workers Compensation":
        lines.append("**Workers Compensation:** Statutory")
        el = occurrence_limit or 1000000
        lines.append(f"**E.L. Each Accident:** {_fmt_amount(el)}")
        lines.append(f"**E.L. Disease - Policy Limit:** {_fmt_amount(el)}")
        lines.append(f"**E.L. Disease - Each Employee:** {_fmt_amount(el)}")
    elif policy_type == "Homeowners":
        lines.append(f"**Dwelling Coverage (A):** {_fmt_amount(rng.choice([200000, 350000, 500000, 750000]))}")
        lines.append(f"**Other Structures (B):** {_fmt_amount(rng.choice([20000, 35000, 50000]))}")
        lines.append(f"**Personal Property (C):** {_fmt_amount(rng.choice([100000, 175000, 250000]))}")
        lines.append(f"**Loss of Use (D):** {_fmt_amount(rng.choice([40000, 70000, 100000]))}")

    lines.append("")

    # Premium
    lines.append("---")
    lines.append("")
    if coverage_breakdown and rng.random() > 0.3:
        lines.append("### Premium")
        lines.append("")
        for cov_name, cov_amt in coverage_breakdown:
            lines.append(f"- {cov_name}: {_fmt_amount(cov_amt)}")
        lines.append("")
        lines.append(f"**Total Premium: {_fmt_amount(total_premium)}**")
    else:
        lines.append(f"**Total Annual Premium:** {_fmt_amount(total_premium)}")
    lines.append("")

    # Endorsements
    if endorsements:
        lines.append("---")
        lines.append("")
        lines.append("### Forms and Endorsements")
        lines.append("")
        for form_no, title in endorsements:
            lines.append(f"- {form_no} — {title}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Layout: NARRATIVE
# ---------------------------------------------------------------------------

def _render_narrative_layout(
    insurer: str,
    insured_name: str,
    insured_addr: str,
    policy_number: str,
    policy_type: str,
    eff_display: str,
    exp_display: str,
    total_premium: int,
    occurrence_limit: int | None,
    aggregate_limit: int | None,
    endorsements: list[tuple[str, str]] | None,
    coverage_breakdown: list[tuple[str, int]] | None,
    rng: random.Random,
) -> str:
    lines = []

    # Vary heading style
    narr_style = rng.choice(["company_heading", "policy_heading"])
    if narr_style == "company_heading":
        lines.append(f"## {insurer.upper()}")
        lines.append("")
        lines.append(f"## {policy_type} Policy — Declarations")
    else:
        lines.append(f"## {policy_type} Policy — Declarations")
        lines.append("")
        lines.append(f"**Insurance Company:** {insurer}")
    lines.append("")

    # Opening paragraph
    lines.append(
        f"In consideration of the premium stated herein, {insurer} "
        f"(hereinafter referred to as the \"Company\") agrees to provide "
        f"the insurance described in this policy to the Named Insured "
        f"identified below, subject to the terms, conditions, and "
        f"limitations of this policy."
    )
    lines.append("")

    lines.append(f"**Named Insured:** {insured_name}")
    lines.append(f"**Address:** {insured_addr}")
    lines.append("")

    lines.append(
        f"This policy, numbered **{policy_number}**, is effective from "
        f"**{eff_display}** to **{exp_display}** (12:01 A.M. standard "
        f"time at the address of the Named Insured)."
    )
    lines.append("")

    # Limits paragraph
    limits_parts = []
    if occurrence_limit is not None:
        limits_parts.append(
            f"The Each Occurrence Limit is {_fmt_amount(occurrence_limit)}"
        )
    if aggregate_limit is not None:
        limits_parts.append(
            f"the General Aggregate Limit is {_fmt_amount(aggregate_limit)}"
        )
    if limits_parts:
        limits_text = "; ".join(limits_parts) + "."
        lines.append(f"**Limits of Insurance:** {limits_text}")
        lines.append("")

    if policy_type == "Workers Compensation":
        el = occurrence_limit or 1000000
        lines.append(
            f"Part One — Workers Compensation Insurance: Statutory. "
            f"Part Two — Employers Liability Insurance: Each Accident "
            f"{_fmt_amount(el)}; Disease — Policy Limit {_fmt_amount(el)}; "
            f"Disease — Each Employee {_fmt_amount(el)}."
        )
        lines.append("")

    # Premium paragraph
    lines.append(
        f"The total advance premium for this policy is "
        f"**{_fmt_amount(total_premium)}**, payable at inception."
    )
    if coverage_breakdown and len(coverage_breakdown) > 1:
        lines.append(" This premium is allocated as follows:")
        lines.append("")
        for cov_name, cov_amt in coverage_breakdown:
            lines.append(f"  - {cov_name}: {_fmt_amount(cov_amt)}")
    lines.append("")

    # Endorsements as prose
    if endorsements:
        lines.append("---")
        lines.append("")
        lines.append("**Schedule of Forms and Endorsements**")
        lines.append("")
        lines.append(
            "The following forms and endorsements are attached to and "
            "form a part of this policy at the time of issue:"
        )
        lines.append("")
        for form_no, title in endorsements:
            lines.append(f"  {form_no}  {title}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Document generation
# ---------------------------------------------------------------------------

LAYOUT_RENDERERS = [_render_table_layout, _render_kv_layout, _render_narrative_layout]

# Distribution: type -> count
TYPE_SCHEDULE = [
    ("Commercial General Liability", 7),
    ("Businessowners", 6),
    ("Workers Compensation", 6),
    ("Commercial Auto", 6),
    ("Homeowners", 6),
    ("Commercial Property", 6),
    ("Umbrella/Excess", 5),
    ("Professional Liability", 5),
    ("Other", 3),
]


def _generate_policy(
    idx: int,
    policy_type: str,
    rng: random.Random,
) -> tuple[str, dict, dict]:
    """Generate one policy document, returning (markdown, expected, manifest)."""

    insurer = rng.choice(INSURERS)

    # Choose insured based on type
    if policy_type == "Homeowners":
        insured_name, insured_addr = rng.choice(PERSONAL_INSUREDS)
    elif policy_type == "Professional Liability":
        insured_name, insured_addr = rng.choice(PROFESSIONAL_INSUREDS)
    else:
        insured_name, insured_addr = rng.choice(COMMERCIAL_INSUREDS)

    policy_number = _make_policy_number(policy_type, rng)
    eff_iso, exp_iso, month, day, year = _eff_exp_dates(rng)

    # Pick a date format for display
    date_fmt = rng.choice(DATE_FORMATS)
    eff_display = _format_date(month, day, year, date_fmt)
    exp_display = _format_date(month, day, year + 1, date_fmt)

    total_premium = _pick_premium(policy_type, rng)
    occurrence_limit = _pick_occurrence_limit(policy_type, rng)
    aggregate_limit = _pick_aggregate_limit(policy_type, rng, occurrence_limit)

    # Decide whether to include endorsements (~60% of docs)
    include_endorsements = rng.random() < 0.6
    endorsements = _pick_endorsements(policy_type, rng) if include_endorsements else None

    # Decide whether to include coverage breakdown (~50% of docs)
    include_breakdown = rng.random() < 0.5
    coverage_breakdown = _make_coverage_breakdown(policy_type, total_premium, rng) if include_breakdown else None

    # Pick layout renderer (roughly even distribution)
    renderer = rng.choice(LAYOUT_RENDERERS)

    # For "Other" type, use a sub-type label
    display_type = policy_type
    if policy_type == "Other":
        display_type = rng.choice(OTHER_SUBTYPES)

    md = renderer(
        insurer=insurer,
        insured_name=insured_name,
        insured_addr=insured_addr,
        policy_number=policy_number,
        policy_type=display_type,
        eff_display=eff_display,
        exp_display=exp_display,
        total_premium=total_premium,
        occurrence_limit=occurrence_limit,
        aggregate_limit=aggregate_limit,
        endorsements=endorsements,
        coverage_breakdown=coverage_breakdown,
        rng=rng,
    )

    expected = {
        "insurer_name": insurer,
        "named_insured": insured_name,
        "policy_number": policy_number,
        "policy_type": policy_type,
        "effective_date": eff_iso,
        "expiration_date": exp_iso,
        "total_premium": total_premium,
        "each_occurrence_limit": occurrence_limit,
        "general_aggregate_limit": aggregate_limit,
    }

    manifest = {
        "filename": f"synth_policy_{idx + 1:03d}.md",
        "source_name": f"Synthetic {policy_type} declarations page",
        "source_url": None,
        "license": "Apache-2.0",
        "license_url": "https://www.apache.org/licenses/LICENSE-2.0",
        "attribution": "FieldBench corpus contributors",
        "original_format": "markdown",
        "r2_url": None,
        "pages": 1,
        "added_date": "2026-04-16",
        "added_by": "accuracy-27",
        "schema": "insurance_policies/schemas/policy_declarations.yaml",
        "doc_type": "policy_declarations",
        "notes": f"Synthetic policy declarations page. Type: {policy_type}. Layout: {renderer.__name__}.",
    }

    return md, expected, manifest


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _write_policy(file_id: str, md: str, expected: dict, manifest: dict) -> None:
    (POLICIES_DIR / "documents" / f"{file_id}.md").write_text(md + "\n")
    (POLICIES_DIR / "expected" / f"{file_id}.expected.json").write_text(json.dumps(expected, indent=2) + "\n")
    (POLICIES_DIR / "manifests" / f"{file_id}.json").write_text(json.dumps(manifest, indent=2) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--extra", type=int, default=0,
                    help="generate N additional policies after the base 50 (distinct seed), cycling policy types")
    args = ap.parse_args()

    rng = random.Random(SEED)

    for sub in ("documents", "expected", "manifests"):
        (POLICIES_DIR / sub).mkdir(parents=True, exist_ok=True)

    total = sum(count for _, count in TYPE_SCHEDULE)
    assert total == 50, f"Expected 50 docs, schedule sums to {total}"

    global_idx = 0
    for policy_type, count in TYPE_SCHEDULE:
        for _ in range(count):
            file_id = f"synth_policy_{global_idx + 1:03d}"
            md, expected, manifest = _generate_policy(global_idx, policy_type, rng)
            _write_policy(file_id, md, expected, manifest)
            print(f"[synth-policy] ({global_idx + 1}/{total}) {file_id}  [{policy_type}]", file=sys.stderr)
            global_idx += 1

    if args.extra:
        # Additional docs: ids continue after the base 50, distinct seed; cycle policy types.
        ergng = random.Random(SEED + 1)
        types = [t for t, _ in TYPE_SCHEDULE]
        for i in range(args.extra):
            gi = 50 + i
            file_id = f"synth_policy_{gi + 1:03d}"
            ptype = types[i % len(types)]
            md, expected, manifest = _generate_policy(gi, ptype, ergng)
            _write_policy(file_id, md, expected, manifest)
            print(f"[synth-policy] (extra {i + 1}/{args.extra}) {file_id}  [{ptype}]", file=sys.stderr)

    print(f"\n[synth-policy] Done. Generated {total + args.extra} synthetic policy declarations pages.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
