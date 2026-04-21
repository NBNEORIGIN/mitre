"""
audit_sequential_csv.py

Answers the key question: does DIP1_Aisle_A_codes_sequential.csv actually
describe more tags than COMPLETE_SOLUTION_ALL_52_PAGES.csv (in which case
we missed half), or is it the same ~932 serials duplicated (in which
case the existing production plan is already complete)?

Writes a short, human-readable report to stdout.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
AISLE_A = PROJECT_ROOT / "001 DESIGN" / "DIP1" / "Aisle A"
SEQ_CSV = AISLE_A / "DIP1_Aisle_A_codes_sequential.csv"
COMPLETE = Path(__file__).resolve().parent.parent / "inputs" / "COMPLETE_SOLUTION_ALL_52_PAGES.csv"


def banner(msg: str) -> None:
    print()
    print("=" * 72)
    print(msg)
    print("=" * 72)


def main() -> int:
    print(f"Reading: {SEQ_CSV}")
    print(f"Reading: {COMPLETE}")
    seq = pd.read_csv(SEQ_CSV)
    comp = pd.read_csv(COMPLETE)

    banner("1. Basic counts")
    print(f"  sequential.csv rows        : {len(seq)}")
    print(f"  sequential.csv unique serials: {seq['serial_number'].nunique()}")
    print(f"  sequential.csv unique UUIDs  : {seq['uuid'].nunique()}")
    print()
    print(f"  complete_solution.csv rows        : {len(comp)}")
    print(f"  complete_solution.csv unique serials: {comp['serial'].nunique()}")
    print(f"  complete_solution.csv unique UUIDs  : {comp['uuid'].nunique()}")

    banner("2. Why 1832 rows? Duplicates-per-serial histogram")
    dup_counts = seq["serial_number"].value_counts()
    per_serial_rows = Counter(dup_counts.values)
    for rows_per_serial, n_serials in sorted(per_serial_rows.items()):
        print(f"  {n_serials:4d} serial(s) appear {rows_per_serial}x in sequential.csv")

    banner("3. For serials that appear 2+ times, do they have consistent UUIDs?")
    multi = dup_counts[dup_counts > 1].index.tolist()
    consistent, inconsistent = 0, 0
    examples_inconsistent = []
    for s in multi:
        uuids = seq.loc[seq["serial_number"] == s, "uuid"].unique()
        if len(uuids) == 1:
            consistent += 1
        else:
            inconsistent += 1
            if len(examples_inconsistent) < 5:
                examples_inconsistent.append((s, list(uuids)))
    print(f"  consistent (same UUID on all rows)  : {consistent}")
    print(f"  inconsistent (different UUID on rows): {inconsistent}")
    if examples_inconsistent:
        print("  examples of inconsistent:")
        for s, uuids in examples_inconsistent:
            print(f"    {s}: {uuids}")

    banner("4. Overlap between the two CSVs (by serial)")
    seq_serials = set(seq["serial_number"].astype(str))
    comp_serials = set(comp["serial"].astype(str))
    print(f"  in sequential only  : {len(seq_serials - comp_serials)}")
    print(f"  in complete only    : {len(comp_serials - seq_serials)}")
    print(f"  in both             : {len(seq_serials & comp_serials)}")
    only_in_seq = sorted(seq_serials - comp_serials)
    only_in_comp = sorted(comp_serials - seq_serials)
    if only_in_seq:
        print(f"  first 10 only-in-sequential: {only_in_seq[:10]}")
    if only_in_comp:
        print(f"  first 10 only-in-complete  : {only_in_comp[:10]}")

    banner("5. Where UUIDs disagree (same serial, different UUIDs)")
    seq_first = seq.drop_duplicates("serial_number", keep="first").set_index("serial_number")["uuid"]
    comp_map = comp.drop_duplicates("serial", keep="first").set_index("serial")["uuid"]
    common = seq_serials & comp_serials
    disagree = [s for s in common if seq_first[s] != comp_map[s]]
    print(f"  serials in both but with different UUIDs: {len(disagree)}")
    for s in disagree[:10]:
        print(f"    {s}: sequential={seq_first[s]!r}  complete={comp_map[s]!r}")

    banner("6. Does sequential.csv contain any physical tag positions we're NOT producing?")
    missing_from_production = seq_serials - comp_serials
    if missing_from_production:
        print(f"  {len(missing_from_production)} serial(s) exist in sequential but NOT in complete_solution.")
        print("  If these are real, they represent tags we haven't planned to produce.")
        for s in sorted(missing_from_production)[:30]:
            print(f"    {s}")
    else:
        print("  No serials exist only in sequential.csv.")

    banner("Conclusion")
    if not missing_from_production:
        n_uniq = seq["serial_number"].nunique()
        print(
            f"  sequential.csv has {len(seq)} rows but only {n_uniq} unique serials "
            f"(duplicated ~{len(seq)/n_uniq:.1f}x on average)."
        )
        print("  Every unique sequential-serial is already in complete_solution (= our production set).")
        print("  The big row count is duplication, not extra tags. No tags have been missed.")
    else:
        print(f"  WARNING: {len(missing_from_production)} sequential-only serials detected.")
        print("  These need to be reviewed before finalising production.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
