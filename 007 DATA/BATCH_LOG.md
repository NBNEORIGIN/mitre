# DIP1 Aisle A — Batch Production Log

Ongoing production record for the C184 Aisle A asset tags. Updated after
every batch so any contributor can pick up the next one.

## Serial numbering scheme

Format: `A{bay}-{shelf_row}{column_letter}`

- Bay: 1–26
- Shelf rows: 1, 2, 3 (screw mount) and 4 (adhesive mount)
- Column letters: A, B, C, D, E, G, H, J, K, L  (no F, no I)

Positions per bay (36 tags total):

    Page 1  Rows 1,2,3,4  Cols A B C D       QR
    Page 2  Rows 1,2      Cols E G H J       QR
    Page 2  Rows 1,2      Cols K L           Aztec
    Page 2  Rows 3,4      Cols E G H J       QR
    Page 2  Rows 3,4      Cols K L           (do not exist)

36 tags/bay × 26 bays = 936 in theory; the authoritative table
(`inputs/COMPLETE_SOLUTION_ALL_52_PAGES.csv`) has 932 rows — 4
positions missing/anomalous.

## Batches

### Batch 1 — shipped, 100% QA confirmed by client
- Input : `inputs/FIRST_100_TAGS_MATCHED.csv`
- Output: `001 DESIGN/DIP1/Aisle A/UV_PRINT_FILES_SPLIT/` (originals)
- Covers: A1 full (36) + A2 full (36) + A3 first 28 (page-1 all + page-2 rows 1-2)
- Last serial: `A3-2L`
- Sheets : SHELF_123_SCREW × 4 (80 tags), SHELF_4_ADHESIVE × 1 (20 tags) = 100

### Batch 2 — shipped
- Input : `inputs/COMPLETE_SOLUTION_ALL_52_PAGES.csv` + `inputs/batch-02.serials.txt`
- Output: `001 DESIGN/DIP1/Aisle A/UV_PRINT_FILES_SPLIT_BATCH2/` (originals)
- Covers: A3 remainder (8) + A4 full (36) + A5 full (36) + A6 first 20
- Last serial: `A6-1J`
- Sheets : SHELF_123_SCREW × 4 (76 tags), SHELF_4_ADHESIVE × 1 (24 tags) = 100

### Verification (2026-04-21)
Both batches were regenerated from this clean pipeline and are
**byte-identical** to the originals. See
`src/verify_reproducibility.py`.

### Text-layout adjustment for 2-digit bay numbers (2026-04-21)
For serials whose bay prefix has 2+ digits (A10-..A26-), the 4-character
"A26-" string was impinging on the right edge of the QR code. These tags
now use a font size of 2.025 mm (10% smaller) and shift the text 1 mm to
the right. Single-digit bays (A1-..A9-) are unchanged, so Batches 1 and
2 remain byte-identical (verified).

### Batch 3 — generated 2026-04-21, all remaining 732 tags
- Input : `inputs/COMPLETE_SOLUTION_ALL_52_PAGES.csv` + `inputs/batch-03.serials.txt`
- Output: `output/batch-03/`
- Covers: A6 remainder (16) + A7..A26 inclusive (716 after anomalies) = 732 tags
- Order : **client's requested sequential order** — for each bay in
  A6..A26, rows are visited 1→4 and columns A, B, C, D, E, G, H, J, K, L.
  K/L exist only on rows 1 and 2 per the layout rules.
- Sheets: SHELF_123_SCREW × 23 (569 tags), SHELF_4_ADHESIVE × 7 (163 tags) = 30 sheets
- First serial: `A6-1K` · Last serial: `A26-4J`
- QA    : `sanity_check_batch_03.py` confirms (a) every serial exists in
  COMPLETE_SOLUTION, (b) Batches 1+2+3 partition the full 932 with no
  overlaps or gaps, (c) within-sheet tag order matches the client's
  sequential input.

### Note on the existing `001 DESIGN/DIP1/Aisle A/Aisle A 201 to 932/` folder
Those 30 sheets were produced before the client asked for sequential
ordering, so their serials are scrambled across pages. They are
**superseded** by `007 DATA/output/batch-03/` and should not be used
for this run.

