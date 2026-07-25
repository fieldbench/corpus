#!/usr/bin/env python3
"""Synthetic contract generator — matched-pair partner for the REAL EDGAR
contracts docs.

Purpose: the published corpus sources contracts from SEC EDGAR material-contract
exhibits (all real). To measure the synthetic-vs-real accuracy gap *holding
category (schema, difficulty class) constant*, we add templated synthetic
agreements against the SAME `contract.yaml` schema. Real and synthetic then
differ only in provenance/formatting, not in what is being extracted — the
controlled comparison the paper needs.

Deterministic (seeded). Emits documents/<id>.md, expected/<id>.expected.json,
manifests/<id>.json with source=synthetic, license CC0.

    python synthetic_contracts.py --out <stage>/contracts --n 40 [--seed N] --realism {0,1}
"""
from __future__ import annotations

import argparse
import json
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 52001  # distinct from other generators

# ---- company / person name pools ------------------------------------------
COMPANY_BASE = [
    "Meridian", "Summit", "Pinnacle", "Cascade", "Vanguard", "Keystone",
    "Harbor Point", "Ironwood", "Blue Ridge", "Silverline", "Northgate",
    "Redwood", "Brightwater", "Stonebridge", "Clearfield", "Granite Peak",
    "Copperline", "Fairhaven", "Whitmore", "Aldergrove", "Beacon Hill",
    "Crestwood", "Dunmore", "Eastvale",
]
COMPANY_QUALIFIER = [
    "Technologies", "Industries", "Systems", "Holdings", "Capital",
    "Partners", "Logistics", "Networks", "Pharmaceuticals", "Energy",
    "Materials", "Ventures", "Group", "Labs", "Manufacturing", "Financial",
]
COMPANY_SUFFIX = ["Inc.", "LLC", "Corporation", "L.P.", "Ltd.", "Company"]

FIRST = ["James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael",
         "Linda", "David", "Barbara", "William", "Elizabeth", "Richard", "Susan",
         "Joseph", "Margaret", "Thomas", "Dorothy", "Charles", "Nancy"]
LAST = ["Sterling", "Hollis", "Ashford", "Bramwell", "Carrington", "Delacroix",
        "Ellery", "Fenwick", "Grantham", "Halloran", "Ingersoll", "Kingsley",
        "Lattimore", "Merrick", "Nashe", "Ottway", "Prentice", "Quill",
        "Radcliffe", "Sinclair"]
MIDDLE = ["A.", "B.", "C.", "D.", "E.", "F.", "G.", "H.", "J.", "K."]

# governing-law jurisdictions. (prefix, state); commonwealths use "Commonwealth".
JURISDICTIONS = [
    ("State", "Delaware"), ("State", "New York"), ("State", "California"),
    ("State", "Texas"), ("State", "Illinois"), ("State", "Florida"),
    ("State", "Georgia"), ("State", "Michigan"), ("State", "Ohio"),
    ("State", "New Jersey"), ("State", "Colorado"), ("State", "Washington"),
    ("State", "Minnesota"), ("State", "Tennessee"), ("State", "Maryland"),
    ("Commonwealth", "Pennsylvania"), ("Commonwealth", "Virginia"),
    ("Commonwealth", "Massachusetts"), ("Commonwealth", "Kentucky"),
]

