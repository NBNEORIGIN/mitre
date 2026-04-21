# C184 — Mitre Industrial · DIP1 Aisle A asset tags

Reproducible pipeline for generating Mitre Industrial's DIP1 Aisle A
asset tags (QR + serial print sheets) from the source PDF.

- **Source PDF**: `001 DESIGN/DIP1/Aisle A/DIP1 - AISLE A.pdf` (108 pages)
- **Output**: 74 SVG print sheets in `007 DATA/output/aisle-a-fresh/`
  - 56 screw-mount sheets (shelf rows 1–3, 1397 tags)
  - 18 adhesive-mount sheets (shelf row 4, 431 tags)
  - **Total: 1828 physical tags across 54 bays (A1–A54)**

Shipped Batch 1 (100 tags) and Batch 2 (100 tags) regenerate
byte-identical from the current pipeline — proof that the master
UUID table and generator are consistent with what the client has
already received.

## Repo layout

```
001 DESIGN/DIP1/Aisle A/     Reference inputs (source PDF, shipped batches)
    DIP1 - AISLE A.pdf              108-page source PDF (9.4 MB)
    DIP1_Aisle_A_codes_sequential.csv  client-supplied sequential order
    COMPLETE_SOLUTION_ALL_52_PAGES.csv 932 QA-confirmed A1-A26 UUIDs
    UV_PRINT_FILES_SPLIT/           shipped Batch 1 SVGs (reference)
    UV_PRINT_FILES_SPLIT_BATCH2/    shipped Batch 2 SVGs (reference)

007 DATA/
    BATCH_LOG.md                 full batch history + anomaly notes
    inputs/
        master_uuids.csv                 1828 serial→UUID rows (authoritative)
        aisle_a_sequential.serials.txt   1828 serials in client's print order
        COMPLETE_SOLUTION_ALL_52_PAGES.csv (mirror of the reference above)
    output/
        aisle-a-fresh/   74 fresh SVG sheets (the deliverable)
        extract/         pdf_derived_serials.csv (1828 PDF-decoded rows)
        a7_fix/          audit diff for the A7 relabel (see BATCH_LOG.md)
    src/
        extract_pdf.py                  decode every QR/Aztec in the PDF
        assign_serials.py               infer serial labels from positions
        build_master_and_sequential.py  assemble master + sequential list
        generate_batch.py               render SVG print sheets
        verify_reproducibility.py       confirm shipped Batch 1+2 still match
        qa_check_fresh_output.py        end-to-end coverage / ordering check
        fix_a7_layout.py                A7-specific relabel (see below)
        apply_a7_fix.py                 atomic A7 fix applicator
        ...
```

## Getting set up

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install pandas pymupdf zxing-cpp qrcode pillow opencv-python
```

## Pipeline

```powershell
# 1. Decode every QR / Aztec from the source PDF
.\.venv\Scripts\python.exe "007 DATA\src\extract_pdf.py"

# 2. Infer serial labels from positions
.\.venv\Scripts\python.exe "007 DATA\src\assign_serials.py"

# 3. Build the authoritative master + sequential order
.\.venv\Scripts\python.exe "007 DATA\src\build_master_and_sequential.py"

# 4. Generate all 74 fresh SVG print sheets
.\.venv\Scripts\python.exe "007 DATA\src\generate_batch.py" `
    --from-complete "007 DATA\inputs\master_uuids.csv" `
    --serials "007 DATA\inputs\aisle_a_sequential.serials.txt" `
    --output "007 DATA\output\aisle-a-fresh"

# 5. QA
.\.venv\Scripts\python.exe "007 DATA\src\verify_reproducibility.py"
.\.venv\Scripts\python.exe "007 DATA\src\qa_check_fresh_output.py"
```

## Known anomalies (see `007 DATA/BATCH_LOG.md` for details)

- **A7 layout correction (2026-04-21, resolved)**
  Bay A7 is the one lower-aisle bay that deviates from the canonical
  36-tag layout: its column A exists only on shelf rows 3–4, and its
  column E only on shelf rows 1–2 (32 tags total instead of 36).
  Both the raw PDF extraction and the client-supplied solution CSVs
  had silently shifted every A7 serial label. The fix (in
  `fix_a7_layout.py` + `apply_a7_fix.py`) re-decodes pages 13 + 14
  with pixel positions and applies the physically-printed labels.
  The shipped Batch 1 + Batch 2 are unaffected (A7 is not in them)
  and still regenerate byte-identical. See
  `007 DATA/output/a7_fix/a7_diff_report.csv` for the 36-row audit
  trail.
- **One duplicate UUID at A53-2H and A54-2H**
  Source-PDF duplicate (`d8c8654d-bb1c-9969-2b3f-…`). Flagged for
  manual review on the client side.

## Tag text layout fix

Serials with a 2-digit bay number (e.g. `A10-1A` through `A54-4J`)
previously had text that impinged on the QR code. `generate_batch.py`
now shifts the text 1 mm to the right and reduces its font size by
10 % for those serials. Verified via `src/spot_check_tags.py`.
