# C184 — DIP1 Aisle A — Clean Pipeline

Minimal, reproducible pipeline for generating UV-print SVG sheets for
DIP1 Aisle A asset tags, rebuilt from the known-good Batch 1 and Batch 2
outputs shipped to the client.

## Proof of correctness

The first 200 tags (Batch 1: A1-A3 partial, Batch 2: A3 remainder–A6
partial) were shipped to the client and confirmed correct. This pipeline
regenerates both batches **byte-identically** from the two authoritative
input CSVs. Any future batch uses the same code path, so the output can
be trusted by construction.

Run `python src/verify_reproducibility.py` after any code change to
reconfirm — it re-renders the 10 shipped SVG sheets and byte-compares
them to the originals under `001 DESIGN/DIP1/Aisle A/UV_PRINT_FILES_SPLIT*`.
Last verified: 2026-04-21, all 10/10 sheets byte-identical.

## Layout

```
007 DATA/
├── README.md                                  # this file
├── BATCH_LOG.md                               # batch-by-batch production record
├── requirements.txt                           # pinned deps (pandas, qrcode, Pillow)
├── .gitignore
├── inputs/
│   ├── COMPLETE_SOLUTION_ALL_52_PAGES.csv     # authoritative serial -> UUID map (932 rows)
│   ├── FIRST_100_TAGS_MATCHED.csv             # Batch 1 pre-ordered (kept for verification)
│   └── batch-02.serials.txt                   # Batch 2 serial order (one per line)
├── src/
│   ├── generate_batch.py                      # single generator for all batches
│   └── verify_reproducibility.py              # diffs regenerated SVGs vs shipped SVGs
└── output/
    ├── batch-01/                              # regenerated Batch 1 (matches shipped)
    └── batch-02/                              # regenerated Batch 2 (matches shipped)
```

## Dependencies

- Python 3.13 (tested with 3.13.3)
- Packages are version-pinned in `requirements.txt`. Install into the
  existing project `.venv` at the repo root, or create a fresh one:

  ```powershell
  cd "D:\Google Drive\My Drive\001 NBNE\003 CUSTOM ORDERS\C184 - MITER INDUSTRIAL"
  .\.venv\Scripts\python.exe -m pip install -r "007 DATA\requirements.txt"
  ```

## Usage

All commands from the project root
(`C184 - MITER INDUSTRIAL/`), using the repo-root `.venv`.

### Reproduce shipped Batch 1 (from the pre-matched CSV)

```powershell
.\.venv\Scripts\python.exe "007 DATA\src\generate_batch.py" `
    --from-csv "007 DATA\inputs\FIRST_100_TAGS_MATCHED.csv" `
    --output   "007 DATA\output\batch-01"
```

### Reproduce shipped Batch 2 (from the authoritative table + serial list)

```powershell
.\.venv\Scripts\python.exe "007 DATA\src\generate_batch.py" `
    --from-complete "007 DATA\inputs\COMPLETE_SOLUTION_ALL_52_PAGES.csv" `
    --serials       "007 DATA\inputs\batch-02.serials.txt" `
    --output        "007 DATA\output\batch-02"
```

### Verify reproducibility

```powershell
.\.venv\Scripts\python.exe "007 DATA\src\verify_reproducibility.py"
```

Exits 0 if every regenerated SVG matches (byte-for-byte or semantically)
the corresponding shipped SVG; non-zero otherwise.

### Produce a new batch (e.g. Batch 3)

1. Create `inputs/batch-03.serials.txt` with 100 serials, one per line,
   in the desired physical print order. Comments (`#`) and blank lines
   are allowed. The next batch starts at `A6-1K` (see `BATCH_LOG.md`).
2. Run:

   ```powershell
   .\.venv\Scripts\python.exe "007 DATA\src\generate_batch.py" `
       --from-complete "007 DATA\inputs\COMPLETE_SOLUTION_ALL_52_PAGES.csv" `
       --serials       "007 DATA\inputs\batch-03.serials.txt" `
       --output        "007 DATA\output\batch-03"
   ```

3. Sanity-check counts (script prints them). Spot-check a few SVGs.
4. Append a new entry to `BATCH_LOG.md`.

## Tag / sheet specifications (informational)

All constants live in `src/generate_batch.py`.

| Spec | Value |
|---|---|
| Tag size | 50 mm × 30 mm |
| QR + text area | 34.425 mm × 16.574 mm, vertically offset +1.5 mm |
| QR ECC / version | M / 1 (box_size=10, border=0) |
| Font | Arial bold, 2.25 mm |
| Grid per sheet | 5 cols × 5 rows = 25 tags |
| Tag fill order | right→left per row, bottom→top |
| Sheet size | 250 mm × 150 mm |
| Registration mark | 0.1 mm black square, bottom-right |
| Mount split | row 4 → adhesive; rows 1–3 → screw |

## Data sources (single source of truth)

- **`inputs/COMPLETE_SOLUTION_ALL_52_PAGES.csv`** — 932 rows of
  authoritative serial → UUID mapping for Aisle A. Columns: `page, row,
  column, uuid, serial, code_type, status`. This is the only CSV that
  should be consulted for UUIDs. Do not edit by hand; if a UUID is
  corrected, add a new row with `status` reflecting the change.
- **`inputs/FIRST_100_TAGS_MATCHED.csv`** — preserved as-is so that
  `verify_reproducibility.py` can confirm Batch 1 still reproduces.
- **`inputs/batch-02.serials.txt`** — human-readable ordered list of the
  100 serials that made up Batch 2. Preserved for verification.

## Relationship to the old project tree

The original project accumulated ~200 one-off scripts across three
locations (`001 DESIGN/`, `001 DESIGN/004 QA/`, `001 DESIGN/DIP1/Aisle
A/scripts/`). None of those are needed for the forward path; this
folder contains everything required to produce any future batch. The
old folders can be archived in place — `verify_reproducibility.py`
still reads the shipped SVGs from `001 DESIGN/DIP1/Aisle A/`, so don't
delete those two UV_PRINT_FILES_SPLIT folders.
