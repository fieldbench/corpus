#!/usr/bin/env python3
"""Synthetic loss run report generator for the FieldBench corpus.

Generates 50 synthetic loss run reports (claims history documents) in
markdown format with known ground-truth expected JSON outputs and
manifest files.

A loss run is a tabular claims history report from an insurance carrier
showing all claims filed against a policy over a given period. These
are commonly requested during policy renewals, audits, or M&A due
diligence.

Each report includes:
  - Carrier header with policy info
  - Tabular claims history (2-20 claims per report)
  - Mix of carriers, policy types, claim sizes, and statuses

Uses a fixed random seed (20260416) for reproducibility.
No external dependencies — stdlib only.

Usage:
  python scripts/sources/synthetic_loss_runs.py
"""

from __future__ import annotations

import json
import random
import sys
from datetime import date, timedelta
from pathlib import Path

CORPUS_ROOT = Path(__file__).resolve().parent.parent.parent
CLAIMS_DIR = CORPUS_ROOT / "insurance_claims"

SEED = 20260416
NUM_DOCS = 50

# ---------------------------------------------------------------------------
# Data pools
# ---------------------------------------------------------------------------

CARRIERS = [
    "Liberty Mutual Insurance Company",
    "Travelers Indemnity Company",
    "The Hartford Financial Services Group",
    "Zurich American Insurance Company",
    "CNA Financial Corporation",
    "Great American Insurance Company",
    "Chubb Limited",
    "Nationwide Mutual Insurance Company",
    "Erie Insurance Group",
    "Hanover Insurance Group",
    "American Financial Group",
    "Markel Corporation",
    "Employers Holdings Inc.",
    "AMERITAS Life Partners",
    "Sentry Insurance Group",
    "West Bend Mutual Insurance",
]

INSUREDS = [
    ("Atlas Framing & Construction LLC", "221 Industrial Park Drive", "Lakeland", "FL"),
    ("Meridian Mechanical Services Inc.", "4400 Commerce Drive", "Indianapolis", "IN"),
    ("Silverline Electrical Contractors", "1800 N. Highland Avenue", "Los Angeles", "CA"),
    ("Brookfield Property Management Group", "350 Madison Avenue, 8th Floor", "New York", "NY"),
    ("Clearwater Environmental Solutions", "600 N. Pine Island Road", "Fort Lauderdale", "FL"),
    ("Granite Peak General Contractors", "7700 Mineral Drive, Suite 200", "Coeur d'Alene", "ID"),
    ("Suncoast Roofing & Waterproofing", "2901 Gandy Boulevard", "St. Petersburg", "FL"),
    ("Cascade Plumbing & HVAC Inc.", "15200 NE 8th Street, Suite 300", "Bellevue", "WA"),
    ("Prairie Home Builders LLC", "1100 N. Meridian Street", "Oklahoma City", "OK"),
    ("Summit Landscaping & Excavation", "4500 W. Colfax Avenue", "Denver", "CO"),
    ("Iron Horse Steel Erectors Inc.", "8200 Lehigh Avenue", "Morton Grove", "IL"),
    ("Bayou City Demolition Services", "3200 Westheimer Road", "Houston", "TX"),
    ("Cornerstone Civil Engineering PC", "90 State Street, Suite 700", "Albany", "NY"),
    ("Redline Fire Protection Corp.", "1650 Borel Place, Suite 200", "San Mateo", "CA"),
    ("Valley Forge Painting Contractors", "450 Lancaster Avenue", "Wayne", "PA"),
    ("Northern Star Telecom Services", "2700 University Avenue", "Minneapolis", "MN"),
    ("Coastal Crane & Rigging LLC", "5100 Port Road", "Savannah", "GA"),
    ("Westridge Concrete Foundations", "3300 S. Figueroa Street", "Los Angeles", "CA"),
    ("Evergreen Site Development Corp.", "1400 NW Compton Drive", "Portland", "OR"),
    ("Continental Scaffolding Inc.", "600 N. Michigan Avenue, Suite 800", "Chicago", "IL"),
    ("Apex Trucking & Logistics Co.", "1200 Harbor Blvd", "Fullerton", "CA"),
    ("Blue Ridge Fence & Deck LLC", "312 Valley View Road", "Asheville", "NC"),
    ("Lonestar Welding Services Inc.", "8800 Stemmons Freeway", "Dallas", "TX"),
    ("Great Plains Grain Elevator Co.", "400 N. Broadway", "Salina", "KS"),
    ("Tidewater Marine Repair Inc.", "2200 Shipyard Drive", "Norfolk", "VA"),
    ("Keystone Elevator Services LLC", "1500 JFK Boulevard", "Philadelphia", "PA"),
    ("Redwood Timber Harvesting Co.", "3400 Redwood Highway", "Grants Pass", "OR"),
    ("Sunbelt Paving & Grading Inc.", "7100 Peachtree Industrial Blvd", "Norcross", "GA"),
    ("Mountain West Drilling Corp.", "900 E. Bonneville Avenue", "Las Vegas", "NV"),
    ("Harbor View Hotel Group LLC", "5 Waterfront Plaza", "Honolulu", "HI"),
]

