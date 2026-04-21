"""
build_master_and_sequential.py

Assembles the single authoritative UUID table and sequential serial order
for Aisle A so generate_batch.py can produce every physical tag fresh
for QA.

Inputs (read-only):
  - 007 DATA/output/extract/pdf_derived_serials.csv
      1828 serials decoded from the source PDF via the DPI-laddered zxing
      pipeline. This is the authoritative set of physical tags — the
      four "missing" A7 slots (A7-1L, A7-2L, A7-3D, A7-4D) are the known
      anomalies noted in BATCH_LOG.md ("936 theoretical, 932 real for
      A1-A26" + 896 real for A27-A54 = 1828 total).
  - 007 DATA/inputs/COMPLETE_SOLUTION_ALL_52_PAGES.csv
      QA-confirmed UUIDs for A1-A26 (932 rows). Used only to cross-check
      that the PDF-derived UUIDs agree with the QA-confirmed ones for
      the 932 already-shipped tags.

Outputs (overwritten each run):
  - 007 DATA/inputs/master_uuids.csv
      Columns: serial, uuid. One row per physical tag (1828 rows).
  - 007 DATA/inputs/aisle_a_sequential.serials.txt
      1828 serials, one per line, in the sequential print order the
      client requested (per-bay: row 1 cols, row 2 cols, ...). Shelf
      row 4 rows are included in this file; generate_batch.py splits
      them onto SHELF_4_ADHESIVE sheets automatically.

Run:
  .\\.venv\\Scripts\\python.exe "007 DATA\\src\\build_master_and_sequential.py"
"""
from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
PDF_DERIVED = REPO / "007 DATA" / "output" / "extract" / "pdf_derived_serials.csv"
COMPLETE = REPO / "007 DATA" / "inputs" / "COMPLETE_SOLUTION_ALL_52_PAGES.csv"
OUT_MASTER = REPO / "007 DATA" / "inputs" / "master_uuids.csv"
OUT_ORDER = REPO / "007 DATA" / "inputs" / "aisle_a_sequential.serials.txt"

LOWER_P1_COLS = ["A", "B", "C", "D"]
LOWER_P2_COLS_KL = ["E", "G", "H", "J", "K", "L"]  # rows 1-2
LOWER_P2_COLS_NO_KL = ["E", "G", "H", "J"]  # rows 3-4
UPPER_P1_COLS = ["A", "B", "C", "D"]
UPPER_P2_COLS = ["E", "G", "H", "J"]

# Bays that deviate from the canonical lower-aisle 36-tag layout.
# A7 is missing column A on shelf rows 1 & 2 (those shelf positions do not
# physically exist in that bay) and column E on shelf rows 3 & 4. Verified
# by direct inspection of pages 13 & 14 of DIP1 - AISLE A.pdf.
BAY_LAYOUT_OVERRIDES: dict[str, dict[int, list[str]]] = {
    "A7": {
        1: ["B", "C", "D", "E", "G", "H", "J", "K", "L"],
        2: ["B", "C", "D", "E", "G", "H", "J", "K", "L"],
        3: ["A", "B", "C", "D", "G", "H", "J"],
        4: ["A", "B", "C", "D", "G", "H", "J"],
    },
}


def _lower_bay_row_cols(row: int) -> list[str]:
    cols = LOWER_P1_COLS[:]
    cols += LOWER_P2_COLS_KL if row in (1, 2) else LOWER_P2_COLS_NO_KL
    return cols


def theoretical_full_sequence() -> list[str]:
    """Every physical slot, in sequential print order. 1828 entries.

    Bays listed in BAY_LAYOUT_OVERRIDES use their explicit column set for
    each shelf row. All other lower-aisle bays follow the canonical 36-tag
    layout; upper-aisle bays (A27-A54) follow the canonical 16-tag layout.
    """
    seq: list[str] = []
    for bay in range(1, 27):
        b = f"A{bay}"
        override = BAY_LAYOUT_OVERRIDES.get(b)
        for row in (1, 2, 3, 4):
            cols = override[row] if override else _lower_bay_row_cols(row)
            for c in cols:
                seq.append(f"{b}-{row}{c}")
    for bay in range(27, 55):
        b = f"A{bay}"
        for row in (1, 2, 3, 4):
            for c in UPPER_P1_COLS + UPPER_P2_COLS:
                seq.append(f"{b}-{row}{c}")
    return seq


