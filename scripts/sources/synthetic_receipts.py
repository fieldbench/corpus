#!/usr/bin/env python3
"""Synthetic retail-receipt generator — matched-pair partner for the REAL
SROIE receipts docs.

Purpose: the published corpus has receipts (SROIE) as 100% real OCR'd retail
receipts. To measure the synthetic-vs-real accuracy gap *holding category
(schema, difficulty class) constant*, we add clean, templated synthetic receipts
against the SAME `invoice_basic.yaml` schema. Real and synthetic then differ only
in provenance/formatting, not in what is being extracted — the controlled
comparison the paper needs.

Note on ground truth: the real SROIE expected files populate only
merchant_name / date / total_amount (the SROIE task's four keys). The schema,
however, defines subtotal / tax / currency / items, so the synthetic partner
exercises the full schema with internally-consistent arithmetic
(sum(item.amount) == subtotal, subtotal + tax == total_amount). Every
ground-truth value is present verbatim / recoverably in the receipt text.

Deterministic (seeded). Emits documents/<id>.md, expected/<id>.expected.json,
manifests/<id>.json with source=synthetic, license CC0.

    python synthetic_receipts.py --out <corpus>/receipts --n 40 [--seed N] --realism {0,1}
"""
from __future__ import annotations

import argparse
import json
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 54001  # distinct from other generators

# (merchant_name, address line, phone)
MERCHANTS = [
    ("GREENLEAF GROCERS SDN BHD", "12 JALAN MERPATI, TAMAN SERI, 47100 PUCHONG", "03-8074 2211"),
    ("SUNRISE MART & PROVISIONS", "88 Orchard Road, #02-14, Singapore 238841", "6733 9080"),
    ("HARBOUR POINT CONVENIENCE", "45 Wharf Street, Auckland 1010", "09-303 1122"),
    ("CITY LIGHTS HARDWARE CO", "204 Market Ave, Springfield, IL 62704", "217-555-0142"),
    ("BLUE ORCHID PHARMACY", "17 Bukit Bintang, 55100 Kuala Lumpur", "03-2148 6677"),
    ("MAPLE & OAK BOOKSHOP", "660 Bloor St W, Toronto, ON M6G 1L1", "416-555-0198"),
    ("THE DAILY BEAN CAFE", "9 Rue de la Paix, 75002 Paris", "01 42 60 30 30"),
    ("VICTORIA STATIONERS LTD", "22 High Holborn, London WC1V 6NP", "020 7242 5511"),
    ("PACIFIC FRESH SEAFOOD", "310 Fisherman's Wharf, San Francisco, CA 94133", "415-555-0176"),
    ("GOLDEN LOTUS RESTAURANT", "78 Petaling Street, 50000 Kuala Lumpur", "03-2072 8899"),
    ("NORTHWIND ELECTRONICS", "1150 Robson St, Vancouver, BC V6E 1B5", "604-555-0133"),
    ("SILVERTON DEPARTMENT STORE", "5 Collins Street, Melbourne VIC 3000", "03 9654 2200"),
    ("EASTGATE MINI MARKET", "203 Jalan Ampang, 50450 Kuala Lumpur", "03-4256 7788"),
    ("RIVERSIDE BAKERY & DELI", "14 Canal Road, Dublin D02 XY45", "01 662 4400"),
    ("SUMMIT SPORTS OUTFITTERS", "740 Denver Ave, Boulder, CO 80301", "303-555-0167"),
    ("LOTUS GARDEN NURSERY", "56 Jalan Kebun, 40460 Shah Alam", "03-5510 3344"),
]

# retail line-item names (short, receipt-style)
PRODUCTS = [
    "MINERAL WATER 1.5L", "WHITE BREAD 400G", "FRESH MILK 1L", "BROWN EGGS 12S",
    "INSTANT COFFEE 200G", "GREEN TEA 25S", "CANNED TUNA 185G", "RICE 5KG BAG",
    "COOKING OIL 2L", "SUGAR 1KG", "SALT 500G", "TOMATO SAUCE 340G",
    "BATH SOAP 3PK", "TOOTHPASTE 150G", "SHAMPOO 400ML", "PAPER TOWEL 2PLY",
    "AA BATTERY 4PK", "USB CABLE 1M", "LED BULB 9W", "NOTEBOOK A5",
    "BALLPOINT PEN 5S", "STICKY NOTES 3PK", "PHONE CHARGER 20W", "HAND SANITIZER 250ML",
    "DARK CHOCOLATE 100G", "POTATO CHIPS 150G", "ORANGE JUICE 1L", "YOGURT DRINK 700ML",
    "DISH SOAP 900ML", "LAUNDRY POWDER 1KG", "TRASH BAGS 30S", "FACE MASK 10PK",
]

