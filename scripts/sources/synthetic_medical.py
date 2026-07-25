#!/usr/bin/env python3
"""Synthetic discharge-summary generator — matched-pair partner for the REAL
MTSamples medical_records docs.

Purpose: the published corpus has medical_records as 100% real. To measure the
synthetic-vs-real accuracy gap *holding category (schema, difficulty class)
constant*, we add clean, templated synthetic discharge summaries against the SAME
`discharge_summary.yaml` schema. Real and synthetic then differ only in
provenance/formatting, not in what is being extracted — the controlled comparison
§6.3 needs.

Deterministic (seeded). Emits documents/<id>.md, expected/<id>.expected.json,
manifests/<id>.json with source=synthetic, license CC0.

    python synthetic_medical.py --out <corpus>/medical_records --n 40 [--seed N]
"""
from __future__ import annotations

import argparse
import json
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 70241  # distinct from other generators

FIRST = ["James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael",
         "Linda", "David", "Barbara", "William", "Elizabeth", "Richard", "Susan",
         "Joseph", "Margaret", "Thomas", "Dorothy", "Charles", "Nancy"]
LAST = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
        "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
        "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin"]

# (primary_diagnosis, [candidate procedures], [candidate discharge meds])
CASES = [
    ("Acute myocardial infarction",
     ["Cardiac catheterization", "Percutaneous coronary intervention", "Coronary angioplasty"],
     ["Aspirin", "Atorvastatin", "Metoprolol", "Clopidogrel", "Lisinopril"]),
    ("Community-acquired pneumonia",
     ["Bronchoscopy", "Thoracentesis"],
     ["Azithromycin", "Ceftriaxone", "Albuterol", "Prednisone"]),
    ("Congestive heart failure exacerbation",
     ["Echocardiography", "Right heart catheterization"],
     ["Furosemide", "Carvedilol", "Spironolactone", "Lisinopril"]),
    ("Diabetic ketoacidosis",
     ["Central line placement"],
     ["Insulin glargine", "Insulin lispro", "Metformin", "Potassium chloride"]),
    ("Ischemic stroke",
     ["Thrombolysis", "Carotid endarterectomy", "CT angiography"],
     ["Aspirin", "Atorvastatin", "Clopidogrel", "Amlodipine"]),
    ("Chronic obstructive pulmonary disease exacerbation",
     ["Bronchoscopy"],
     ["Prednisone", "Tiotropium", "Albuterol", "Azithromycin"]),
    ("Acute appendicitis",
     ["Laparoscopic appendectomy"],
     ["Cefazolin", "Metronidazole", "Acetaminophen", "Ondansetron"]),
    ("Sepsis secondary to urinary tract infection",
     ["Central venous catheter placement"],
     ["Piperacillin-tazobactam", "Vancomycin", "Norepinephrine"]),
    ("Gastrointestinal hemorrhage",
     ["Upper endoscopy", "Colonoscopy"],
     ["Pantoprazole", "Octreotide", "Ferrous sulfate"]),
    ("Total knee arthroplasty",
     ["Right total knee replacement"],
     ["Enoxaparin", "Oxycodone", "Acetaminophen", "Celecoxib"]),
    ("Acute cholecystitis",
     ["Laparoscopic cholecystectomy"],
     ["Cefazolin", "Ketorolac", "Ondansetron"]),
    ("Atrial fibrillation with rapid ventricular response",
     ["Electrical cardioversion", "Transesophageal echocardiography"],
     ["Diltiazem", "Apixaban", "Metoprolol"]),
]


def _iso(d: date) -> str:
    return d.isoformat()


def _mdy(d: date) -> str:
    return d.strftime("%m/%d/%Y")


def _render_clean(rng, patient, dr, admit, disc, dx, procedures, meds, age, sex, los):
    """Realism 0 — templated, one labeled fact per line. Trivially extractable;
    the conventional-synthetic extreme."""
    lines = [
        "# Discharge Summary", "",
        f"**Patient:** {patient}",
        f"**Attending:** {dr}",
        f"**Admission Date:** {_mdy(admit)}",
        f"**Discharge Date:** {_mdy(disc)}", "",
        "## History of Present Illness",
        f"The patient is a {age}-year-old {sex} admitted for management of {dx.lower()}.",
        f"The hospital course spanned {los} days and was managed by {dr}.", "",
        "## Principal Diagnosis", dx, "", "## Procedures",
    ]
    for p in procedures:
        lines.append(f"- {p}")
    lines += ["", "## Discharge Medications"]
    for m in meds:
        dose = rng.choice(["once daily", "twice daily", "every 8 hours", "at bedtime"])
        lines.append(f"- {m} {dose}")
    lines += ["", "## Discharge Condition",
              "Stable and improved. The patient was discharged home in good condition "
              "with instructions to follow up with the attending physician.",
              "", f"Dictated by {dr}."]
    return "\n".join(lines) + "\n"


COMORBID = ["Hypertension", "Type 2 diabetes mellitus", "Hyperlipidemia", "GERD",
            "Hypothyroidism", "Chronic kidney disease stage 3", "Anxiety disorder",
            "Osteoarthritis", "Obstructive sleep apnea", "Benign prostatic hyperplasia"]
