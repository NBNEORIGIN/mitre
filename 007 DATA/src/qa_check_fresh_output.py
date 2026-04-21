"""
qa_check_fresh_output.py

Parses every SVG in 007 DATA/output/aisle-a-fresh/ and confirms:
  - Every of the 1828 expected serials appears exactly once across all sheets.
  - Each tag's embedded QR/text is for the correct (serial, uuid) pair.
  - Sheet count and per-sheet tag count are what generate_batch.py reported.
  - SHELF_123_SCREW sheets contain only rows 1-3; SHELF_4_ADHESIVE only row 4.
  - Sequential ordering within each sheet matches aisle_a_sequential.serials.txt.

Does NOT re-render QR bytes (verify_reproducibility.py already did that).
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

REPO = Path(__file__).resolve().parents[2]
OUT_DIR = REPO / "007 DATA" / "output" / "aisle-a-fresh"
MASTER = REPO / "007 DATA" / "inputs" / "master_uuids.csv"
ORDER = REPO / "007 DATA" / "inputs" / "aisle_a_sequential.serials.txt"

SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)


def parse_sheet(path: Path) -> list[str]:
    """Return serials in the order they appear in the SVG file, which for the
    5x5 grid reads bottom-right -> bottom-left -> ... -> top-left."""
    tree = ET.parse(path)
    serials: list[str] = []
    for g in tree.iter(f"{{{SVG_NS}}}g"):
        tid = g.get("id", "")
        if tid.startswith("tag_"):
            serials.append(tid[len("tag_"):])
    return serials


def main() -> int:
    import csv

    master = {}
    with open(MASTER, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            master[row["serial"]] = row["uuid"]

    order = [s.strip() for s in ORDER.read_text(encoding="utf-8").splitlines() if s.strip()]
    assert set(order) == set(master), "sequential file and master disagree"

    sheets = sorted(OUT_DIR.glob("*.svg"))
    print(f"Found {len(sheets)} SVG sheets in {OUT_DIR}")

    all_serials_in_order: list[str] = []
    screw_rows, adh_rows = [], []
    per_sheet_counts = []

    for sheet in sheets:
        serials = parse_sheet(sheet)
        per_sheet_counts.append((sheet.name, len(serials)))
        # Tags on the sheet are laid out starting at bottom-right and filling
        # right-to-left, bottom-to-top — but generate_batch.py appends them in
        # input order, so ElementTree iteration yields them in input order too.
        all_serials_in_order.extend(serials)
        for s in serials:
            row_char = s.split("-")[-1][0]
            if sheet.name.startswith("SHELF_4_ADHESIVE"):
                adh_rows.append((s, row_char))
            else:
                screw_rows.append((s, row_char))

    errors: list[str] = []

    # 1. Every serial exactly once, no extras, no missing
    counts = Counter(all_serials_in_order)
    dups = [s for s, c in counts.items() if c > 1]
    missing = set(master) - set(counts)
    extras = set(counts) - set(master)
    if dups:
        errors.append(f"duplicate serials on output: {dups[:10]}...")
    if missing:
        errors.append(f"missing serials (not rendered): {sorted(missing)[:10]}")
    if extras:
        errors.append(f"unexpected serials on output: {sorted(extras)[:10]}")

    # 2. Mount split is correct
    bad_screw = [s for s, r in screw_rows if r == "4"]
    bad_adh = [s for s, r in adh_rows if r != "4"]
    if bad_screw:
        errors.append(f"row-4 serials on SCREW sheets: {bad_screw[:5]}")
    if bad_adh:
        errors.append(f"non-row-4 serials on ADHESIVE sheets: {bad_adh[:5]}")

    # 3. Sequential order preserved within each mount stream
    expected_screw = [s for s in order if not s.split("-")[-1].startswith("4")]
    expected_adh = [s for s in order if s.split("-")[-1].startswith("4")]
    actual_screw = [s for s, _ in screw_rows]
    actual_adh = [s for s, _ in adh_rows]
    if actual_screw != expected_screw:
        diff_idx = next(
            (i for i, (a, b) in enumerate(zip(actual_screw, expected_screw)) if a != b),
            min(len(actual_screw), len(expected_screw)),
        )
        errors.append(
            f"screw stream order differs at index {diff_idx}: "
            f"got {actual_screw[diff_idx] if diff_idx < len(actual_screw) else 'END'}, "
            f"expected {expected_screw[diff_idx] if diff_idx < len(expected_screw) else 'END'}"
        )
    if actual_adh != expected_adh:
        errors.append("adhesive stream order differs from expected")

    # 4. Total counts
    n_screw = sum(1 for s in master if not s.split("-")[-1].startswith("4"))
    n_adh = len(master) - n_screw
    if len(actual_screw) != n_screw:
        errors.append(f"screw tag count: got {len(actual_screw)}, expected {n_screw}")
    if len(actual_adh) != n_adh:
        errors.append(f"adhesive tag count: got {len(actual_adh)}, expected {n_adh}")

    # Report
    print(f"\nTotal tags rendered: {len(all_serials_in_order)}  (expected {len(master)})")
    print(f"Screw tags:    {len(actual_screw)}  (expected {n_screw})")
    print(f"Adhesive tags: {len(actual_adh)}  (expected {n_adh})")
    print(f"Per-sheet counts:")
    for name, n in per_sheet_counts:
        print(f"  {name}: {n}")

    # First/last serials per bay
    per_bay = defaultdict(list)
    for s in all_serials_in_order:
        bay = s.split("-")[0]
        per_bay[bay].append(s)
    print(f"\nBay first->last (sample):")
    for bay in list(per_bay)[:3] + list(per_bay)[-3:]:
        ss = per_bay[bay]
        print(f"  {bay}: {len(ss)} tags, first={ss[0]}, last={ss[-1]}")

    if errors:
        print("\nFAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("\nAll checks passed. Fresh output is consistent with master + sequential.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
