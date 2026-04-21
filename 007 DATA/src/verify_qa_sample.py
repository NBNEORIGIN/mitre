"""Verify the QA sample sheets: scan every QR/Aztec and confirm it
matches the expected UUID for its placed serial position."""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "007 DATA" / "src"))

from verify_tag_placement import check_sheet, REPO as _REPO  # reuse logic
import pandas as pd

SAMPLE_DIR = REPO / "007 DATA" / "output" / "qa-sample"
MASTER = REPO / "007 DATA" / "inputs" / "master_uuids.csv"


def main() -> int:
    master = pd.read_csv(MASTER)
    master_map = dict(zip(master.serial, master.uuid))
    sheets = sorted(SAMPLE_DIR.glob("*.svg"))
    print(f"Scanning {len(sheets)} QA sample sheet(s)...")
    all_mis = []
    for sheet in sheets:
        mis = check_sheet(sheet, master_map)
        print(f"  {sheet.name:45s}  mismatches: {len(mis)}")
        all_mis.extend(mis)
    if all_mis:
        print("\nMISMATCHES:")
        for m in all_mis:
            print(f"  {m}")
        return 1
    print("\nPASS: every tag in the QA sample contains the correct UUID.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