POLICY_TYPES = [
    ("GL", "General Liability"),
    ("WC", "Workers Compensation"),
    ("AUTO", "Commercial Auto"),
    ("PROP", "Commercial Property"),
]

# Claim descriptions by policy type
GL_DESCRIPTIONS = [
    "Slip and fall on wet floor in lobby area",
    "Trip and fall over uneven sidewalk at job site",
    "Customer injured by falling merchandise",
    "Third-party property damage during renovation",
    "Bodily injury — visitor struck by swinging door",
    "Slip on icy walkway outside main entrance",
    "Product liability — defective component failure",
    "Advertising injury — alleged trademark infringement",
    "Customer allergic reaction to cleaning chemicals",
    "Contractor damaged adjacent property during excavation",
    "Visitor fell through temporary floor covering",
    "Delivery driver injured on insured's premises",
    "Water damage to neighboring tenant from burst pipe",
    "Pedestrian struck by debris from roof work",
    "Completed operations — foundation crack post-construction",
    "Mold exposure claim from building occupant",
]

WC_DESCRIPTIONS = [
    "Employee back strain lifting heavy materials",
    "Laceration — worker cut by power saw",
    "Repetitive motion injury — carpal tunnel syndrome",
    "Fall from scaffold — fractured wrist",
    "Heat exhaustion during outdoor work",
    "Employee struck by forklift in warehouse",
    "Chemical burn from solvent exposure",
    "Knee injury descending ladder",
    "Shoulder rotator cuff tear — overhead work",
    "Finger amputation — press machine incident",
    "Slip on oily shop floor — hip fracture",
    "Electric shock from faulty wiring",
    "Lower back herniated disc — material handling",
    "Eye injury from metal grinding debris",
    "Ankle sprain on uneven terrain at job site",
    "Hearing loss — prolonged noise exposure",
]

AUTO_DESCRIPTIONS = [
    "Rear-end collision on highway",
    "Backing accident in parking lot",
    "Side-swipe while merging on interstate",
    "Intersection collision — driver ran red light",
    "Single vehicle rollover on rural road",
    "Pedestrian struck in crosswalk",
    "Multi-vehicle pileup in construction zone",
    "Company van hit parked vehicle",
    "Delivery truck struck bridge overpass",
    "T-bone collision at uncontrolled intersection",
    "Vehicle struck deer on highway",
    "Driver lost control on wet road — hit guardrail",
    "Cargo spill on highway — hazmat response required",
    "Fleet vehicle stolen from job site lot",
    "Windshield damage from road debris",
    "Collision with utility pole — power outage",
]

PROP_DESCRIPTIONS = [
    "Fire damage to warehouse — electrical fault",
    "Wind damage to roof from severe thunderstorm",
    "Burst water pipe — office flooding",
    "Hail damage to building exterior and vehicles",
    "Theft of equipment from storage facility",
    "Vandalism — graffiti and broken windows",
    "Lightning strike — electrical system damage",
    "Frozen pipe burst — water damage to inventory",
    "HVAC unit failure — spoiled temperature-sensitive goods",
    "Roof collapse under heavy snow load",
    "Smoke damage from neighboring building fire",
    "Sewer backup — contamination of basement storage",
    "Tree fell on building during windstorm",
    "Sprinkler system malfunction — water damage",
    "Power surge damaged server room equipment",
    "Foundation settling — structural crack in exterior wall",
]