### Fresh full-aisle regeneration — 2026-04-21
All 1828 physical Aisle A tags regenerated from scratch for end-to-end QA.
This supersedes the piecemeal Batch 1 + Batch 2 + Batch 3 outputs for
QA review purposes (the shipped originals are still on file and still
byte-identical to this pipeline).

- Master UUID table: `inputs/master_uuids.csv` (1828 rows)
  - Built by `src/build_master_and_sequential.py`.
  - UUIDs taken from `output/extract/pdf_derived_serials.csv` (the
    full-PDF zxing extraction). Cross-checked: every one of the 932
    A1-A26 serials that appears in `COMPLETE_SOLUTION_ALL_52_PAGES.csv`
    carries the **same** UUID in both tables.
- Sequential order: `inputs/aisle_a_sequential.serials.txt` (1828 lines)
  - Client's requested order: for each bay in A1..A54, visit rows 1→4
    and within each row emit every physical column.
- Output: `output/aisle-a-fresh/`
  - SHELF_123_SCREW × 56 (1397 tags, rows 1-3)
  - SHELF_4_ADHESIVE × 18 (431 tags, row 4)
  - Total: 74 sheets, 1828 tags.
- QA scripts used:
  - `src/verify_reproducibility.py` — confirms the 10 shipped sheets
    still come out byte-identical (10/10, 2026-04-21).
  - `src/qa_check_fresh_output.py` — parses every fresh SVG and
    confirms full-coverage, no duplicates, correct mount split, and
    correct sequential ordering within each mount stream.
  - `src/spot_check_tags.py` — confirms the 2-digit-bay text fix is
    applied only to A10-..A54- (font 2.025mm, text x-shift +1mm).

**Known anomalies surfaced during the fresh run:**

- *A7 layout anomaly (resolved)*: Bay A7 is the only lower-aisle bay
  that deviates from the canonical 36-tag layout. The physical PDF
  (pages 13 + 14) contains 32 A7 tags:
    - Column A has only shelf rows 3, 4 (no 1A or 2A)
    - Column E has only shelf rows 1, 2 (no 3E or 4E)
    - Columns B, C, D, G, H, J have all 4 rows
    - Columns K, L have rows 1, 2 (as with every other lower bay)
  Both the initial `pdf_derived_serials.csv` and the client-supplied
  `COMPLETE_SOLUTION_ALL_52_PAGES.csv` / `DIP1_Aisle_A_codes_sequential.csv`
  had been generated with the assumption of 36 tags per lower bay,
  which silently shifted every A7 serial label by two positions and
  produced four phantom serials (A7-1A, A7-2A, A7-3E, A7-4E). The
  genuine tags A7-3D, A7-4D, A7-1L, A7-2L were incorrectly marked
  absent. This was spotted by the client from photos of the printed
  PDF (pages 13 + 14).

  **Fix applied (2026-04-21)**: `src/fix_a7_layout.py` re-decoded the
  32 A7 codes with pixel positions, sorted them into the two visual
  rows, and applied the physically-printed labels from the PDF
  render. `src/apply_a7_fix.py` rewrote both `master_uuids.csv` and
  `pdf_derived_serials.csv` with the corrected A7 mapping and
  regenerated the sequential list. `build_master_and_sequential.py`
  now knows A7's layout via `BAY_LAYOUT_OVERRIDES`. Diff summary in
  `output/a7_fix/a7_diff_report.csv`: 4 added (A7-1L, A7-2L, A7-3D,
  A7-4D), 4 removed phantoms (A7-1A, A7-2A, A7-3E, A7-4E), 26
  relabeled, 2 unchanged. All 32 physical UUIDs are preserved; only
  the serial labels changed. Shipped Batches 1 and 2 are unaffected
  and still regenerate byte-identical (A7 is not in those batches).
- *One duplicate UUID in the source PDF*: `d8c8654d-bb1c-9969-2b3f-…`
  appears at two physical positions, A53-2H and A54-2H. Both tags are
  generated with that same UUID because the source PDF is what it is;
  flag for human decision at print time if a fix is needed.

---

## Ladder validation (acceptance criterion)

