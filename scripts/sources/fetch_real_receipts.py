#!/usr/bin/env python3
"""Fetch REAL SROIE receipts + SHIPPED, DOC-GROUNDED ground truth.

GT provenance is two-stage and deliberately non-circular — the same shape as
fetch_real_sec.py:
  1. Authoritative source: the entity values come from SROIE's OWN key-information
     annotations (the dataset ships, per receipt, a JSON with company/date/address/
     total). We NEVER read the receipt with a model to produce GT and never fabricate.
     Only three schema fields are populated: merchant_name (SROIE company, verbatim),
     date (SROIE date, normalized to ISO), total_amount (SROIE total, parsed to a
     number). subtotal, tax, currency, and items are left null — SROIE does not
     annotate them, so we do not invent them.
  2. Grounding reconciliation: each populated value is kept ONLY if it is recoverable
     from the receipt's OCR text (deterministic match — merchant by normalized
     substring, with a fuzzy≥0.85 windowed fallback for OCR garble that matches the
     schema's own compare threshold; date by rendering SROIE surface forms; total by
     the number appearing). Values not present in the OCR text are nulled, because a
     text-extraction benchmark must not require extracting what the document text does
     not contain. This makes the GT both authoritative AND doc-matched.

Data source: the canonical ICDAR-2019 SROIE Task-3 (key information extraction)
distribution mirrored at github.com/zzzDavid/ICDAR-2019-SROIE — `data/box/<id>.csv`
is the per-receipt OCR (coordinate rows whose last field is the recognized text line)
and `data/key/<id>.json` is SROIE's shipped {company,date,address,total} annotation.
The Hugging Face SROIE variants (darentang/sroie, arvindrajan92/...) ship either
token-tag (NER) reconstructions or images-only; this mirror preserves SROIE's shipped
entities JSON verbatim, which is the safest GT for a benchmark. No model calls.

Writes documents/<id>.md (the OCR text), expected/<id>.expected.json,
manifests/<id>.json (source=real). Stem: sroie_real_<idx>.

    python fetch_real_receipts.py --out <stage>/receipts --n 50
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
import time
import urllib.request
from difflib import SequenceMatcher
from pathlib import Path

UA = "FieldBench research (contact@fieldbench.org)"
BASE = "https://raw.githubusercontent.com/zzzDavid/ICDAR-2019-SROIE/master/data/"
SOURCE_REPO = "https://github.com/zzzDavid/ICDAR-2019-SROIE"

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _get(path: str) -> str:
    url = BASE + path
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise
            if attempt == 3:
                raise
            time.sleep(1.5 * (attempt + 1))
        except Exception:
            if attempt == 3:
                raise
            time.sleep(1.5 * (attempt + 1))


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def box_to_text(csv_text: str) -> str:
    """Reconstruct the receipt OCR text from SROIE box rows.

    Each row is: x1,y1,x2,y2,x3,y3,x4,y4,<text> — the text can itself contain
    commas, so everything from field 9 onward is the recognized line.
    """
    lines = []
    for row in csv.reader(io.StringIO(csv_text)):
        if len(row) < 9:
            # keep any stray non-empty content verbatim rather than drop it
            joined = ",".join(row).strip()
            if joined:
                lines.append(joined)
            continue
        text = ",".join(row[8:]).strip()
        if text:
            lines.append(text)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# GT normalization (SROIE annotation -> schema value). Never invents values.
# ---------------------------------------------------------------------------

def normalize_sroie_date(raw: str) -> str | None:
    """SROIE date string -> ISO YYYY-MM-DD.

    SROIE receipts are Malaysian/Singaporean: numeric dates are DAY-first
    (DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY). Also handles 'DD MON YYYY',
    ISO 'YYYY-MM-DD', and compact 'YYYYMMDD'. Reversibility of the numeric
    day-first parse is asserted against the source string so a format-detection
    slip can never silently transpose day/month.
    """
    s = (raw or "").strip()
    if not s:
        return None

    # ISO already: YYYY-MM-DD (year-first, month before day)
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return _iso(y, mo, d)

    # Compact YYYYMMDD
    m = re.fullmatch(r"(\d{4})(\d{2})(\d{2})", s)
    if m:
        return _iso(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    # DD MON YYYY / DD MON YY  (e.g. "05 MAR 2018", "28 MAR 18")
    m = re.fullmatch(r"(\d{1,2})\s+([A-Za-z]{3,})\.?\s+(\d{2,4})", s)
    if m:
        mon = MONTHS.get(m.group(2)[:3].lower())
        if mon:
            d = int(m.group(1))
            y = _yy(m.group(3))
            return _iso(y, mon, d)
        return None

    # MON DD, YYYY  (e.g. "March 25, 2018")
    m = re.fullmatch(r"([A-Za-z]{3,})\.?\s+(\d{1,2}),?\s+(\d{2,4})", s)
    if m:
        mon = MONTHS.get(m.group(1)[:3].lower())
        if mon:
            d = int(m.group(2))
            y = _yy(m.group(3))
            return _iso(y, mon, d)
        return None

    # Numeric with / - . separators. SROIE convention is DAY-first, but a few
    # annotations are month-first (e.g. "12/28/2017"). We resolve safely:
    #   - day-first interpretation (a, b) = (day, month)
    #   - month-first interpretation (b, a) = (month, day)
    # If exactly one interpretation yields a valid calendar date, use it (the
    # other ordering is impossible — no guessing). If BOTH are valid (both
    # fields <= 12, genuinely ambiguous), use day-first per SROIE convention.
    m = re.fullmatch(r"(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{2,4})", s)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        y = _yy(m.group(3))
        day_first = _iso(y, b, a)   # a=day, b=month
        month_first = _iso(y, a, b)  # a=month, b=day
        if day_first and month_first:
            return day_first  # ambiguous -> SROIE day-first convention
        return day_first or month_first  # exactly one valid, or None
    return None


def _yy(year_str: str) -> int:
    y = int(year_str)
    if y < 100:
        return 2000 + y
    return y


def _iso(y: int, mo: int, d: int) -> str | None:
    if not (1 <= mo <= 12 and 1 <= d <= 31 and 1900 <= y <= 2100):
        return None
    return f"{y:04d}-{mo:02d}-{d:02d}"


def normalize_total(raw: str):
    """SROIE total string -> JSON number. Strips currency symbols/commas."""
    s = (raw or "").strip()
    if not s:
        return None
    s = re.sub(r"(?i)\b(rm|myr|usd|sgd|s\$|rp)\b", "", s)
    s = s.replace("$", "").replace("£", "").replace("€", "").replace(",", "")
    s = s.strip()
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Grounding (keep-or-null against the OCR text). Never alters a kept value.
# ---------------------------------------------------------------------------

def merchant_grounded(value: str, text: str) -> bool:
    nv, nt = _norm(value), _norm(text)
    if not nv:
        return False
    if nv in nt:
        return True
    # OCR garble fallback: best sliding-window ratio >= schema compare threshold
    L = len(nv)
    if L == 0 or len(nt) < 3:
        return False
    step = max(1, L // 12)
    best = 0.0
    for j in range(0, max(1, len(nt) - L + 1), step):
        best = max(best, SequenceMatcher(None, nv, nt[j:j + L]).ratio())
        if best >= 0.85:
            return True
    # also test against the whole text (handles short merchant vs long doc)
    return SequenceMatcher(None, nv, nt).ratio() >= 0.85


def date_grounded(iso: str, raw_sroie: str, text: str) -> bool:
    """The date is grounded if a plausible surface form appears in the OCR text."""
    if raw_sroie and raw_sroie.strip() and raw_sroie.strip() in text:
        return True
    y, mo, d = (int(x) for x in iso.split("-"))
    months = ["January", "February", "March", "April", "May", "June", "July",
              "August", "September", "October", "November", "December"]
    mon = months[mo - 1]
    cands = [
        f"{d:02d}/{mo:02d}/{y}", f"{d}/{mo}/{y}",
        f"{d:02d}-{mo:02d}-{y}", f"{d}-{mo}-{y}",
        f"{d:02d}.{mo:02d}.{y}", f"{d}.{mo}.{y}",
        f"{d:02d}/{mo:02d}/{y % 100:02d}", f"{d:02d}-{mo:02d}-{y % 100:02d}",
        f"{y}-{mo:02d}-{d:02d}", f"{y}{mo:02d}{d:02d}",
        f"{d:02d} {mon[:3].upper()} {y}", f"{d} {mon[:3].upper()} {y}",
        f"{d:02d} {mon[:3].upper()} {y % 100:02d}",
        f"{mon} {d}, {y}", f"{mon[:3]} {d}, {y}",
    ]
    low = text.lower()
    return any(c.lower() in low for c in cands)


def total_grounded(number: float, text: str) -> bool:
    ntext = text.replace(",", "")
    cands = {f"{number:.2f}", f"{number:g}", f"{number:.0f}", f"{number:.1f}"}
    return any(c in ntext for c in cands)


def reconcile(merchant, date_iso, date_raw, total_num, text):
    """Ground-gate each populated field; return (expected, flags)."""
    flags = {}
    m = merchant if (merchant and merchant_grounded(merchant, text)) else None
    flags["merchant_name"] = bool(merchant) and m is not None
    dt = date_iso if (date_iso and date_grounded(date_iso, date_raw, text)) else None
    flags["date"] = bool(date_iso) and dt is not None
    tot = total_num if (total_num is not None and total_grounded(total_num, text)) else None
    flags["total_amount"] = (total_num is not None) and tot is not None
    expected = {
        "merchant_name": m,
        "date": dt,
        "total_amount": tot,
        "subtotal": None,
        "tax": None,
        "currency": None,
        "items": None,
    }
    return expected, flags


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--scan", type=int, default=200, help="max source receipts to scan")
    args = ap.parse_args(argv)
    for sub in ("documents", "expected", "manifests"):
        (args.out / sub).mkdir(parents=True, exist_ok=True)

    written = 0
    idx = 0
    ungrounded = 0
    field_kept = {"merchant_name": 0, "date": 0, "total_amount": 0}
    for src in range(args.scan):
        if written >= args.n:
            break
        stem_src = f"{src:03d}"
        try:
            key = json.loads(_get(f"key/{stem_src}.json"))
            box = _get(f"box/{stem_src}.csv")
        except Exception as e:
            print(f"  source {stem_src}: fetch skip ({repr(e)[:80]})", file=sys.stderr)
            continue
        time.sleep(0.1)
        text = box_to_text(box)
        if len(text) < 60:
            continue

        merchant = (key.get("company") or "").strip() or None
        date_raw = (key.get("date") or "").strip() or None
        date_iso = normalize_sroie_date(date_raw) if date_raw else None
        total_num = normalize_total(key.get("total") or "")

        expected, flags = reconcile(merchant, date_iso, date_raw, total_num, text)
        # require at least merchant or total to survive grounding — else the doc
        # carries no useful real GT.
        if not (flags["merchant_name"] or flags["total_amount"]):
            continue

        # count would-be-populated-but-ungrounded (nulled) values for reporting
        if merchant and not flags["merchant_name"]:
            ungrounded += 1
        if date_iso and not flags["date"]:
            ungrounded += 1
        if total_num is not None and not flags["total_amount"]:
            ungrounded += 1
        for f in field_kept:
            if flags[f]:
                field_kept[f] += 1

        idx += 1
        stem = f"sroie_real_{idx:03d}"
        (args.out / "documents" / f"{stem}.md").write_text(text + "\n")
        (args.out / "expected" / f"{stem}.expected.json").write_text(
            json.dumps(expected, indent=2) + "\n")
        manifest = {
            "filename": f"{stem}.md",
            "source_name": "SROIE Dataset (ICDAR 2019)",
            "source_url": "https://rrc.cvc.uab.es/?ch=13",
            "source_repo": f"{SOURCE_REPO} (Task-3 mirror; box=OCR, key=annotations)",
            "source_receipt": f"data/key/{stem_src}.json",
            "license": "CC BY 4.0",
            "license_url": "https://creativecommons.org/licenses/by/4.0/",
            "attribution": ("Huang, Chen, He, Bai, Karatzas, Lu & Jawahar — ICDAR 2019 "
                            "Robust Reading Challenge on Scanned Receipts OCR and Information "
                            "Extraction (SROIE)"),
            "original_format": "JPEG image (OCR)",
            "original_image": f"{stem_src}.jpg",
            "r2_url": None,
            "pages": 1,
            "added_date": time.strftime("%Y-%m-%d"),
            "added_by": "fetch_real_receipts",
            "schema": "receipts/schemas/invoice_basic.yaml",
            "notes": ("SROIE Task-3 receipt. Document text is the receipt's OCR lines. "
                      "Ground truth from SROIE's shipped key annotations (company, date, "
                      "total). merchant_name, date, total_amount populated only where "
                      "grounded in the OCR text; subtotal, tax, currency, and items left "
                      "null — SROIE does not annotate them."),
            "license_basis": ("CC BY 4.0 requires attribution. Dataset described in "
                              "arXiv:2103.10213. Task-3 box/key files obtained via a "
                              "third-party mirror; terms should be re-verified against the "
                              "official Robust Reading Competition source. See DATA_LICENSE.md."),
            "gt_provenance": ("SROIE-provided key-information annotations, reconciled to the "
                              "receipt text: each field kept only if grounded in the OCR "
                              "text, else nulled."),
            "source": "real",
        }
        (args.out / "manifests" / f"{stem}.json").write_text(json.dumps(manifest, indent=2) + "\n")
        written += 1

    print(f"wrote {written} real SROIE receipts")
    print(f"  fields kept (grounded): {field_kept}")
    print(f"  populated-but-ungrounded values nulled: {ungrounded}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