# (iso_code, symbol) — symbol is printed on amounts, code printed explicitly too
CURRENCIES = [
    ("USD", "$"), ("MYR", "RM"), ("SGD", "S$"), ("GBP", "£"),
    ("EUR", "€"), ("CAD", "C$"), ("AUD", "A$"),
]

TAX_LABELS = ["SALES TAX", "GST", "VAT", "TAX"]


def _iso(d: date) -> str:
    return d.isoformat()


def _mdy(d: date) -> str:
    return d.strftime("%m/%d/%Y")


def _dmon(d: date) -> str:
    # e.g. "24 Jul 2026" — unambiguous, OCR-footer style
    return d.strftime("%d %b %Y")


def _money(sym: str, cents: int) -> str:
    """Render a cent amount with its currency symbol, e.g. 'RM9.00' / '$12.50'."""
    return f"{sym}{cents / 100:.2f}"


def _plain(cents: int) -> float:
    return round(cents / 100, 2)


def _build_cart(rng: random.Random):
    """Return (items, subtotal_cents, tax_cents, total_cents, tax_rate) with exact
    integer-cent arithmetic so sum(item.amount)==subtotal and subtotal+tax==total."""
    n_items = rng.randint(1, 5)
    names = rng.sample(PRODUCTS, k=n_items)
    items = []
    subtotal_cents = 0
    for name in names:
        qty = rng.randint(1, 4)
        unit_cents = rng.randint(150, 9999)  # 1.50 .. 99.99
        amount_cents = qty * unit_cents      # exact
        subtotal_cents += amount_cents
        items.append({
            "name": name,
            "quantity": qty,
            "unit_price": _plain(unit_cents),
            "amount": _plain(amount_cents),
            "_qty": qty,
            "_unit_cents": unit_cents,
            "_amount_cents": amount_cents,
        })
    tax_rate = rng.choice([0.0, 0.05, 0.06, 0.07, 0.08, 0.10])
    tax_cents = round(subtotal_cents * tax_rate)
    total_cents = subtotal_cents + tax_cents
    return items, subtotal_cents, tax_cents, total_cents, tax_rate


def _render_clean(rng, merchant, addr, phone, d, sym, code, items,
                  subtotal_cents, tax_cents, total_cents, tax_label):
    """Realism 0 — templated, one labeled fact per line. Trivially extractable;
    the conventional-synthetic extreme."""
    lines = [
        "## Merchant Information",
        f"**Merchant Name:** {merchant}",
        f"**Address:** {addr}",
        f"**Phone:** {phone}",
        "",
        "## Receipt Information",
        f"**Date:** {_mdy(d)}",
        f"**Currency:** {code}",
        "",
        "## Items",
    ]
    for it in items:
        lines.append(
            f"- **Item:** {it['name']}  "
            f"**Qty:** {it['_qty']}  "
            f"**Unit Price:** {_money(sym, it['_unit_cents'])}  "
            f"**Amount:** {_money(sym, it['_amount_cents'])}"
        )
    lines += [
        "",
        "## Totals",
        f"**Subtotal:** {_money(sym, subtotal_cents)}",
        f"**{tax_label}:** {_money(sym, tax_cents)}",
        f"**Total:** {_money(sym, total_cents)}",
        "",
        "**Thank you for your purchase!**",
    ]
    return "\n".join(lines) + "\n"