Before shipping any regenerated batch the pipeline must pass
`src/ladder_validation.py` with **72 / 72**. The script re-decodes
pages 1, 2, 29, 30 of the source PDF and cross-checks every position
against `COMPLETE_SOLUTION_ALL_52_PAGES.csv`.

**History of the ladder**: early in the project the decoder had to be
iteratively validated starting from a single QR (A1-2A) and doubling
until a whole page passed, because the combination of scaling, Aztec
decoding, and row/column clustering could drift silently. The
accepted sequence is 1 tag -> 2 -> 4 -> 6 -> 8 -> 16 -> 20 -> 36 -> 72
positions, doubling coverage each step. The four pages chosen (1, 2,
29, 30) together span every layout the document contains:

- Pure-QR 16-code page (pages 1 and 29)
- Mixed QR + Aztec 20-code page (pages 2 and 30)
- Client-confirmed ground truth (pages 1 and 2)
- Historically flagged bay (pages 29 and 30, bay A15 with A15-2A /
  A15-2H)

If a future PDF introduces a new layout (e.g. pages 53+ which switch
to all-16-per-page, or pages 105-108 which are pure Aztec), add that
page to `LADDER_PAGES` in `ladder_validation.py` and keep its expected
count in sync.

The decoder itself (`src/extract_pdf.py`) was *not* modified during
the most recent ladder pass (2026-04-21, 72/72). The ladder confirmed
that the existing multi-DPI + UUID-regex + position-deduplication
approach was already correct; earlier reports of "wrong" A15-2A /
A15-2H turned out to be either mislabeled prints or UUIDs from
neighbouring tags (the `...6133` UUID that looked like a bad A15-2A
decode is actually A15-1G).

## Client QA sample — 2026-04-21 — 25 / 25 PASS

First end-to-end human-in-the-loop acceptance of the fresh pipeline.
The client manually scanned all 25 tags of the stratified QA sample
(`007 DATA/output/qa-sample/`) and every decoded UUID matched the
expected value in `QA_SAMPLE_CHECKLIST.csv`.

- Sample composition: 17 QR + 8 Aztec, 19 screw + 6 adhesive, spans
  every layout in the document (shipped-batch sanity, A7 anomaly,
  historical A15 flags, 2-digit-bay text offset, upper-aisle spot
  checks, all-Aztec pages 105-108, known duplicate-UUID pair).
- Generator / checklist: `src/make_qa_sample.py` (reproducible; edit
  the `SAMPLE` list and rerun to produce a different sample).
- Self-consistency gate before print: `src/verify_qa_sample.py`
  rasterises the two sample sheets at print scale and confirms every
  `<g id="tag_SERIAL">` contains the UUID that `master_uuids.csv`
  expects (25 / 25 on 2026-04-21).
- Client result: **25 / 25** scanned UUIDs match expected.

This is the first time the whole chain — source PDF -> zxing decoder
-> A7 layout fix -> master_uuids.csv -> generate_batch.py -> UV print
-> physical tag -> phone scanner -> human eyeball -> checklist — has
been validated end-to-end without a human-in-the-loop correction in
the middle. Treat this as the green light for production of the
remaining tags not in Batches 1, 2, 3.

## NEXT

Aisle A is now fully accounted for. Future work: DNR1 and/or DIP1
B/C/D aisles — those inputs live under `001 DESIGN/DNR1/` and
`001 DESIGN/DIP1/Aisle {B,C,D}/` and would be onboarded by adding
their authoritative serial→UUID CSV(s) into `inputs/` and
generating batches the same way.

## How to produce a new batch

1. Create `inputs/batch-0N.serials.txt` with one serial per line in
   the desired order (comments / blank lines allowed). You can
   hand-write it or generate it with
   `src/build_remaining_serials.py` (see that script's docstring).
2. Run `python src/generate_batch.py --from-complete
   inputs/COMPLETE_SOLUTION_ALL_52_PAGES.csv --serials
   inputs/batch-0N.serials.txt --output output/batch-0N`.
3. Sanity-check the printed tag counts (screw vs adhesive).
4. Spot-check a few SVGs in a browser or Inkscape.
5. Add a new entry to this log (covers / last serial / sheet counts).
