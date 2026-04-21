# AGENTS.md — C184 Mitre Industrial DIP1 Aisle A pipeline

This file exists so that any agent (Claude Code, Cursor agent, GPT,
future-you, etc.) dropped into this repository without prior context
can safely operate the pipeline. Read it before touching anything.

## What this project is

Reproducible pipeline to generate **1828 laser-cut / UV-printed asset
tags** for Mitre Industrial's DIP1 Aisle A (racking bays A1–A54). The
source of truth is a 108-page PDF (`001 DESIGN/DIP1/Aisle A/DIP1 -
AISLE A.pdf`) supplied by the client, which contains the raw QR and
Aztec codes for every tag. The pipeline decodes that PDF, assigns
physical serials to each code, and renders 74 sheet-sized SVG print
files that go straight to the UV printer.

Two batches (200 tags total) have **already been shipped and accepted
by the client**. Those printed artwork SVGs live in
`001 DESIGN/DIP1/Aisle A/UV_PRINT_FILES_SPLIT/` and
`001 DESIGN/DIP1/Aisle A/UV_PRINT_FILES_SPLIT_BATCH2/` and the
pipeline regenerates them **byte-identical**. Do not break that.

## Key documents

| Read if you want to ...                   | File                                      |
| ----------------------------------------- | ----------------------------------------- |
| Get oriented on the pipeline              | `README.md` (repo root)                   |
| See the batch history + known anomalies   | `007 DATA/BATCH_LOG.md`                   |
| Understand the ladder test (acceptance)   | `007 DATA/src/ladder_validation.py`       |

## Key files (data)

| Role                                                    | Path                                                                |
| ------------------------------------------------------- | ------------------------------------------------------------------- |
| Source PDF (authoritative)                              | `001 DESIGN/DIP1/Aisle A/DIP1 - AISLE A.pdf`                        |
| Client-accepted ground truth for A1-A26 (932 rows)      | `001 DESIGN/DIP1/Aisle A/COMPLETE_SOLUTION_ALL_52_PAGES.csv`        |
| Master serial → UUID table, 1828 rows (authoritative)   | `007 DATA/inputs/master_uuids.csv`                                  |
| Client's requested print order                          | `007 DATA/inputs/aisle_a_sequential.serials.txt`                    |
| PDF extraction output                                   | `007 DATA/output/extract/pdf_derived_serials.csv`                   |
| Fresh SVG print sheets (the deliverable)                | `007 DATA/output/aisle-a-fresh/`                                    |

## Key files (code, in `007 DATA/src/`)

| Stage                                | Script                                |
| ------------------------------------ | ------------------------------------- |
| 1. Decode PDF (QR + Aztec)           | `extract/extract_pdf.py`              |
| 2. Cluster rows/cols → serials       | `assign_serials.py`                   |
| 3. Build master + sequential order   | `build_master_and_sequential.py`      |
| 4. Render SVG sheets                 | `generate_batch.py`                   |
| 5. Reproducibility (shipped batches) | `verify_reproducibility.py`           |
| 5. Coverage + ordering QA            | `qa_check_fresh_output.py`            |
| 5. Every QR is under the right label | `verify_tag_placement.py`             |
| 5. Ladder regression (MUST pass)     | `ladder_validation.py`                |
| One-off: A7 anomaly fix              | `fix_a7_layout.py` + `apply_a7_fix.py`|

## How to run the pipeline end-to-end

```powershell
.\.venv\Scripts\python.exe "007 DATA\src\extract\extract_pdf.py"
.\.venv\Scripts\python.exe "007 DATA\src\assign_serials.py"
.\.venv\Scripts\python.exe "007 DATA\src\build_master_and_sequential.py"
.\.venv\Scripts\python.exe "007 DATA\src\generate_batch.py" `
    --from-complete "007 DATA\inputs\master_uuids.csv" `
    --serials       "007 DATA\inputs\aisle_a_sequential.serials.txt" `
    --output        "007 DATA\output\aisle-a-fresh"
