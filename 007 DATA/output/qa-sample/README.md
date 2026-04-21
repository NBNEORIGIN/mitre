# QA sample — DIP1 Aisle A asset tags

This folder contains a small, stratified sample of 25 asset tags that
the client can scan and cross-check against the original supplied PDF
(`001 DESIGN/DIP1/Aisle A/DIP1 - AISLE A.pdf`). It is intentionally
tiny so QA takes minutes, not days — but every pick covers a
specific risk surface in the pipeline.

## Files

| File                            | What it is                                                  |
| ------------------------------- | ----------------------------------------------------------- |
| `QA_SAMPLE_SHEET_01_SCREW.svg`  | 19 screw-mount tags (shelf rows 1-3), 5 x 5 grid print sheet |
| `QA_SAMPLE_SHEET_02_ADHESIVE.svg` | 6 adhesive-mount tags (shelf row 4), 5 x 5 grid print sheet  |
| `QA_SAMPLE_CHECKLIST.csv`       | The 25 tags with expected UUIDs + a blank column for the observed UUID |
| `qa_sample.serials.txt`         | Plain serial list used to drive the generator (reproducibility aid)    |

## How to run the QA

1. Print the two SVG sheets (same UV-print workflow as the main batches).
2. Open `QA_SAMPLE_CHECKLIST.csv` in Excel / Google Sheets.
3. For each tag on the printed sheet, scan the QR or Aztec with any
   phone camera or barcode scanner.
4. Paste the scanned UUID into the `observed_uuid` column on the matching
   row.
5. Fill in the `pass_fail` column (`=IF(LOWER(G2)=LOWER(C2), "PASS", "FAIL")`
   works in Sheets / Excel if you want it automated).
6. **Pass criterion**: all 25 `pass_fail` cells = `PASS`.
7. If any row fails: take a photo of the tag, note the serial, and
   forward to the production team. The `source_pdf_page` column tells
   you which page of the source PDF to cross-check against.

## What the 25 tags cover (and why)

| Category                         | Serials                                             | Why it's in the sample |
| -------------------------------- | --------------------------------------------------- | ---------------------- |
| Shipped-batch sanity (4)         | A1-1A, A3-2L, A4-1A, A6-1J                          | Already accepted by the client in Batches 1 & 2. Byte-identical to the shipped artwork -> catches any accidental regression in the pipeline. |
| A7 layout anomaly (5)            | A7-1B, A7-1L, A7-2L, A7-3D, A7-4D                   | Bay A7 has 32 physical tags, not 36. The label-to-UUID mapping had to be fixed; these tags were the ones most affected. |
| User-flagged history (3)         | A15-1G, A15-2A, A15-2H                              | Historically reported as "wrong" (UUIDs ending `...6133` / `...3e9c` / `...05b3`). The `...6133` is the real A15-1G, a label confusion — verifying all three together closes that loop. |
| 2-digit bay text offset (4)      | A10-1A, A20-4J, A26-1L, A26-4J                      | Tags with bays A10..A54 use a 10 %-smaller font shifted 1 mm right so the text doesn't impinge on the QR quiet zone. Picks a first, a last, a row-4 adhesive, and an Aztec variant. |
| Upper-aisle spot checks (5)      | A27-1A, A30-2H, A40-3E, A45-4A, A52-4J              | A27..A54 have less historical ground truth than A1..A26, so we spread five picks across rows and bays. |
| All-Aztec upper-aisle pages (3)  | A53-1A, A53-2H, A54-4J                              | Pages 105-108 of the source PDF are all Aztec. Includes one example per shelf row extreme. |
| Known duplicate UUID (2)         | A53-2H, A54-2H                                      | The source PDF has one genuine duplicate UUID (`d8c8654d-bb1c-9969-2b3f-…`). Both tags intentionally carry it; confirm this is accepted on the client side. |

(The totals come out to 25 tags; some serials count in multiple
categories — e.g. A53-2H is both the duplicate watch and an
all-Aztec upper-aisle page.)

## Code formats in the sample

- QR Code: 17 tags
- Aztec:    8 tags

## If the client wants a different sample

`007 DATA/src/make_qa_sample.py` is the single source of truth. Edit
the `SAMPLE = [...]` list at the top (add / remove `(serial,
rationale)` pairs) and re-run:

```powershell
.\.venv\Scripts\python.exe "007 DATA\src\make_qa_sample.py"
```

It will regenerate the sheets + checklist from the authoritative
`master_uuids.csv`. Any number of tags up to 25 fits on a single sheet
pair; more than that and additional sheets will be produced automatically.

## Pipeline provenance

The UUIDs in this sample came from the same `master_uuids.csv` that
drives the full-aisle fresh output in `../aisle-a-fresh/`. That table
was verified against the client-accepted `COMPLETE_SOLUTION_ALL_52_PAGES.csv`
for all 900 non-A7 shipped serials (0 disagreements) and against the
physical tags in bay A15 via the `src/ladder_validation.py` regression
test (72 / 72 match). Additionally `src/verify_qa_sample.py` rasterises
the two sample sheets at print resolution and re-decodes every symbol,
confirming each tag group contains the correct UUID for its label
before the sheet leaves this folder.
