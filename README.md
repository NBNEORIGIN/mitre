# C184 — Mitre Industrial · DIP1 Aisle A asset tags

Reproducible pipeline for generating Mitre Industrial's DIP1 Aisle A
asset tags (QR + Aztec + serial print sheets) from the client-supplied
source PDF.

> **Production status (2026-04-21): approved.** Client manual scan of
> the 25-tag stratified QA sample returned **25 / 25 PASS** —
> end-to-end acceptance from source PDF through physical printed tag.
> All five internal gates are green (see *Acceptance gates* below).

## At a glance

- **Source**: `001 DESIGN/DIP1/Aisle A/DIP1 - AISLE A.pdf` (108 pages,
  1660 QR + 168 Aztec symbols).
- **Deliverable**: 74 SVG print sheets in
  `007 DATA/output/aisle-a-fresh/`
  - 56 screw-mount sheets (shelf rows 1-3, 1397 tags)
  - 18 adhesive-mount sheets (shelf row 4, 431 tags)
  - **Total: 1828 physical tags across 54 bays (A1-A54)**
- **QA sample for client scan**: 25 tags in
  `007 DATA/output/qa-sample/` (see folder `README.md`).
- **Shipped Batches 1 + 2** (200 tags, accepted by client) regenerate
  **byte-identical** from this pipeline.
- **GitHub**: <https://github.com/NBNEORIGIN/mitre>

## Acceptance gates

All five must be green before shipping regenerated output. Last full
run 2026-04-21:

| # | Gate                                           | Script                              | Result     |
| - | ---------------------------------------------- | ----------------------------------- | ---------- |
| 1 | Shipped Batch 1 + 2 byte-identical             | `verify_reproducibility.py`         | 10 / 10    |
| 2 | Coverage + mount split + ordering              | `qa_check_fresh_output.py`          | 1828 / 1828 |
| 3 | Per-tag QR placement across every fresh sheet  | `verify_tag_placement.py`           | 0 mismatches (74 sheets) |
| 4 | PDF decode vs client-accepted ground truth     | `ladder_validation.py`              | 72 / 72    |
| 5 | Client manual scan of the 25-tag QA sample     | `007 DATA/output/qa-sample/`        | **25 / 25** |

## Repo layout

```
001 DESIGN/DIP1/Aisle A/            Reference inputs (read-only)
    DIP1 - AISLE A.pdf                 108-page source PDF
    COMPLETE_SOLUTION_ALL_52_PAGES.csv 932 QA-confirmed A1-A26 UUIDs
    DIP1_Aisle_A_codes_sequential.csv  client's sequential order list
                                       (UUID column is NOT authoritative -
                                       see AGENTS.md)
    UV_PRINT_FILES_SPLIT/              shipped Batch 1 SVGs
    UV_PRINT_FILES_SPLIT_BATCH2/       shipped Batch 2 SVGs

007 DATA/
    BATCH_LOG.md                       full batch history + anomaly notes
    inputs/
        master_uuids.csv               1828 serial -> UUID (authoritative)
        aisle_a_sequential.serials.txt 1828 serials in print order
        COMPLETE_SOLUTION_ALL_52_PAGES.csv  mirror of reference above
    output/
        aisle-a-fresh/                 74 fresh SVG sheets (deliverable)
        qa-sample/                     25-tag client QA sample + checklist
        extract/                       raw_symbols.csv + pdf_derived_serials.csv
        a7_fix/                        audit trail for the A7 relabel
    src/
        extract/extract_pdf.py         decode every QR/Aztec in the PDF
        extract/assign_serials.py      infer serial labels from positions
        build_master_and_sequential.py assemble master + sequential list
        fix_a7_layout.py / apply_a7_fix.py  A7 non-canonical layout fix
        generate_batch.py              render SVG print sheets
        verify_reproducibility.py      gate 1
        qa_check_fresh_output.py       gate 2
        verify_tag_placement.py        gate 3
        ladder_validation.py           gate 4
        make_qa_sample.py              build the 25-tag QA sample
        verify_qa_sample.py            scan the QA sample sheets

AGENTS.md   Pickup briefing for Claude Code / any future agent
README.md   (this file)
```

## Getting set up

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install pandas pymupdf zxing-cpp qrcode pillow opencv-python cairosvg
```

## Pipeline (full re-run from scratch)

```powershell
# 1. Decode every QR / Aztec from the source PDF
.\.venv\Scripts\python.exe "007 DATA\src\extract\extract_pdf.py"

# 2. Infer serial labels from positions
.\.venv\Scripts\python.exe "007 DATA\src\extract\assign_serials.py"

# 3. Apply the A7 non-canonical layout fix + (re)build master & sequential
#    (apply_a7_fix.py internally calls build_master_and_sequential.py)
.\.venv\Scripts\python.exe "007 DATA\src\apply_a7_fix.py"

