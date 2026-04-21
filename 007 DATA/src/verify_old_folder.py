"""Verify every tag placement in the older 'Aisle A 201 to 932' output folder
(generated 26 Mar 2026, predates the fresh pipeline) against the current
master_uuids.csv."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, "007 DATA/src")
from verify_tag_placement import check_sheet

REPO = Path(".")
OLD = REPO / "001 DESIGN" / "DIP1" / "Aisle A" / "Aisle A 201 to 932"
master = pd.read_csv(REPO / "007 DATA" / "inputs" / "master_uuids.csv")
master_map = dict(zip(master.serial, master.uuid))

sheets = sorted(OLD.glob("*.svg"))
print(f"checking {len(sheets)} older sheets against current master_uuids.csv")

all_mis = []
for i, sheet in enumerate(sheets, 1):
    mis = check_sheet(sheet, master_map)
    if mis:
        all_mis.extend(mis)
    if i % 5 == 0 or i == len(sheets):
        print(f"  [{i}/{len(sheets)}]  cumulative mismatches: {len(all_mis)}")

print(f"\nTOTAL mismatches in 'Aisle A 201 to 932': {len(all_mis)}")

# Focus on A15-2A specifically
a15_2a = [m for m in all_mis if m["serial"] == "A15-2A"]
print(f"A15-2A mismatches: {len(a15_2a)}")
for m in a15_2a:
    print(f"  {m['sheet']}  expected={m['expected']}  actual={m['actual']}  reason={m['reason']}")

if all_mis:
    out = REPO / "007 DATA" / "output" / "old_folder_mismatches.csv"
    pd.DataFrame(all_mis).to_csv(out, index=False)
    print(f"\nReport -> {out}")

    # First 25 mismatches overall
    print("\n=== first 25 mismatches ===")
    for m in all_mis[:25]:
        if m["actual"] is None:
            print(f"  {m['sheet']:45s}  {m['serial']:<10}  NO DECODE  (expected {m['expected']})")
        else:
            print(f"  {m['sheet']:45s}  {m['serial']:<10}  expected={m['expected']}  actual={m['actual']}")
