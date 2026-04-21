"""Inspect a specific upper-bay pair of pages to understand the layout."""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
indexed = pd.read_csv(ROOT / "007 DATA" / "output" / "extract" / "raw_symbols_indexed.csv")
seq = pd.read_csv(ROOT / "001 DESIGN" / "DIP1" / "Aisle A" / "DIP1_Aisle_A_codes_sequential.csv")
seq_map = dict(zip(seq["uuid"].astype(str), seq["serial_number"].astype(str)))

for bay in [27, 28, 40, 50]:
    p1, p2 = 2 * bay - 1, 2 * bay
    print(f"\n=== bay A{bay}  pages {p1} (upper-p1), {p2} (upper-p2) ===")
    for page in [p1, p2]:
        syms = indexed[indexed["page"] == page].sort_values(["page_row_idx", "page_col_idx"])
        print(f"  page {page}:")
        for _, r in syms.iterrows():
            seq_label = seq_map.get(str(r["payload"]), "(not in seq)")
            print(f"    pr={r['page_row_idx']} pc={r['page_col_idx']}  x={r['center_x']:.3f} y={r['center_y']:.3f}  {r['payload'][:24]}...  -> seq:{seq_label}")
