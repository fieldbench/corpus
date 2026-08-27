# Annotation Guidelines — FieldBench Corpus

> **Status: v1.0 — methodology final; IAA results in collection.** The
> annotation rules and per-field definitions below are authoritative. The IAA
> *numbers* are being collected (see § Annotators & provenance) and will be
> reported in `DATASHEET.md`; until then, real-document ground truth is marked
> single-source there.

## Why this document exists

Real-document ground truth in this corpus is **produced by an AI extraction
pipeline**, not hand-labeled. Inter-annotator agreement here therefore measures
something specific: **how well an independent human, reading the document,
reproduces the AI-produced ground truth.** It is a validation of AI-generated
labels against independent human judgment — not human-vs-human agreement on
human labels.

That number is only interpretable relative to the instructions the human
annotators followed. "Agreement was 0.9x" means nothing without "…under these
rules." This file is that reference: it defines what a *correct* annotation is
for each field, so that (a) an independent annotator can reproduce a label, and
(b) an outside reader can judge what the agreement number does and doesn't
establish.

It is derived from the per-field `extraction_hint` blocks in each schema
(`<category>/schemas/<name>.yaml`) — the same rules the extraction pipeline is
given — restated for a human annotator.

## Scope of the IAA pass

- **Sample.** A stratified, deterministic sample of **real** documents drawn by
  `scripts/iaa_harness.py sample` (fixed seed). Current pass: 60 documents, 12
  each across `contracts`, `legal_filings`, `medical_records`, `receipts`,
  `sec_filings`.
- **Excluded pools.** `insurance_claims` is excluded (`--exclude`): its real
  documents are blank government form templates whose only extractable field is
  `form_type`, so they carry no IAA signal and would inflate agreement with
  trivial nulls. Synthetic documents are excluded by construction (their GT is
  correct by definition).
- **Blind.** Annotators see the document and the schema fields only — never the
  existing ground truth.

## General principles

1. **Answer only from the document.** Enter what *this document* states. Do not
   use outside knowledge, look values up elsewhere, or confer with another
   annotator. Independence is what the measurement depends on.
2. **Absent vs. blank.** If a field is genuinely not present in the document,
   mark it **absent** (→ `null`). This is a real answer, distinct from "not yet
   done." The scorer treats a correct `null` as a *correct absence* (a pass),
   and a value where GT is `null` as a *hallucination* (a fail).
3. **One document, one judgment.** Each field is decided from the document in
   front of you; do not carry assumptions between documents.
4. **Whole value.** Enter the complete value (e.g. a full court name, a full
   registrant name), not an abbreviation or fragment.

## How agreement is scored (so you know what counts as a match)

`scripts/iaa_harness.py score` compares each annotation to ground truth
field-by-field with `fieldbench.scoring.compare_field`, **strict** (exact after
normalization — the schema-level `fuzzy_threshold: 0.85` applies to the main
benchmark, **not** to the IAA harness). Normalization the scorer already
absorbs, so these do **not** count as disagreements:

- **Numbers:** `$`, commas, and surrounding spaces are stripped; compared within
  ±0.01. `1,234.50` = `$1,234.50` = `1234.5`.
- **Dates:** numeric formats normalize to `YYYY-MM-DD`. `12/31/2025` =
  `2025-12-31`. (Text dates like "December 31, 2025" do **not** auto-normalize —
  the annotation app's date fields emit ISO dates to avoid this.)
- **Strings:** case-, punctuation-, and internal-whitespace-insensitive.
  `Smith, Jones & Co.` = `Smith Jones Co`.
- **Arrays:** compared as sets after the above; order does not matter, but a
  missing/extra element is a disagreement.

Genuine differences that remain (a different word, a real typo, the wrong one of
several candidates) are true disagreements — that is the signal.

`score --against <dir>` compares two annotators to each other instead of to GT
(annotator-vs-annotator agreement), over the same field set.

## Per-field rules

Organized by schema. For each field: where to look → what a correct value looks
like → what not to confuse it with → when it is absent.

### `sec_filings` — `filing_metadata`

- **filer_name** — Cover page, above "(Exact name of registrant…)"; on a 6-K, an
  ALL-CAPS line after "Commission File Number:". The full company name; combine
  bold fragments split across lines. Not the address/building name. Always
  present.
- **form_type** — Cover-page header plus any "Amendment No. N" line. The form id
  with amendment suffix: base form + "Amendment No. 1" → append "/A" (`S-1/A`).
  Don't drop "/A". Always present.
- **filing_date** — The **SIGNATURES** page near the end: the date next to an
  officer signature (`/s/`, "Dated:"). On a DEF 14A (no signature block), the
  "on or about [date]" mailing date. **Not** the auditor's signing date, the
  "as of" share-count date, or an 8-K cover "Date of Report" (event date). For a
  10-K/A, the amendment's signature date. Absent only if no filing/signature
  date appears anywhere.
- **period_fiscal_year_end** _(10-K/-A only)_ — Cover, "For the fiscal year
  ended". Not the filing date; not a comparison-period date.
- **period_quarter_end** _(10-Q/-A only)_ — Cover, "For the quarterly period
  ended"; if several, the most recent.
- **period_date_of_report** _(8-K/-A, 6-K/-A)_ — 8-K: "Date of Report (Date of
  earliest event reported)" — the event date, not the filing date. 6-K: a bare
  date near the top after "Pursuant to Rule 13a-16".