DESCRIPTIONS_BY_TYPE = {
    "GL": GL_DESCRIPTIONS,
    "WC": WC_DESCRIPTIONS,
    "AUTO": AUTO_DESCRIPTIONS,
    "PROP": PROP_DESCRIPTIONS,
}

CLAIMANT_FIRST_NAMES = [
    "James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael",
    "Linda", "David", "Elizabeth", "William", "Barbara", "Richard", "Susan",
    "Joseph", "Jessica", "Thomas", "Sarah", "Charles", "Karen", "Daniel",
    "Lisa", "Matthew", "Nancy", "Anthony", "Betty", "Mark", "Margaret",
    "Donald", "Sandra", "Steven", "Ashley", "Paul", "Dorothy", "Andrew",
    "Kimberly", "Joshua", "Emily", "Kenneth", "Donna", "Kevin", "Michelle",
    "Brian", "Carol", "George", "Amanda", "Timothy", "Melissa", "Ronald",
    "Deborah",
]

CLAIMANT_LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
    "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
    "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark",
    "Ramirez", "Lewis", "Robinson", "Walker", "Young", "Allen", "King",
    "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores", "Green",
    "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell",
    "Carter", "Roberts",
]

STATE_ABBREVS = {
    "FL": "Florida", "IN": "Indiana", "CA": "California", "NY": "New York",
    "ID": "Idaho", "WA": "Washington", "OK": "Oklahoma", "CO": "Colorado",
    "IL": "Illinois", "TX": "Texas", "PA": "Pennsylvania", "MN": "Minnesota",
    "GA": "Georgia", "OR": "Oregon", "NC": "North Carolina", "KS": "Kansas",
    "VA": "Virginia", "NV": "Nevada", "HI": "Hawaii",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fmt_dollars(amount: int) -> str:
    """Format integer cents as dollar string."""
    if amount == 0:
        return "$0.00"
    dollars = amount // 100
    cents = amount % 100
    return f"${dollars:,}.{cents:02d}"


def _gen_policy_number(policy_type: str, rng: random.Random) -> str:
    """Generate a realistic policy number."""
    prefixes = {
        "GL": ["GL", "CGL", "GLO"],
        "WC": ["WC", "WCP", "WCA"],
        "AUTO": ["CA", "BAP", "AUT"],
        "PROP": ["CP", "CPP", "BOP"],
    }
    prefix = rng.choice(prefixes[policy_type])
    num = rng.randint(100000, 9999999)
    return f"{prefix}-{num}"


def _gen_claim_number(carrier_abbrev: str, rng: random.Random) -> str:
    """Generate a realistic claim number."""
    year = rng.choice(["2023", "2024", "2025", "2026"])
    seq = rng.randint(10000, 99999)
    return f"{carrier_abbrev}-{year}-{seq}"


def _carrier_abbrev(carrier_name: str) -> str:
    """Get a short abbreviation for a carrier."""
    words = carrier_name.split()
    if len(words) >= 2:
        return (words[0][0] + words[1][0]).upper()
    return words[0][:3].upper()


def _random_date(rng: random.Random, start: date, end: date) -> date:
    """Pick a random date in [start, end]."""
    delta = (end - start).days
    return start + timedelta(days=rng.randint(0, max(delta, 0)))


def _gen_claimant_name(rng: random.Random) -> str:
    return f"{rng.choice(CLAIMANT_FIRST_NAMES)} {rng.choice(CLAIMANT_LAST_NAMES)}"


def _gen_claims(
    policy_type: str,
    num_claims: int,
    carrier_name: str,
    policy_period_start: date,
    policy_period_end: date,
    rng: random.Random,
) -> list[dict]:
    """Generate a list of claim records."""
    abbrev = _carrier_abbrev(carrier_name)
    descriptions = DESCRIPTIONS_BY_TYPE[policy_type]
    claims = []

    for _ in range(num_claims):
        loss_date = _random_date(rng, policy_period_start, policy_period_end)
        status = rng.choice(["Open", "Closed", "Closed", "Closed"])  # bias toward closed

        # Reserve and paid amounts
        severity = rng.random()
        if severity < 0.3:
            # Small claim
            reserve = rng.randint(50000, 2500000)  # $500 - $25,000
            if status == "Closed":
                paid = rng.randint(int(reserve * 0.2), reserve)
                reserve = 0
            else:
                paid = rng.randint(0, int(reserve * 0.5))
        elif severity < 0.7:
            # Medium claim
            reserve = rng.randint(2500000, 10000000)  # $25,000 - $100,000
            if status == "Closed":
                paid = rng.randint(int(reserve * 0.3), int(reserve * 1.2))
                reserve = 0
            else:
                paid = rng.randint(0, int(reserve * 0.4))
        elif severity < 0.9:
            # Large claim
            reserve = rng.randint(10000000, 50000000)  # $100,000 - $500,000
            if status == "Closed":
                paid = rng.randint(int(reserve * 0.5), int(reserve * 1.5))
                reserve = 0
            else:
                paid = rng.randint(0, int(reserve * 0.3))
        else:
            # Very large claim ($500K+)
            reserve = rng.randint(50000000, 200000000)  # $500,000 - $2,000,000
            if status == "Closed":
                paid = rng.randint(int(reserve * 0.4), reserve)
                reserve = 0
            else:
                paid = rng.randint(0, int(reserve * 0.2))

        claims.append({
            "claim_number": _gen_claim_number(abbrev, rng),
            "date_of_loss": loss_date.isoformat(),
            "claimant_name": _gen_claimant_name(rng),
            "description": rng.choice(descriptions),
            "status": status,
            "reserve": reserve,
            "paid": paid,
        })

    # Sort by date of loss
    claims.sort(key=lambda c: c["date_of_loss"])
    return claims


# ---------------------------------------------------------------------------
# Markdown renderers
# ---------------------------------------------------------------------------

def _render_standard(
    carrier: str,
    insured: tuple,
    policy_number: str,
    policy_type_long: str,
    policy_period_start: date,
    policy_period_end: date,
    report_date: date,
    claims: list[dict],
) -> str:
    """Standard loss run layout with header block and claims table."""
    name, addr, city, st = insured
    lines = [
        "# Loss Run Report",
        "",
        "---",
        "",
        f"**Carrier:** {carrier}",
        "",
        f"**Named Insured:** {name}",
        f"**Address:** {addr}, {city}, {st}",
        "",
        f"**Policy Number:** {policy_number}",
        f"**Policy Type:** {policy_type_long}",
        f"**Policy Period:** {policy_period_start.strftime('%m/%d/%Y')} to {policy_period_end.strftime('%m/%d/%Y')}",
        "",
        f"**Report Date:** {report_date.strftime('%m/%d/%Y')}",
        f"**Report Generated:** {report_date.strftime('%B %d, %Y')}",
        "",
        "---",
        "",
    ]

    if not claims:
        lines.append("## Claims History")
        lines.append("")
        lines.append("**No claims reported for this policy period.**")
        lines.append("")
    else:
        lines.append("## Claims History")
        lines.append("")
        lines.append("| Claim # | Date of Loss | Claimant | Description | Status | Reserve | Paid |")
        lines.append("|---|---|---|---|---|---|---|")
        for c in claims:
            lines.append(
                f"| {c['claim_number']} "
                f"| {date.fromisoformat(c['date_of_loss']).strftime('%m/%d/%Y')} "
                f"| {c['claimant_name']} "
                f"| {c['description']} "
                f"| {c['status']} "
                f"| {_fmt_dollars(c['reserve'])} "
                f"| {_fmt_dollars(c['paid'])} |"
            )
        lines.append("")

        # Totals
        total_reserve = sum(c["reserve"] for c in claims)
        total_paid = sum(c["paid"] for c in claims)
        lines.append(f"**Total Reserve:** {_fmt_dollars(total_reserve)}")
        lines.append(f"**Total Paid:** {_fmt_dollars(total_paid)}")
        lines.append(f"**Total Incurred:** {_fmt_dollars(total_reserve + total_paid)}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("*This report is provided for informational purposes only and does not constitute a guarantee of coverage.*")
    lines.append("")

    return "\n".join(lines)


def _render_compact(
    carrier: str,
    insured: tuple,
    policy_number: str,
    policy_type_long: str,
    policy_period_start: date,
    policy_period_end: date,
    report_date: date,
    claims: list[dict],
) -> str:
    """Compact loss run — KV header, minimal formatting."""
    name, addr, city, st = insured
    lines = [
        f"# {carrier}",
        "",
        "## Loss Run / Claims History Report",
        "",
        f"Insured: {name}",
        f"Location: {addr}, {city}, {st}",
        f"Policy: {policy_number} ({policy_type_long})",
        f"Period: {policy_period_start.strftime('%m/%d/%Y')} — {policy_period_end.strftime('%m/%d/%Y')}",
        f"As of: {report_date.strftime('%m/%d/%Y')}",
        "",
        "---",
        "",
    ]

    if not claims:
        lines.append("No losses reported.")
        lines.append("")
    else:
        lines.append("| Claim No. | Loss Date | Claimant Name | Description | Status | Reserve | Paid to Date |")
        lines.append("|---|---|---|---|---|---|---|")
        for c in claims:
            lines.append(
                f"| {c['claim_number']} "
                f"| {date.fromisoformat(c['date_of_loss']).strftime('%m/%d/%Y')} "
                f"| {c['claimant_name']} "
                f"| {c['description']} "
                f"| {c['status']} "
                f"| {_fmt_dollars(c['reserve'])} "
                f"| {_fmt_dollars(c['paid'])} |"
            )
        lines.append("")

        total_reserve = sum(c["reserve"] for c in claims)
        total_paid = sum(c["paid"] for c in claims)
        lines.append(f"Totals — Reserve: {_fmt_dollars(total_reserve)} | Paid: {_fmt_dollars(total_paid)} | Incurred: {_fmt_dollars(total_reserve + total_paid)}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("*End of loss run report.*")
    lines.append("")

    return "\n".join(lines)


def _render_detailed(
    carrier: str,
    insured: tuple,
    policy_number: str,
    policy_type_long: str,
    policy_period_start: date,
    policy_period_end: date,
    report_date: date,
    claims: list[dict],
) -> str:
    """Detailed layout — each claim as a sub-section instead of a table row."""
    name, addr, city, st = insured
    lines = [
        "# LOSS RUN REPORT",
        "",
        "## Policy Information",
        "",
        f"- **Insurance Carrier:** {carrier}",
        f"- **Named Insured:** {name}",
        f"- **Mailing Address:** {addr}, {city}, {st}",
        f"- **Policy Number:** {policy_number}",
        f"- **Coverage Type:** {policy_type_long}",
        f"- **Effective Date:** {policy_period_start.strftime('%m/%d/%Y')}",
        f"- **Expiration Date:** {policy_period_end.strftime('%m/%d/%Y')}",
        f"- **Report Run Date:** {report_date.strftime('%m/%d/%Y')}",
        "",
        "---",
        "",
    ]

    if not claims:
        lines.append("## Claims Summary")
        lines.append("")
        lines.append("No claims have been filed against this policy during the reporting period.")
        lines.append("")
    else:
        lines.append(f"## Claims Summary ({len(claims)} claim{'s' if len(claims) != 1 else ''})")
        lines.append("")

        # Summary table
        lines.append("| Claim # | Date of Loss | Claimant | Status | Reserve | Paid |")
        lines.append("|---|---|---|---|---|---|")
        for c in claims:
            lines.append(
                f"| {c['claim_number']} "
                f"| {date.fromisoformat(c['date_of_loss']).strftime('%m/%d/%Y')} "
                f"| {c['claimant_name']} "
                f"| {c['status']} "
                f"| {_fmt_dollars(c['reserve'])} "
                f"| {_fmt_dollars(c['paid'])} |"
            )
        lines.append("")

        # Detail per claim
        lines.append("## Claim Details")
        lines.append("")
        for i, c in enumerate(claims, 1):
            lines.append(f"### Claim {i}: {c['claim_number']}")
            lines.append("")
            lines.append(f"- **Date of Loss:** {date.fromisoformat(c['date_of_loss']).strftime('%B %d, %Y')}")
            lines.append(f"- **Claimant:** {c['claimant_name']}")
            lines.append(f"- **Description:** {c['description']}")
            lines.append(f"- **Status:** {c['status']}")
            lines.append(f"- **Outstanding Reserve:** {_fmt_dollars(c['reserve'])}")
            lines.append(f"- **Total Paid:** {_fmt_dollars(c['paid'])}")
            lines.append(f"- **Total Incurred:** {_fmt_dollars(c['reserve'] + c['paid'])}")
            lines.append("")

        total_reserve = sum(c["reserve"] for c in claims)
        total_paid = sum(c["paid"] for c in claims)
        lines.append("## Totals")
        lines.append("")
        lines.append(f"| | Amount |")
        lines.append(f"|---|---|")
        lines.append(f"| Total Outstanding Reserve | {_fmt_dollars(total_reserve)} |")
        lines.append(f"| Total Paid | {_fmt_dollars(total_paid)} |")
        lines.append(f"| Total Incurred | {_fmt_dollars(total_reserve + total_paid)} |")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("*This document is a summary of claims activity and may not reflect all pending adjustments. Contact your claims representative for the most current information.*")
    lines.append("")

    return "\n".join(lines)


def _render_multi_year(
    carrier: str,
    insured: tuple,
    policy_number: str,
    policy_type_long: str,
    policy_period_start: date,
    policy_period_end: date,
    report_date: date,
    claims: list[dict],
) -> str:
    """Multi-year style — groups claims by policy year."""
    name, addr, city, st = insured
    lines = [
        f"# {carrier}",
        "",
        "# Loss Run — Multi-Year Claims History",
        "",
        f"**Policyholder:** {name}",
        f"**Address:** {addr}, {city}, {st}",
        "",
        f"**Policy No:** {policy_number}",
        f"**Line of Business:** {policy_type_long}",
        f"**Reporting Period:** {policy_period_start.strftime('%m/%d/%Y')} to {policy_period_end.strftime('%m/%d/%Y')}",
        f"**Date Prepared:** {report_date.strftime('%m/%d/%Y')}",
        "",
        "---",
        "",
    ]

    if not claims:
        lines.append("**No claims activity during reporting period.**")
        lines.append("")
    else:
        # Group by year
        by_year: dict[int, list[dict]] = {}
        for c in claims:
            yr = date.fromisoformat(c["date_of_loss"]).year
            by_year.setdefault(yr, []).append(c)

        for yr in sorted(by_year.keys()):
            year_claims = by_year[yr]
            yr_reserve = sum(c["reserve"] for c in year_claims)
            yr_paid = sum(c["paid"] for c in year_claims)
            lines.append(f"## Policy Year {yr}")
            lines.append("")
            lines.append(f"Claims Count: {len(year_claims)} | Reserve: {_fmt_dollars(yr_reserve)} | Paid: {_fmt_dollars(yr_paid)}")
            lines.append("")
            lines.append("| Claim # | Date of Loss | Claimant | Description | Status | Reserve | Paid |")
            lines.append("|---|---|---|---|---|---|---|")
            for c in year_claims:
                lines.append(
                    f"| {c['claim_number']} "
                    f"| {date.fromisoformat(c['date_of_loss']).strftime('%m/%d/%Y')} "
                    f"| {c['claimant_name']} "
                    f"| {c['description']} "
                    f"| {c['status']} "
                    f"| {_fmt_dollars(c['reserve'])} "
                    f"| {_fmt_dollars(c['paid'])} |"
                )
            lines.append("")

        total_reserve = sum(c["reserve"] for c in claims)
        total_paid = sum(c["paid"] for c in claims)
        lines.append("## Grand Total")
        lines.append("")
        lines.append(f"- **Total Claims:** {len(claims)}")
        lines.append(f"- **Total Reserve:** {_fmt_dollars(total_reserve)}")
        lines.append(f"- **Total Paid:** {_fmt_dollars(total_paid)}")
        lines.append(f"- **Total Incurred:** {_fmt_dollars(total_reserve + total_paid)}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("*Prepared by the claims department. This report may not include claims reported after the preparation date.*")
    lines.append("")

    return "\n".join(lines)


RENDERERS = [
    _render_standard,
    _render_compact,
    _render_detailed,
    _render_multi_year,
]


# ---------------------------------------------------------------------------
# Expected / manifest builders
# ---------------------------------------------------------------------------

def _build_expected(
    insured: tuple,
    policy_number: str,
    state: str,
) -> dict:
    """Build expected JSON matching claim_form schema fields where applicable."""
    name, _addr, _city, st = insured
    return {
        "form_type": "Loss Run",
        "claimant_name": None,
        "employer_name": name,
        "policy_number": policy_number,
        "state": state,
    }


def _build_manifest(idx: int, policy_type: str, num_claims: int) -> dict:
    file_id = f"synth_loss_run_{idx + 1:03d}"
    return {
        "filename": f"{file_id}.md",
        "source_name": "Synthetic generator (synthetic_loss_runs.py)",
        "source_url": None,
        "license": "Apache-2.0",
        "license_url": "https://www.apache.org/licenses/LICENSE-2.0",
        "attribution": "FieldBench corpus contributors",
        "original_format": "markdown",
        "r2_url": None,
        "pages": 1,
        "added_date": "2026-04-16",
        "added_by": "accuracy-27",
        "schema": "insurance_claims/schemas/claim_form.yaml",
        "doc_type": "loss_run",
        "notes": f"Synthetic loss run report — {policy_type} policy, {num_claims} claims.",
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    rng = random.Random(SEED)

    for sub in ("documents", "expected", "manifests"):
        (CLAIMS_DIR / sub).mkdir(parents=True, exist_ok=True)

    generated = 0

    for idx in range(NUM_DOCS):
        file_id = f"synth_loss_run_{idx + 1:03d}"

        # Pick carrier, insured, policy type
        carrier = rng.choice(CARRIERS)
        insured = INSUREDS[idx % len(INSUREDS)]
        policy_type_code, policy_type_long = rng.choice(POLICY_TYPES)

        # Policy period
        period_start = _random_date(rng, date(2023, 1, 1), date(2025, 6, 1))
        period_end = period_start + timedelta(days=365)

        # Report date: sometime after period start
        report_date = _random_date(
            rng,
            period_start + timedelta(days=90),
            min(period_end + timedelta(days=180), date(2026, 4, 15)),
        )

        policy_number = _gen_policy_number(policy_type_code, rng)

        # Number of claims: mix of clean and heavy histories
        roll = rng.random()
        if roll < 0.12:
            # Clean history (no claims)
            num_claims = 0
        elif roll < 0.45:
            # Light history
            num_claims = rng.randint(2, 5)
        elif roll < 0.75:
            # Moderate
            num_claims = rng.randint(5, 10)
        elif roll < 0.9:
            # Heavy
            num_claims = rng.randint(10, 15)
        else:
            # Very heavy
            num_claims = rng.randint(15, 20)

        claims = _gen_claims(
            policy_type_code, num_claims, carrier,
            period_start, period_end, rng,
        )

        # Pick a renderer
        renderer = rng.choice(RENDERERS)
        md = renderer(
            carrier, insured, policy_number, policy_type_long,
            period_start, period_end, report_date, claims,
        )

        state = insured[3]  # state abbreviation
        expected = _build_expected(insured, policy_number, state)
        manifest = _build_manifest(idx, policy_type_code, num_claims)

        doc_path = CLAIMS_DIR / "documents" / f"{file_id}.md"
        exp_path = CLAIMS_DIR / "expected" / f"{file_id}.expected.json"
        man_path = CLAIMS_DIR / "manifests" / f"{file_id}.json"

        doc_path.write_text(md + "\n")
        exp_path.write_text(json.dumps(expected, indent=2) + "\n")
        man_path.write_text(json.dumps(manifest, indent=2) + "\n")

        print(
            f"[synth-loss-run] ({idx + 1}/{NUM_DOCS}) {file_id}  "
            f"[{policy_type_code}, {num_claims} claims, {renderer.__name__}]",
            file=sys.stderr,
        )
        generated += 1

    print(f"\n[synth-loss-run] Done. Generated {generated} synthetic loss run reports.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