# Distractor meds for the "on transfer/admission" list — NOT the discharge meds.
TRANSFER_MEDS = ["Heparin", "Docusate", "Ondansetron", "Pantoprazole", "Acetaminophen",
                 "Multivitamin", "Famotidine", "Sliding-scale insulin", "Senna"]


def _render_realistic(rng, patient, dr, admit, disc, dx, procedures, meds, age, sex, los):
    """Realism 1 — MTSamples-grade difficulty. The GT values are all present and
    determinable, but buried among strong same-type distractors that mirror how real
    discharge summaries actually mislead an extractor:
      - admission/discharge dates sit inside a comma-mangled HOSPITAL COURSE run-on
        alongside a surgery date and 2-3 lab/study dates, DOB, and a follow-up date;
      - the transfer-medication list (a DIFFERENT drug set) precedes the true discharge
        meds — the classic trap where a model grabs the wrong list;
      - the primary diagnosis is item 1 of a numbered DISCHARGE DIAGNOSES list whose
        other items are comorbidities;
      - the attending (GT) competes with a surgeon and a consulting physician."""
    dob = admit - timedelta(days=rng.randint(20000, 32000))
    surg = admit + timedelta(days=rng.randint(0, max(1, los - 1)))
    lab1 = admit + timedelta(days=rng.randint(1, max(1, los - 1)))
    lab2 = admit + timedelta(days=rng.randint(1, max(1, los - 1)))
    followup = disc + timedelta(days=rng.randint(7, 30))
    surgeon = f"Dr. {rng.choice(LAST)}"       # distractor physician
    consultant = f"Dr. {rng.choice(LAST)}"    # distractor physician
    secondary = rng.sample(COMORBID, k=rng.randint(2, 4))
    transfer = rng.sample([m for m in TRANSFER_MEDS if m not in meds],
                          k=rng.randint(3, 5))
    proc_prose = " and ".join(procedures).lower()
    dxlist = ",".join(f"{i}. {d}." for i, d in enumerate([dx] + secondary, start=1))
    para = (
        f"{patient} is a {age}-year-old {sex} (DOB {_mdy(dob)}).,ADMISSION/DISCHARGE:,"
        f"The patient was admitted {_mdy(admit)} and, following an uneventful course, "
        f"discharged {_mdy(disc)}.,HISTORY OF PRESENT ILLNESS:,The patient presented "
        f"with symptoms subsequently attributed to the principal problem below and was "
        f"taken to the operating room on {_mdy(surg)}, where {surgeon} performed "
        f"{proc_prose}.,MEDICATIONS ON TRANSFER:,{', '.join(transfer)}.,HOSPITAL "
        f"COURSE:,Over the ensuing {los} days the patient was managed by the attending "
        f"physician, {dr}, with {consultant} consulting.,A CBC obtained {_mdy(lab1)} "
        f"and a repeat metabolic panel on {_mdy(lab2)} were within normal limits.,"
        f"DISCHARGE DIAGNOSES:,{dxlist},DISCHARGE MEDICATIONS:,At discharge the patient "
        f"was instructed to take {', '.join(meds)}, and to discontinue the transfer "
        f"medications listed above.,DISPOSITION:,Discharged home in stable condition.,"
        f"FOLLOW-UP:,An appointment was scheduled with {dr} on {_mdy(followup)}.,"
        f"Dictated by {dr}, attending."
    )
    return f"# Discharge Summary\n\n{para}\n"


def make_doc(rng: random.Random, idx: int, realism: int = 0) -> tuple[str, dict, dict]:
    fn, ln = rng.choice(FIRST), rng.choice(LAST)
    patient = f"{fn} {ln}"
    dr = f"Dr. {rng.choice(LAST)}"
    dx, proc_pool, med_pool = rng.choice(CASES)
    age = rng.randint(28, 89)
    sex = rng.choice(["male", "female"])

    admit = date(2023, 1, 1) + timedelta(days=rng.randint(0, 700))
    los = rng.randint(2, 14)
    disc = admit + timedelta(days=los)

    procedures = rng.sample(proc_pool, k=rng.randint(1, min(2, len(proc_pool))))
    meds = rng.sample(med_pool, k=rng.randint(2, min(5, len(med_pool))))

    stem = f"synth-med-r{realism}-{idx:03d}"
    render = _render_clean if realism == 0 else _render_realistic
    doc = render(rng, patient, dr, admit, disc, dx, procedures, meds, age, sex, los)

    expected = {
        "admission_date": _iso(admit),
        "discharge_date": _iso(disc),
        "primary_diagnosis": dx,
        "procedures": procedures,
        "medications_at_discharge": meds,
        "attending_physician": dr,
    }
    manifest = {
        "id": stem,
        "source_name": "Synthetic generator (synthetic_medical.py)",
        "source_url": None,
        "license": "CC0-1.0",
        "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
        "schema": "medical_records/schemas/discharge_summary.yaml",
        "document": f"documents/{stem}.md",
        "expected": f"expected/{stem}.expected.json",
        "attribution": "Synthetic — no real patient data.",
        "license_basis": "Machine-generated synthetic document; released CC0.",
        "source": "synthetic",
    }
    return doc, expected, manifest


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, type=Path, help="medical_records category dir")
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
    print(f"wrote {args.n} synthetic discharge summaries to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