def _render_realistic(rng, merchant, addr, phone, d, sym, code, items,
                      subtotal_cents, tax_cents, total_cents, tax_label):
    """Realism 1 — messy OCR-style receipt: aligned monospace columns,
    abbreviations, a DISTRACTOR CASH TENDERED / CHANGE pair that is NOT the total,
    and the date embedded in a footer line rather than labeled. All ground-truth
    values are present and recoverable, just not neatly labeled."""
    # distractor tender: round total UP to the next whole 5 currency units, so
    # CASH TENDERED and CHANGE are both non-total amounts.
    tendered_cents = ((total_cents // 500) + 1) * 500
    if tendered_cents <= total_cents:
        tendered_cents += 500
    change_cents = tendered_cents - total_cents

    doc_no = f"{rng.choice(['CS', 'TD', 'INV', 'R'])}{rng.randint(10000, 99999)}"
    cashier = rng.choice(["ADORA", "USER01", "MEI LING", "JAMAL", "P.OS", "STAFF7"])
    # Same-type distractors that mirror real receipts:
    #  - a shopping-plaza name printed ABOVE the merchant + a payment-processor footer,
    #    so the merchant (GT) is one of several business-like names;
    #  - a second date (a promo "REDEEM BY") competing with the transaction date;
    #  - extra amount lines (YOU SAVED, ROUNDING, POINTS, AMOUNT DUE=total) so the TOTAL
    #    must be picked out of many numbers. GT (merchant / transaction date / total)
    #    stays present and determinable, just no longer the only candidate of its type.
    plaza = rng.choice(["SUNWAY PYRAMID", "MID VALLEY MEGAMALL", "1 UTAMA SHOPPING CTR",
                        "PAVILION KL", "GURNEY PLAZA"])
    processor = rng.choice(["Powered by iPay88", "EFTPOS via MyDebit",
                            "Terminal by Razer Merchant", "GHL ePayment"])
    saved_cents = rng.randint(50, max(51, subtotal_cents // 5))
    rounding_cents = rng.choice([-2, -1, 0, 1, 2])
    points = rng.randint(1, 999)
    promo = d + timedelta(days=rng.randint(20, 120))  # distractor date (promo expiry)

    out = []
    out.append("```")
    out.append(f"        {plaza}")            # distractor business name (plaza)
    out.append(f"{merchant}")                 # GT merchant
    out.append(f"{addr}")
    out.append(f"TEL {phone}")
    out.append(f"TAX INV  {code}")
    out.append("-" * 44)
    out.append(f"DOC {doc_no}          CASHIER {cashier}")
    out.append(f"MEMBER 88{rng.randint(10000, 99999)}   REDEEM BY {_dmon(promo)}")  # distractor date
    out.append("-" * 44)
    out.append("QTY DESCRIPTION              AMT")
    out.append("-" * 44)
    for it in items:
        name = it["name"]
        if len(name) > 20:
            name = name[:20]
        amt = _money(sym, it["_amount_cents"])
        out.append(f"{it['_qty']:>3} {name:<20} {amt:>8}")
    out.append("-" * 44)
    out.append(f"    {'SUBTOT':<20} {_money(sym, subtotal_cents):>8}")
    out.append(f"    {'YOU SAVED':<20} {_money(sym, saved_cents):>8}")   # distractor amount
    out.append(f"    {tax_label[:20]:<20} {_money(sym, tax_cents):>8}")
    out.append(f"    {'ROUNDING ADJ':<20} {_money(sym, rounding_cents):>8}")  # distractor amount
    out.append(f"    {'TOTAL':<20} {_money(sym, total_cents):>8}")
    out.append(f"    {'AMOUNT DUE':<20} {_money(sym, total_cents):>8}")   # equals total (not a distractor value)
    out.append("=" * 44)
    out.append(f"    {'CASH TENDERED':<20} {_money(sym, tendered_cents):>8}")  # distractor amount
    out.append(f"    {'CHANGE':<20} {_money(sym, change_cents):>8}")           # distractor amount
    out.append(f"    POINTS EARNED {points}")                                  # distractor number
    out.append("-" * 44)
    out.append("GOODS SOLD ARE NOT RETURNABLE")
    out.append(f"{processor}")                # distractor business name (processor)
    out.append("THANK YOU  PLEASE COME AGAIN")
    out.append(f"{_dmon(d)}   {d.strftime('%H:%M:%S')}   TERMINAL 03")  # transaction date (GT)
    out.append("```")
    return "\n".join(out) + "\n"


def make_doc(rng: random.Random, idx: int, realism: int = 0) -> tuple[str, dict, dict]:
    merchant, addr, phone = rng.choice(MERCHANTS)
    code, sym = rng.choice(CURRENCIES)
    tax_label = rng.choice(TAX_LABELS)

    d = date(2023, 1, 1) + timedelta(days=rng.randint(0, 900))

    items, subtotal_cents, tax_cents, total_cents, _rate = _build_cart(rng)

    stem = f"synth-receipt-r{realism}-{idx:03d}"
    render = _render_clean if realism == 0 else _render_realistic
    doc = render(rng, merchant, addr, phone, d, sym, code, items,
                 subtotal_cents, tax_cents, total_cents, tax_label)

    expected = {
        "merchant_name": merchant,
        "date": _iso(d),
        "total_amount": _plain(total_cents),
        "subtotal": _plain(subtotal_cents),
        "tax": _plain(tax_cents),
        "currency": code,
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
    manifest = {
        "id": stem,
        "source_name": "Synthetic generator (synthetic_receipts.py)",
        "source_url": None,
        "license": "CC0-1.0",
        "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
        "schema": "receipts/schemas/invoice_basic.yaml",
        "document": f"documents/{stem}.md",
        "expected": f"expected/{stem}.expected.json",
        "attribution": "Synthetic — no real merchant or transaction data.",
        "license_basis": "Machine-generated synthetic document; released CC0.",
        "source": "synthetic",
    }
    return doc, expected, manifest


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, type=Path, help="receipts category dir")
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--start", type=int, default=0, help="starting index (append)")
    ap.add_argument("--realism", type=int, default=0, choices=[0, 1],
                    help="0=clean templated, 1=OCR-style with distractors")
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
    print(f"wrote {args.n} synthetic receipts (realism {args.realism}) to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
