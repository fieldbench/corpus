# FieldBench Corpus

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21532677.svg)](https://doi.org/10.5281/zenodo.21532677)

A cross-domain, field-level benchmark for **schema-driven document extraction**
(document → structured JSON). 1,442 documents across 10 categories with per-field
ground truth, released so extraction-accuracy claims become **falsifiable and
comparable**.

- **Scorer + run harness:** https://github.com/fieldbench/fieldbench (`pip install fieldbench`)
- **Read first:** [`DATASHEET.md`](DATASHEET.md) — composition, provenance, licensing, and limitations.

## ⚠️ Read before quoting any accuracy number

- **~90% of documents are extraction-from-clean-text, not rendered-page extraction**
  (only 9.8% came from an image or PDF). Parse-stage difficulty — OCR error, layout
  collapse, table-structure loss — is largely absent by construction. See
  [`docs/composition.md`](docs/composition.md).
- **Synthetic documents (~48%) overestimate accuracy** relative to real ones. Always
  report results **stratified by `source`** (real / synthetic).
- **Matched-pair subset:** five categories are dual-source — real documents plus
  synthetic ones generated against the *same schema* (tagged `matched_pair` /
  `synthetic_realism` in their manifests) — so the synthetic-vs-real gap can be measured
  holding category constant. See `DATASHEET.md` and `scripts/wire_matched_pairs.py`.

## Layout

```
<category>/
  documents/<id>.md            # the markdown representation to extract from
  expected/<id>.expected.json  # ground-truth {field: value} map
  manifests/<id>.json          # provenance + source + original_format + schema ref
  schemas/<schema>.yaml        # field definitions for the category
```

10 categories: `sec_filings`, `invoices`, `insurance_claims`, `insurance_policies`,
`contracts`, `medical_records`, `insurance_certificates`, `legal_filings`, `receipts`,
`irs_forms`.

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
attribution; Caselaw Access Project public domain; government forms public
domain. ACORD/ISO copyrighted insurance form layouts are **not** included — those
categories use functionally-equivalent synthetic documents.

## Tooling (`scripts/`)

- `sources/` — deterministic synthetic-document generators.
- `grounding_audit.py` — grounding audit + coverage probe (are missed fields present in the
  source? which fields does no system recover?); depends only on the released scorer.
- `composition_report.py` — regenerate the input-composition disclosure.
- `iaa_harness.py` — inter-annotator-agreement sampling + scoring.
- `fetch_corpus.py` — re-fetch raw source documents from their origins.
- `build_hf_dataset.py` — pack the corpus into a JSONL for HuggingFace.

## Citation

See `CITATION.cff`. Zenodo DOI (all versions): [10.5281/zenodo.21532677](https://doi.org/10.5281/zenodo.21532677).
