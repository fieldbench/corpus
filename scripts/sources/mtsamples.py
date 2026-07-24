#!/usr/bin/env python3
"""Source medical transcription samples from MTSamples (via Kaggle mirror on GitHub).

Downloads the MTSamples dataset (CC0 Public Domain), selects 100 diverse
samples across medical specialties, and creates corpus documents with
expected JSON and manifests.

Usage:
  uv run python scripts/sources/mtsamples.py
  python3 scripts/sources/mtsamples.py
"""

from __future__ import annotations

import csv
import io
import json
import re
import sys
import urllib.request
from pathlib import Path

CORPUS_ROOT = Path(__file__).resolve().parent.parent.parent
MED_DIR = CORPUS_ROOT / "medical_records"
DOCS_DIR = MED_DIR / "documents"
EXPECTED_DIR = MED_DIR / "expected"
MANIFESTS_DIR = MED_DIR / "manifests"

# GitHub mirrors of the Kaggle MTSamples dataset
DATASET_URL = "https://raw.githubusercontent.com/eshza/medicalTranscriptsKaggle/master/mtsamples.csv"

# Fallback URLs if primary doesn't work
FALLBACK_URLS = [
    "https://raw.githubusercontent.com/singla007/MTSamples/main/mtsamples.csv",
    "https://raw.githubusercontent.com/salgadev/medical-nlp/master/mtsamples.csv",
]

# Priority specialties and their target counts
# We want discharge summaries, consultation notes, operative reports, ED notes
# spread across specialties
PRIORITY_SPECIALTIES = {
    "Discharge Summary": 15,
    "Consult - History and Phy.": 10,
    "Surgery": 10,
    "Orthopedic": 8,
    "Cardiovascular / Pulmonary": 8,
    "Neurology": 7,
    "Gastroenterology": 7,
    "Emergency Room Reports": 5,
    "General Medicine": 5,
    "Radiology": 5,
    "Urology": 4,
    "Obstetrics / Gynecology": 4,
    "Nephrology": 3,
    "Hematology - Oncology": 3,
    "ENT - Otolaryngology": 3,
    "Psychiatry / Psychology": 3,
}

TOTAL_TARGET = 100


