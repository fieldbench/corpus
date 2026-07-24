# FieldBench Corpus

A cross-domain, field-level benchmark for **schema-driven document extraction**
(document → structured JSON). 1,114 documents across 12 categories with per-field
ground truth, released so extraction-accuracy claims become **falsifiable and
comparable**.

- **Scorer + run harness:** https://github.com/fieldbench/fieldbench (`pip install fieldbench`)
- **Read first:** [`DATASHEET.md`](DATASHEET.md) — composition, provenance, licensing, and limitations.

## ⚠️ Read before quoting any accuracy number

- **~94% of documents are extraction-from-clean-text, not rendered-page extraction**
  (only 5.7% came from an image or PDF). Parse-stage difficulty — OCR error, layout
  collapse, table-structure loss — is largely absent by construction. See
  [`docs/composition.md`](docs/composition.md).
- **Synthetic documents (~45%) overestimate accuracy** relative to real ones. Always
  report results **stratified by `source`** (real / synthetic).

## Layout

```
<category>/
  documents/<id>.md            # the markdown representation to extract from
  expected/<id>.expected.json  # ground-truth {field: value} map
  manifests/<id>.json          # provenance + source + original_format + schema ref
  schemas/<schema>.yaml        # field definitions for the category
```

12 categories: `sec_filings`, `invoices`, `insurance_claims`, `insurance_policies`,
`contracts`, `medical_records`, `insurance_certificates`, `legal_filings`, `receipts`,
`irs_forms`, `adversarial`, `multi_format`.

## Score a system

Produce one prediction file per document (`<id>.json`, a flat `{field: value}` map),
then score with the canonical type-aware scorer:

```bash
pip install fieldbench
fieldbench score --corpus . --results <your-predictions>/
```

The scorer reports overall accuracy, a real-vs-synthetic split, a four-way null
breakdown (match / miss / hallucination / correct-absence), and per-category results.

## Licensing

Ground-truth annotations, schemas, and tooling are freely licensed (see `LICENSE`).
**Document licensing is per-source** — see [`ATTRIBUTION.md`](ATTRIBUTION.md): synthetic
CC0; SEC EDGAR public disclosure; SROIE CC BY 4.0; MTSamples educational-use with
attribution; CourtListener / Caselaw Access public domain; government forms public
domain. ACORD/ISO copyrighted insurance form layouts are **not** included — those
categories use functionally-equivalent synthetic documents.

## Tooling (`scripts/`)

- `sources/` — deterministic synthetic-document generators.
- `composition_report.py` — regenerate the input-composition disclosure.
- `iaa_harness.py` — inter-annotator-agreement sampling + scoring.
- `fetch_corpus.py` — re-fetch raw source documents from their origins.
- `build_hf_dataset.py` — pack the corpus into a JSONL for HuggingFace.

## Citation

See `CITATION.cff`. A Zenodo DOI is minted on the first tagged release.