def main() -> int:
    derived = pd.read_csv(PDF_DERIVED)
    uuid_map = dict(zip(derived.serial, derived.uuid))

    # Cross-check: every UUID the PDF produced for an A1-A26 serial must
    # match the QA-confirmed complete_solution entry. If it doesn't, the
    # PDF-extract pipeline has drifted and we should stop.
    # NOTE: A7 is excluded from this cross-check because both the source
    # PDF extraction and complete_solution were generated with the same
    # grid-filling assumption that incorrectly labeled A7 (which has 32
    # physical tags, not the canonical 36). The true A7 mapping comes
    # from fix_a7_layout.py and is the ground truth in master_uuids.csv.
    complete = pd.read_csv(COMPLETE)
    complete_map = dict(zip(complete.serial, complete.uuid))
    disagreements = []
    for s, u in uuid_map.items():
        if s.startswith("A7-"):
            continue
        if s in complete_map and complete_map[s] != u:
            disagreements.append((s, u, complete_map[s]))
    if disagreements:
        print("ERROR: PDF-derived UUIDs disagree with QA-confirmed complete_solution:")
        for s, pdf_u, comp_u in disagreements[:20]:
            print(f"  {s}  pdf={pdf_u}  complete={comp_u}")
        return 1
    print(f"Cross-check OK: all {sum(1 for s in uuid_map if s in complete_map and not s.startswith('A7-'))} "
          f"non-A7 shipped-batch serials match QA-confirmed UUIDs.")

    full_seq = theoretical_full_sequence()
    print(f"Physical slots (A1-A54, A7 layout corrected): {len(full_seq)}")

    physical_seq = [s for s in full_seq if s in uuid_map]
    missing_from_pdf = [s for s in full_seq if s not in uuid_map]
    print(f"Physical tags (present in PDF extraction): {len(physical_seq)}")
    if missing_from_pdf:
        print(f"WARNING: {len(missing_from_pdf)} slots in the theoretical "
              f"layout are not in pdf_derived_serials.csv: {missing_from_pdf}")

    # Sanity: every decoded UUID should have a sequential slot to print on
    extra_in_pdf = [s for s in uuid_map if s not in set(full_seq)]
    if extra_in_pdf:
        print(f"WARNING: {len(extra_in_pdf)} decoded serials are not in "
              f"the theoretical layout: {extra_in_pdf[:20]}")

    # Write master UUIDs (serial,uuid) in sequential order
    OUT_MASTER.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_MASTER, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["serial", "uuid"])
        w.writeheader()
        for s in physical_seq:
            w.writerow({"serial": s, "uuid": uuid_map[s]})

    # Write the ordered serial list (what generate_batch.py --serials consumes)
    with open(OUT_ORDER, "w", encoding="utf-8") as f:
        f.write("\n".join(physical_seq) + "\n")

    print(f"\nWrote {OUT_MASTER} ({len(physical_seq)} rows)")
    print(f"Wrote {OUT_ORDER} ({len(physical_seq)} serials)")

    # Mount split summary (row 4 -> adhesive, rows 1-3 -> screw)
    screw = sum(1 for s in physical_seq if not s.split("-")[-1].startswith("4"))
    adhesive = len(physical_seq) - screw
    print(f"\nMount split: {screw} screw-mount + {adhesive} adhesive")
    print(f"Estimated SVG sheets: {-(-screw // 25)} screw + {-(-adhesive // 25)} adhesive")

    # Flag duplicate UUIDs (known source-PDF anomaly — same UUID at 2 serials)
    dup_u = {u: c for u, c in Counter(uuid_map.values()).items() if c > 1}
    if dup_u:
        print(f"\nNOTE: {len(dup_u)} UUID(s) appear on >1 physical tag "
              f"(source-PDF duplicate):")
        for u, c in dup_u.items():
            ss = [s for s, uu in uuid_map.items() if uu == u]
            print(f"  {u}  x{c}  serials: {ss}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