def download_dataset() -> str:
    """Download the CSV dataset, trying multiple mirrors."""
    urls = [DATASET_URL] + FALLBACK_URLS
    for url in urls:
        try:
            print(f"Trying {url}...")
            req = urllib.request.Request(url, headers={"User-Agent": "FieldBench-Corpus/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read().decode("utf-8")
                if len(data) > 1000:
                    print(f"  Downloaded {len(data)} bytes")
                    return data
        except Exception as e:
            print(f"  Failed: {e}")
    print("ERROR: Could not download dataset from any mirror.", file=sys.stderr)
    sys.exit(1)


def parse_csv(raw: str) -> list[dict]:
    """Parse the CSV into a list of dicts."""
    reader = csv.DictReader(io.StringIO(raw))
    rows = []
    for row in reader:
        rows.append(row)
    print(f"Parsed {len(rows)} total samples")
    return rows


def word_count(text: str | None) -> int:
    if not text:
        return 0
    return len(text.split())


def clean_text(text: str | None) -> str:
    if not text:
        return ""
    # Remove leading/trailing whitespace, normalize line endings
    text = text.strip()
    # Remove excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def slugify(name: str) -> str:
    """Create a filesystem-safe slug from a sample name."""
    s = name.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"-+", "-", s)
    s = s.strip("-")
    return s[:80] if s else "unnamed"


def select_samples(rows: list[dict]) -> list[dict]:
    """Select 100 diverse samples prioritizing certain specialties and longer texts."""
    # Normalize specialty field name (CSV might have different column names)
    # Common column names: medical_specialty, specialty
    specialty_key = None
    transcription_key = None
    name_key = None
    description_key = None
    keywords_key = None

    if rows:
        first = rows[0]
        keys = list(first.keys())
        print(f"CSV columns: {keys}")

        for k in keys:
            kl = k.lower().strip()
            if "specialty" in kl:
                specialty_key = k
            elif "transcription" in kl:
                transcription_key = k
            elif "sample_name" in kl or "sample" in kl:
                name_key = k
            elif "description" in kl:
                description_key = k
            elif "keyword" in kl:
                keywords_key = k

    if not transcription_key:
        print("ERROR: Could not find transcription column", file=sys.stderr)
        sys.exit(1)

    print(f"Using columns: specialty={specialty_key}, transcription={transcription_key}, "
          f"name={name_key}, description={description_key}")

    # Filter to samples with substantial transcriptions (500+ words)
    candidates = []
    for row in rows:
        text = row.get(transcription_key, "")
        wc = word_count(text)
        if wc >= 500:
            candidates.append((row, wc))

    print(f"Found {len(candidates)} samples with 500+ words")

    # Sort each specialty's candidates by word count (prefer longer/richer)
    by_specialty: dict[str, list[tuple[dict, int]]] = {}
    for row, wc in candidates:
        spec = (row.get(specialty_key, "") or "Unknown").strip()
        by_specialty.setdefault(spec, []).append((row, wc))

    for spec in by_specialty:
        by_specialty[spec].sort(key=lambda x: x[1], reverse=True)

    print(f"Specialties with 500+ word samples: {len(by_specialty)}")
    for spec, items in sorted(by_specialty.items(), key=lambda x: -len(x[1])):
        print(f"  {spec}: {len(items)} candidates")

    # Select from priority specialties first
    selected: list[dict] = []
    selected_indices: set[int] = set()

    for spec, target_count in PRIORITY_SPECIALTIES.items():
        # Find matching specialty (fuzzy match)
        matching_spec = None
        for s in by_specialty:
            if s.lower().strip() == spec.lower().strip():
                matching_spec = s
                break
            if spec.lower() in s.lower() or s.lower() in spec.lower():
                matching_spec = s
                break

        if not matching_spec:
            print(f"  Warning: No candidates for {spec}")
            continue

        available = by_specialty[matching_spec]
        count = 0
        for row, wc in available:
            if count >= target_count:
                break
            idx = id(row)
            if idx not in selected_indices:
                selected.append(row)
                selected_indices.add(idx)
                count += 1

    print(f"Selected {len(selected)} from priority specialties")

    # Fill remaining from other specialties, round-robin
    remaining = TOTAL_TARGET - len(selected)
    if remaining > 0:
        other_specs = [s for s in by_specialty if s not in
                       [k for k in PRIORITY_SPECIALTIES]]
        # Also include priority specs that have more samples
        all_remaining = []
        for spec_items in by_specialty.values():
            for row, wc in spec_items:
                if id(row) not in selected_indices:
                    all_remaining.append((row, wc))

        # Sort by word count, take the longest remaining
        all_remaining.sort(key=lambda x: x[1], reverse=True)
        for row, wc in all_remaining[:remaining]:
            selected.append(row)
            selected_indices.add(id(row))

    print(f"Final selection: {len(selected)} samples")
    return selected[:TOTAL_TARGET]


def extract_fields_from_transcription(text: str) -> dict:
    """Best-effort extraction of schema fields from transcription text.

    Since these are transcription reports (not structured EHR), many fields
    will be null. We do simple pattern matching for what's present.
    """
    result = {
        "admission_date": None,
        "discharge_date": None,
        "primary_diagnosis": None,
        "procedures": None,
        "medications_at_discharge": None,
        "attending_physician": None,
    }

    lines = text.split("\n")

    # Look for admission date
    for line in lines:
        m = re.search(r"(?:admission|admitted|admit)\s*(?:date)?[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", line, re.I)
        if m:
            result["admission_date"] = m.group(1).strip()
            break

    # Look for discharge date
    for line in lines:
        m = re.search(r"(?:discharge|discharged)\s*(?:date)?[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", line, re.I)
        if m:
            result["discharge_date"] = m.group(1).strip()
            break

    # Look for diagnosis
    diag_patterns = [
        r"(?:discharge|principal|primary|admitting)\s*diagnosis[:\s]*(.+)",
        r"diagnosis[:\s]*(.+)",
        r"(?:preoperative|postoperative)\s*diagnosis[:\s]*(.+)",
    ]
    for pat in diag_patterns:
        for line in lines:
            m = re.search(pat, line, re.I)
            if m:
                diag = m.group(1).strip().rstrip(".")
                if len(diag) > 3 and diag.lower() not in ("none", "n/a", "same"):
                    result["primary_diagnosis"] = diag
                    break
        if result["primary_diagnosis"]:
            break

    # Look for procedures - collect from PROCEDURE or OPERATION sections
    procedures = []
    in_proc_section = False
    proc_patterns = [
        r"(?:procedure|operation)\s*(?:performed|name)?[:\s]*(.+)",
        r"(?:name of procedure|procedures? performed)[:\s]*(.+)",
        r"(?:operative procedure|surgical procedure)[:\s]*(.+)",
    ]

    for line in lines:
        # Check for procedure in a labeled line
        for pat in proc_patterns:
            m = re.search(pat, line, re.I)
            if m:
                proc = m.group(1).strip().rstrip(".")
                if len(proc) > 3 and proc.lower() not in ("none", "n/a"):
                    procedures.append(proc)

    if procedures:
        result["procedures"] = procedures[:10]  # Cap at 10

    # Look for medications
    meds = []
    in_med_section = False
    for i, line in enumerate(lines):
        if re.search(r"(?:discharge\s+)?medications?|medications?\s+(?:on|at)\s+discharge", line, re.I):
            in_med_section = True
            # Check if meds are on the same line
            m = re.search(r"medications?[:\s]*(.+)", line, re.I)
            if m:
                med_text = m.group(1).strip()
                if len(med_text) > 3:
                    # Could be comma-separated or just one
                    for med in re.split(r"[,;]", med_text):
                        med = med.strip()
                        if med and len(med) > 2:
                            meds.append(med)
            continue

        if in_med_section:
            stripped = line.strip()
            if not stripped:
                if meds:
                    in_med_section = False
                continue
            # Check if we hit a new section header
            if re.match(r"^[A-Z][A-Z\s]{3,}:", stripped) or re.match(r"^[A-Z][A-Z\s]{5,}$", stripped):
                in_med_section = False
                continue
            # Parse medication entries (numbered or bulleted)
            med = re.sub(r"^\d+[\.\)]\s*", "", stripped)
            med = re.sub(r"^[-*]\s*", "", med)
            if med and len(med) > 2:
                # Extract just the medication name (first word(s) before dosage)
                med_name = re.split(r"\s+\d+\s*(?:mg|mcg|ml|units?|tablets?|capsules?|times)", med, maxsplit=1, flags=re.I)[0]
                meds.append(med_name.strip())

    if meds:
        result["medications_at_discharge"] = meds[:15]  # Cap at 15

    # Look for attending physician
    for line in lines:
        m = re.search(r"(?:attending|physician|dictated by|signed by)[:\s]*(?:Dr\.?\s*)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})", line, re.I)
        if m:
            result["attending_physician"] = m.group(1).strip()
            break

    return result


def make_sample_id(index: int, specialty: str, name: str) -> str:
    """Generate a unique sample ID."""
    spec_slug = slugify(specialty)[:20]
    name_slug = slugify(name)[:40]
    return f"mts-{index:03d}-{spec_slug}-{name_slug}"


def write_document(sample_id: str, row: dict, specialty_key: str | None,
                   transcription_key: str, name_key: str | None,
                   description_key: str | None, keywords_key: str | None) -> Path:
    """Write a markdown document for a sample."""
    specialty = (row.get(specialty_key, "") if specialty_key else "Unknown").strip()
    transcription = clean_text(row.get(transcription_key, ""))
    sample_name = (row.get(name_key, "") if name_key else "").strip()
    description = (row.get(description_key, "") if description_key else "").strip()
    keywords = (row.get(keywords_key, "") if keywords_key else "").strip()

    title = sample_name or f"{specialty} Report"

    md_parts = [
        f"# {title}",
        "",
        "---",
        f"**Specialty:** {specialty}",
    ]
    if description:
        md_parts.append(f"**Description:** {description}")
    if keywords:
        md_parts.append(f"**Keywords:** {keywords}")
    md_parts.extend([
        f"**Source:** MTSamples (Medical Transcription Samples)",
        "---",
        "",
        transcription,
    ])

    content = "\n".join(md_parts)
    path = DOCS_DIR / f"{sample_id}.md"
    path.write_text(content, encoding="utf-8")
    return path


def write_expected(sample_id: str, transcription: str) -> Path:
    """Write expected extraction JSON for a sample.

    Sets all fields to null — MTSamples transcriptions use non-standard
    formatting (comma-delimited sections) that breaks regex extraction.
    Re-annotate with the extract service for accurate ground truth:
      python scripts/auto_annotate.py --category medical_records
    """
    fields = {
        "admission_date": None,
        "discharge_date": None,
        "primary_diagnosis": None,
        "procedures": None,
        "medications_at_discharge": None,
        "attending_physician": None,
    }
    path = EXPECTED_DIR / f"{sample_id}.expected.json"
    path.write_text(json.dumps(fields, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def write_manifest(sample_id: str, row: dict, specialty_key: str | None,
                   transcription_key: str, name_key: str | None) -> Path:
    """Write manifest JSON for a sample."""
    specialty = (row.get(specialty_key, "") if specialty_key else "Unknown").strip()
    sample_name = (row.get(name_key, "") if name_key else "").strip()
    transcription = row.get(transcription_key, "")

    manifest = {
        "id": sample_id,
        "source_name": "MTSamples (Medical Transcription Samples)",
        "source_url": "https://www.kaggle.com/datasets/tboyle10/medicaltranscriptions",
        "original_source": "https://www.mtsamples.com/",
        "license": "CC0 (Public Domain)",
        "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
        "specialty": specialty,
        "sample_name": sample_name,
        "word_count": word_count(transcription),
        "schema": "discharge_summary",
        "document": f"documents/{sample_id}.md",
        "expected": f"expected/{sample_id}.expected.json",
    }

    path = MANIFESTS_DIR / f"{sample_id}.json"
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def main():
    # Ensure directories exist
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    EXPECTED_DIR.mkdir(parents=True, exist_ok=True)
    MANIFESTS_DIR.mkdir(parents=True, exist_ok=True)

    # Download dataset
    raw = download_dataset()
    rows = parse_csv(raw)

    if not rows:
        print("ERROR: No rows parsed from CSV", file=sys.stderr)
        sys.exit(1)

    # Detect column names
    first = rows[0]
    keys = list(first.keys())
    specialty_key = transcription_key = name_key = description_key = keywords_key = None
    for k in keys:
        kl = k.lower().strip()
        if "specialty" in kl:
            specialty_key = k
        elif "transcription" in kl:
            transcription_key = k
        elif "sample_name" in kl or (kl == "sample" and "name" not in kl):
            name_key = k
        elif "description" in kl:
            description_key = k
        elif "keyword" in kl:
            keywords_key = k

    if not transcription_key:
        print(f"ERROR: No transcription column found in {keys}", file=sys.stderr)
        sys.exit(1)

    # Select 100 diverse samples
    selected = select_samples(rows)

    # Write documents, expected JSON, and manifests
    written = 0
    for i, row in enumerate(selected, start=1):
        specialty = (row.get(specialty_key, "") if specialty_key else "Unknown").strip()
        sample_name = (row.get(name_key, "") if name_key else f"sample-{i}").strip()
        transcription = row.get(transcription_key, "")

        sample_id = make_sample_id(i, specialty, sample_name)

        doc_path = write_document(sample_id, row, specialty_key, transcription_key,
                                  name_key, description_key, keywords_key)
        exp_path = write_expected(sample_id, transcription)
        man_path = write_manifest(sample_id, row, specialty_key, transcription_key, name_key)

        written += 1
        if written % 10 == 0:
            print(f"  Written {written}/{len(selected)}...")

    print(f"\nDone! Wrote {written} samples:")
    print(f"  Documents: {DOCS_DIR}")
    print(f"  Expected:  {EXPECTED_DIR}")
    print(f"  Manifests: {MANIFESTS_DIR}")

    # Summary of specialties
    spec_counts: dict[str, int] = {}
    for row in selected:
        spec = (row.get(specialty_key, "") if specialty_key else "Unknown").strip()
        spec_counts[spec] = spec_counts.get(spec, 0) + 1

    print(f"\nSpecialty distribution ({len(spec_counts)} specialties):")
    for spec, count in sorted(spec_counts.items(), key=lambda x: -x[1]):
        print(f"  {spec}: {count}")


if __name__ == "__main__":
    main()