- **period_meeting_date** _(DEF 14A only)_ — The "NOTICE OF ANNUAL MEETING"
  meeting date. Not the record date, fiscal year-end, mailing date, or a future
  year's meeting.

### `contracts` — `contract`

- **contract_type** — Title/preamble; nearest option to the title; "Other" only
  if none fit. Prefer "Other" over absent.
- **parties** — Preamble ("by and between/among …"), one entry per distinct
  party: a named entity by its name (resolve aliases — "the Company" = the named
  company, listed once); a class/group by its **short defined term**
  ("Guarantors", "Noteholders", "Holders", "Anchor Investors"). Don't copy the
  long descriptor ("each of the parties listed on the signature pages hereto
  under 'Holders'") — use the label it defines; don't enumerate the individuals
  behind a class; not the drafting law firm or signatory titles. **Absent** only
  if no party is named or defined.
- **effective_date** — Preamble/header ("effective as of", "dated"). **Not** the
  signature date unless the document equates them. Absent if unstated.
- **termination_date** — Term/termination clause; a specific date or a computable
  term ("three years from the effective date"). Absent for evergreen /
  at-will / renew-until-terminated contracts.
- **governing_law** — Governing-law clause; the jurisdiction ("laws of the State
  of Delaware" → Delaware). Absent if no such clause.

### `legal_filings` — `legal_filing`

- **case_number** — The **bare docket number** ("114582", "24-1234",
  "1:24-cv-01234") — drop the "No." / "Case No." label. On an appeal use the
  **appellate** docket, not the trial-court "Case No. …" or "Motion No. …" also
  in the caption.
- **court** — The **full** court name from the body heading, including
  district/division/county ("Court of Appeals of Ohio, Eighth Appellate
  District, County of Cuyahoga"). Not a "Court:" metadata slug at the top
  ("Ohioctapp"), not an abbreviation.
- **filing_date** — Clerk's file-stamp, a "Dated:" signature line, or — for an
  opinion — the **released / journalized / decision** date (often a "Decision
  Date:" line). Prefer the file-stamp when several appear. Absent only if the
  document truly carries none — an opinion's journalized date counts.
- **filing_type** — Nearest option to the title. A court's **Opinion** is
  "Opinion" even when it decides a motion/application (don't pick "Motion" off
  the "Application for Reopening" / "Motion No." it rules on). "Other" if none fit.
- **plaintiff** — Caption, above "v."; person/company/government. For a class
  action, the named plaintiff.
- **defendant** — Caption, below "v.".
- **judge** — The judge who **authored/decided this filing** — the
  byline/signature block ("EMANUELLA D. GROVES, J.:"; or "MORI, acting P.J."
  above "We concur:"). Full name where given, **drop the ", J." / "P.J." /
  "Honorable" honorific**. On an appellate opinion this is NOT the trial judge
  in the caption ("…County, Steve Cochran, Judge" = the judge being reviewed).
  Often **absent** on initial complaints (no judge assigned yet).

### `medical_records` — `discharge_summary`

- **admission_date** — Header, "Admission Date:".
- **discharge_date** — Header, "Discharge Date:".
- **primary_diagnosis** — Diagnosis section ("Principal/Primary/Discharge
  Diagnosis"); the first (principal) one if several. Not the secondaries.
- **procedures** — Take from a labeled header ("PROCEDURE PERFORMED", "OPERATION",
  "TITLE OF OPERATION"), **verbatim** — *not* from the "PROCEDURE IN DETAIL" /
  operative narrative. One entry per named operation: split numbered lists and
  comma-joined distinct operations. Not the operative steps (trocars, clamping,
  closure); not the patient's past-history procedures ("has had six
  cardioversions"). Where there is no header (many discharge summaries /
  consults), list procedures performed *this* admission from the hospital-course
  text; include a diagnostic procedure only if the note lists it as one.
  **Absent** if none. *(This is the softest field — see § Limitations: list
  fields are scored with partial-credit F1, not all-or-nothing.)*
- **medications_at_discharge** — "Discharge Medications" section; medication
  names (drop dosing unless part of the name). Absent if none listed.
- **attending_physician** — Header ("Attending:") or signature. Records are
  de-identified, so the name usually appears as a short token ("Dr. X", "Dr.
  A") — enter it **as written**; that token is the value. Mark **absent** only
  when no attending physician is named at all. _(Confirmed against GT: of 140
  medical files, 103 carry a de-identified name, 37 are null, none store a
  placeholder as the value.)_

### `receipts` — `invoice_basic`

- **merchant_name** — Top/header; the **seller**, not the bill-to/customer.
- **date** — Header ("Invoice/Receipt date").
- **total_amount** — Totals; the final amount **including** tax/fees. Not the
  subtotal.
- **subtotal** — Totals, before tax; **absent** on receipts that show only a
  total.
- **tax** — Totals ("Tax/VAT/GST"); **absent** if no tax line (do not enter 0).
- **currency** — ISO code inferred from explicit code > symbol+country >
  address. A bare "$" defaults to USD unless a Canadian/Australian/Singaporean
  address indicates CAD/AUD/SGD.
- **items** — Line-items table; one row per item (name, quantity, unit_price,
  amount). `unit_price` is per **one** unit; `amount` is the line total (qty ×
  unit_price). Absent if there are no itemized lines.

## Annotators & provenance

- **Ground truth.** Real-document ground truth is produced by an **AI extraction
  pipeline**, then used as the reference the IAA measures against. The human
  annotators below do **not** see the ground truth while annotating (blind), and
  none of them produced it — so their agreement with it is an independent check
  on the AI labels, not self-agreement.
- **Annotators.** Independent human annotators fill the blind templates through
  the annotation tool. Each carries a distinct token so the harness can score
  each against the AI ground truth and against one another. Arms are recorded by
  role, and any arm annotated by an author of the accompanying paper is disclosed
  as such rather than presented as fully independent. At least one **fully
  external** annotator (unaffiliated with the corpus) is included so the headline
  number rests on a disinterested arm.
- **Annotators are trained, not naive.** Annotators are given these guidelines
  (the same rules the extraction pipeline follows). The number therefore reports
  *"a competent human following the documented guideline agrees with the
  AI-produced ground truth"* — not *"the document is unambiguous to a naive
  reader."* Because the humans did not produce the ground truth, this is a
  genuine independent validation of the AI labels; the shared element is the
  guideline, not the answers.
- **Adjudication.** Field-level disagreements are surfaced with
  `iaa_harness.py score --disagreements`; each is reviewed to separate genuine
  ground-truth errors (which are corrected) from defensible differences and
  document ambiguity (which are left as signal).

## Limitations

- **Cohen's κ coverage.** κ is computed only on enum-typed fields
  (`contract_type`, `filing_type`, `form_type`), ~12 instances each in the
  current sample — too few for a stable κ. It is reported with an explicit n
  caveat; enlarging the enum-bearing categories is left to a future pass.
- **Scoring — strict and partial.** Comparison is exact-after-normalization
  (fuzzy matching off), so the strict `agreement_rate` is a lower bound relative
  to the main benchmark's fuzzy threshold. Array/list fields (`procedures`,
  `medications_at_discharge`, `items`) are **additionally** reported with an
  element-F1 partial-credit rate (`agreement_rate_partial`): a near-miss on a
  multi-item list scores its F1, not zero.
- **Free-prose list fields double as a GT audit.** For `procedures` the ground
  truth is an AI-synthesized reading of narrative text, so disagreement there
  reflects open-ended-extraction consistency (segmentation, naming, granularity)
  as much as correctness — read it against the partial-credit rate, and treat
  disagreements as a check on the AI labels, not only on the annotators.

## Reproducing this document

The per-field rules are derived from the schema `extraction_hint` content;
the PDF is generated from this markdown by `scripts/render_guidelines_pdf.sh`.
Corpus reference: see the `corpus_ref` recorded with each ingested batch.
