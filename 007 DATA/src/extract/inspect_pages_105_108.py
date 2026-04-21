"""Inspect pages 105-108 (all Aztec) -- does treating them as normal upper bays work?"""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
pdf = pd.read_csv(ROOT / "007 DATA" / "output" / "extract" / "pdf_derived_serials.csv")
rec = pd.read_csv(ROOT / "007 DATA" / "output" / "extract" / "reconcile.csv")
idx = pd.read_csv(ROOT / "007 DATA" / "output" / "extract" / "raw_symbols_indexed.csv")
seq = pd.read_csv(ROOT / "001 DESIGN" / "DIP1" / "Aisle A" / "DIP1_Aisle_A_codes_sequential.csv")

print("=== Pages 105-108: assignment + sequential agreement ===")
for pg in [105, 106, 107, 108]:
    sub = pdf[pdf["page"] == pg].sort_values(["page_row_idx", "page_col_idx"])
    fmts = sub["symbol_format"].unique().tolist()
    print(f"\n  page {pg} ({len(sub)} tags, format={fmts}):")
    for _, r in sub.iterrows():
        cls_df = rec[rec["serial"] == r["serial"]]
        cls = cls_df["classification"].iloc[0] if len(cls_df) else "?"
        agr = cls_df["agrees_sequential"].iloc[0] if len(cls_df) else "?"
        print(f"    {r['serial']:<8s}  pr={r['page_row_idx']} pc={r['page_col_idx']}  "
              f"{r['uuid'][:16]}...  seq-agrees={agr}  {cls}")

print("\n=== Symbol-format distribution, last 10 pages ===")
print(idx.groupby(["page", "symbol_format"]).size().unstack(fill_value=0).tail(10))

print("\n=== sequential.csv: rows per bay, last 10 bays ===")
seq["bay"] = pd.to_numeric(seq["serial_number"].str.extract(r"A(\d+)-")[0], errors="coerce")
print(seq.groupby("bay").size().tail(10))

print("\n=== Are any PDF UUIDs from pages 105-108 assigned to a bay number != (page+1)//2 in sequential? ===")
pdf105 = pdf[pdf["page"].between(105, 108)]
seq_map = dict(zip(seq["uuid"].astype(str), seq["serial_number"].astype(str)))
for _, r in pdf105.iterrows():
    seq_serial = seq_map.get(r["uuid"], "(not in seq)")
    expected_bay = (int(r["page"]) + 1) // 2
    if seq_serial != "(not in seq)":
        seq_bay = int(seq_serial.split("-")[0][1:])
        if seq_bay != expected_bay:
            print(f"  PDF says page={r['page']} (bay A{expected_bay}) for UUID {r['uuid'][:20]}; sequential says {seq_serial}")
