"""Quick followup diagnostics for the sequential CSV gap."""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
SEQ = ROOT / "001 DESIGN" / "DIP1" / "Aisle A" / "DIP1_Aisle_A_codes_sequential.csv"
COMP = Path(__file__).resolve().parent.parent / "inputs" / "COMPLETE_SOLUTION_ALL_52_PAGES.csv"


def bay(s: str) -> int | None:
    m = re.match(r"A(\d+)-", str(s))
    return int(m.group(1)) if m else None


def main() -> None:
    seq = pd.read_csv(SEQ)
    comp = pd.read_csv(COMP)
    seq["bay"] = seq["serial_number"].map(bay)
    comp["bay"] = comp["serial"].map(bay)

    print("== Bay coverage ==")
    sbays = sorted(seq["bay"].dropna().unique().astype(int).tolist())
    cbays = sorted(comp["bay"].dropna().unique().astype(int).tolist())
    print(f"  sequential.csv bays: A{sbays[0]}..A{sbays[-1]}  (count={len(sbays)})")
    print(f"  complete.csv bays  : A{cbays[0]}..A{cbays[-1]}  (count={len(cbays)})")

    print()
    print("== Tags per bay (sequential.csv) ==")
    per_bay = seq.groupby("bay").size().astype(int)
    for b in sorted(per_bay.index):
        marker = "  " if b <= 26 else "* "   # mark bays missing from our production set
        print(f"  {marker}A{int(b):2d}: {per_bay[b]} tags")

    print()
    print("== A27+ block summary (the 900 currently un-planned serials) ==")
    missing = seq[seq["bay"] >= 27]
    print(f"  rows:              {len(missing)}")
    print(f"  unique serials:    {missing['serial_number'].nunique()}")
    print(f"  unique UUIDs:      {missing['uuid'].nunique()}")
    print(f"  blank UUIDs:       {missing['uuid'].isna().sum()}")
    print()
    print("  extraction_status breakdown:")
    print(missing["extraction_status"].value_counts().to_string())
    print()
    print("  extraction_method breakdown:")
    print(missing["extraction_method"].value_counts().to_string())
    print()
    print("  duplicates column distribution:")
    print(missing["duplicates"].value_counts(dropna=False).to_string())

    print()
    print("== Do any A27+ serials share a UUID with an A1..A26 serial? ==")
    lower_uuids = set(comp["uuid"].astype(str))
    collisions = missing[missing["uuid"].astype(str).isin(lower_uuids)]
    print(f"  rows in A27+ whose UUID also appears in complete_solution (A1-A26): {len(collisions)}")
    if len(collisions):
        print("  first 10 collisions:")
        for _, row in collisions.head(10).iterrows():
            match_serial = comp.loc[comp["uuid"] == row["uuid"], "serial"].iloc[0]
            print(f"    {row['serial_number']}  uuid={row['uuid']}  also used for: {match_serial}")

    print()
    print("== Source PDFs known to exist ==")
    pdf_dir = ROOT / "001 DESIGN" / "DIP1" / "Aisle A"
    for p in sorted(pdf_dir.glob("*.pdf")):
        print(f"  {p.name}  ({p.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