# ---- per-contract-type configuration --------------------------------------
# each: titles (uppercase doc titles), prose_noun, party roles, party kinds.
# party kind "company" or "person"; parties list order == expected order.
CONTRACT_TYPES = [
    {
        "type": "Supply Agreement",
        "titles": ["MASTER SUPPLY AGREEMENT", "SUPPLY AGREEMENT"],
        "prose_noun": "Supply Agreement",
        "roles": ("Supplier", "Buyer"),
        "kinds": ("company", "company"),
    },
    {
        "type": "License Agreement",
        "titles": ["SOFTWARE LICENSE AGREEMENT", "TECHNOLOGY LICENSE AGREEMENT",
                   "LICENSE AGREEMENT"],
        "prose_noun": "License Agreement",
        "roles": ("Licensor", "Licensee"),
        "kinds": ("company", "company"),
    },
    {
        "type": "Employment Agreement",
        "titles": ["EXECUTIVE EMPLOYMENT AGREEMENT", "EMPLOYMENT AGREEMENT"],
        "prose_noun": "Employment Agreement",
        "roles": ("Executive", "Company"),
        "kinds": ("person", "company"),
    },
    {
        "type": "Credit Agreement",
        "titles": ["CREDIT AGREEMENT", "REVOLVING CREDIT AGREEMENT",
                   "LOAN AND SECURITY AGREEMENT"],
        "prose_noun": "Credit Agreement",
        "roles": ("Borrower", "Lender"),
        "kinds": ("company", "company"),
    },
    {
        "type": "Lease",
        "titles": ["COMMERCIAL LEASE AGREEMENT", "OFFICE LEASE AGREEMENT",
                   "LEASE AGREEMENT"],
        "prose_noun": "Lease",
        "roles": ("Landlord", "Tenant"),
        "kinds": ("company", "company"),
    },
    {
        "type": "Settlement Agreement",
        "titles": ["SETTLEMENT AGREEMENT AND RELEASE", "SETTLEMENT AGREEMENT"],
        "prose_noun": "Settlement Agreement and Release",
        "roles": ("Releasor", "Releasee"),
        "kinds": ("company", "company"),
    },
    {
        "type": "Merger Agreement",
        "titles": ["AGREEMENT AND PLAN OF MERGER", "MERGER AGREEMENT"],
        "prose_noun": "Agreement and Plan of Merger",
        "roles": ("Parent", "Company"),
        "kinds": ("company", "company"),
    },
    {
        "type": "Services Agreement",
        "titles": ["MASTER SERVICES AGREEMENT", "PROFESSIONAL SERVICES AGREEMENT",
                   "SERVICES AGREEMENT"],
        "prose_noun": "Master Services Agreement",
        "roles": ("Service Provider", "Client"),
        "kinds": ("company", "company"),
    },
    {
        "type": "Non-Disclosure Agreement",
        "titles": ["MUTUAL NON-DISCLOSURE AGREEMENT", "CONFIDENTIALITY AGREEMENT",
                   "NON-DISCLOSURE AGREEMENT"],
        "prose_noun": "Mutual Non-Disclosure Agreement",
        "roles": ("Disclosing Party", "Receiving Party"),
        "kinds": ("company", "company"),
    },
]


def _iso(d: date) -> str:
    return d.isoformat()


def _longdate(d: date) -> str:
    """Recognizable long form, no zero-padded day: 'June 5, 2008'."""
    return f"{d.strftime('%B')} {d.day}, {d.year}"


def _company(rng: random.Random) -> str:
    base = rng.choice(COMPANY_BASE)
    suffix = rng.choice(COMPANY_SUFFIX)
    if rng.random() < 0.75:
        return f"{base} {rng.choice(COMPANY_QUALIFIER)} {suffix}"
    return f"{base} {suffix}"


def _person(rng: random.Random) -> str:
    if rng.random() < 0.5:
        return f"{rng.choice(FIRST)} {rng.choice(MIDDLE)} {rng.choice(LAST)}"
    return f"{rng.choice(FIRST)} {rng.choice(LAST)}"


def _party(rng: random.Random, kind: str, used: set[str]) -> str:
    for _ in range(50):
        name = _person(rng) if kind == "person" else _company(rng)
        if name not in used:
            used.add(name)
            return name
    used.add(name)
    return name


def _governing(rng: random.Random) -> tuple[str, str]:
    """Returns (ground_truth_string, distractor_venue_string).

    ground_truth is e.g. 'State of Delaware' / 'Commonwealth of Virginia'.
    distractor names a DIFFERENT jurisdiction for the venue clause.
    """
    prefix, state = rng.choice(JURISDICTIONS)
    gt = f"{prefix} of {state}"
    while True:
        p2, s2 = rng.choice(JURISDICTIONS)
        if s2 != state:
            return gt, f"{p2} of {s2}"


# ---------------------------------------------------------------------------
def _render_clean(rng, cfg, p1, p2, effective, termination, governing):
    """Realism 0 — templated, one labeled fact per line. Trivially extractable;
    the conventional-synthetic extreme."""
    title = rng.choice(cfg["titles"])
    lines = [
        f"# {title}", "",
        f"**Contract Type:** {cfg['type']}",
        f"**Parties:** {p1}; {p2}",
        f"**Effective Date:** {_longdate(effective)}",
    ]
    if termination is not None:
        lines.append(f"**Termination Date:** {_longdate(termination)}")
    lines += [
        f"**Governing Law:** {governing}", "",
        "## Preamble",
        f"This {cfg['prose_noun']} (this \"Agreement\") is entered into "
        f"by and between {p1}, as {cfg['roles'][0]}, and {p2}, as "
        f"{cfg['roles'][1]}.", "",
        "## Term",
    ]
    if termination is not None:
        lines.append(
            f"This Agreement is effective as of {_longdate(effective)} and "
            f"shall remain in full force and effect until {_longdate(termination)}."
        )
    else:
        lines.append(
            f"This Agreement is effective as of {_longdate(effective)} and "
            f"shall continue until terminated by either party in accordance "
            f"with the provisions hereof."
        )
    lines += [
        "", "## Governing Law",
        f"This Agreement shall be governed by the laws of the {governing}.",
    ]
    return "\n".join(lines) + "\n"


