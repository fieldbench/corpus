#!/usr/bin/env python3
"""Synthetic COI generator for the FieldBench corpus.

Generates 40 synthetic ACORD-style Certificate of Liability Insurance
documents in markdown format with known ground-truth expected JSON
outputs and manifest files. Each COI targets a specific extraction
pain point:

  - Category 1: Carrier letter-code resolution (8 docs)
  - Category 2: Per-policy additional insureds (8 docs)
  - Category 3: Blanket additional insureds (5 docs)
  - Category 4: Complex limits from multiple sections (8 docs)
  - Category 5: ACORD layout variations (6 docs)
  - Category 6: Multi-coverage complexity (5 docs)

Uses a fixed random seed (20260416) for reproducibility.
No external dependencies — stdlib only.

Usage:
  python scripts/sources/synthetic_cois.py
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

CORPUS_ROOT = Path(__file__).resolve().parent.parent.parent
CERTS_DIR = CORPUS_ROOT / "insurance_certificates"

SEED = 20260416

# ---------------------------------------------------------------------------
# Data pools
# ---------------------------------------------------------------------------

PRODUCERS = [
    ("Harborline Insurance Services, Inc.", "4820 Westshore Blvd, Suite 300", "Tampa, FL 33609", "(813) 555-0142"),
    ("Summit Risk Advisors LLC", "1200 Market Street, 4th Floor", "Philadelphia, PA 19107", "(215) 555-0188"),
    ("Pacific Brokerage Group", "700 Wilshire Blvd, Suite 1500", "Los Angeles, CA 90017", "(310) 555-0199"),
    ("Heartland Insurance Associates", "2500 Grand Avenue", "Des Moines, IA 50312", "(515) 555-0166"),
    ("Granite State Agency Inc.", "44 Pleasant Street", "Concord, NH 03301", "(603) 555-0133"),
    ("Bayshore Risk Management", "One Financial Center, 22nd Floor", "Boston, MA 02111", "(617) 555-0211"),
    ("Redwood Insurance Partners", "555 Montgomery Street", "San Francisco, CA 94111", "(415) 555-0177"),
    ("Magnolia Brokerage Services", "800 Poydras Street, Suite 2400", "New Orleans, LA 70112", "(504) 555-0144"),
    ("Prairie Wind Insurance Group", "300 N. Main Street", "Wichita, KS 67202", "(316) 555-0155"),
    ("Blue Ridge Underwriters", "200 South College Street", "Charlotte, NC 28202", "(704) 555-0122"),
    ("Cascadia Insurance Brokers", "1001 Fourth Avenue, Suite 3000", "Seattle, WA 98154", "(206) 555-0199"),
    ("Great Lakes Risk Advisors", "150 W. Jefferson Avenue", "Detroit, MI 48226", "(313) 555-0188"),
]

CARRIERS = [
    "Evergreen Mutual Insurance Company",
    "Pacific Crest Casualty",
    "Redwood Workers Compensation Fund",
    "Continental Shield Insurance Co.",
    "Liberty Bell Underwriters",
    "Golden Gate Assurance Corp.",
    "Appalachian Fidelity Mutual",
    "Midwest Indemnity Holdings",
    "Pinnacle Specialty Insurance",
    "Tidewater Surety & Casualty",
    "Sterling National Insurance Co.",
    "Ironbridge Excess Carriers Ltd.",
    "Atlantic Coast Mutual",
    "Keystone Indemnity Group",
    "Mountain West Casualty Co.",
    "Sunbelt Workers Comp Trust",
    "Northern Lights Insurance Corp.",
    "Compass Rose Specialty",
]

INSUREDS = [
    ("Atlas Framing & Construction LLC", "221 Industrial Park Drive", "Lakeland, FL 33805"),
    ("Meridian Mechanical Services Inc.", "4400 Commerce Drive", "Indianapolis, IN 46268"),
    ("Silverline Electrical Contractors", "1800 N. Highland Avenue", "Los Angeles, CA 90028"),
    ("Brookfield Property Management Group", "350 Madison Avenue, 8th Floor", "New York, NY 10017"),
    ("Clearwater Environmental Solutions", "600 N. Pine Island Road", "Fort Lauderdale, FL 33324"),
    ("Granite Peak General Contractors", "7700 Mineral Drive, Suite 200", "Coeur d'Alene, ID 83815"),
    ("Suncoast Roofing & Waterproofing", "2901 Gandy Boulevard", "St. Petersburg, FL 33702"),
    ("Cascade Plumbing & HVAC Inc.", "15200 NE 8th Street, Suite 300", "Bellevue, WA 98007"),
    ("Prairie Home Builders LLC", "1100 N. Meridian Street", "Oklahoma City, OK 73107"),
    ("Summit Landscaping & Excavation", "4500 W. Colfax Avenue", "Denver, CO 80204"),
    ("Iron Horse Steel Erectors Inc.", "8200 Lehigh Avenue", "Morton Grove, IL 60053"),
    ("Bayou City Demolition Services", "3200 Westheimer Road", "Houston, TX 77098"),
    ("Cornerstone Civil Engineering PC", "90 State Street, Suite 700", "Albany, NY 12207"),
    ("Redline Fire Protection Corp.", "1650 Borel Place, Suite 200", "San Mateo, CA 94402"),
    ("Valley Forge Painting Contractors", "450 Lancaster Avenue", "Wayne, PA 19087"),
    ("Northern Star Telecom Services", "2700 University Avenue", "Minneapolis, MN 55414"),
    ("Coastal Crane & Rigging LLC", "5100 Port Road", "Savannah, GA 31415"),
    ("Westridge Concrete Foundations", "3300 S. Figueroa Street", "Los Angeles, CA 90007"),
    ("Evergreen Site Development Corp.", "1400 NW Compton Drive", "Portland, OR 97209"),
    ("Continental Scaffolding Inc.", "600 N. Michigan Avenue, Suite 800", "Chicago, IL 60611"),
]

CERT_HOLDERS = [
    ("Sunshine Development Partners LLC", "1000 Brickell Avenue, Suite 900", "Miami, FL 33131"),
    ("Lakewood Properties Inc.", "225 W. Washington Street, Suite 1200", "Chicago, IL 60606"),
    ("Triton Capital Group", "One Market Street, 36th Floor", "San Francisco, CA 94105"),
    ("Harbor Point Real Estate Holdings", "500 Atlantic Avenue", "Boston, MA 02210"),
    ("Pinnacle Ventures LLC", "3500 Piedmont Road NE, Suite 400", "Atlanta, GA 30305"),
    ("Golden Crest Hospitality Corp.", "2600 Michelson Drive", "Irvine, CA 92612"),
    ("Northwind Infrastructure Partners", "800 Fifth Avenue, Suite 4100", "Seattle, WA 98104"),
    ("Liberty Square Investments", "1700 Broadway, 41st Floor", "New York, NY 10019"),
    ("Riverstone Development Group", "100 Peabody Place, Suite 1400", "Memphis, TN 38103"),
    ("Crossroads Commercial Properties", "11000 Regency Parkway", "Cary, NC 27518"),
]

ADDITIONAL_INSUREDS = [
    "Titan Construction Management LLC",
    "Heritage Capital Partners",
    "Vanguard Property Holdings Inc.",
    "Olympus General Contractors",
    "Crestview Development Corp.",
    "Ironworks Joint Venture LLC",
    "Pacific Rim Investments Group",
    "Sentinel Real Estate Trust",
    "Bluewater Infrastructure LLC",
    "Keystone Realty Advisors",
    "Metro Transit Authority",
    "First National Lending Corp.",
]

# Coverage type definitions with typical limits
CGL_LIMITS = [
    ("Each Occurrence", [1000000, 2000000]),
    ("General Aggregate", [2000000, 4000000]),
    ("Products / Completed Operations", [2000000, 4000000]),
    ("Personal & Advertising Injury", [1000000, 2000000]),
    ("Damage to Rented Premises", [100000, 300000, 500000]),
    ("Medical Expense (Any One Person)", [5000, 10000, 15000]),
]

AUTO_LIMITS = [
    ("Combined Single Limit (Each Accident)", [1000000, 2000000]),
]

UMBRELLA_LIMITS = [
    ("Each Occurrence", [5000000, 10000000, 25000000]),
    ("Aggregate", [5000000, 10000000, 25000000]),
    ("Self-Insured Retention", [10000, 25000]),
]

WC_LIMITS = [
    ("Bodily Injury by Accident (Each Accident)", [500000, 1000000]),
    ("Bodily Injury by Disease (Policy Limit)", [500000, 1000000]),
    ("Bodily Injury by Disease (Each Employee)", [500000, 1000000]),
]

PROF_LIMITS = [
    ("Each Claim", [1000000, 2000000, 5000000]),
    ("Aggregate", [2000000, 5000000, 10000000]),
    ("Deductible", [10000, 25000, 50000]),
]

CYBER_LIMITS = [
    ("Each Incident", [1000000, 2000000, 5000000]),
    ("Aggregate", [2000000, 5000000]),
    ("Retention", [15000, 25000, 50000]),
]

EXCESS_LIMITS = [
    ("Each Occurrence", [5000000, 10000000]),
    ("Aggregate", [5000000, 10000000]),
]

COVERAGE_DEFS = {
    "Commercial General Liability": {
        "prefix": "CGL",
        "limits": CGL_LIMITS,
    },
    "Automobile Liability": {
        "prefix": "AUT",
        "limits": AUTO_LIMITS,
    },
    "Umbrella Liability": {
        "prefix": "UMB",
        "limits": UMBRELLA_LIMITS,
    },
    "Workers Compensation": {
        "prefix": "WC",
        "limits": WC_LIMITS,
    },
    "Professional Liability": {
        "prefix": "PL",
        "limits": PROF_LIMITS,
    },
    "Cyber Liability": {
        "prefix": "CYB",
        "limits": CYBER_LIMITS,
    },
    "Excess Liability": {
        "prefix": "EXC",
        "limits": EXCESS_LIMITS,
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_policy_number(prefix: str, rng: random.Random) -> str:
    return f"{prefix}{rng.randint(1000000, 9999999)}"


def _pick_date(rng: random.Random) -> tuple[str, str]:
    """Return (iso_date, display_date) for a certificate date."""
    year = rng.choice([2025, 2025, 2026])
    month = rng.randint(1, 12)
    day = rng.randint(1, 28)
    iso = f"{year}-{month:02d}-{day:02d}"
    display = f"{month:02d}/{day:02d}/{year}"
    return iso, display


def _eff_exp_dates(rng: random.Random) -> tuple[str, str, str, str]:
    """Return (eff_iso, exp_iso, eff_display, exp_display)."""
    year = rng.choice([2025, 2025, 2026])
    month = rng.randint(1, 12)
    day = rng.randint(1, 28)
    eff_iso = f"{year}-{month:02d}-{day:02d}"
    exp_iso = f"{year + 1}-{month:02d}-{day:02d}"
    eff_disp = f"{month:02d}/{day:02d}/{year}"
    exp_disp = f"{month:02d}/{day:02d}/{year + 1}"
    return eff_iso, exp_iso, eff_disp, exp_disp


def _fmt_amount(val: int) -> str:
    """Format a dollar amount: $1,000,000."""
    return f"${val:,}"


def _generate_limits(limit_defs: list, rng: random.Random) -> list[dict]:
    """Pick one amount for each limit in the definition."""
    return [{"name": name, "amount": rng.choice(amounts)} for name, amounts in limit_defs]


def _pick_carriers(n: int, rng: random.Random) -> list[str]:
    """Pick n distinct carriers."""
    return rng.sample(CARRIERS, n)


def _assign_carrier_letters(carriers: list[str]) -> dict[str, str]:
    """Map carrier names to letters A, B, C, ..."""
    letters = "ABCDEFGHIJ"
    return {carriers[i]: letters[i] for i in range(len(carriers))}


def _make_policies(
    coverage_types: list[str],
    carrier_assignments: dict[str, str],
    rng: random.Random,
) -> list[dict]:
    """Generate policy records for the given coverage types.

    carrier_assignments maps coverage_type -> carrier_name.
    """
    eff_iso, exp_iso, eff_disp, exp_disp = _eff_exp_dates(rng)
    policies = []
    for ctype in coverage_types:
        cdef = COVERAGE_DEFS[ctype]
        policies.append({
            "policy_number": _make_policy_number(cdef["prefix"], rng),
            "coverage_type": ctype,
            "carrier_name": carrier_assignments[ctype],
            "effective_date": eff_iso,
            "expiration_date": exp_iso,
            "eff_display": eff_disp,
            "exp_display": exp_disp,
            "limits": _generate_limits(cdef["limits"], rng),
            "additional_insureds": [],
        })
    return policies


# ---------------------------------------------------------------------------
# Markdown renderers
# ---------------------------------------------------------------------------

def _render_header_standard(
    cert_date_display: str,
    producer: tuple,
    insured: tuple,
    carrier_letter_map: dict[str, str],
) -> str:
    """Standard ACORD-style header: title, producer, insured, insurer list."""
    p_name, p_addr, p_city, p_phone = producer
    i_name, i_addr, i_city = insured
    lines = [
        "# Certificate of Liability Insurance",
        "",
        f"Date (MM/DD/YYYY): {cert_date_display}",
        "",
        "---",
        "",
        "## Producer",
        "",
        p_name,
        p_addr,
        p_city,
        f"Phone: {p_phone}",
        "",
        "## Insured",
        "",
        i_name,
        i_addr,
        i_city,
        "",
        "## Insurers Affording Coverage",
        "",
    ]
    # Invert: letter -> carrier
    letter_to_carrier = {v: k for k, v in carrier_letter_map.items()}
    for letter in sorted(letter_to_carrier):
        lines.append(f"- Insurer {letter}: {letter_to_carrier[letter]}")
    lines.append("")
    return "\n".join(lines)


def _render_header_date_first(
    cert_date_display: str,
    producer: tuple,
    insured: tuple,
    carrier_letter_map: dict[str, str],
) -> str:
    """Variant: date at the very top before producer."""
    p_name, p_addr, p_city, p_phone = producer
    i_name, i_addr, i_city = insured
    lines = [
        "# ACORD 25 — Certificate of Liability Insurance",
        "",
        f"**Certificate Date:** {cert_date_display}",
        "",
        "---",
        "",
        "### Producer",
        "",
        f"**{p_name}**",
        f"{p_addr}, {p_city}",
        f"Phone: {p_phone}",
        "",
        "### Named Insured",
        "",
        i_name,
        f"{i_addr}, {i_city}",
        "",
        "### Insurers Providing Coverage",
        "",
    ]
    letter_to_carrier = {v: k for k, v in carrier_letter_map.items()}
    for letter in sorted(letter_to_carrier):
        lines.append(f"Insurer {letter}: {letter_to_carrier[letter]}")
    lines.append("")
    return "\n".join(lines)


def _render_header_kv_style(
    cert_date_display: str,
    producer: tuple,
    insured: tuple,
    carrier_letter_map: dict[str, str],
) -> str:
    """Key-value pair layout (no markdown headers for sections)."""
    p_name, p_addr, p_city, p_phone = producer
    i_name, i_addr, i_city = insured
    lines = [
        "# Certificate of Liability Insurance",
        "",
        f"**DATE:** {cert_date_display}",
        "",
        f"**PRODUCER:** {p_name}, {p_addr}, {p_city}",
        f"**PHONE:** {p_phone}",
        "",
        f"**INSURED:** {i_name}, {i_addr}, {i_city}",
        "",
        "**INSURERS AFFORDING COVERAGE:**",
        "",
    ]
    letter_to_carrier = {v: k for k, v in carrier_letter_map.items()}
    for letter in sorted(letter_to_carrier):
        lines.append(f"- **{letter}**: {letter_to_carrier[letter]}")
    lines.append("")
    return "\n".join(lines)


def _render_coverage_grid(policies: list[dict], carrier_letter_map: dict) -> str:
    """Render the coverage summary table using insurer letters."""
    lines = [
        "---",
        "",
        "## Coverage Summary",
        "",
        "| INSR LTR | Type of Insurance | Policy Number | Effective | Expires |",
        "|---|---|---|---|---|",
    ]
    for p in policies:
        letter = carrier_letter_map.get(p["carrier_name"], "?")
        lines.append(
            f"| {letter} | {p['coverage_type']} | {p['policy_number']} "
            f"| {p['eff_display']} | {p['exp_display']} |"
        )
    lines.append("")
    return "\n".join(lines)


def _render_coverage_grid_no_table(policies: list[dict], carrier_letter_map: dict) -> str:
    """Render coverage summary as key-value pairs instead of a table."""
    lines = [
        "---",
        "",
        "## Policies in Force",
        "",
    ]
    for p in policies:
        letter = carrier_letter_map.get(p["carrier_name"], "?")
        lines.append(f"**{p['coverage_type']}**")
        lines.append(f"- Insurer: {letter}")
        lines.append(f"- Policy No.: {p['policy_number']}")
        lines.append(f"- Effective: {p['eff_display']}")
        lines.append(f"- Expires: {p['exp_display']}")
        lines.append("")
    return "\n".join(lines)


def _render_limits_combined(policies: list[dict]) -> str:
    """Render all limits in a single Coverage Detail section."""
    lines = [
        "---",
        "",
        "## Coverage Detail",
        "",
        "Detailed limits for each policy listed in the summary above:",
        "",
    ]
    for p in policies:
        lines.append(f"### Policy {p['policy_number']} \u2014 {p['coverage_type']}")
        lines.append("")
        for lim in p["limits"]:
            lines.append(f"- {lim['name']}: {_fmt_amount(lim['amount'])}")
        lines.append("")
    return "\n".join(lines)


def _render_limits_split(policies: list[dict], rng: random.Random) -> tuple[str, list[dict]]:
    """Split limits between the coverage grid and a separate detailed section.

    Returns (markdown, updated_policies_with_all_limits).
    Some limits appear only in the grid, some only in the detail section,
    some in both. The expected JSON must have ALL of them.
    """
    grid_lines = [
        "---",
        "",
        "## Coverage Summary — Limits",
        "",
        "| Policy | Limit | Amount |",
        "|---|---|---|",
    ]
    detail_lines = [
        "",
        "---",
        "",
        "## Schedule of Limits — Additional Detail",
        "",
    ]

    for p in policies:
        all_limits = list(p["limits"])
        # Split: some go to grid only, some to detail only, some to both
        grid_only = []
        detail_only = []
        both = []
        for lim in all_limits:
            r = rng.random()
            if r < 0.3:
                grid_only.append(lim)
            elif r < 0.6:
                detail_only.append(lim)
            else:
                both.append(lim)

        # Ensure at least one in each section
        if not grid_only and not both:
            if detail_only:
                both.append(detail_only.pop())
        if not detail_only and not both:
            if grid_only:
                both.append(grid_only.pop())

        for lim in grid_only + both:
            grid_lines.append(
                f"| {p['policy_number']} | {lim['name']} | {_fmt_amount(lim['amount'])} |"
            )

        detail_lines.append(f"### {p['coverage_type']} ({p['policy_number']})")
        detail_lines.append("")
        for lim in detail_only + both:
            detail_lines.append(f"- {lim['name']}: {_fmt_amount(lim['amount'])}")
        detail_lines.append("")

    grid_lines.append("")
    return "\n".join(grid_lines) + "\n".join(detail_lines), policies


def _render_description_blanket(cert_holder_name: str) -> str:
    """Description of Operations with blanket additional insured language."""
    return "\n".join([
        "---",
        "",
        "## Description of Operations / Locations / Vehicles",
        "",
        f"All policies listed herein include {cert_holder_name} as additional insured "
        "as required by written contract. Coverage is primary and non-contributory.",
        "",
    ])


def _render_description_per_policy(
    assignments: list[tuple[str, list[str]]],
) -> str:
    """Description of Operations with per-policy additional insured assignments.

    assignments: list of (party_name, [policy_numbers])
    """
    lines = [
        "---",
        "",
        "## Description of Operations / Locations / Vehicles",
        "",
    ]
    for party, pnums in assignments:
        if len(pnums) == 1:
            lines.append(
                f"{party} is additional insured on policy #{pnums[0]} only, "
                "per endorsement CG 20 26."
            )
        else:
            nums = " and ".join(f"#{pn}" for pn in pnums)
            lines.append(
                f"{party} is additional insured on policies {nums} only, "
                "per endorsement CG 20 26."
            )
    lines.append("")
    return "\n".join(lines)


def _render_description_plain(text: str) -> str:
    """Plain description with custom text."""
    return "\n".join([
        "---",
        "",
        "## Description of Operations / Locations / Vehicles",
        "",
        text,
        "",
    ])


def _render_cert_holder(ch: tuple) -> str:
    ch_name, ch_addr, ch_city = ch
    return "\n".join([
        "## Certificate Holder",
        "",
        ch_name,
        ch_addr,
        ch_city,
        "",
    ])


# ---------------------------------------------------------------------------
# Category generators
# ---------------------------------------------------------------------------

def _gen_cat1_carrier_letter(idx: int, rng: random.Random) -> tuple[str, dict, dict]:
    """Category 1: Carrier letter-code resolution.

    2-4 carriers per doc, coverage grid uses letters only.
    Expected must have full carrier names.
    """
    producer = rng.choice(PRODUCERS)
    insured = INSUREDS[idx % len(INSUREDS)]
    cert_holder = rng.choice(CERT_HOLDERS)

    cert_iso, cert_display = _pick_date(rng)

    n_carriers = rng.randint(2, 4)
    carriers = _pick_carriers(n_carriers, rng)
    letter_map = _assign_carrier_letters(carriers)  # carrier_name -> letter

    # Pick 2-4 coverage types
    n_policies = rng.randint(2, 4)
    coverage_types = rng.sample(
        ["Commercial General Liability", "Automobile Liability",
         "Umbrella Liability", "Workers Compensation"],
        min(n_policies, 4),
    )

    # Assign each coverage to a carrier
    carrier_assignments = {}
    for i, ct in enumerate(coverage_types):
        carrier_assignments[ct] = carriers[i % n_carriers]

    policies = _make_policies(coverage_types, carrier_assignments, rng)

    # Build markdown
    header_fn = rng.choice([_render_header_standard, _render_header_date_first])
    md = header_fn(cert_display, producer, insured, letter_map)
    md += _render_coverage_grid(policies, letter_map)
    md += _render_limits_combined(policies)
    md += _render_description_plain(
        "General construction operations. Certificate holder is for informational purposes only."
    )
    md += _render_cert_holder(cert_holder)

    expected = _build_expected(cert_iso, producer, insured, cert_holder, policies)
    manifest = _build_manifest(idx, "carrier-letter-code-resolution")
    return md, expected, manifest


def _gen_cat2_per_policy_ai(idx: int, rng: random.Random) -> tuple[str, dict, dict]:
    """Category 2: Per-policy additional insureds.

    Specific parties named as AI on specific policies only.
    """
    producer = rng.choice(PRODUCERS)
    insured = INSUREDS[idx % len(INSUREDS)]
    cert_holder = rng.choice(CERT_HOLDERS)

    cert_iso, cert_display = _pick_date(rng)

    carriers = _pick_carriers(3, rng)
    letter_map = _assign_carrier_letters(carriers)

    coverage_types = ["Commercial General Liability", "Automobile Liability",
                      "Umbrella Liability", "Workers Compensation"]
    carrier_assignments = {ct: carriers[i % 3] for i, ct in enumerate(coverage_types)}
    policies = _make_policies(coverage_types, carrier_assignments, rng)

    # Pick 2-3 additional insureds and assign to specific policies
    n_ai = rng.randint(2, 3)
    ai_parties = rng.sample(ADDITIONAL_INSUREDS, n_ai)

    # Also sometimes include the cert holder as an AI on specific policies
    include_ch = rng.random() > 0.4
    if include_ch:
        ai_parties.append(cert_holder[0])

    assignments = []
    for party in ai_parties:
        # Each party gets 1-2 policies
        n_assigned = rng.randint(1, min(2, len(policies)))
        assigned_policies = rng.sample(policies, n_assigned)
        assigned_pnums = [p["policy_number"] for p in assigned_policies]
        assignments.append((party, assigned_pnums))
        for p in assigned_policies:
            p["additional_insureds"].append(party)

    md = _render_header_standard(cert_display, producer, insured, letter_map)
    md += _render_coverage_grid(policies, letter_map)
    md += _render_limits_combined(policies)
    md += _render_description_per_policy(assignments)
    md += _render_cert_holder(cert_holder)

    expected = _build_expected(cert_iso, producer, insured, cert_holder, policies)
    manifest = _build_manifest(idx, "per-policy-additional-insureds")
    return md, expected, manifest


def _gen_cat3_blanket_ai(idx: int, rng: random.Random) -> tuple[str, dict, dict]:
    """Category 3: Blanket additional insureds.

    Certificate holder is AI on ALL policies.
    """
    producer = rng.choice(PRODUCERS)
    insured = INSUREDS[idx % len(INSUREDS)]
    cert_holder = rng.choice(CERT_HOLDERS)

    cert_iso, cert_display = _pick_date(rng)

    carriers = _pick_carriers(rng.randint(2, 3), rng)
    letter_map = _assign_carrier_letters(carriers)

    coverage_types = rng.sample(
        ["Commercial General Liability", "Automobile Liability",
         "Umbrella Liability", "Workers Compensation"],
        rng.randint(2, 4),
    )
    carrier_assignments = {ct: carriers[i % len(carriers)] for i, ct in enumerate(coverage_types)}
    policies = _make_policies(coverage_types, carrier_assignments, rng)

    # Blanket: cert holder is AI on every policy
    for p in policies:
        p["additional_insureds"].append(cert_holder[0])

    md = _render_header_standard(cert_display, producer, insured, letter_map)
    md += _render_coverage_grid(policies, letter_map)
    md += _render_limits_combined(policies)
    md += _render_description_blanket(cert_holder[0])
    md += _render_cert_holder(cert_holder)

    expected = _build_expected(cert_iso, producer, insured, cert_holder, policies)
    manifest = _build_manifest(idx, "blanket-additional-insureds")
    return md, expected, manifest


def _gen_cat4_complex_limits(idx: int, rng: random.Random) -> tuple[str, dict, dict]:
    """Category 4: Complex limits from multiple sections.

    Limits split between coverage grid table and a separate schedule.
    Expected must collate ALL limits from both.
    """
    producer = rng.choice(PRODUCERS)
    insured = INSUREDS[idx % len(INSUREDS)]
    cert_holder = rng.choice(CERT_HOLDERS)

    cert_iso, cert_display = _pick_date(rng)

    carriers = _pick_carriers(3, rng)
    letter_map = _assign_carrier_letters(carriers)

    coverage_types = ["Commercial General Liability", "Automobile Liability",
                      "Umbrella Liability", "Workers Compensation"]
    carrier_assignments = {ct: carriers[i % 3] for i, ct in enumerate(coverage_types)}
    policies = _make_policies(coverage_types, carrier_assignments, rng)

    md = _render_header_standard(cert_display, producer, insured, letter_map)
    md += _render_coverage_grid(policies, letter_map)
    limits_md, policies = _render_limits_split(policies, rng)
    md += limits_md
    md += _render_description_plain(
        "Commercial construction and renovation services. "
        "Certificate is for informational purposes."
    )
    md += _render_cert_holder(cert_holder)

    expected = _build_expected(cert_iso, producer, insured, cert_holder, policies)
    manifest = _build_manifest(idx, "complex-limits-multiple-sections")
    return md, expected, manifest


def _gen_cat5_layout_variation(idx: int, rng: random.Random) -> tuple[str, dict, dict]:
    """Category 5: ACORD layout variations.

    Different header orders, table vs key-value, section naming.
    """
    producer = rng.choice(PRODUCERS)
    insured = INSUREDS[idx % len(INSUREDS)]
    cert_holder = rng.choice(CERT_HOLDERS)

    cert_iso, cert_display = _pick_date(rng)

    carriers = _pick_carriers(rng.randint(2, 3), rng)
    letter_map = _assign_carrier_letters(carriers)

    coverage_types = rng.sample(
        ["Commercial General Liability", "Automobile Liability",
         "Umbrella Liability", "Workers Compensation"],
        rng.randint(2, 4),
    )
    carrier_assignments = {ct: carriers[i % len(carriers)] for i, ct in enumerate(coverage_types)}
    policies = _make_policies(coverage_types, carrier_assignments, rng)

    # Vary the header layout
    variant = idx % 3
    if variant == 0:
        header_fn = _render_header_date_first
    elif variant == 1:
        header_fn = _render_header_kv_style
    else:
        header_fn = _render_header_standard

    md = header_fn(cert_display, producer, insured, letter_map)

    # Vary the coverage grid layout
    if idx % 2 == 0:
        md += _render_coverage_grid_no_table(policies, letter_map)
    else:
        md += _render_coverage_grid(policies, letter_map)

    md += _render_limits_combined(policies)
    md += _render_description_plain(
        "General business operations and services as required by contract."
    )
    md += _render_cert_holder(cert_holder)

    expected = _build_expected(cert_iso, producer, insured, cert_holder, policies)
    manifest = _build_manifest(idx, "acord-layout-variations")
    return md, expected, manifest


def _gen_cat6_multi_coverage(idx: int, rng: random.Random) -> tuple[str, dict, dict]:
    """Category 6: Multi-coverage complexity.

    4-6 policies spanning CGL, auto, umbrella, WC, professional, cyber.
    """
    producer = rng.choice(PRODUCERS)
    insured = INSUREDS[idx % len(INSUREDS)]
    cert_holder = rng.choice(CERT_HOLDERS)

    cert_iso, cert_display = _pick_date(rng)

    carriers = _pick_carriers(rng.randint(3, 5), rng)
    letter_map = _assign_carrier_letters(carriers)

    # Always include CGL + auto, then add 2-4 more
    base = ["Commercial General Liability", "Automobile Liability"]
    extras = rng.sample(
        ["Umbrella Liability", "Workers Compensation",
         "Professional Liability", "Cyber Liability", "Excess Liability"],
        rng.randint(2, 4),
    )
    coverage_types = base + extras

    carrier_assignments = {ct: carriers[i % len(carriers)] for i, ct in enumerate(coverage_types)}
    policies = _make_policies(coverage_types, carrier_assignments, rng)

    # Maybe add blanket AI
    if rng.random() > 0.5:
        for p in policies:
            p["additional_insureds"].append(cert_holder[0])
        desc = _render_description_blanket(cert_holder[0])
    else:
        desc = _render_description_plain(
            "Technology consulting and professional services. "
            "See attached endorsement schedule for additional insured details."
        )

    md = _render_header_standard(cert_display, producer, insured, letter_map)
    md += _render_coverage_grid(policies, letter_map)
    md += _render_limits_combined(policies)
    md += desc
    md += _render_cert_holder(cert_holder)

    expected = _build_expected(cert_iso, producer, insured, cert_holder, policies)
    manifest = _build_manifest(idx, "multi-coverage-complexity")
    return md, expected, manifest


# ---------------------------------------------------------------------------
# Expected / manifest builders
# ---------------------------------------------------------------------------

def _build_expected(
    cert_iso: str,
    producer: tuple,
    insured: tuple,
    cert_holder: tuple,
    policies: list[dict],
) -> dict:
    return {
        "certificate_date": cert_iso,
        "producer_name": producer[0],
        "producer_phone": producer[3],
        "insured_name": insured[0],
        "certificate_holder_name": cert_holder[0],
        "policies": [
            {
                "policy_number": p["policy_number"],
                "coverage_type": p["coverage_type"],
                "carrier_name": p["carrier_name"],
                "effective_date": p["effective_date"],
                "expiration_date": p["expiration_date"],
                "limits": [{"name": lim["name"], "amount": lim["amount"]} for lim in p["limits"]],
                "additional_insureds": p["additional_insureds"] if p["additional_insureds"] else [],
            }
            for p in policies
        ],
    }


def _build_manifest(idx: int, pain_point: str) -> dict:
    file_id = f"synth_coi_{idx + 1:03d}"
    return {
        "filename": f"{file_id}.md",
        "source_name": "Synthetic generator (synthetic_cois.py)",
        "source_url": None,
        "license": "Apache-2.0",
        "license_url": "https://www.apache.org/licenses/LICENSE-2.0",
        "attribution": "FieldBench corpus contributors",
        "original_format": "markdown",
        "r2_url": None,
        "pages": 1,
        "added_date": "2026-04-16",
        "added_by": "accuracy-24",
        "schema": "insurance_certificates/schemas/certificate_of_liability.yaml",
        "doc_type": "coi",
        "notes": f"Synthetic COI targeting pain point: {pain_point}.",
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

# Category schedule: (generator_fn, count)
CATEGORIES = [
    (_gen_cat1_carrier_letter, 8),
    (_gen_cat2_per_policy_ai, 8),
    (_gen_cat3_blanket_ai, 5),
    (_gen_cat4_complex_limits, 8),
    (_gen_cat5_layout_variation, 6),
    (_gen_cat6_multi_coverage, 5),
]


def _write_coi(file_id: str, md: str, expected: dict, manifest: dict) -> None:
    (CERTS_DIR / "documents" / f"{file_id}.md").write_text(md + "\n")
    (CERTS_DIR / "expected" / f"{file_id}.expected.json").write_text(json.dumps(expected, indent=2) + "\n")
    (CERTS_DIR / "manifests" / f"{file_id}.json").write_text(json.dumps(manifest, indent=2) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--extra", type=int, default=0,
                    help="generate N additional COIs after the base 40 (distinct seed), cycling the category generators")
    args = ap.parse_args()

    rng = random.Random(SEED)

    for sub in ("documents", "expected", "manifests"):
        (CERTS_DIR / sub).mkdir(parents=True, exist_ok=True)

    total = sum(count for _, count in CATEGORIES)
    assert total == 40, f"Expected 40 docs, schedule sums to {total}"

    global_idx = 0
    for gen_fn, count in CATEGORIES:
        for _ in range(count):
            file_id = f"synth_coi_{global_idx + 1:03d}"
            md, expected, manifest = gen_fn(global_idx, rng)
            _write_coi(file_id, md, expected, manifest)
            cat_name = manifest["notes"].split("pain point: ")[1].rstrip(".")
            print(f"[synth-coi] ({global_idx + 1}/{total}) {file_id}  [{cat_name}]", file=sys.stderr)
            global_idx += 1

    if args.extra:
        # Additional docs: ids continue after the base 40, distinct seed so they
        # are not identical to the base set; cycle the category generators.
        ergng = random.Random(SEED + 1)
        gens = [g for g, _ in CATEGORIES]
        for i in range(args.extra):
            gi = 40 + i
            file_id = f"synth_coi_{gi + 1:03d}"
            md, expected, manifest = gens[i % len(gens)](gi, ergng)
            _write_coi(file_id, md, expected, manifest)
            print(f"[synth-coi] (extra {i + 1}/{args.extra}) {file_id}", file=sys.stderr)

    print(f"\n[synth-coi] Done. Generated {total + args.extra} synthetic COIs.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
