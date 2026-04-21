"""Apply the A7 fix atomically: overwrite master_uuids.csv and
pdf_derived_serials.csv with corrected A7 labels so the whole pipeline
is internally consistent, then regenerate the sequential order."""
from __future__ import annotations

import csv
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
FIXED_MASTER = REPO / "007 DATA" / "output" / "a7_fix" / "master_uuids_a7_fixed.csv"
MASTER = REPO / "007 DATA" / "inputs" / "master_uuids.csv"
DERIVED = REPO / "007 DATA" / "output" / "extract" / "pdf_derived_serials.csv"


def main() -> int:
    # --- 1. Overwrite master_uuids.csv with the corrected A7 mapping ------
    shutil.copy2(FIXED_MASTER, MASTER)
    master = pd.read_csv(MASTER)
    print(f"master_uuids.csv: {len(master)} rows, A7 count: {sum(master.serial.str.startswith('A7-'))}")

    # --- 2. Relabel A7 rows in pdf_derived_serials.csv --------------------
    derived = pd.read_csv(DERIVED)
    master_uuid_to_serial = dict(zip(master.uuid, master.serial))

    a7_mask = derived.serial.str.startswith("A7-")
    print(f"pdf_derived rows before: {len(derived)} (A7: {a7_mask.sum()})")

    non_a7 = derived[~a7_mask].copy()
    # For A7 rows, keep every column except `serial`, but replace serial
    # using the UUID lookup from the corrected master.
    a7_rows = derived[a7_mask].copy()
    a7_rows["serial"] = a7_rows["uuid"].map(master_uuid_to_serial)
    if a7_rows["serial"].isna().any():
        print("ERROR: some A7 UUIDs could not be found in the corrected master:")
        print(a7_rows[a7_rows["serial"].isna()])
        return 1

    # Re-emit with the same column order, sorted by (page, page_row_idx, page_col_idx)
    fixed_derived = pd.concat([non_a7, a7_rows], ignore_index=True)
    fixed_derived = fixed_derived.sort_values(
        ["page", "page_row_idx", "page_col_idx"]
    ).reset_index(drop=True)
    fixed_derived.to_csv(DERIVED, index=False)
    print(f"pdf_derived rows after:  {len(fixed_derived)} (A7: {(fixed_derived.serial.str.startswith('A7-')).sum()})")

    a7_final = sorted(fixed_derived[fixed_derived.serial.str.startswith("A7-")].serial.tolist())
    print(f"\nA7 serials after fix ({len(a7_final)}): {a7_final}")

    # --- 3. Run build_master_and_sequential.py to regen ordered list -----
    print("\n--- running build_master_and_sequential.py ---")
    result = subprocess.run(
        [sys.executable, str(REPO / "007 DATA" / "src" / "build_master_and_sequential.py")],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    print(result.stdout)
    if result.returncode != 0:
        print("STDERR:", result.stderr)
        return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
