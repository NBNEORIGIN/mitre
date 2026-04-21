"""
sanity_check_batch_03.py

Post-generation checks:
  1. Every serial in batch-03 also appears in COMPLETE_SOLUTION.
  2. Batches 1 + 2 + 3 = 932 (the full COMPLETE_SOLUTION set, no overlaps, no gaps).
  3. The tag IDs inside the generated SVGs preserve the client's input order
     (i.e. screw sheets iterate through non-row-4 serials in batch-03 order
     and adhesive sheets iterate through row-4 serials in batch-03 order).
"""

from __future__ import annotations

import sys
from pathlib import Path
from xml.etree import ElementTree as ET

import pandas as pd

HERE = Path(__file__).resolve().parent
INPUTS = HERE.parent / "inputs"
OUTPUT = HERE.parent / "output" / "batch-03"
SVG_NS = "{http://www.w3.org/2000/svg}"


def read_serials_file(path: Path) -> list[str]:
    return [
        s.strip()
        for s in path.read_text(encoding="utf-8").splitlines()
        if s.strip() and not s.strip().startswith("#")
    ]


def tag_ids_in_sheet_order(svg_path: Path) -> list[str]:
    """Return the tag IDs in the order they appear in the SVG's XML
    (= the order the generator placed them into the sheet = the input order)."""
    ids = []
    for g in ET.parse(svg_path).getroot().findall(f".//{SVG_NS}g[@id]"):
        gid = g.get("id", "")
        if gid.startswith("tag_"):
            ids.append(gid[4:])
    return ids


def main() -> int:
    complete = pd.read_csv(INPUTS / "COMPLETE_SOLUTION_ALL_52_PAGES.csv")
    complete_set = set(complete["serial"].astype(str))
    batch1 = set(pd.read_csv(INPUTS / "FIRST_100_TAGS_MATCHED.csv")["Serial"].astype(str))
    batch2 = set(read_serials_file(INPUTS / "batch-02.serials.txt"))
    batch3 = read_serials_file(INPUTS / "batch-03.serials.txt")
    batch3_set = set(batch3)

    problems = 0

    print("Check 1 — every batch-03 serial exists in COMPLETE_SOLUTION")
    missing = [s for s in batch3 if s not in complete_set]
    if missing:
        print(f"  FAIL: {len(missing)} serial(s) not in COMPLETE_SOLUTION: {missing[:10]}")
        problems += 1
    else:
        print(f"  OK  ({len(batch3)} serials)")

    print()
    print("Check 2 — Batches 1 + 2 + 3 fully partition COMPLETE_SOLUTION")
    print(f"  Batch 1: {len(batch1)}  Batch 2: {len(batch2)}  Batch 3: {len(batch3_set)}")
    print(f"  COMPLETE_SOLUTION: {len(complete_set)}")
    all_batches = batch1 | batch2 | batch3_set
    b1_b2 = batch1 & batch2
    b1_b3 = batch1 & batch3_set
    b2_b3 = batch2 & batch3_set
    if b1_b2 or b1_b3 or b2_b3:
        print(f"  FAIL: overlapping serials b1&b2={b1_b2} b1&b3={b1_b3} b2&b3={b2_b3}")
        problems += 1
    else:
        print(f"  OK  no overlaps between batches")
    missing_from_batches = complete_set - all_batches
    unexpected_in_batches = all_batches - complete_set
    if missing_from_batches:
        print(f"  FAIL: {len(missing_from_batches)} COMPLETE_SOLUTION serial(s) not in any batch: {sorted(missing_from_batches)[:20]}")
        problems += 1
    elif unexpected_in_batches:
        print(f"  FAIL: {len(unexpected_in_batches)} serial(s) in a batch but not in COMPLETE_SOLUTION: {sorted(unexpected_in_batches)[:20]}")
        problems += 1
    else:
        print("  OK  every COMPLETE_SOLUTION serial is in exactly one batch")

    print()
    print("Check 3 — SVG tag order reflects client's sequential input order")
    expected_screw = [s for s in batch3 if not ("-" in s and "4" in s.split("-")[-1])]
    expected_adh = [s for s in batch3 if ("-" in s and "4" in s.split("-")[-1])]

    got_screw = []
    for svg in sorted(OUTPUT.glob("SHELF_123_SCREW_SHEET_*.svg")):
        got_screw.extend(tag_ids_in_sheet_order(svg))
    got_adh = []
    for svg in sorted(OUTPUT.glob("SHELF_4_ADHESIVE_SHEET_*.svg")):
        got_adh.extend(tag_ids_in_sheet_order(svg))

    if got_screw == expected_screw:
        print(f"  OK  screw sheets: {len(got_screw)} tags in expected order")
        print(f"       first 6: {got_screw[:6]}")
        print(f"       last  6: {got_screw[-6:]}")
    else:
        print("  FAIL: screw-sheet order does not match expected input order")
        for i, (e, g) in enumerate(zip(expected_screw, got_screw)):
            if e != g:
                print(f"    position {i}: expected {e!r}, got {g!r}")
                break
        problems += 1

    if got_adh == expected_adh:
        print(f"  OK  adhesive sheets: {len(got_adh)} tags in expected order")
        print(f"       first 6: {got_adh[:6]}")
        print(f"       last  6: {got_adh[-6:]}")
    else:
        print("  FAIL: adhesive-sheet order does not match expected input order")
        for i, (e, g) in enumerate(zip(expected_adh, got_adh)):
            if e != g:
                print(f"    position {i}: expected {e!r}, got {g!r}")
                break
        problems += 1

    print()
    if problems:
        print(f"RESULT: {problems} check(s) FAILED")
        return 1
    print("RESULT: ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
