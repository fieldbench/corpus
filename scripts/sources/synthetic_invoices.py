#!/usr/bin/env python3
"""Synthetic invoice generator for the FieldBench corpus.

Generates 50 diverse invoices in markdown format with known ground-truth
expected JSON outputs and manifest files. Since the invoices are synthetic,
every field value is deterministic and requires no manual review.

The generator produces variety across:
  - Industries (tech consulting, construction, food service, medical, etc.)
  - Line item counts (1 to 12)
  - Tax rates (0%, 6%, 7.25%, 8.875%, 13%, 19%, 20%)
  - Currencies (USD, EUR, GBP, CAD, AUD, SGD)
  - Date formats (Nov 3, 2025 / 2025-11-03 / 03/11/2025 / etc.)
  - Invoice number formats (INV-001, #2025-0147, SBD-2025-0147, etc.)
  - Layouts (header+table, bill-to/ship-to, receipt-style, multilingual)

Uses a fixed random seed for reproducibility.

Usage:
  python scripts/sources/synthetic_invoices.py
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

CORPUS_ROOT = Path(__file__).resolve().parent.parent.parent
INVOICES_DIR = CORPUS_ROOT / "invoices"

SEED = 20260415

# ---------------------------------------------------------------------------
# Data pools
# ---------------------------------------------------------------------------

MERCHANTS = [
    # (name, address lines, industry, phone/email)
    ("Pinnacle IT Solutions", ["4500 Tech Parkway, Suite 310", "Austin, TX 78759"], "tech", "info@pinnacleit.example"),
    ("Greenfield Construction Ltd.", ["88 Harbor Road", "Vancouver, BC V6Z 2R3, Canada"], "construction", "(604) 555-0211"),
    ("Sakura Sushi Bar", ["1927 Elm Street", "Seattle, WA 98101"], "food", "(206) 555-0188"),
    ("MedPro Surgical Supplies", ["220 Camelback Rd, Bldg A", "Phoenix, AZ 85016"], "medical", "orders@medprosurg.example"),
    ("Ravenna Consulting Group", ["71 Via Maggio", "50125 Firenze, Italy"], "consulting", "consulting@ravenna.example"),
    ("Bright Spark Electrical", ["14 Woodlands Industrial Park", "Singapore 738972"], "electrical", "+65 6555 0142"),
    ("Cloudline Analytics Pty Ltd", ["Level 8, 200 George Street", "Sydney NSW 2000, Australia"], "tech", "billing@cloudline.example"),
    ("Thornbury & Associates LLP", ["42 Bedford Row", "London WC1R 4JS, United Kingdom"], "legal", "+44 20 7946 0958"),
    ("Boulangerie Saint-Martin", ["12 Rue du Faubourg Saint-Antoine", "75012 Paris, France"], "food", "contact@bsm.example"),
    ("Nordic Timber AB", ["Storgatan 15", "SE-111 29 Stockholm, Sweden"], "construction", "+46 8 555 01 23"),
    ("Cascade Plumbing & Heating", ["3301 Pacific Highway", "Portland, OR 97232"], "trades", "(503) 555-0177"),
    ("LegalEase Document Services", ["900 Third Avenue, 17th Floor", "New York, NY 10022"], "legal", "docs@legalease.example"),
    ("Alpine Dental Supply GmbH", ["Bahnhofstrasse 42", "8001 Zürich, Switzerland"], "medical", "+41 44 555 01 88"),
    ("Oceanic Freight Logistics", ["Dock 7, Container Terminal", "Melbourne VIC 3000, Australia"], "logistics", "ops@oceanicfreight.example"),
    ("Redwood Creative Agency", ["1221 Mission Street, Suite 400", "San Francisco, CA 94103"], "marketing", "hello@redwoodcreative.example"),
    ("Hartmann Elektrotechnik GmbH", ["Industriestraße 55", "70565 Stuttgart, Deutschland"], "electrical", "+49 711 555 0190"),
    ("Prairie Veterinary Clinic", ["402 Main Street West", "Saskatoon, SK S7M 0K1, Canada"], "veterinary", "(306) 555-0144"),
    ("Tanglin Catering Pte Ltd", ["Block 21 Toa Payoh Lorong 8", "Singapore 310021"], "food", "+65 6555 0299"),
    ("PixelForge Studios", ["88 Shoreditch High Street", "London E1 6JJ, United Kingdom"], "design", "studio@pixelforge.example"),
    ("Atlas Civil Engineering Inc.", ["5500 Wilshire Blvd, Suite 700", "Los Angeles, CA 90036"], "construction", "(213) 555-0166"),
    ("Emerald Isle Imports", ["17 Grafton Street", "Dublin 2, D02 FK84, Ireland"], "retail", "+353 1 555 0172"),
    ("Summit Accounting Services", ["1100 Peachtree Street NE", "Atlanta, GA 30309"], "accounting", "info@summitacct.example"),
    ("Pacifica Marine Services", ["Pier 39, Fisherman's Wharf", "San Francisco, CA 94133"], "marine", "(415) 555-0199"),
    ("Kensington Physiotherapy", ["55 Kensington High Street", "London W8 5BA, United Kingdom"], "medical", "+44 20 7946 1122"),
    ("Maple Leaf Landscaping", ["2244 King Street East", "Toronto, ON M5A 1K2, Canada"], "landscaping", "(416) 555-0133"),
    ("Solaris Energy Systems", ["300 Solar Way", "Denver, CO 80202"], "energy", "sales@solarisenergy.example"),
    ("Blue Horizon Travel", ["Level 3, 44 Market Street", "Sydney NSW 2000, Australia"], "travel", "+61 2 5550 0188"),
    ("Precision Optics AG", ["Lichtweg 7", "07745 Jena, Deutschland"], "manufacturing", "+49 3641 555 022"),
    ("Golden Gate Catering Co.", ["450 Embarcadero", "San Francisco, CA 94105"], "food", "(415) 555-0211"),
    ("Sterling Architectural Design", ["800 Connecticut Avenue NW", "Washington, DC 20006"], "architecture", "projects@sterlingarch.example"),
    ("Compass Data Recovery", ["2100 Main Street, Unit B", "Irvine, CA 92614"], "tech", "(949) 555-0188"),
    ("Rotterdam Port Services BV", ["Europaweg 800", "3199 LD Rotterdam, Netherlands"], "logistics", "+31 10 555 0144"),
    ("Whistler Ski Rentals", ["4293 Mountain Square", "Whistler, BC V8E 1B8, Canada"], "recreation", "(604) 555-0299"),
    ("Ivory & Clarke Solicitors", ["11 King's Bench Walk", "London EC4Y 7EQ, United Kingdom"], "legal", "+44 20 7946 0811"),
    ("Sahara Print Solutions", ["45 Innovation Drive", "Dubai Internet City, UAE"], "printing", "+971 4 555 0188"),
    ("Heartland Grain Cooperative", ["1500 Prairie Avenue", "Des Moines, IA 50309"], "agriculture", "(515) 555-0177"),
    ("Catalonia Web Development", ["Carrer de Pau Claris 162", "08037 Barcelona, Spain"], "tech", "+34 93 555 01 88"),
    ("Bay Area Pet Hospital", ["790 Van Ness Avenue", "San Francisco, CA 94102"], "veterinary", "(415) 555-0166"),
    ("Phoenix Solar Installations", ["7700 E Doubletree Ranch Rd", "Scottsdale, AZ 85258"], "energy", "(480) 555-0199"),
    ("Queenstown Adventure Tours", ["12 Camp Street", "Queenstown 9300, New Zealand"], "tourism", "+64 3 555 0122"),
    ("Metro Office Supplies Inc.", ["350 Fifth Avenue, Suite 3300", "New York, NY 10118"], "office", "(212) 555-0144"),
    ("Vancouver Film Equipment Rentals", ["1055 West Hastings Street", "Vancouver, BC V6E 2E9, Canada"], "entertainment", "(604) 555-0188"),
    ("Berlin Language Academy", ["Friedrichstraße 191", "10117 Berlin, Deutschland"], "education", "+49 30 555 0166"),
    ("Gulf Coast Marine Repair", ["1200 Harbor Boulevard", "Corpus Christi, TX 78401"], "marine", "(361) 555-0211"),
    ("Highline Security Systems", ["2500 Sand Hill Road", "Menlo Park, CA 94025"], "security", "(650) 555-0177"),
    ("Aotearoa Wool Export Ltd", ["15 Queen Street", "Auckland 1010, New Zealand"], "agriculture", "+64 9 555 0188"),
    ("Capitol Hill Flowers", ["618 Pennsylvania Avenue SE", "Washington, DC 20003"], "retail", "(202) 555-0133"),
    ("Osaka Electronics Trading Co.", ["3-2-1 Namba", "Chuo-ku, Osaka 542-0076, Japan"], "electronics", "+81 6 5550 0199"),
    ("Santiago Mining Equipment SpA", ["Av. Providencia 1208", "Providencia, Santiago, Chile"], "mining", "+56 2 2555 0188"),
    ("TransAlpine Courier GmbH", ["Maximilianstraße 35", "80539 München, Deutschland"], "logistics", "+49 89 555 0144"),
]

# Currency → symbol mapping
CURRENCY_SYMBOLS = {
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
    "CAD": "CA$",
    "AUD": "A$",
    "SGD": "S$",
}

# Tax configurations: (label, rate)
TAX_CONFIGS = [
    ("Sales tax (0%)", 0.0),
    ("Sales tax (6%)", 0.06),
    ("Sales tax (7.25%)", 0.0725),
    ("Sales tax (8.875%)", 0.08875),
    ("HST (13%)", 0.13),
    ("MwSt. (19%)", 0.19),
    ("VAT (20%)", 0.20),
    ("GST (7%)", 0.07),
]

# Items per industry — (name, unit_price_range_low, unit_price_range_high)
ITEMS_BY_INDUSTRY = {
    "tech": [
        ("Cloud hosting (monthly)", 150, 2500),
        ("Software license renewal", 200, 5000),
        ("Technical consultation (hourly)", 150, 350),
        ("Data migration service", 1000, 8000),
        ("API integration setup", 800, 4000),
        ("Security audit", 2000, 10000),
        ("Server maintenance (monthly)", 300, 1500),
        ("SSL certificate (annual)", 50, 300),
        ("Database optimization", 500, 3000),
        ("Load testing service", 400, 2000),
        ("DevOps pipeline setup", 1500, 6000),
        ("Disaster recovery plan", 2000, 8000),
    ],
    "construction": [
        ("Concrete (per cubic yard)", 120, 180),
        ("Rebar #4 (per ton)", 700, 1200),
        ("Lumber 2x4x8 (per bundle)", 250, 450),
        ("Roofing shingles (per square)", 80, 200),
        ("Excavation (per hour)", 150, 350),
        ("Drywall sheets 4x8", 12, 25),
        ("Plumbing rough-in", 800, 3000),
        ("Electrical wiring (per room)", 400, 1200),
        ("Foundation inspection", 300, 800),
        ("Structural steel beam", 500, 2500),
        ("Window installation", 200, 800),
        ("Paint and finishing (per room)", 150, 500),
    ],
    "food": [
        ("Catering — appetizer platter", 45, 120),
        ("Catering — entrée (per person)", 18, 65),
        ("Beverage service (per person)", 8, 25),
        ("Dessert platter", 35, 90),
        ("Table setup and service", 100, 400),
        ("Equipment rental", 50, 200),
        ("Delivery charge", 25, 75),
        ("Specialty cake", 60, 250),
        ("Linen rental", 30, 100),
        ("Staff (per hour)", 25, 50),
        ("Coffee and tea service", 15, 45),
        ("Late-night snack station", 80, 200),
    ],
    "medical": [
        ("Surgical gloves (box of 100)", 8, 25),
        ("Disposable gown (pack of 10)", 15, 45),
        ("Suture kit 4-0", 12, 35),
        ("Sterile drape pack", 20, 60),
        ("Examination table paper (case)", 30, 80),
        ("Blood pressure cuff", 25, 90),
        ("Digital thermometer", 15, 50),
        ("Stethoscope", 40, 250),
        ("Pulse oximeter", 20, 80),
        ("Bandage roll (case of 12)", 10, 35),
        ("Hand sanitizer (gallon)", 12, 30),
        ("Face shield (box of 25)", 18, 45),
    ],
    "consulting": [
        ("Strategy workshop (full day)", 2000, 8000),
        ("Market analysis report", 3000, 12000),
        ("Process optimization review", 1500, 6000),
        ("Executive coaching session", 500, 2000),
        ("Competitive intelligence brief", 1000, 5000),
        ("Risk assessment", 2000, 7000),
        ("Organizational design", 3000, 10000),
        ("Change management plan", 2500, 8000),
        ("Board presentation materials", 1000, 4000),
        ("Due diligence review", 5000, 20000),
        ("Quarterly advisory retainer", 3000, 15000),
        ("Stakeholder interview series", 1500, 5000),
    ],
    "electrical": [
        ("LED panel light 600x600", 35, 80),
        ("Circuit breaker 20A", 8, 25),
        ("Cable tray (3m section)", 20, 60),
        ("Electrical conduit (bundle)", 15, 45),
        ("Distribution board", 100, 400),
        ("Emergency lighting unit", 50, 150),
        ("Wiring (per meter)", 2, 8),
        ("Installation labor (per hour)", 60, 120),
        ("Safety inspection", 200, 600),
        ("Smoke detector", 15, 45),
        ("Surge protector panel", 80, 250),
        ("Switch and socket set", 10, 35),
    ],
    "legal": [
        ("Legal consultation (hourly)", 250, 800),
        ("Contract drafting", 500, 3000),
        ("Document review (per page)", 5, 15),
        ("Court filing preparation", 300, 1500),
        ("Corporate formation", 800, 3000),
        ("Trademark application", 500, 2000),
        ("Compliance review", 1000, 5000),
        ("Mediation services (half day)", 1500, 5000),
        ("Legal research memo", 400, 1500),
        ("Notarization (per document)", 10, 50),
        ("Deposition preparation", 800, 3000),
        ("Settlement negotiation", 2000, 8000),
    ],
    "logistics": [
        ("Container shipping 20ft", 1500, 4000),
        ("Customs clearance", 200, 800),
        ("Warehouse storage (per pallet/month)", 15, 50),
        ("Freight insurance", 100, 500),
        ("Last-mile delivery", 50, 200),
        ("Packaging service", 30, 150),
        ("Refrigerated transport", 500, 2000),
        ("Loading and unloading", 100, 400),
        ("Express courier", 25, 100),
        ("Documentation handling", 50, 200),
        ("Tracking and monitoring", 20, 80),
        ("Pallet wrapping", 5, 20),
    ],
    "marketing": [
        ("Brand strategy session", 1500, 5000),
        ("Logo design package", 500, 3000),
        ("Social media management (monthly)", 800, 3000),
        ("Video production (30s spot)", 2000, 8000),
        ("Copywriting (per page)", 100, 500),
        ("SEO audit and recommendations", 500, 2000),
        ("Email campaign setup", 300, 1200),
        ("Photography session (half day)", 500, 2000),
        ("Print collateral design", 200, 800),
        ("PPC campaign management", 400, 1500),
        ("Market research survey", 1000, 4000),
        ("Press release drafting", 200, 600),
    ],
    "design": [
        ("UI/UX design (per screen)", 200, 800),
        ("Design system creation", 3000, 12000),
        ("Wireframe prototype", 500, 2000),
        ("User research interview", 200, 600),
        ("Usability testing session", 500, 1500),
        ("Icon set design", 300, 1000),
        ("Motion graphics (per second)", 50, 200),
        ("Brand guidelines document", 1000, 4000),
        ("Illustration (per piece)", 150, 600),
        ("Design review and critique", 200, 500),
        ("Interactive prototype", 800, 3000),
        ("Print layout design", 300, 1000),
    ],
}

# Default items for industries not in the map above
DEFAULT_ITEMS = [
    ("Professional service", 100, 500),
    ("Consultation fee", 150, 600),
    ("Materials and supplies", 50, 300),
    ("Administrative fee", 25, 100),
    ("Equipment rental", 75, 400),
    ("Travel expenses", 50, 250),
    ("Shipping and handling", 15, 75),
    ("Setup and configuration", 200, 800),
    ("Maintenance service", 100, 500),
    ("Documentation", 50, 200),
    ("Training session", 200, 800),
    ("Inspection and testing", 100, 400),
]

# Date format functions
DATE_FORMATS = [
    lambda y, m, d: f"{['January','February','March','April','May','June','July','August','September','October','November','December'][m-1]} {d}, {y}",
    lambda y, m, d: f"{['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][m-1]} {d}, {y}",
    lambda y, m, d: f"{y}-{m:02d}-{d:02d}",
    lambda y, m, d: f"{m:02d}/{d:02d}/{y}",
    lambda y, m, d: f"{d:02d}/{m:02d}/{y}",
    lambda y, m, d: f"{d} {['January','February','March','April','May','June','July','August','September','October','November','December'][m-1]} {y}",
    lambda y, m, d: f"{d:02d}.{m:02d}.{y}",
]

# Invoice number format generators
def _inv_number(rng: random.Random, idx: int) -> str:
    """Generate a varied invoice number."""
    formats = [
        lambda: f"INV-{rng.randint(1000, 9999)}",
        lambda: f"#{idx + 2025_0100}",
        lambda: f"INV-{rng.randint(2024, 2026)}-{rng.randint(100, 9999):04d}",
        lambda: f"{rng.choice(['SVC', 'PRJ', 'ORD', 'BIL'])}-{rng.randint(2024, 2026)}-{rng.randint(1000, 9999)}",
        lambda: f"{rng.randint(100000, 999999)}",
        lambda: f"F{rng.randint(2024, 2026)}-{rng.randint(1, 999):04d}",
        lambda: f"INV{rng.choice(['', '-'])}{rng.randint(10000, 99999)}",
    ]
    return rng.choice(formats)()


# ---------------------------------------------------------------------------
# Layout templates — each returns (markdown_str, expected_dict)
# ---------------------------------------------------------------------------

def _fmt_amount(value: float, currency: str) -> str:
    """Format a monetary amount with the appropriate currency symbol."""
    sym = CURRENCY_SYMBOLS.get(currency, "$")
    if currency in ("EUR",):
        # European style: 1.234,56 €
        int_part = int(value)
        dec_part = round((value - int_part) * 100)
        if int_part >= 1000:
            thousands = int_part // 1000
            remainder = int_part % 1000
            formatted = f"{thousands}.{remainder:03d},{dec_part:02d} {sym}"
        else:
            formatted = f"{int_part},{dec_part:02d} {sym}"
        return formatted
    else:
        # US/UK style: $1,234.56
        if value >= 1000:
            int_part = int(value)
            dec_part = round((value - int_part) * 100)
            thousands = int_part // 1000
            remainder = int_part % 1000
            formatted = f"{sym}{thousands},{remainder:03d}.{dec_part:02d}"
        else:
            formatted = f"{sym}{value:,.2f}"
        return formatted


def _round2(val: float) -> float:
    """Round to 2 decimal places."""
    return round(val, 2)


def layout_standard_table(
    merchant: tuple, items: list[dict], tax_label: str, tax_rate: float,
    currency: str, date_str: str, inv_number: str, rng: random.Random,
) -> tuple[str, float, float, float]:
    """Standard layout: header, bill-to, markdown table, totals."""
    name, addr_lines, industry, contact = merchant
    subtotal = _round2(sum(it["amount"] for it in items))
    tax = _round2(subtotal * tax_rate)
    total = _round2(subtotal + tax)

    bill_to_names = [
        "Acme Corporation", "Global Dynamics Inc.", "Starlight Ventures LLC",
        "Horizon Partners", "Evergreen Solutions Ltd.", "Pacific Rim Trading Co.",
        "Summit Holdings Group", "Atlas Worldwide Corp.", "Beacon Industries",
        "Crestview Enterprises",
    ]
    bill_to = rng.choice(bill_to_names)

    lines = []
    lines.append(f"# INVOICE")
    lines.append("")
    lines.append(f"**{name}**")
    for a in addr_lines:
        lines.append(a)
    lines.append(contact)
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"**Invoice Number:** {inv_number}")
    lines.append(f"**Invoice Date:** {date_str}")
    lines.append("")
    lines.append("## Bill To")
    lines.append("")
    lines.append(bill_to)
    lines.append("")
    lines.append("## Items")
    lines.append("")
    lines.append("| Description | Qty | Unit Price | Amount |")
    lines.append("|---|---|---|---|")
    for it in items:
        lines.append(f"| {it['name']} | {it['quantity']} | {_fmt_amount(it['unit_price'], currency)} | {_fmt_amount(it['amount'], currency)} |")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"| | |")
    lines.append(f"|---|---|")
    lines.append(f"| Subtotal | {_fmt_amount(subtotal, currency)} |")
    lines.append(f"| {tax_label} | {_fmt_amount(tax, currency)} |")
    lines.append(f"| **Total Due** | **{_fmt_amount(total, currency)}** |")
    lines.append("")

    terms = rng.choice([
        "Payment terms: Net 30.",
        "Payment due within 30 days of invoice date.",
        "Due upon receipt.",
        "Terms: Net 45. Late payments subject to 1.5% monthly interest.",
        "Please remit payment within 14 days.",
    ])
    lines.append(terms)

    return "\n".join(lines), subtotal, tax, total


def layout_receipt_style(
    merchant: tuple, items: list[dict], tax_label: str, tax_rate: float,
    currency: str, date_str: str, inv_number: str, rng: random.Random,
) -> tuple[str, float, float, float]:
    """Receipt/POS-style layout with no markdown table."""
    name, addr_lines, industry, contact = merchant
    subtotal = _round2(sum(it["amount"] for it in items))
    tax = _round2(subtotal * tax_rate)
    total = _round2(subtotal + tax)

    lines = []
    lines.append(f"# RECEIPT")
    lines.append("")
    lines.append(f"**{name}**")
    for a in addr_lines:
        lines.append(a)
    lines.append(contact)
    lines.append("")
    lines.append(f"Receipt: {inv_number}")
    lines.append(f"Date: {date_str}")
    lines.append("")
    lines.append("---")
    lines.append("")

    for it in items:
        qty_str = f"{it['quantity']}x" if it['quantity'] > 1 else "1x"
        padding = 40 - len(f"{qty_str}  {it['name']}")
        pad = " " * max(padding, 2)
        lines.append(f"{qty_str}  {it['name']}{pad}{_fmt_amount(it['amount'], currency)}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"Subtotal{' ' * 20}{_fmt_amount(subtotal, currency)}")
    lines.append(f"{tax_label}{' ' * max(1, 28 - len(tax_label))}{_fmt_amount(tax, currency)}")
    lines.append("")
    lines.append(f"**TOTAL{' ' * 21}{_fmt_amount(total, currency)}**")
    lines.append("")

    payment_method = rng.choice([
        "Paid: Visa ****4821 — Approved",
        "Paid: Cash",
        "Paid: Mastercard ****7733",
        "Paid: Debit ****1156",
        "Paid: AMEX ****3009",
    ])
    lines.append(payment_method)
    lines.append("")
    lines.append("Thank you!")

    return "\n".join(lines), subtotal, tax, total


def layout_plain_text(
    merchant: tuple, items: list[dict], tax_label: str, tax_rate: float,
    currency: str, date_str: str, inv_number: str, rng: random.Random,
) -> tuple[str, float, float, float]:
    """Plain text / monospaced layout mimicking OCR from a scanned invoice."""
    name, addr_lines, industry, contact = merchant
    subtotal = _round2(sum(it["amount"] for it in items))
    tax = _round2(subtotal * tax_rate)
    total = _round2(subtotal + tax)

    lines = []
    lines.append(name.upper())
    for a in addr_lines:
        lines.append(a)
    lines.append(f"Tel: {contact}")
    lines.append("")
    lines.append("INVOICE")
    lines.append("")
    lines.append(f"Invoice No:      {inv_number}")
    lines.append(f"Invoice Date:    {date_str}")

    # Optionally add PO and terms
    if rng.random() > 0.5:
        lines.append(f"Customer PO:     PO-{rng.randint(2024, 2026)}-{rng.randint(1000, 9999)}")
    if rng.random() > 0.4:
        lines.append(f"Payment Terms:   Net {rng.choice([15, 30, 45, 60])}")

    sold_to_names = [
        "Midwest Manufacturing Corp", "Coastal Engineering Group",
        "Valley Tech Solutions", "Northern Supplies Inc.",
        "Heritage Partners LLC", "Pinnacle Systems Group",
    ]
    lines.append("")
    lines.append(f"SOLD TO:")
    lines.append(rng.choice(sold_to_names))
    lines.append("")

    lines.append("=" * 60)
    lines.append(f"{'ITEM':<6}{'DESCRIPTION':<30}{'QTY':>5}{'PRICE':>10}{'EXT':>9}")
    lines.append("=" * 60)
    for i, it in enumerate(items, 1):
        desc = it["name"][:28]
        lines.append(f"{i:03d}   {desc:<30}{it['quantity']:>5}{it['unit_price']:>10.2f}{it['amount']:>9.2f}")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"{'Subtotal:':>48}{subtotal:>12.2f}")
    lines.append(f"{tax_label + ':':>48}{tax:>12.2f}")
    lines.append(f"{'TOTAL DUE:':>48}{total:>12.2f}")

    return "\n".join(lines), subtotal, tax, total


def layout_ship_to(
    merchant: tuple, items: list[dict], tax_label: str, tax_rate: float,
    currency: str, date_str: str, inv_number: str, rng: random.Random,
) -> tuple[str, float, float, float]:
    """Layout with both bill-to and ship-to addresses."""
    name, addr_lines, industry, contact = merchant
    subtotal = _round2(sum(it["amount"] for it in items))
    tax = _round2(subtotal * tax_rate)
    total = _round2(subtotal + tax)

    bill_to_companies = [
        ("Meridian Holdings Inc.", "1200 Park Avenue, Suite 500", "New York, NY 10128"),
        ("Lighthouse Financial Group", "8800 Sunset Blvd", "West Hollywood, CA 90069"),
        ("Ironclad Manufacturing Ltd.", "45 Industrial Drive", "Birmingham, B1 2AX, UK"),
        ("Tidewater Resources Corp.", "3300 Riverfront Plaza", "Richmond, VA 23219"),
        ("Alpine Ventures AG", "Talstrasse 20", "8001 Zürich, Switzerland"),
    ]
    bt = rng.choice(bill_to_companies)

    ship_to_locs = [
        "Warehouse B, Loading Dock 3",
        "Receiving Dept — Building 7",
        "Job Site #14, Lot 2200",
        "Distribution Center East",
        "Attn: Inventory Control",
    ]

    lines = []
    lines.append(f"# Invoice {inv_number}")
    lines.append("")
    lines.append(f"**{name}**")
    for a in addr_lines:
        lines.append(a)
    lines.append(contact)
    lines.append("")
    lines.append(f"**Date:** {date_str}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("**Bill To:**")
    lines.append(bt[0])
    lines.append(bt[1])
    lines.append(bt[2])
    lines.append("")
    lines.append("**Ship To:**")
    lines.append(bt[0])
    lines.append(rng.choice(ship_to_locs))
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("| # | Item | Qty | Rate | Amount |")
    lines.append("|---|------|-----|------|--------|")
    for i, it in enumerate(items, 1):
        lines.append(f"| {i} | {it['name']} | {it['quantity']} | {_fmt_amount(it['unit_price'], currency)} | {_fmt_amount(it['amount'], currency)} |")
    lines.append("")
    lines.append(f"**Subtotal:** {_fmt_amount(subtotal, currency)}")
    lines.append(f"**{tax_label}:** {_fmt_amount(tax, currency)}")
    lines.append("")
    lines.append(f"### Total: {_fmt_amount(total, currency)}")

    if rng.random() > 0.5:
        lines.append("")
        lines.append(f"Payment Terms: Net {rng.choice([15, 30, 45, 60])}")

    return "\n".join(lines), subtotal, tax, total


def layout_minimal(
    merchant: tuple, items: list[dict], tax_label: str, tax_rate: float,
    currency: str, date_str: str, inv_number: str, rng: random.Random,
) -> tuple[str, float, float, float]:
    """Minimal invoice — just the essentials, fewer visual cues."""
    name, addr_lines, industry, contact = merchant
    subtotal = _round2(sum(it["amount"] for it in items))
    tax = _round2(subtotal * tax_rate)
    total = _round2(subtotal + tax)

    lines = []
    lines.append(f"**{name}**")
    lines.append("")
    lines.append(f"Invoice {inv_number} — {date_str}")
    lines.append("")
    for it in items:
        lines.append(f"- {it['name']}: {it['quantity']} × {_fmt_amount(it['unit_price'], currency)} = {_fmt_amount(it['amount'], currency)}")
    lines.append("")
    lines.append(f"Subtotal: {_fmt_amount(subtotal, currency)}")
    lines.append(f"{tax_label}: {_fmt_amount(tax, currency)}")
    lines.append(f"**Total: {_fmt_amount(total, currency)}**")

    return "\n".join(lines), subtotal, tax, total


LAYOUT_FUNCS = [
    layout_standard_table,
    layout_receipt_style,
    layout_plain_text,
    layout_ship_to,
    layout_minimal,
]


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def generate_invoice(idx: int, rng: random.Random) -> tuple[str, dict, dict]:
    """Generate one synthetic invoice. Returns (markdown, expected, manifest)."""

    merchant = MERCHANTS[idx % len(MERCHANTS)]
    name, addr_lines, industry, contact = merchant

    # Pick currency based on address hints
    if "Canada" in " ".join(addr_lines) or ", BC " in " ".join(addr_lines) or ", ON " in " ".join(addr_lines) or ", SK " in " ".join(addr_lines):
        currency = "CAD"
    elif "Australia" in " ".join(addr_lines) or "NSW" in " ".join(addr_lines) or "VIC" in " ".join(addr_lines):
        currency = "AUD"
    elif "Singapore" in " ".join(addr_lines):
        currency = "SGD"
    elif any(w in " ".join(addr_lines) for w in ["United Kingdom", "London"]):
        currency = "GBP"
    elif any(w in " ".join(addr_lines) for w in ["France", "Italy", "Deutschland", "Germany", "Spain", "Netherlands", "Ireland", "Stockholm", "Zürich", "Switzerland"]):
        currency = "EUR"
    else:
        currency = "USD"

    # Pick date
    year = rng.choice([2024, 2025, 2025, 2025, 2026])
    month = rng.randint(1, 12)
    day = rng.randint(1, 28)
    date_iso = f"{year}-{month:02d}-{day:02d}"
    date_fmt_fn = rng.choice(DATE_FORMATS)
    date_display = date_fmt_fn(year, month, day)

    # Pick tax config
    tax_label, tax_rate = rng.choice(TAX_CONFIGS)

    # Pick number of items (1 to 12, weighted toward 2-5)
    num_items = rng.choices(range(1, 13), weights=[3, 8, 8, 7, 5, 4, 3, 2, 2, 1, 1, 1], k=1)[0]

    # Generate items
    industry_items = ITEMS_BY_INDUSTRY.get(industry, DEFAULT_ITEMS)
    selected_item_templates = rng.sample(industry_items, min(num_items, len(industry_items)))
    while len(selected_item_templates) < num_items:
        selected_item_templates.append(rng.choice(industry_items))

    items = []
    for tmpl in selected_item_templates:
        item_name, lo, hi = tmpl
        unit_price = _round2(rng.uniform(lo, hi))
        quantity = rng.choices(range(1, 51), weights=[20] + [5] * 4 + [3] * 5 + [2] * 10 + [1] * 30, k=1)[0]
        amount = _round2(unit_price * quantity)
        items.append({
            "name": item_name,
            "quantity": quantity,
            "unit_price": unit_price,
            "amount": amount,
        })

    # Pick layout and invoice number
    inv_number = _inv_number(rng, idx)
    layout_fn = rng.choice(LAYOUT_FUNCS)

    markdown, subtotal, tax_amount, total = layout_fn(
        merchant, items, tax_label, tax_rate,
        currency, date_display, inv_number, rng,
    )

    expected = {
        "merchant_name": name,
        "date": date_iso,
        "total_amount": total,
        "subtotal": subtotal,
        "tax": tax_amount,
        "currency": currency,
        "items": [
            {
                "name": it["name"],
                "quantity": it["quantity"],
                "unit_price": it["unit_price"],
                "amount": it["amount"],
            }
            for it in items
        ],
    }

    file_id = f"synth_{idx + 1:03d}"

    notes_parts = [
        f"Synthetic {industry} invoice",
        f"{len(items)} line item{'s' if len(items) != 1 else ''}",
        currency,
        f"tax {tax_rate*100:.2g}%",
    ]

    manifest = {
        "filename": f"{file_id}.md",
        "source_name": "Synthetic generator (synthetic_invoices.py)",
        "source_url": None,
        "license": "Apache-2.0",
        "license_url": "https://www.apache.org/licenses/LICENSE-2.0",
        "attribution": "FieldBench corpus contributors",
        "original_format": "markdown",
        "r2_url": None,
        "pages": 1,
        "added_date": "2026-04-15",
        "added_by": "accuracy-22",
        "schema": "invoices/schemas/invoice_basic.yaml",
        "notes": f"{'. '.join(notes_parts)}.",
    }

    return markdown, expected, manifest


def main() -> int:
    rng = random.Random(SEED)

    # Ensure target dirs exist
    for sub in ("documents", "expected", "manifests"):
        (INVOICES_DIR / sub).mkdir(parents=True, exist_ok=True)

    count = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    start = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    for idx in range(start, start + count):
        file_id = f"synth_{idx + 1:03d}"

        markdown, expected, manifest = generate_invoice(idx, rng)

        doc_path = INVOICES_DIR / "documents" / f"{file_id}.md"
        exp_path = INVOICES_DIR / "expected" / f"{file_id}.expected.json"
        man_path = INVOICES_DIR / "manifests" / f"{file_id}.json"

        doc_path.write_text(markdown + "\n")
        exp_path.write_text(json.dumps(expected, indent=2) + "\n")
        man_path.write_text(json.dumps(manifest, indent=2) + "\n")

        print(f"[synth] ({idx + 1}/{count}) {file_id}", file=sys.stderr)

    print(f"\n[synth] Done. Generated {count} synthetic invoices.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
