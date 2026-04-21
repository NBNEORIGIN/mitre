"""
Map UUID disagreements (sequential vs complete_solution) onto shipped batches.

Goal: tell the user exactly how many already-shipped/generated tags have a
UUID that differs from the one in DIP1_Aisle_A_codes_sequential.csv, and
which specific serials are affected.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
SEQ = ROOT / "001 DESIGN" / "DIP1" / "Aisle A" / "DIP1_Aisle_A_codes_sequential.csv"
COMP = Path(__file__).resolve().parent.parent / "inputs" / "COMPLETE_SOLUTION_ALL_52_PAGES.csv"
FIRST100 = Path(__file__).resolve().parent.parent / "inputs" / "FIRST_100_TAGS_MATCHED.csv"
BATCH2_SERIALS = Path(__file__).resolve().parent.parent / "inputs" / "batch-02.serials.txt"
BATCH3_SERIALS = Path(__file__).resolve().parent.parent / "inputs" / "batch-03.serials.txt"


def read_serials_txt(p: Path) -> list[str]:
    lines = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        lines.append(line)
    return lines


def main() -> None:
    seq = pd.read_csv(SEQ)
    comp = pd.read_csv(COMP)

    seq_first = seq.drop_duplicates("serial_number", keep="first").set_index("serial_number")["uuid"]
    comp_map = comp.drop_duplicates("serial", keep="first").set_index("serial")["uuid"]

    common = set(seq_first.index) & set(comp_map.index)
    disagree = {s for s in common if seq_first[s] != comp_map[s]}
    print(f"Total A1-A26 disagreements (sequential vs complete): {len(disagree)}")

    batch1 = pd.read_csv(FIRST100)["Serial"].astype(str).tolist()
    batch2 = read_serials_txt(BATCH2_SERIALS)
    batch3 = read_serials_txt(BATCH3_SERIALS)

    print()
    for name, serials in [("Batch 1 (shipped, QA-confirmed)", batch1),
                          ("Batch 2 (shipped)", batch2),
                          ("Batch 3 (generated, not yet printed)", batch3)]:
        affected = [s for s in serials if s in disagree]
        print(f"{name}: {len(serials)} tags total, {len(affected)} differ from sequential.csv")
        for s in affected[:8]:
            print(f"   {s}:  shipped/complete -> {comp_map[s]}")
            print(f"         sequential.csv  -> {seq_first[s]}")
        if len(affected) > 8:
            print(f"   ... {len(affected) - 8} more")
        print()


if __name__ == "__main__":
    main()
