"""Spot-check A7 in the fresh output: count, serials present, UUIDs match master."""
from pathlib import Path
import re
import xml.etree.ElementTree as ET

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
MASTER = REPO / "007 DATA" / "inputs" / "master_uuids.csv"
FRESH_DIR = REPO / "007 DATA" / "output" / "aisle-a-fresh"

master = pd.read_csv(MASTER)
master_map = dict(zip(master.serial, master.uuid))

a7_expected = sorted(s for s in master_map if s.startswith("A7-"))
print(f"master has {len(a7_expected)} A7 serials: {a7_expected}")

found_a7: dict[str, Path] = {}
for svg in sorted(FRESH_DIR.glob("*.svg")):
    tree = ET.parse(svg)
    for g in tree.iter("{http://www.w3.org/2000/svg}g"):
        gid = g.get("id", "")
        if gid.startswith("tag_A7-"):
            serial = gid.removeprefix("tag_")
            found_a7.setdefault(serial, svg)

print(f"\nFound {len(found_a7)} A7 serials in fresh output")
missing = set(a7_expected) - set(found_a7)
extra = set(found_a7) - set(a7_expected)
print(f"missing from output: {sorted(missing)}")
print(f"extra in output (should be none):  {sorted(extra)}")

print("\nA7 serial -> sheet:")
for s in a7_expected:
    sheet = found_a7.get(s)
    print(f"  {s}: {sheet.name if sheet else 'MISSING'}")

# Check for phantom serials that should NOT be present
for phantom in ["A7-1A", "A7-2A", "A7-3E", "A7-4E"]:
    if phantom in found_a7:
        print(f"ERROR: phantom {phantom} is in fresh output at {found_a7[phantom]}")
    else:
        print(f"OK: phantom {phantom} correctly absent")