# 4. Generate all 74 fresh SVG print sheets
.\.venv\Scripts\python.exe "007 DATA\src\generate_batch.py" `
    --from-complete "007 DATA\inputs\master_uuids.csv" `
    --serials       "007 DATA\inputs\aisle_a_sequential.serials.txt" `
    --output        "007 DATA\output\aisle-a-fresh"

# 5. Acceptance gates (1 -> 4) - all must print PASS
.\.venv\Scripts\python.exe "007 DATA\src\verify_reproducibility.py"
.\.venv\Scripts\python.exe "007 DATA\src\qa_check_fresh_output.py"
.\.venv\Scripts\python.exe "007 DATA\src\verify_tag_placement.py"
.\.venv\Scripts\python.exe "007 DATA\src\ladder_validation.py"

# 6. (Optional) Regenerate the 25-tag client QA sample
.\.venv\Scripts\python.exe "007 DATA\src\make_qa_sample.py"
.\.venv\Scripts\python.exe "007 DATA\src\verify_qa_sample.py"
```

## Ladder validation (gate 4) — the acceptance regression test

`007 DATA/src/ladder_validation.py` must print `72 pass / 0 fail`
before any regenerated batch ships.

Historically the decoder had to be *taught* by a human to read the
source PDF reliably, in incremental steps that doubled coverage
each rung:

| Rung | Scope                              | Content                                |
| ---- | ---------------------------------- | -------------------------------------- |
| 1    | 1 tag                              | A1-2A (top-left QR of page 1)          |
| 2    | 1 row × 2 columns                  | A1-2A + A1-1A                          |
| 3    | 2 rows × 2 columns                 | first 2x2 block of page 1              |
| 4    | 2 rows × 3 columns                 | first 2x3 block of page 1              |
| 5    | 2 rows × 4 columns                 | first 2x4 block of page 1              |
| 6    | Whole page 1 (16 pure-QR)          | bay A1, rows 1-4 × cols A-D            |
| 7    | Whole page 2 (20 mixed QR+Aztec)   | bay A1, rows 1-4 × cols E,G,H,J,K,L    |
| 8    | Page 29 (16 pure-QR)               | bay A15, rows 1-4 × cols A-D           |
| 9    | Page 30 (20 mixed QR+Aztec)        | bay A15, rows 1-4 × cols E,G,H,J,K,L   |

Each rung is cross-checked against the client-accepted ground truth
in `COMPLETE_SOLUTION_ALL_52_PAGES.csv`. Pages 1 and 2 are the client-
confirmed rungs; pages 29 and 30 cover a historically-problematic bay
(A15-2A / A15-2H). Together they span every layout the document
contains (pure-QR, mixed QR+Aztec). Locking these four pages catches
any regression in the decoder, row/column clusterer, or serial
assignment.

If a future PDF introduces a new layout (e.g. the all-Aztec A53/A54
pages 105-108 are currently covered only by the QA sample, not the
ladder), add that page number to `LADDER_PAGES` in
`ladder_validation.py`.

## QA sample (gate 5) — client-facing scan check

`007 DATA/output/qa-sample/` contains a deliberately small
(25-tag) stratified sample covering every layout / anomaly surface:
shipped-batch sanity, A7 anomaly, historical A15 flags, 2-digit bay
text offset, upper-aisle spot checks, all-Aztec pages 105-108, and
the known duplicate-UUID pair.

The client scans each tag and pastes the decoded UUID into
`QA_SAMPLE_CHECKLIST.csv`; a pass is 25 / 25 matches. Full
instructions in `007 DATA/output/qa-sample/README.md`.

To regenerate (e.g. with a different sample), edit the `SAMPLE`
list at the top of `007 DATA/src/make_qa_sample.py` and run it.

## Known anomalies (detail in `007 DATA/BATCH_LOG.md`)

- **A7 non-canonical layout (resolved)**. Bay A7 is the only
  lower-aisle bay with 32 tags instead of 36: column A exists only on
  shelf rows 3-4, column E only on rows 1-2. Both the raw PDF
  extraction and the client-supplied solution CSVs had historically
  shifted the A7 serial labels; `fix_a7_layout.py` +
  `apply_a7_fix.py` re-decode pages 13 + 14 with pixel positions and
  apply the physically-printed labels. Shipped Batches 1 + 2 are
  unaffected (A7 is not in them) and still regenerate byte-identical.
  Audit trail: `007 DATA/output/a7_fix/a7_diff_report.csv`.

- **Duplicate UUID at A53-2H and A54-2H**. The source PDF has one
  genuine duplicate (`d8c8654d-bb1c-9969-2b3f-…`) assigned to two
  physical positions. Both tags are generated with that same UUID
  because the source PDF is what it is; the QA sample includes both
  so the client sees it at scan time.

- **`DIP1_Aisle_A_codes_sequential.csv` is NOT authoritative for
  UUIDs.** The row / column ordering is correct but ~60 % of the UUID
  column disagrees with the source PDF (most of A27-A52 is shifted).
  The authoritative UUID table is `007 DATA/inputs/master_uuids.csv`.

## Tag text layout fix (2-digit bays)

Serials with a 2-digit bay number (`A10-*` through `A54-*`) previously
had text that impinged on the QR quiet zone.
`generate_batch.py` now shifts the text 1 mm to the right and reduces
its font size by 10 % for those serials. Verified via
`src/spot_check_tags.py`. Single-digit bays (A1-A9) are unchanged, so
shipped Batches 1 + 2 remain byte-identical.

## For future agents / contributors

Start with [`AGENTS.md`](AGENTS.md) at the repo root. It contains the
hard rules ("don't modify UV_PRINT_FILES_SPLIT/...", A7 is
non-canonical, the sequential CSV is unreliable for UUIDs, etc.) and
pointers to every acceptance gate in one place.
