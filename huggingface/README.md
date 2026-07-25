---
license: cc-by-4.0
language:
- en
tags:
- document-extraction
- information-extraction
- schema-driven
- benchmark
- evaluation
size_categories:
- 1K<n<10K
pretty_name: FieldBench Corpus
---

# FieldBench Corpus

A cross-domain, field-level benchmark for **schema-driven document extraction**
(document → structured JSON). 1,470 documents across 12 categories with per-field
ground truth, released so extraction-accuracy claims become falsifiable and comparable.

- **Code / scorer:** https://github.com/fieldbench/fieldbench (`pip install fieldbench`)
- **Full corpus + datasheet:** https://github.com/fieldbench/corpus
- **Datasheet:** see `DATASHEET.md` in the corpus repo — read it before drawing conclusions.

## Load

```python
from datasets import load_dataset
ds = load_dataset("fieldbench/corpus")["test"]
ex = ds[0]
# ex["document"]  -> the markdown representation to extract from
# ex["expected"]  -> ground-truth field map (JSON string; json.loads it)
# ex["category"], ex["source"] ("real"|"synthetic"), ex["schema"]
```

Score predictions with the canonical scorer:

```bash
pip install fieldbench
fieldbench score --corpus <corpus-checkout> --results <your-predictions>/
```

## Fields

| field | description |
|---|---|
| `doc_id` | document identifier |
| `category` | one of 12 categories (sec_filings, invoices, medical_records, …) |
| `source` | `real` or `synthetic` — **always report results stratified by this** |
| `original_format` | how the document reached the extractor (see composition note) |
| `document` | the markdown representation to extract from |
| `expected` | ground-truth `{field: value}` map, serialized as a JSON string |
| `schema` | schema file name defining the fields for this category |

## Important caveats

- **~90% of documents are extraction-from-clean-text, not rendered-page extraction**
  (only 9.8% came from an image/PDF). Parse-stage difficulty is largely absent by
  construction — scope accuracy claims accordingly. See the composition table in the
  corpus repo.
- **Synthetic documents (~48%) overestimate accuracy** relative to real ones. Never
  report a synthetic-inclusive number without the real/synthetic split.
- **Licensing is per-source** (see `ATTRIBUTION.md`): synthetic CC0; SEC EDGAR public
  disclosure; SROIE CC BY 4.0; MTSamples educational-use with attribution;
  Caselaw Access Project public domain; government forms public domain. ACORD/ISO
  copyrighted forms are not included (those categories use synthetic equivalents).

## Citation

See `CITATION.cff` in the corpus repo.