.\.venv\Scripts\python.exe "007 DATA\src\verify_reproducibility.py"
.\.venv\Scripts\python.exe "007 DATA\src\qa_check_fresh_output.py"
.\.venv\Scripts\python.exe "007 DATA\src\ladder_validation.py"
```

Acceptance gates (all must hold before the output is shippable):

1. `verify_reproducibility.py` — shipped Batch 1 + Batch 2 SVGs
   regenerate byte-identical (10 / 10).
2. `qa_check_fresh_output.py` — 1828 unique serials, correct mount
   split (1397 screw + 431 adhesive = 1828), client's sequential
   order preserved within each mount stream.
3. `verify_tag_placement.py` — every `<g id="tag_SERIAL">` in every
   generated SVG contains the UUID from `master_uuids.csv` (0
   mismatches).
4. `ladder_validation.py` — **72 / 72** across pages 1, 2, 29, 30 of
   the source PDF against `COMPLETE_SOLUTION_ALL_52_PAGES.csv`.

## Hard rules (things that have broken us before)

- **Never modify** `001 DESIGN/DIP1/Aisle A/UV_PRINT_FILES_SPLIT/`
  or `UV_PRINT_FILES_SPLIT_BATCH2/`. Those are the shipped originals.
  Use them read-only as reproducibility witnesses.
- **Bay A7 is not canonical.** Its physical layout is 32 tags, not 36:
  column A only exists on shelf rows 3-4, column E only on rows 1-2.
  The pipeline encodes this in `BAY_LAYOUT_OVERRIDES` inside
  `build_master_and_sequential.py`. Do not regress that. See
  `output/a7_fix/a7_diff_report.csv` and the A7 section of
  `BATCH_LOG.md` for the full story.
- **`DIP1_Aisle_A_codes_sequential.csv` is NOT authoritative for
  UUIDs.** It is the correct sequential order + correct list of
  serials, but ~60 % of its UUID column disagrees with the real PDF
  (most of A27–A52 is shifted). Use it only for the page/row/column
  sequence, never for UUIDs. The authoritative UUID table is
  `007 DATA/inputs/master_uuids.csv`.
- **The source PDF contains one genuine duplicate UUID**
  (`d8c8654d-bb1c-9969-2b3f-…`) at both A53-2H and A54-2H. Flag, do
  not "fix", unless the client tells you to.
- **Serials with 2-digit bay numbers** (A10- through A54-) use a
  10 % smaller font and a 1 mm horizontal offset so the text doesn't
  impinge on the QR. `generate_batch.py` handles this automatically;
  don't revert it. Single-digit bays (A1–A9) are unchanged (that's
  how shipped Batches 1 + 2 remain byte-identical).

## The ladder (acceptance test) — detailed

`src/ladder_validation.py` is the **single regression test** that
gates a new batch. It re-decodes pages 1, 2, 29, 30 of the source PDF
and compares every position against the client-accepted
`COMPLETE_SOLUTION_ALL_52_PAGES.csv`. Must print
`72 pass / 0 fail` before shipping.

The sequence was historically:

```
  1 tag    →  2 tags  →  4 tags  →  6 tags  →  8 tags
          →  16 tags (all of page 1)
          →  20 tags (all of page 2, mixed QR+Aztec)
          →  16 tags (page 29)
          →  20 tags (page 30)
```

This mirrors how the extractor was originally validated by a human
starting from a single QR and doubling coverage. It catches (a)
decoder drift, (b) row/column clustering regressions and (c)
serial-assignment regressions in one script.

## Decoder notes (for anyone tempted to "optimise" it)

`extract/extract_pdf.py` uses:

- PyMuPDF (`fitz`) to rasterise each page at 300 / 400 / 250 / 450 DPI
  (ladder fallback — stop as soon as we hit the expected count).
- `zxing-cpp` for decoding both QR Code and Aztec.
- A UUID regex filter (`UUID_RE`) to discard junk decodes such as
  `"089"`.
- Position-based deduplication within a page (centre of symbol in
  normalised page coords, tolerance 0.02).
- A preprocessing fallback (Otsu threshold, inversion, sharpen) if
  the DPI ladder alone can't hit the expected symbol count.

This combination was developed empirically (the original "training"
the user did). **Don't change it speculatively.** If you think a
change is needed, run `ladder_validation.py` before and after and
post the before/after pass counts.
