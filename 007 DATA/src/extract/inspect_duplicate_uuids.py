"""Find UUIDs that appear at more than one physical position in the PDF."""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
pdf = pd.read_csv(ROOT / "007 DATA" / "output" / "extract" / "pdf_derived_serials.csv")

dup = pdf[pdf.duplicated("uuid", keep=False)].sort_values(["uuid", "serial"])
print(f"Distinct UUIDs appearing at >1 physical position: {dup['uuid'].nunique()}")
print(f"Rows involved:                                     {len(dup)}")
print()
print("=== Each duplicated UUID and where it appears ===")
for u, grp in dup.groupby("uuid"):
    serials = grp["serial"].tolist()
    pages = grp["page"].tolist()
    print(f"  {u[:24]}... ->  {serials}  (pages {pages})")