def _render_realistic(rng, cfg, p1, p2, effective, termination, governing):
    """Realism 1 — facts embedded in dense legal prose with distractor dates
    (an execution/signature date, a recital letter-of-intent date) and a
    distractor jurisdiction in the venue clause. The ground-truth values are
    all present and recoverable; they are just not labeled."""
    title = rng.choice(cfg["titles"])
    gt, venue = governing

    exec_date = effective + timedelta(days=rng.randint(1, 21))     # distractor
    recital_date = effective - timedelta(days=rng.randint(14, 120))  # distractor
    role1, role2 = cfg["roles"]

    body = (
        f"# {title}\n\n"
        f"This {cfg['prose_noun']} (this “Agreement”), is made and "
        f"entered into as of {_longdate(effective)}, by and between {p1} "
        f"(the “{role1}”), and {p2} (the “{role2}”). "
        f"Although executed and delivered by the parties on {_longdate(exec_date)}, "
        f"this Agreement shall be effective as of the date first written above.\n\n"
        f"RECITALS\n\n"
        f"WHEREAS, the parties entered into a non-binding letter of intent "
        f"dated {_longdate(recital_date)} setting forth the general terms of "
        f"their proposed arrangement; and WHEREAS, the parties now desire to "
        f"set forth the definitive terms and conditions governing their "
        f"relationship as {role1} and {role2}; NOW, THEREFORE, in "
        f"consideration of the mutual covenants set forth herein, the parties "
        f"agree as follows:\n\n"
        f"1. TERM. "
    )

    if termination is not None:
        years = max(1, round((termination - effective).days / 365))
        body += (
            f"The term of this Agreement shall commence on the Effective Date "
            f"and, unless earlier terminated in accordance with the provisions "
            f"hereof, shall continue for an initial term of approximately "
            f"{years} year(s), expiring on {_longdate(termination)}.\n\n"
        )
    else:
        notice = rng.choice([30, 60, 90])
        body += (
            f"This Agreement shall commence on the Effective Date and shall "
            f"remain in full force and effect until terminated by either party "
            f"upon not less than {notice} days’ prior written notice to the "
            f"other party.\n\n"
        )

    body += (
        f"2. GOVERNING LAW; VENUE. This Agreement shall be governed by and "
        f"construed in accordance with the laws of the {gt}, without regard to "
        f"its conflict of laws principles. Notwithstanding the foregoing, the "
        f"parties agree that any action to enforce an arbitral award may, for "
        f"the convenience of the parties, be brought in the courts of the "
        f"{venue}.\n\n"
        f"IN WITNESS WHEREOF, the parties have caused this Agreement to be "
        f"executed by their duly authorized representatives as of the date "
        f"first written above.\n\n"
        f"{p1}\nBy: /s/ {_person(rng)}\n\n"
        f"{p2}\nBy: /s/ {_person(rng)}\n"
    )
    return body


def make_doc(rng: random.Random, idx: int, realism: int = 0) -> tuple[str, dict, dict]:
    cfg = rng.choice(CONTRACT_TYPES)

    used: set[str] = set()
    p1 = _party(rng, cfg["kinds"][0], used)
    p2 = _party(rng, cfg["kinds"][1], used)

    effective = date(2015, 1, 1) + timedelta(days=rng.randint(0, 3200))

    # termination often null (~45%). when present, a whole number of years out.
    if rng.random() < 0.55:
        years = rng.choice([1, 2, 3, 3, 5, 5, 7, 10])
        termination = effective + timedelta(days=365 * years)
    else:
        termination = None

    gov_gt, gov_venue = _governing(rng)

    stem = f"synth-contract-r{realism}-{idx:03d}"
    if realism == 0:
        doc = _render_clean(rng, cfg, p1, p2, effective, termination, gov_gt)
    else:
        doc = _render_realistic(rng, cfg, p1, p2, effective, termination,
                                (gov_gt, gov_venue))

    expected = {
        "contract_type": cfg["type"],
        "parties": [p1, p2],
        "effective_date": _iso(effective),
        "termination_date": _iso(termination) if termination is not None else None,
        "governing_law": gov_gt,
    }
    manifest = {
        "id": stem,
        "source_name": "Synthetic generator (synthetic_contracts.py)",
        "source_url": None,
        "license": "CC0-1.0",
        "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
        "schema": "contracts/schemas/contract.yaml",
        "document": f"documents/{stem}.md",
        "expected": f"expected/{stem}.expected.json",
        "attribution": "Synthetic — no real contract or party data.",
        "license_basis": "Machine-generated synthetic document; released CC0.",
        "source": "synthetic",
    }
    return doc, expected, manifest


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, type=Path, help="contracts category dir")
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
    print(f"wrote {args.n} synthetic contracts (realism {args.realism}) to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
