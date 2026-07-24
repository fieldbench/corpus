#!/usr/bin/env python3
"""Synthetic insurance document generator — binders, demand letters, claim forms.

Generates three document types for the FieldBench corpus:

  - Insurance Binders (30 docs) → insurance_policies/
  - Subrogation Demand Letters (30 docs) → insurance_claims/
  - Filled-In Claim Forms (50 docs: 30 WC FROI + 20 property proof of loss) → insurance_claims/

Uses a fixed random seed (20260416) for reproducibility.
No external dependencies — stdlib only.

Usage:
  python scripts/sources/synthetic_insurance_misc.py
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

CORPUS_ROOT = Path(__file__).resolve().parent.parent.parent
POLICIES_DIR = CORPUS_ROOT / "insurance_policies"
CLAIMS_DIR = CORPUS_ROOT / "insurance_claims"

SEED = 20260416

# ---------------------------------------------------------------------------
# Data pools
# ---------------------------------------------------------------------------

CARRIERS = [
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
    "Ironbridge Excess Carriers Ltd.",
]

INSURED_PERSONS = [
    "James R. Henderson", "Maria L. Vasquez", "Robert T. Nakamura",
    "Patricia A. O'Brien", "William K. Chen", "Linda M. Johansson",
    "Michael D. Baptiste", "Susan E. Kowalski", "David C. Ramirez",
    "Jennifer P. Thornton", "Thomas H. Fitzgerald", "Barbara J. Okafor",
    "Christopher S. Patel", "Margaret A. Lindstrom", "Daniel F. McAllister",
    "Elizabeth R. Dominguez", "Richard G. Tanaka", "Karen N. Blackwell",
    "Joseph W. Moreau", "Nancy B. Stephenson", "Charles E. Gutierrez",
    "Sandra L. Walsh", "Matthew T. Ivanov", "Dorothy H. Kessler",
    "Andrew J. Callahan", "Angela M. Petrovic", "Steven R. Yamamoto",
    "Cynthia D. Hartley", "Kevin P. Sinclair", "Donna J. Bergstrom",
    "Brian K. Fontaine", "Laura C. Novak", "Mark A. Castellano",
    "Michelle T. Pemberton", "Gregory S. Huang", "Deborah L. Saddler",
    "Timothy N. Reeves", "Pamela E. Ogilvie", "Jason R. Dietrich",
    "Sharon K. Melendez", "Jeffrey D. Cranston", "Kathleen M. Beaumont",
    "Gary W. Ishikawa", "Rebecca F. Salazar", "Ryan P. Gallagher",
    "Amy L. Thatcher", "Scott J. Murakami", "Christine A. Holloway",
    "Frank B. Estrada", "Heather N. Ridgeway",
]

EMPLOYERS = [
    "Atlas Framing & Construction LLC",
    "Meridian Mechanical Services Inc.",
    "Silverline Electrical Contractors",
    "Clearwater Environmental Solutions",
    "Granite Peak General Contractors",
    "Suncoast Roofing & Waterproofing",
    "Cascade Plumbing & HVAC Inc.",
    "Prairie Home Builders LLC",
    "Summit Landscaping & Excavation",
    "Iron Horse Steel Erectors Inc.",
    "Bayou City Demolition Services",
    "Cornerstone Civil Engineering PC",
    "Redline Fire Protection Corp.",
    "Valley Forge Painting Contractors",
    "Northern Star Telecom Services",
    "Coastal Crane & Rigging LLC",
    "Westridge Concrete Foundations",
    "Evergreen Site Development Corp.",
    "Continental Scaffolding Inc.",
    "Metro Distribution Centers Inc.",
    "Highland Lumber & Supply Co.",
    "Pacific Coast Cold Storage LLC",
    "Pinnacle Manufacturing Group",
    "Riverside Food Processing Inc.",
    "Tri-State Warehouse Solutions",
]

ADDRESSES = [
    ("221 Industrial Park Drive", "Lakeland", "FL", "33805"),
    ("4400 Commerce Drive", "Indianapolis", "IN", "46268"),
    ("1800 N. Highland Avenue", "Los Angeles", "CA", "90028"),
    ("600 N. Pine Island Road", "Fort Lauderdale", "FL", "33324"),
    ("7700 Mineral Drive, Suite 200", "Coeur d'Alene", "ID", "83815"),
    ("2901 Gandy Boulevard", "St. Petersburg", "FL", "33702"),
    ("15200 NE 8th Street, Suite 300", "Bellevue", "WA", "98007"),
    ("1100 N. Meridian Street", "Oklahoma City", "OK", "73107"),
    ("4500 W. Colfax Avenue", "Denver", "CO", "80204"),
    ("8200 Lehigh Avenue", "Morton Grove", "IL", "60053"),
    ("3200 Westheimer Road", "Houston", "TX", "77098"),
    ("90 State Street, Suite 700", "Albany", "NY", "12207"),
    ("1650 Borel Place, Suite 200", "San Mateo", "CA", "94402"),
    ("450 Lancaster Avenue", "Wayne", "PA", "19087"),
    ("2700 University Avenue", "Minneapolis", "MN", "55414"),
    ("5100 Port Road", "Savannah", "GA", "31415"),
    ("3300 S. Figueroa Street", "Los Angeles", "CA", "90007"),
    ("1400 NW Compton Drive", "Portland", "OR", "97209"),
    ("600 N. Michigan Avenue, Suite 800", "Chicago", "IL", "60611"),
    ("1025 Thomas Jefferson Street", "Washington", "DC", "20007"),
    ("400 Poydras Street, Suite 1100", "New Orleans", "LA", "70130"),
    ("9800 Hillwood Parkway", "Fort Worth", "TX", "76177"),
    ("330 Madison Avenue, 12th Floor", "New York", "NY", "10017"),
    ("2200 Market Street", "Philadelphia", "PA", "19103"),
    ("700 Central Expressway", "Santa Clara", "CA", "95050"),
]

RESPONSIBLE_PARTIES = [
    "John M. Castellano", "Apex Transport LLC", "Greenfield Properties Inc.",
    "Marcus T. Holloway", "Superior Plumbing & Heating Co.",
    "Northside Roofing Contractors", "Elena V. Marchetti",
    "Delta Mechanical Services Inc.", "Brightstar Property Management LLC",
    "Raymond K. Okonkwo", "Coastal Trucking Inc.", "Vanguard Maintenance Corp.",
    "Samantha L. Prescott", "Horizon Landscaping Services",
    "Riverside Construction Group", "Edward P. Flanagan",
    "Metro Delivery Services LLC", "Keystone Cleaning Co.",
    "Catherine B. Navarro", "Summit Contracting Inc.",
    "Alliance Building Services", "Douglas R. Wentworth",
    "Pacific Coast Moving & Storage", "Titan Equipment Rentals Inc.",
    "Franklin J. Ashworth", "Sterling Property Holdings LLC",
    "Westgate Electrical Contractors", "Pauline M. Chandra",
    "Ironclad Fencing & Decks LLC", "Consolidated Freight Lines Inc.",
]

STATES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
]

POLICY_TYPES = [
    "Commercial General Liability",
    "Businessowners",
    "Commercial Property",
    "Commercial Auto",
    "Umbrella/Excess",
]

BODY_PARTS = [
    "left knee", "right knee", "lower back", "upper back", "right hand",
    "left hand", "right shoulder", "left shoulder", "right ankle",
    "left ankle", "right wrist", "left wrist", "right elbow",
    "left elbow", "neck", "head", "left foot", "right foot",
    "right hip", "left hip", "right eye", "left eye", "abdomen",
    "chest", "multiple body parts",
]

WC_INJURY_DESCRIPTIONS = [
    "Employee slipped on wet floor in warehouse and fell, striking {part}.",
    "Worker was lifting heavy boxes when they felt a sharp pain in {part}.",
    "Employee tripped over unsecured electrical cord and injured {part}.",
    "Worker was struck by falling equipment, causing injury to {part}.",
    "Employee was operating forklift when sudden stop caused whiplash and injury to {part}.",
    "Worker caught {part} in conveyor belt mechanism.",
    "Employee fell from ladder approximately 8 feet, landing on {part}.",
    "Worker strained {part} while pulling heavy pallet across loading dock.",
    "Employee was hit by swinging door, impacting {part}.",
    "Worker slipped on ice in parking lot, injuring {part}.",
    "Employee repetitive motion injury to {part} from assembly line work.",
    "Worker was splashed with hot liquid, burning {part}.",
    "Employee cut {part} on exposed metal edge of equipment.",
    "Worker twisted {part} while stepping off truck bed.",
    "Employee was pinched between two heavy objects, crushing {part}.",
    "Worker fell through unsecured floor opening, injuring {part}.",
    "Employee was struck by coworker's tool, impacting {part}.",
    "Worker strained {part} while shoveling gravel.",
    "Employee hyperextended {part} while reaching for overhead item.",
    "Worker slipped on oily surface and landed hard on {part}.",
]

PROPERTY_LOSS_DESCRIPTIONS = [
    "Burst pipe in second-floor bathroom caused extensive water damage to ceilings, walls, and flooring on first floor.",
    "Kitchen fire originated at stove, spreading to cabinets and causing smoke damage throughout living areas.",
    "Severe hailstorm damaged roof shingles, gutters, and exterior siding; interior water intrusion in attic.",
    "Fallen tree limb during windstorm struck roof, penetrating into upstairs bedroom and causing structural damage.",
    "Basement flooding from sustained heavy rainfall; sump pump failure led to 18 inches of standing water.",
    "Electrical fire in garage destroyed stored property and caused structural damage to attached wall.",
    "Vandalism to commercial property: broken windows, graffiti, and damage to interior fixtures.",
    "Frozen pipes burst during winter cold snap, causing water damage to multiple rooms and flooring.",
    "Lightning strike caused power surge destroying HVAC system, appliances, and electronic equipment.",
    "Smoke and fire damage from neighboring unit spread through shared wall in multi-family dwelling.",
    "Wind-driven rain entered through damaged window seals, causing mold growth in walls and flooring.",
    "Vehicle crashed into storefront, causing structural damage to front wall and display area.",
    "Sprinkler system malfunction discharged water throughout office space, damaging equipment and furnishings.",
    "Theft and burglary: forced entry through rear door; electronics, tools, and inventory stolen.",
    "Roof collapse under weight of accumulated snow and ice; interior water damage to all rooms below.",
    "Grease fire in restaurant kitchen caused hood system damage and smoke damage to dining area.",
    "Sewer backup through basement floor drain damaged stored inventory and flooring materials.",
    "Tornado damage to detached garage and partial roof loss on main structure.",
    "Accidental discharge from water heater flooded utility room and adjacent hallway.",
    "Fire from faulty wiring in attic destroyed roof structure and caused smoke damage to entire residence.",
]

AUTO_ACCIDENT_DESCRIPTIONS = [
    "insured's vehicle was rear-ended at a red light by the responsible party's vehicle",
    "responsible party ran a stop sign and collided with the insured's vehicle in the intersection",
    "responsible party's vehicle crossed the center line and struck the insured's vehicle head-on",
    "responsible party lost control on wet pavement and sideswiped the insured's vehicle",
    "responsible party backed out of a parking space into the insured's parked vehicle",
    "responsible party failed to yield while merging and struck the insured's vehicle",
]

SUBROGATION_INCIDENT_TYPES = [
    "auto_accident",
    "property_damage_water",
    "property_damage_fire",
    "slip_and_fall",
    "property_damage_tree",
    "property_damage_construction",
]

SUBROGATION_NARRATIVES = {
    "auto_accident": [
        "On {date}, our insured, {claimant}, was involved in a motor vehicle accident at the intersection of {street1} and {street2} in {city}, {state}. {accident_desc}. As a result of this collision, our insured's {vehicle} sustained significant damage. {claimant} also incurred medical expenses for treatment of injuries sustained in the accident.\n\nOur investigation, including the police report (Report No. {report_no}), confirms that your insured / client, {responsible}, was solely at fault for this accident. The police report cites {responsible} for {violation}.\n\nWe have paid our insured under Policy No. {policy} in the total amount of ${amount}, itemized as follows:\n\n- Vehicle repair: ${repair}\n- Medical payments: ${medical}\n- Rental reimbursement: ${rental}\n\nTotal: ${amount}",
    ],
    "property_damage_water": [
        "On {date}, a water leak originating from property owned or managed by {responsible} at {address} caused extensive damage to our insured's property located at {insured_address} in {city}, {state}. The leak, which appears to have resulted from {cause}, went undetected for approximately {duration}, allowing water to infiltrate our insured's {area}.\n\nOur adjuster inspected the damage on {inspect_date} and documented the following:\n\n- Damaged drywall and paint in {rooms}\n- Water-damaged flooring requiring replacement\n- Damaged personal property and furnishings\n- Mold remediation required in affected areas\n\nWe have indemnified our insured, {claimant}, under Policy No. {policy} in the total amount of ${amount}.",
    ],
    "property_damage_fire": [
        "On {date}, a fire originating at {address}, owned or operated by {responsible}, spread to our insured's adjacent property at {insured_address} in {city}, {state}. The {city} Fire Department responded and confirmed the fire originated at your client's property. The fire department report (Incident No. {report_no}) indicates the cause was {cause}.\n\nOur insured, {claimant}, sustained the following damages as a result:\n\n- Structural damage to exterior wall and roof\n- Smoke damage throughout interior\n- Damaged personal property\n- Temporary housing costs during repairs\n\nWe have compensated our insured under Policy No. {policy} in the amount of ${amount}.",
    ],
    "slip_and_fall": [
        "On {date}, our insured, {claimant}, sustained injuries in a slip-and-fall incident at {address} in {city}, {state}, a property owned or managed by {responsible}. {claimant} slipped on {hazard} while {activity} and fell, sustaining injuries to {injury_area}.\n\nOur investigation confirms that {responsible} had a duty to maintain safe conditions on the premises and failed to {duty}. Witness statements corroborate that the hazardous condition existed for a significant period prior to the incident.\n\nWe have paid medical expenses on behalf of our insured under Policy No. {policy} in the amount of ${amount}, covering:\n\n- Emergency room visit and treatment\n- Follow-up physician visits\n- Physical therapy ({pt_sessions} sessions)\n- Prescription medications",
    ],
    "property_damage_tree": [
        "On {date}, a tree located on property owned by {responsible} at {address} fell onto our insured's property at {insured_address} in {city}, {state}. The tree, which our arborist confirms was dead or severely diseased prior to the incident, caused substantial damage to our insured's {damaged_area}.\n\nWe notified {responsible} of the hazardous condition of this tree on {notice_date} via certified letter, but no remedial action was taken. Our insured, {claimant}, has been indemnified under Policy No. {policy} in the amount of ${amount}.",
    ],
    "property_damage_construction": [
        "On {date}, construction work being performed by {responsible} at {address} in {city}, {state} caused damage to our insured's adjacent property at {insured_address}. The damage resulted from {cause} during the construction process.\n\nOur insured, {claimant}, reported {symptoms} beginning on {date}. Our adjuster inspected the property on {inspect_date} and documented:\n\n- {damage1}\n- {damage2}\n- {damage3}\n\nWe have indemnified our insured under Policy No. {policy} in the amount of ${amount}.",
    ],
}

STREETS = [
    "Oak Street", "Main Street", "Elm Avenue", "Park Boulevard",
    "Washington Road", "Jefferson Drive", "Lincoln Avenue", "Cedar Lane",
    "Maple Drive", "Pine Street", "River Road", "Lake Boulevard",
    "Highland Avenue", "Market Street", "Broadway", "First Avenue",
    "Second Street", "Third Avenue", "Church Street", "Mill Road",
]

VEHICLES = [
    "2022 Honda Accord", "2021 Toyota Camry", "2023 Ford F-150",
    "2020 Chevrolet Silverado", "2022 Subaru Outback", "2021 Hyundai Sonata",
    "2023 Nissan Altima", "2022 Jeep Grand Cherokee", "2021 BMW 3 Series",
    "2023 Tesla Model 3", "2020 Mazda CX-5", "2022 Kia Sorento",
]

VIOLATIONS = [
    "failure to obey a traffic signal",
    "following too closely",
    "improper lane change",
    "failure to yield right of way",
    "reckless driving",
    "distracted driving",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_policy_number(prefix: str, rng: random.Random) -> str:
    return f"{prefix}-{rng.randint(100000, 999999)}"


def _make_binder_number(rng: random.Random) -> str:
    return f"BND-{rng.randint(100000, 999999)}"


def _pick_date(rng: random.Random) -> tuple[str, str]:
    """Return (iso_date, display_date)."""
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
    return f"${val:,}"


def _fmt_amount_plain(val: int) -> str:
    return f"{val:,}"


def _pick_address(rng: random.Random) -> tuple:
    return rng.choice(ADDRESSES)


def _pick_state(rng: random.Random) -> str:
    return rng.choice(STATES)


# ---------------------------------------------------------------------------
# Part 1: Insurance Binders (30 docs)
# ---------------------------------------------------------------------------

def _gen_binder(idx: int, rng: random.Random) -> tuple[str, dict, dict]:
    """Generate a single insurance binder document."""
    carrier = rng.choice(CARRIERS)
    insured = rng.choice(INSURED_PERSONS)
    addr = _pick_address(rng)
    policy_type = rng.choice(POLICY_TYPES)
    eff_iso, exp_iso, eff_disp, exp_disp = _eff_exp_dates(rng)

    # Binder number vs policy number — some use binder numbers, some use policy
    use_binder_number = rng.random() < 0.6
    if use_binder_number:
        number = _make_binder_number(rng)
    else:
        prefix_map = {
            "Commercial General Liability": "CGL",
            "Businessowners": "BOP",
            "Commercial Property": "CPP",
            "Commercial Auto": "AUT",
            "Umbrella/Excess": "UMB",
        }
        number = _make_policy_number(prefix_map[policy_type], rng)

    # Limits
    each_occurrence = rng.choice([500000, 1000000, 2000000])
    gen_aggregate = rng.choice([1000000, 2000000, 4000000])

    # Premium — often TBD or deposit for binders
    premium_style = rng.choice(["tbd", "deposit", "full"])
    if premium_style == "tbd":
        premium_display = "TBD"
        premium_value = None
    elif premium_style == "deposit":
        premium_value = rng.choice([500, 1000, 1500, 2000, 2500, 5000])
        premium_display = f"{_fmt_amount(premium_value)} (deposit)"
    else:
        premium_value = rng.choice([2500, 3500, 4800, 6200, 7500, 8900, 12000, 15000])
        premium_display = _fmt_amount(premium_value)

    # Agent / broker info
    agent_name = rng.choice([
        "Harborline Insurance Services, Inc.",
        "Summit Risk Advisors LLC",
        "Pacific Brokerage Group",
        "Heartland Insurance Associates",
        "Granite State Agency Inc.",
        "Bayshore Risk Management",
    ])
    agent_phone = f"({rng.randint(200,999)}) {rng.randint(100,999)}-{rng.randint(1000,9999)}"

    # Format variation: letter style vs form style
    format_style = rng.choice(["letter", "letter", "form", "form", "form"])

    if format_style == "letter":
        md = _render_binder_letter(
            carrier, insured, addr, policy_type, number,
            eff_disp, exp_disp, each_occurrence, gen_aggregate,
            premium_display, agent_name, agent_phone, rng,
        )
    else:
        md = _render_binder_form(
            carrier, insured, addr, policy_type, number,
            eff_disp, exp_disp, each_occurrence, gen_aggregate,
            premium_display, agent_name, agent_phone, rng,
        )

    expected = {
        "insurer_name": carrier,
        "named_insured": insured,
        "policy_number": number,
        "policy_type": policy_type,
        "effective_date": eff_iso,
        "expiration_date": exp_iso,
        "each_occurrence_limit": each_occurrence,
        "general_aggregate_limit": gen_aggregate,
        "total_premium": premium_value,
    }

    file_id = f"synth_binder_{idx + 1:03d}"
    manifest = {
        "filename": f"{file_id}.md",
        "source_name": "Synthetic generator (synthetic_insurance_misc.py)",
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
        "doc_type": "binder",
        "notes": f"Synthetic insurance binder — {policy_type.lower()}, {'letter' if format_style == 'letter' else 'form'} format.",
    }

    return md, expected, manifest


def _render_binder_letter(
    carrier: str, insured: str, addr: tuple, policy_type: str,
    number: str, eff_disp: str, exp_disp: str,
    each_occ: int, gen_agg: int, premium_disp: str,
    agent_name: str, agent_phone: str, rng: random.Random,
) -> str:
    street, city, state, zipcode = addr
    date_iso, date_disp = _pick_date(rng)

    lines = [
        f"# INSURANCE BINDER",
        "",
        f"**{carrier}**",
        "",
        f"Date: {date_disp}",
        "",
        "---",
        "",
        f"To: {insured}",
        f"    {street}",
        f"    {city}, {state} {zipcode}",
        "",
        f"Re: Binder of Insurance — {policy_type}",
        f"Binder/Policy No.: {number}",
        "",
        "---",
        "",
        f"Dear {insured.split(',')[0].split(' ')[-1]}:",
        "",
        f"This letter confirms that {carrier} has bound the following coverage "
        f"effective {eff_disp} through {exp_disp}, subject to the terms, conditions, "
        f"and exclusions of the policy to be issued.",
        "",
        f"**Type of Insurance:** {policy_type}",
        "",
        f"**Named Insured:** {insured}",
        "",
        f"**Policy/Binder Number:** {number}",
        "",
        f"**Policy Period:** {eff_disp} to {exp_disp}",
        "",
        "**Limits of Liability:**",
        "",
        f"- Each Occurrence: {_fmt_amount(each_occ)}",
        f"- General Aggregate: {_fmt_amount(gen_agg)}",
        "",
        f"**Premium:** {premium_disp}",
        "",
        "This binder is issued as temporary evidence of insurance and will be replaced "
        "by the policy when issued. This binder may be cancelled by either party upon "
        "ten (10) days written notice to the other.",
        "",
        "**Conditions:**",
        "",
        "1. Coverage is subject to the insured completing and returning the application.",
        "2. Final premium will be determined upon policy issuance.",
        "3. This binder does not waive any of the terms or conditions of the policy.",
        "",
        "---",
        "",
        f"Binding Authority: {agent_name}",
        f"Phone: {agent_phone}",
        "",
        f"Authorized Signature: _________________________",
    ]
    return "\n".join(lines)


def _render_binder_form(
    carrier: str, insured: str, addr: tuple, policy_type: str,
    number: str, eff_disp: str, exp_disp: str,
    each_occ: int, gen_agg: int, premium_disp: str,
    agent_name: str, agent_phone: str, rng: random.Random,
) -> str:
    street, city, state, zipcode = addr
    date_iso, date_disp = _pick_date(rng)

    # Vary the header
    header = rng.choice(["BINDER OF INSURANCE", "INSURANCE BINDER", "TEMPORARY BINDER"])

    lines = [
        f"# {header}",
        "",
        f"**Issuing Company:** {carrier}",
        "",
        f"**Date Issued:** {date_disp}",
        "",
        "---",
        "",
        "## Insured Information",
        "",
        f"| Field | Value |",
        f"|---|---|",
        f"| Named Insured | {insured} |",
        f"| Address | {street}, {city}, {state} {zipcode} |",
        f"| Binder/Policy No. | {number} |",
        "",
        "## Coverage Information",
        "",
        f"| Field | Value |",
        f"|---|---|",
        f"| Type of Insurance | {policy_type} |",
        f"| Effective Date | {eff_disp} |",
        f"| Expiration Date | {exp_disp} |",
        "",
        "## Limits of Liability",
        "",
        f"| Coverage | Limit |",
        f"|---|---|",
        f"| Each Occurrence | {_fmt_amount(each_occ)} |",
        f"| General Aggregate | {_fmt_amount(gen_agg)} |",
        "",
        f"**Premium:** {premium_disp}",
        "",
        "---",
        "",
        "## Conditions",
        "",
        "This binder provides temporary evidence of coverage and is subject to "
        "the terms and conditions of the policy to be issued. Coverage is bound "
        f"effective {eff_disp} at 12:01 AM standard time at the insured's address.",
        "",
        "This binder may be cancelled by the company upon ten (10) days written "
        "notice mailed to the named insured.",
        "",
        "---",
        "",
        f"**Issuing Agent:** {agent_name}",
        f"**Phone:** {agent_phone}",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Part 2: Subrogation Demand Letters (30 docs)
# ---------------------------------------------------------------------------

def _gen_demand_letter(idx: int, rng: random.Random) -> tuple[str, dict, dict]:
    """Generate a single subrogation demand letter."""
    carrier = rng.choice(CARRIERS)
    claimant = rng.choice(INSURED_PERSONS)
    responsible = rng.choice(RESPONSIBLE_PARTIES)
    addr = _pick_address(rng)
    state = addr[2]
    city = addr[1]

    loss_iso, loss_disp = _pick_date(rng)
    policy_number = _make_policy_number(rng.choice(["CGL", "HO", "AUT", "CPP"]), rng)

    incident_type = rng.choice(SUBROGATION_INCIDENT_TYPES)
    amount = rng.choice([
        3200, 4500, 6800, 8500, 9750, 11200, 14500, 17800,
        22500, 28000, 35000, 42000, 55000, 68000, 85000, 125000,
    ])

    # Build the narrative
    narrative = _build_subrogation_narrative(
        incident_type, loss_disp, claimant, responsible,
        city, state, policy_number, amount, addr, rng,
    )

    # Build the letter
    letter_date_iso, letter_date_disp = _pick_date(rng)
    # Make letter date after loss date
    resp_addr = _pick_address(rng)

    description = _summarize_incident(incident_type, claimant, responsible, city, state, rng)

    md = _render_demand_letter(
        carrier, claimant, responsible, resp_addr, letter_date_disp,
        loss_disp, policy_number, amount, narrative, rng,
    )

    expected = {
        "form_type": "Demand Letter",
        "claimant_name": claimant,
        "employer_name": None,
        "date_of_loss": loss_iso,
        "description_of_loss": description,
        "amount_claimed": amount,
        "policy_number": policy_number,
        "body_part": None,
        "state": state,
    }

    file_id = f"synth_demand_{idx + 1:03d}"
    manifest = {
        "filename": f"{file_id}.md",
        "source_name": "Synthetic generator (synthetic_insurance_misc.py)",
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
        "doc_type": "demand_letter",
        "notes": f"Synthetic subrogation demand letter — {incident_type.replace('_', ' ')}.",
    }

    return md, expected, manifest


def _summarize_incident(
    incident_type: str, claimant: str, responsible: str,
    city: str, state: str, rng: random.Random,
) -> str:
    """Generate a short description_of_loss for the expected output."""
    summaries = {
        "auto_accident": f"Motor vehicle accident in {city}, {state}; insured's vehicle struck by {responsible}.",
        "property_damage_water": f"Water damage to insured's property caused by leak from {responsible}'s property in {city}, {state}.",
        "property_damage_fire": f"Fire damage from adjacent property owned by {responsible} in {city}, {state}.",
        "slip_and_fall": f"Slip-and-fall injury at premises owned/managed by {responsible} in {city}, {state}.",
        "property_damage_tree": f"Fallen tree from {responsible}'s property damaged insured's property in {city}, {state}.",
        "property_damage_construction": f"Construction damage from work by {responsible} at adjacent property in {city}, {state}.",
    }
    return summaries.get(incident_type, f"Loss at {city}, {state} involving {responsible}.")


def _build_subrogation_narrative(
    incident_type: str, loss_disp: str, claimant: str, responsible: str,
    city: str, state: str, policy_number: str, amount: int,
    addr: tuple, rng: random.Random,
) -> str:
    """Build the full narrative body for the demand letter."""
    street1 = rng.choice(STREETS)
    street2 = rng.choice(STREETS)
    insured_addr = f"{addr[0]}, {addr[1]}, {addr[2]} {addr[3]}"
    resp_addr_t = _pick_address(rng)
    resp_address = f"{resp_addr_t[0]}, {resp_addr_t[1]}, {resp_addr_t[2]} {resp_addr_t[3]}"

    if incident_type == "auto_accident":
        accident_desc = rng.choice(AUTO_ACCIDENT_DESCRIPTIONS)
        vehicle = rng.choice(VEHICLES)
        repair = int(amount * rng.uniform(0.5, 0.7))
        medical = int(amount * rng.uniform(0.15, 0.3))
        rental = amount - repair - medical
        report_no = f"{rng.randint(2025, 2026)}-{rng.randint(100000, 999999)}"
        violation = rng.choice(VIOLATIONS)

        return (
            f"On {loss_disp}, our insured, {claimant}, was involved in a motor vehicle "
            f"accident at the intersection of {street1} and {street2} in {city}, {state}. "
            f"The {accident_desc}. As a result of this collision, our insured's {vehicle} "
            f"sustained significant damage.\n\n"
            f"Our investigation, including the police report (Report No. {report_no}), "
            f"confirms that {responsible} was solely at fault for this accident. The police "
            f"report cites {responsible} for {violation}.\n\n"
            f"We have paid our insured under Policy No. {policy_number} in the total amount "
            f"of {_fmt_amount(amount)}, itemized as follows:\n\n"
            f"- Vehicle repair: {_fmt_amount(repair)}\n"
            f"- Medical payments: {_fmt_amount(medical)}\n"
            f"- Rental reimbursement: {_fmt_amount(rental)}\n\n"
            f"Total: {_fmt_amount(amount)}"
        )

    elif incident_type == "property_damage_water":
        cause = rng.choice([
            "a burst pipe", "a faulty washing machine hose",
            "a leaking water heater", "a broken supply line",
            "improper plumbing repairs",
        ])
        duration = rng.choice(["several hours", "approximately 24 hours", "two days", "over a weekend"])
        area = rng.choice(["living room and kitchen", "bedroom and hallway", "office space", "basement and first floor"])
        rooms = rng.choice(["living room, kitchen, and hallway", "two bedrooms and bathroom", "main office and reception area"])
        inspect_date = f"{rng.randint(1,12):02d}/{rng.randint(1,28):02d}/{rng.choice([2025,2026])}"

        return (
            f"On {loss_disp}, a water leak originating from property owned or managed by "
            f"{responsible} at {resp_address} caused extensive damage to our insured's property "
            f"located at {insured_addr}. The leak, which appears to have resulted from {cause}, "
            f"went undetected for approximately {duration}, allowing water to infiltrate our "
            f"insured's {area}.\n\n"
            f"Our adjuster inspected the damage on {inspect_date} and documented the following:\n\n"
            f"- Damaged drywall and paint in {rooms}\n"
            f"- Water-damaged flooring requiring replacement\n"
            f"- Damaged personal property and furnishings\n"
            f"- Mold remediation required in affected areas\n\n"
            f"We have indemnified our insured, {claimant}, under Policy No. {policy_number} "
            f"in the total amount of {_fmt_amount(amount)}."
        )

    elif incident_type == "property_damage_fire":
        cause = rng.choice([
            "improperly discarded smoking materials",
            "a faulty electrical system",
            "an unattended cooking fire",
            "improper storage of flammable materials",
        ])
        report_no = f"FD-{rng.randint(2025, 2026)}-{rng.randint(10000, 99999)}"

        return (
            f"On {loss_disp}, a fire originating at {resp_address}, owned or operated by "
            f"{responsible}, spread to our insured's adjacent property at {insured_addr}. "
            f"The {city} Fire Department responded and confirmed the fire originated at your "
            f"client's property. The fire department report (Incident No. {report_no}) "
            f"indicates the cause was {cause}.\n\n"
            f"Our insured, {claimant}, sustained the following damages as a result:\n\n"
            f"- Structural damage to exterior wall and roof\n"
            f"- Smoke damage throughout interior\n"
            f"- Damaged personal property\n"
            f"- Temporary housing costs during repairs\n\n"
            f"We have compensated our insured under Policy No. {policy_number} in the "
            f"amount of {_fmt_amount(amount)}."
        )

    elif incident_type == "slip_and_fall":
        hazard = rng.choice([
            "an unmarked wet floor", "accumulated ice and snow",
            "a broken handrail", "an uneven walkway surface",
            "debris in the parking lot",
        ])
        activity = rng.choice([
            "entering the building", "walking through the parking lot",
            "descending the stairs", "crossing the lobby",
        ])
        injury_area = rng.choice(["the left knee and hip", "the right wrist and shoulder", "the lower back", "the right ankle"])
        duty = rng.choice([
            "address the known hazard in a timely manner",
            "provide adequate warning of the dangerous condition",
            "maintain the premises in a reasonably safe condition",
        ])
        pt_sessions = rng.randint(8, 24)

        return (
            f"On {loss_disp}, our insured, {claimant}, sustained injuries in a slip-and-fall "
            f"incident at {resp_address}, a property owned or managed by {responsible}. "
            f"{claimant} slipped on {hazard} while {activity} and fell, sustaining injuries "
            f"to {injury_area}.\n\n"
            f"Our investigation confirms that {responsible} had a duty to maintain safe "
            f"conditions on the premises and failed to {duty}. Witness statements corroborate "
            f"that the hazardous condition existed for a significant period prior to the incident.\n\n"
            f"We have paid medical expenses on behalf of our insured under Policy No. "
            f"{policy_number} in the amount of {_fmt_amount(amount)}, covering:\n\n"
            f"- Emergency room visit and treatment\n"
            f"- Follow-up physician visits\n"
            f"- Physical therapy ({pt_sessions} sessions)\n"
            f"- Prescription medications"
        )

    elif incident_type == "property_damage_tree":
        damaged_area = rng.choice(["roof and upper bedroom", "garage and driveway", "fence and landscaping", "patio and rear exterior wall"])
        notice_date = f"{rng.randint(1,12):02d}/{rng.randint(1,28):02d}/{rng.choice([2024,2025])}"

        return (
            f"On {loss_disp}, a tree located on property owned by {responsible} at "
            f"{resp_address} fell onto our insured's property at {insured_addr}. The tree, "
            f"which our arborist confirms was dead or severely diseased prior to the incident, "
            f"caused substantial damage to our insured's {damaged_area}.\n\n"
            f"We notified {responsible} of the hazardous condition of this tree on {notice_date} "
            f"via certified letter, but no remedial action was taken. Our insured, {claimant}, "
            f"has been indemnified under Policy No. {policy_number} in the amount of "
            f"{_fmt_amount(amount)}."
        )

    else:  # property_damage_construction
        cause = rng.choice([
            "excessive vibration from pile driving",
            "improper excavation near the property line",
            "failure to secure construction debris",
            "negligent operation of heavy equipment",
        ])
        symptoms = rng.choice([
            "cracking in foundation walls and ceilings",
            "water intrusion through damaged exterior",
            "structural settling and door misalignment",
        ])
        inspect_date = f"{rng.randint(1,12):02d}/{rng.randint(1,28):02d}/{rng.choice([2025,2026])}"
        damages = rng.sample([
            "Foundation cracks requiring structural repair",
            "Damaged drywall and plaster throughout first floor",
            "Broken windows from vibration impact",
            "Displaced roof tiles and flashing",
            "Cracked exterior brick veneer",
            "Damaged plumbing connections",
            "Misaligned doors and window frames",
        ], 3)

        return (
            f"On {loss_disp}, construction work being performed by {responsible} at "
            f"{resp_address} caused damage to our insured's adjacent property at "
            f"{insured_addr}. The damage resulted from {cause} during the construction process.\n\n"
            f"Our insured, {claimant}, reported {symptoms} beginning shortly after "
            f"construction commenced. Our adjuster inspected the property on {inspect_date} "
            f"and documented:\n\n"
            f"- {damages[0]}\n"
            f"- {damages[1]}\n"
            f"- {damages[2]}\n\n"
            f"We have indemnified our insured under Policy No. {policy_number} in the "
            f"amount of {_fmt_amount(amount)}."
        )


def _render_demand_letter(
    carrier: str, claimant: str, responsible: str, resp_addr: tuple,
    letter_date_disp: str, loss_disp: str, policy_number: str,
    amount: int, narrative: str, rng: random.Random,
) -> str:
    resp_street, resp_city, resp_state, resp_zip = resp_addr
    deadline_days = rng.choice([30, 30, 30, 45])
    claim_ref = f"SUB-{rng.randint(100000, 999999)}"

    lines = [
        f"# {carrier}",
        "",
        f"**Subrogation Recovery Department**",
        "",
        f"Date: {letter_date_disp}",
        "",
        "---",
        "",
        f"**VIA CERTIFIED MAIL**",
        "",
        f"{responsible}",
        f"{resp_street}",
        f"{resp_city}, {resp_state} {resp_zip}",
        "",
        f"**RE: Subrogation Demand**",
        f"**Our Insured:** {claimant}",
        f"**Claim Reference:** {claim_ref}",
        f"**Policy No.:** {policy_number}",
        f"**Date of Loss:** {loss_disp}",
        f"**Amount Demanded:** {_fmt_amount(amount)}",
        "",
        "---",
        "",
        f"Dear {responsible.split(',')[0].split(' ')[-1] if ' ' in responsible else responsible}:",
        "",
        "We represent the above-referenced insured with respect to damages sustained "
        f"on {loss_disp}. We are writing to advise you of our subrogation claim and "
        "to demand reimbursement for payments made under our policy.",
        "",
        narrative,
        "",
        "---",
        "",
        "## Demand",
        "",
        f"Accordingly, we hereby demand payment of **{_fmt_amount(amount)}** within "
        f"**{deadline_days} days** of the date of this letter. Please make your check "
        f"payable to {carrier} and reference Claim No. {claim_ref}.",
        "",
        "If we do not receive payment within the stated time frame, we will pursue "
        "all available legal remedies to recover these funds, including the filing "
        "of a civil action, in which case we will also seek recovery of court costs, "
        "interest, and attorneys' fees as permitted by law.",
        "",
        "Please direct all correspondence regarding this matter to our Subrogation "
        "Recovery Department at the address above.",
        "",
        "Sincerely,",
        "",
        f"**{carrier}**",
        f"Subrogation Recovery Department",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Part 3: Filled-In Claim Forms (50 docs: 30 WC FROI + 20 property PoL)
# ---------------------------------------------------------------------------

def _gen_wc_froi(idx: int, rng: random.Random) -> tuple[str, dict, dict]:
    """Generate a filled-in Workers Compensation First Report of Injury form."""
    claimant = rng.choice(INSURED_PERSONS)
    employer = rng.choice(EMPLOYERS)
    addr = _pick_address(rng)
    state = addr[2]
    body_part = rng.choice(BODY_PARTS)

    loss_iso, loss_disp = _pick_date(rng)
    policy_number = _make_policy_number("WC", rng)

    desc_template = rng.choice(WC_INJURY_DESCRIPTIONS)
    description = desc_template.format(part=body_part)

    carrier = rng.choice(CARRIERS)
    report_date_iso, report_date_disp = _pick_date(rng)

    # Employee info
    ssn_last4 = f"XXX-XX-{rng.randint(1000, 9999)}"
    dob_month = rng.randint(1, 12)
    dob_day = rng.randint(1, 28)
    dob_year = rng.randint(1965, 2000)
    dob = f"{dob_month:02d}/{dob_day:02d}/{dob_year}"
    hire_year = rng.randint(2010, 2025)
    hire_date = f"{rng.randint(1,12):02d}/{rng.randint(1,28):02d}/{hire_year}"
    occupation = rng.choice([
        "Warehouse Associate", "Construction Laborer", "Machine Operator",
        "Electrician", "Plumber", "Carpenter", "Forklift Operator",
        "Maintenance Technician", "Assembly Line Worker", "Truck Driver",
        "Welding Technician", "HVAC Installer", "Painter", "Roofer",
        "Delivery Driver",
    ])
    wage = rng.choice([15, 18, 20, 22, 25, 28, 30, 32, 35, 40, 45])
    time_of_injury = f"{rng.randint(6, 17):02d}:{rng.choice(['00', '15', '30', '45'])}"

    md = _render_wc_froi(
        claimant, employer, addr, state, body_part, loss_disp,
        policy_number, description, carrier, report_date_disp,
        ssn_last4, dob, hire_date, occupation, wage, time_of_injury, rng,
    )

    expected = {
        "form_type": "First Report of Injury",
        "claimant_name": claimant,
        "employer_name": employer,
        "date_of_loss": loss_iso,
        "description_of_loss": description,
        "body_part": body_part,
        "amount_claimed": None,
        "policy_number": policy_number,
        "state": state,
    }

    file_id = f"synth_claim_{idx + 1:03d}"
    manifest = {
        "filename": f"{file_id}.md",
        "source_name": "Synthetic generator (synthetic_insurance_misc.py)",
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
        "doc_type": "wc_froi",
        "notes": "Synthetic filled-in Workers Compensation First Report of Injury form.",
    }

    return md, expected, manifest


def _render_wc_froi(
    claimant: str, employer: str, addr: tuple, state: str,
    body_part: str, loss_disp: str, policy_number: str,
    description: str, carrier: str, report_date_disp: str,
    ssn_last4: str, dob: str, hire_date: str, occupation: str,
    wage: int, time_of_injury: str, rng: random.Random,
) -> str:
    street, city, st, zipcode = addr
    supervisor = rng.choice(INSURED_PERSONS)
    emp_phone = f"({rng.randint(200,999)}) {rng.randint(100,999)}-{rng.randint(1000,9999)}"
    fein = f"{rng.randint(10,99)}-{rng.randint(1000000,9999999)}"

    # Vary form header style
    header = rng.choice([
        "FIRST REPORT OF INJURY",
        "EMPLOYER'S FIRST REPORT OF INJURY OR ILLNESS",
        "WORKERS' COMPENSATION — FIRST REPORT OF INJURY",
    ])

    lines = [
        f"# {header}",
        "",
        f"**State:** {state}",
        f"**Report Date:** {report_date_disp}",
        "",
        "---",
        "",
        "## Carrier / Insurer Information",
        "",
        f"| Field | Value |",
        f"|---|---|",
        f"| Insurance Carrier | {carrier} |",
        f"| Policy Number | {policy_number} |",
        "",
        "## Employer Information",
        "",
        f"| Field | Value |",
        f"|---|---|",
        f"| Employer Name | {employer} |",
        f"| FEIN | {fein} |",
        f"| Address | {street} |",
        f"| City, State, ZIP | {city}, {st} {zipcode} |",
        f"| Phone | {emp_phone} |",
        "",
        "## Employee / Injured Worker Information",
        "",
        f"| Field | Value |",
        f"|---|---|",
        f"| Employee Name | {claimant} |",
        f"| SSN | {ssn_last4} |",
        f"| Date of Birth | {dob} |",
        f"| Date of Hire | {hire_date} |",
        f"| Occupation / Job Title | {occupation} |",
        f"| Average Weekly Wage | ${wage:.2f}/hr |",
        "",
        "## Injury / Illness Information",
        "",
        f"| Field | Value |",
        f"|---|---|",
        f"| Date of Injury | {loss_disp} |",
        f"| Time of Injury | {time_of_injury} |",
        f"| Body Part Affected | {body_part} |",
        f"| Nature of Injury | {_classify_injury(body_part, rng)} |",
        f"| Cause of Injury | {_classify_cause(description, rng)} |",
        "",
        "## Description of Accident",
        "",
        description,
        "",
        "---",
        "",
        f"**Supervisor:** {supervisor}",
        f"**Date Report Prepared:** {report_date_disp}",
        f"**Preparer Signature:** _________________________",
    ]
    return "\n".join(lines)


def _classify_injury(body_part: str, rng: random.Random) -> str:
    if "back" in body_part:
        return rng.choice(["Strain", "Sprain", "Herniated Disc"])
    if "knee" in body_part or "ankle" in body_part or "hip" in body_part:
        return rng.choice(["Strain", "Sprain", "Contusion", "Fracture"])
    if "hand" in body_part or "wrist" in body_part or "finger" in body_part:
        return rng.choice(["Laceration", "Fracture", "Crush Injury", "Sprain"])
    if "shoulder" in body_part or "elbow" in body_part:
        return rng.choice(["Strain", "Dislocation", "Contusion"])
    if "eye" in body_part:
        return rng.choice(["Foreign Body", "Chemical Burn", "Contusion"])
    if "head" in body_part:
        return rng.choice(["Concussion", "Laceration", "Contusion"])
    return rng.choice(["Strain", "Contusion", "Multiple Injuries"])


def _classify_cause(description: str, rng: random.Random) -> str:
    desc_lower = description.lower()
    if "slip" in desc_lower or "fell" in desc_lower or "fall" in desc_lower:
        return "Fall/Slip"
    if "struck" in desc_lower or "hit" in desc_lower:
        return "Struck by Object"
    if "lift" in desc_lower or "pull" in desc_lower or "strain" in desc_lower:
        return "Overexertion"
    if "caught" in desc_lower or "pinch" in desc_lower or "crush" in desc_lower:
        return "Caught in/between"
    if "cut" in desc_lower:
        return "Cut/Laceration"
    if "burn" in desc_lower or "splash" in desc_lower:
        return "Burn/Scald"
    if "repetitive" in desc_lower:
        return "Repetitive Motion"
    return "Other"


def _gen_property_pol(idx: int, rng: random.Random) -> tuple[str, dict, dict]:
    """Generate a filled-in property Proof of Loss form."""
    claimant = rng.choice(INSURED_PERSONS)
    addr = _pick_address(rng)
    state = addr[2]

    loss_iso, loss_disp = _pick_date(rng)
    policy_number = _make_policy_number(rng.choice(["HO", "CPP", "FLD"]), rng)
    carrier = rng.choice(CARRIERS)

    description = rng.choice(PROPERTY_LOSS_DESCRIPTIONS)

    # Dollar amounts
    building_damage = rng.choice([0, 5000, 8000, 12000, 18000, 25000, 35000, 50000, 75000])
    contents_damage = rng.choice([0, 2000, 4500, 6000, 8500, 12000, 15000, 22000])
    other_damage = rng.choice([0, 0, 0, 1500, 3000, 5000, 8000])
    amount_claimed = building_damage + contents_damage + other_damage
    # Ensure non-zero
    if amount_claimed == 0:
        building_damage = 12000
        contents_damage = 4500
        amount_claimed = 16500

    report_date_iso, report_date_disp = _pick_date(rng)

    md = _render_property_pol(
        claimant, addr, state, loss_disp, policy_number, carrier,
        description, building_damage, contents_damage, other_damage,
        amount_claimed, report_date_disp, rng,
    )

    expected = {
        "form_type": "Proof of Loss",
        "claimant_name": claimant,
        "employer_name": None,
        "date_of_loss": loss_iso,
        "description_of_loss": description,
        "body_part": None,
        "amount_claimed": amount_claimed,
        "policy_number": policy_number,
        "state": state,
    }

    file_id = f"synth_claim_{idx + 1:03d}"
    manifest = {
        "filename": f"{file_id}.md",
        "source_name": "Synthetic generator (synthetic_insurance_misc.py)",
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
        "doc_type": "property_proof_of_loss",
        "notes": "Synthetic filled-in property Proof of Loss form.",
    }

    return md, expected, manifest


def _render_property_pol(
    claimant: str, addr: tuple, state: str, loss_disp: str,
    policy_number: str, carrier: str, description: str,
    building_damage: int, contents_damage: int, other_damage: int,
    amount_claimed: int, report_date_disp: str, rng: random.Random,
) -> str:
    street, city, st, zipcode = addr
    claim_number = f"CLM-{rng.randint(100000, 999999)}"
    occupancy = rng.choice([
        "Single Family Dwelling", "Commercial Office Space",
        "Multi-Family Dwelling", "Retail Storefront",
        "Warehouse / Industrial", "Mixed Use",
    ])
    mortgage_holder = rng.choice([
        "First National Bank", "Wells Fargo Home Mortgage",
        "Chase Home Finance", "Bank of America, N.A.",
        None, None, None,
    ])

    lines = [
        f"# PROOF OF LOSS",
        "",
        f"**Insurance Company:** {carrier}",
        "",
        "---",
        "",
        "## Policy and Claim Information",
        "",
        f"| Field | Value |",
        f"|---|---|",
        f"| Policy Number | {policy_number} |",
        f"| Claim Number | {claim_number} |",
        f"| Date of Loss | {loss_disp} |",
        f"| Date Reported | {report_date_disp} |",
        "",
        "## Insured Information",
        "",
        f"| Field | Value |",
        f"|---|---|",
        f"| Insured Name | {claimant} |",
        f"| Property Address | {street} |",
        f"| City, State, ZIP | {city}, {st} {zipcode} |",
        f"| Occupancy Type | {occupancy} |",
    ]
    if mortgage_holder:
        lines.append(f"| Mortgage Holder | {mortgage_holder} |")
    lines += [
        "",
        "## Description of Loss",
        "",
        description,
        "",
        "## Amount of Loss Claimed",
        "",
        f"| Category | Amount |",
        f"|---|---|",
        f"| Building Damage | {_fmt_amount(building_damage)} |",
        f"| Contents Damage | {_fmt_amount(contents_damage)} |",
        f"| Additional Living Expense / Other | {_fmt_amount(other_damage)} |",
        f"| **Total Amount Claimed** | **{_fmt_amount(amount_claimed)}** |",
        "",
        "---",
        "",
        "## Sworn Statement",
        "",
        f"I, {claimant}, being duly sworn, do hereby state that the foregoing "
        "is a true and complete statement of my loss and that I have not "
        "concealed or misrepresented any material fact.",
        "",
        f"**Signature:** _________________________",
        f"**Date:** {report_date_disp}",
        "",
        f"**State of {state}**",
        f"Subscribed and sworn to before me this date.",
        f"**Notary Public:** _________________________",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    rng = random.Random(SEED)

    # Create output directories
    for sub in ("documents", "expected", "manifests"):
        (POLICIES_DIR / sub).mkdir(parents=True, exist_ok=True)
        (CLAIMS_DIR / sub).mkdir(parents=True, exist_ok=True)

    # --- Binders (30 docs) → insurance_policies/ ---
    binder_count = 30
    for i in range(binder_count):
        file_id = f"synth_binder_{i + 1:03d}"
        md, expected, manifest = _gen_binder(i, rng)

        (POLICIES_DIR / "documents" / f"{file_id}.md").write_text(md + "\n")
        (POLICIES_DIR / "expected" / f"{file_id}.expected.json").write_text(
            json.dumps(expected, indent=2) + "\n"
        )
        (POLICIES_DIR / "manifests" / f"{file_id}.json").write_text(
            json.dumps(manifest, indent=2) + "\n"
        )
        print(
            f"[synth-binder] ({i + 1}/{binder_count}) {file_id}",
            file=sys.stderr,
        )

    print(f"\n[synth-binder] Done. Generated {binder_count} insurance binders.\n", file=sys.stderr)

    # --- Demand Letters (30 docs) → insurance_claims/ ---
    demand_count = 30
    for i in range(demand_count):
        file_id = f"synth_demand_{i + 1:03d}"
        md, expected, manifest = _gen_demand_letter(i, rng)

        (CLAIMS_DIR / "documents" / f"{file_id}.md").write_text(md + "\n")
        (CLAIMS_DIR / "expected" / f"{file_id}.expected.json").write_text(
            json.dumps(expected, indent=2) + "\n"
        )
        (CLAIMS_DIR / "manifests" / f"{file_id}.json").write_text(
            json.dumps(manifest, indent=2) + "\n"
        )
        print(
            f"[synth-demand] ({i + 1}/{demand_count}) {file_id}",
            file=sys.stderr,
        )

    print(f"\n[synth-demand] Done. Generated {demand_count} demand letters.\n", file=sys.stderr)

    # --- Filled-In Claim Forms (50 docs: 30 WC FROI + 20 property PoL) → insurance_claims/ ---
    wc_count = 30
    pol_count = 20
    claim_count = wc_count + pol_count
    claim_idx = 0

    for i in range(wc_count):
        file_id = f"synth_claim_{claim_idx + 1:03d}"
        md, expected, manifest = _gen_wc_froi(claim_idx, rng)

        (CLAIMS_DIR / "documents" / f"{file_id}.md").write_text(md + "\n")
        (CLAIMS_DIR / "expected" / f"{file_id}.expected.json").write_text(
            json.dumps(expected, indent=2) + "\n"
        )
        (CLAIMS_DIR / "manifests" / f"{file_id}.json").write_text(
            json.dumps(manifest, indent=2) + "\n"
        )
        print(
            f"[synth-claim] ({claim_idx + 1}/{claim_count}) {file_id}  [WC FROI]",
            file=sys.stderr,
        )
        claim_idx += 1

    for i in range(pol_count):
        file_id = f"synth_claim_{claim_idx + 1:03d}"
        md, expected, manifest = _gen_property_pol(claim_idx, rng)

        (CLAIMS_DIR / "documents" / f"{file_id}.md").write_text(md + "\n")
        (CLAIMS_DIR / "expected" / f"{file_id}.expected.json").write_text(
            json.dumps(expected, indent=2) + "\n"
        )
        (CLAIMS_DIR / "manifests" / f"{file_id}.json").write_text(
            json.dumps(manifest, indent=2) + "\n"
        )
        print(
            f"[synth-claim] ({claim_idx + 1}/{claim_count}) {file_id}  [Property PoL]",
            file=sys.stderr,
        )
        claim_idx += 1

    print(f"\n[synth-claim] Done. Generated {claim_count} filled-in claim forms.\n", file=sys.stderr)

    total = binder_count + demand_count + claim_count
    print(f"[synthetic_insurance_misc] All done. Generated {total} documents total.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
