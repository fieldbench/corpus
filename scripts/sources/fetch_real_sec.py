#!/usr/bin/env python3
"""Fetch REAL SEC filings + AUTHORITATIVE, DOC-GROUNDED ground truth.

GT provenance is two-stage and deliberately non-circular:
  1. Authoritative anchor: filer name, form type, filing date, and period-of-report
     come from EDGAR's own structured submissions index (data.sec.gov) — never from
     reading the document, never from a model.
  2. Grounding reconciliation: each authoritative value is kept ONLY if it is
     recoverable from the extractable document text (deterministic match — dates by
     rendering, strings by normalized substring). Values not present in the text are
     nulled, because a text-extraction benchmark must not require extracting what the
     document does not contain. This makes the GT both authoritative AND doc-matched.

Writes documents/<id>.md, expected/<id>.expected.json, manifests/<id>.json (source=real).

    python fetch_real_sec.py --out <corpus>/sec_filings --n 50
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path.home() / "dev/fieldbench/fieldbench/src"))
from fieldbench.scoring import normalize_date, to_number  # noqa: E402
from markdownify import markdownify as md  # noqa: E402

UA = "FieldBench research (contact@fieldbench.org)"
# Keep the corpus apolitical: skip any filing whose text names a political figure
# (they appear incidentally in large-cap risk factors / director bios, but read as
# political). EDGAR is vast, so dropping these costs nothing.
POLITICAL = re.compile(
    r"\b(trump|biden|obama|pence|desantis|pelosi|mcconnell|kamala|"
    r"hillary\s+clinton|president\s+clinton|george\s+w\.?\s+bush)\b"
    r"|trumprx", re.I)
# A spread of filers across size/sector so metadata isn't monoculture.
CIKS = [
    320193, 789019, 1018724, 1652044, 1045810, 200406, 21344, 51143, 40545,
    354950, 1090872, 731766, 78003, 310158, 66740, 97476, 858877, 909832,
    19617, 72971, 34088, 104169, 80424, 1103982, 64040, 313616, 936468,
    1467373, 796343, 1341439,
    # broader set (consumer staples / industrials / REITs — less policy-heavy)
    27419, 60667, 320187, 63908, 829224, 1048911, 18230, 315189, 773840,
    100885, 277948, 92122, 56873, 21665, 55785, 40704, 55067, 47111, 91142,
    1755672, 320335, 726728, 874716, 30625, 875045, 1090727, 764478, 106040,
]
# Form -> which period field the EDGAR reportDate maps to for that form.
FORM_PERIOD = {
    "10-K": "period_fiscal_year_end",
    "10-Q": "period_quarter_end",
    "8-K": "period_date_of_report",
    "DEF 14A": "period_meeting_date",
    "S-1": None,
}
WANT = list(FORM_PERIOD)


def _get(url: str, binary=False):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read()
                return data if binary else data.decode("utf-8", "replace")
        except Exception:
            if attempt == 3:
                raise
            time.sleep(1.5 * (attempt + 1))


def _string_grounded(value: str, doc: str) -> bool:
    norm = lambda s: re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()
    v = norm(value)
    if not v:
        return False
    # try the full value, then drop common corporate suffixes for a looser match
    if v in norm(doc):
        return True
    stripped = re.sub(r"\b(inc|corp|corporation|company|co|ltd|llc|plc|lp)\b", "", v).strip()
    return bool(stripped) and stripped in norm(doc)


def _date_grounded(iso: str, doc: str) -> bool:
    nd = normalize_date(iso)
    if not nd:
        return False
    y, m, d = iso.split("-")
    months = ["January", "February", "March", "April", "May", "June", "July",
              "August", "September", "October", "November", "December"]
    mon = months[int(m) - 1]
    # candidate surface forms an EDGAR filing might print (incl. the odd "31 , 2025" spacing)
    cands = [
        f"{mon} {int(d)}, {y}", f"{mon} {int(d)} , {y}", f"{mon} {int(d)},{y}",
        f"{int(m)}/{int(d)}/{y}", f"{int(m):02d}/{int(d):02d}/{y}",
        f"{y}-{m}-{d}", f"{mon[:3]} {int(d)}, {y}", f"{int(d)} {mon} {y}",
    ]
    low = doc.lower()
    return any(c.lower() in low for c in cands)


def reconcile(expected: dict, doc: str) -> tuple[dict, dict]:
    """Ground-gate each field; return (grounded_gt, per_field_grounded_flags)."""
    out, flags = {}, {}
    for field, val in expected.items():
        if val is None:
            out[field] = None
            continue
        if field.endswith("_date") or field.startswith("period_"):
            ok = _date_grounded(val, doc)
        elif field == "form_type":
            ok = re.search(re.escape(val).replace(r"\ ", r"\s*"), doc, re.I) is not None
        else:  # filer_name and other strings
            ok = _string_grounded(val, doc)
        flags[field] = ok
        out[field] = val if ok else None
    return out, flags


def fetch_filings(cik: int):
    sub = json.loads(_get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json"))
    name = sub.get("name", "")
    recent = sub["filings"]["recent"]
    rows = []
    for i, form in enumerate(recent["form"]):
        if form not in WANT:
            continue
        rows.append({
            "name": name, "form": form,
            "filingDate": recent["filingDate"][i],
            "reportDate": recent["reportDate"][i] or None,
            "accession": recent["accessionNumber"][i],
            "primaryDocument": recent["primaryDocument"][i],
        })
    return rows


def build_expected(row: dict) -> dict:
    exp = {
        "filer_name": _titlecase_filer(row["name"]),
        "form_type": row["form"],
        "filing_date": row["filingDate"] or None,
        "period_fiscal_year_end": None,
        "period_quarter_end": None,
        "period_date_of_report": None,
        "period_meeting_date": None,
    }
    pf = FORM_PERIOD.get(row["form"])
    if pf and row["reportDate"]:
        exp[pf] = row["reportDate"]
    return exp


def _titlecase_filer(name: str) -> str:
    # EDGAR stores names uppercase; the cover page is usually Title Case or as-is.
    # Keep as EDGAR gives it; the scorer is case/punct tolerant, and grounding checks
    # a normalized (case-insensitive) form.
    return name


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--per-form-cap", type=int, default=16, help="max docs per form type (variety)")
    ap.add_argument("--per-cik-cap", type=int, default=4, help="max docs per filer (variety)")
    ap.add_argument("--max-chars", type=int, default=200000)
    args = ap.parse_args(argv)
    for sub in ("documents", "expected", "manifests"):
        (args.out / sub).mkdir(parents=True, exist_ok=True)

    written = 0
    form_counts = {f: 0 for f in WANT}
    idx = 0
    for cik in CIKS:
        if written >= args.n:
            break
        try:
            rows = fetch_filings(cik)
        except Exception as e:
            print(f"  CIK {cik}: fetch failed ({e})", file=sys.stderr)
            continue
        time.sleep(0.3)
        cik_written = 0
        for row in rows:
            if written >= args.n or cik_written >= args.per_cik_cap:
                break
            if form_counts[row["form"]] >= args.per_form_cap:
                continue
            acc_nodash = row["accession"].replace("-", "")
            doc_url = (f"https://www.sec.gov/Archives/edgar/data/{cik}/"
                       f"{acc_nodash}/{row['primaryDocument']}")
            try:
                html = _get(doc_url)
            except Exception as e:
                print(f"  doc fetch failed {doc_url}: {e}", file=sys.stderr)
                continue
            time.sleep(0.3)
            text = md(html, heading_style="ATX", strip=["script", "style"])
            text = re.sub(r"\n{3,}", "\n\n", text).strip()[:args.max_chars]
            if len(text) < 500:
                continue
            if POLITICAL.search(text):
                continue  # keep the corpus apolitical
            expected_auth = build_expected(row)
            expected, flags = reconcile(expected_auth, text)
            # require the two cover-page anchors to be grounded, else skip the doc
            if not (flags.get("filer_name") and flags.get("form_type")):
                continue
            idx += 1
            stem = f"edgar_real_{idx:03d}"
            (args.out / "documents" / f"{stem}.md").write_text(text)
            (args.out / "expected" / f"{stem}.expected.json").write_text(
                json.dumps(expected, indent=2) + "\n")
            manifest = {
                "id": stem,
                "source_name": "SEC EDGAR",
                "source_url": doc_url,
                "license": "Public disclosure record",
                "schema": "sec_filings/schemas/filing_metadata.yaml",
                "document": f"documents/{stem}.md",
                "expected": f"expected/{stem}.expected.json",
                "attribution": "U.S. SEC EDGAR — public company filing.",
                "license_basis": ("Not a US Government work: 17 U.S.C. 105 does not apply "
                                  "(authored by the registrant, not the SEC). Redistributed "
                                  "as a public disclosure record. See DATA_LICENSE.md."),
                "gt_provenance": ("Authoritative EDGAR submissions index, reconciled to the "
                                  "document text: each field kept only if grounded in the "
                                  "extractable text, else nulled."),
                "source": "real",
            }
            (args.out / "manifests" / f"{stem}.json").write_text(json.dumps(manifest, indent=2) + "\n")
            form_counts[row["form"]] += 1
            written += 1
            cik_written += 1
    print(f"wrote {written} real SEC docs; form distribution: {form_counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
