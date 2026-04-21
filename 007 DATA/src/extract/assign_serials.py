"""
assign_serials.py  --  Turn (page, center_x, center_y, payload) rows into
serials of the form A{bay}-{shelf_row}{shelf_col}.

Strategy: we don't hardcode what position A1-1A "should" be at on the page.
Instead we learn the mapping empirically from Batch 1's 100 shipped
(serial, UUID) pairs, which are known-correct. Then we apply that mapping
to every symbol in the PDF and emit the PDF-derived serial table.

This separates two questions cleanly:
  (a) What's physically on each page?  (extract_pdf.py)
  (b) Which physical position corresponds to which serial label?
      (this script, grounded in verified ship data.)
"""
from __future__ import annotations

import csv
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
RAW = PROJECT_ROOT / "007 DATA" / "output" / "extract" / "raw_symbols.csv"
GROUND_TRUTH = PROJECT_ROOT / "007 DATA" / "inputs" / "FIRST_100_TAGS_MATCHED.csv"
SEQUENTIAL = PROJECT_ROOT / "001 DESIGN" / "DIP1" / "Aisle A" / "DIP1_Aisle_A_codes_sequential.csv"
OUT_INDEXED = PROJECT_ROOT / "007 DATA" / "output" / "extract" / "raw_symbols_indexed.csv"
OUT_SERIALS = PROJECT_ROOT / "007 DATA" / "output" / "extract" / "pdf_derived_serials.csv"
OUT_LAYOUT = PROJECT_ROOT / "007 DATA" / "output" / "extract" / "layout_mapping.csv"


def page_layout_key(page_num: int) -> str:
    """Classify pages into layout types whose internal grid is consistent.

    Lower half (pages 1..52): 2 pages per bay, page-1-of-bay = 16 symbols,
        page-2-of-bay = 20 symbols. These are likely distinct layouts.
    Upper half (pages 53..108): 2 pages per bay, both have 16 symbols.
        The 'page 1' of a bay still holds A/B/C/D columns and the 'page 2'
        holds E/G/H/J (inferred); they may differ in shelf-col order, so
        we keep them as separate layouts as well.
    """
    half = "lower" if page_num <= 52 else "upper"
    parity = "p1" if page_num % 2 == 1 else "p2"
    return f"{half}-{parity}"


ROW_GAP_THRESHOLD = 0.05   # normalized page-height; >> intra-row y-noise (<0.01), << inter-row gap (>0.2)


def cluster_rows_by_y(ys: list[float], threshold: float = ROW_GAP_THRESHOLD) -> list[int]:
    """Return a row index (0-based, top→bottom = small y → large y) for each y value.

    Threshold-based: sort y's, and any consecutive gap > `threshold` starts a
    new row. Works for any number of rows without needing to specify it in
    advance.
    """
    n = len(ys)
    if n == 0:
        return []
    sorted_idx = sorted(range(n), key=lambda i: ys[i])
    sorted_ys = [ys[i] for i in sorted_idx]
    row_of_sorted_pos = [0] * n
    cur = 0
    for i in range(n):
        if i > 0 and (sorted_ys[i] - sorted_ys[i - 1]) > threshold:
            cur += 1
        row_of_sorted_pos[i] = cur
    out = [0] * n
    for sorted_pos, orig_idx in enumerate(sorted_idx):
        out[orig_idx] = row_of_sorted_pos[sorted_pos]
    return out


def index_page(symbols: pd.DataFrame) -> pd.DataFrame:
    """Assign (page_row_idx, page_col_idx) to each symbol on one page."""
    ys = symbols["center_y"].tolist()
    row_idx = cluster_rows_by_y(ys)
    symbols = symbols.copy()
    symbols["page_row_idx"] = row_idx
    # Within each row, sort by x left→right.
    out_parts = []
    for _, grp in symbols.groupby("page_row_idx", sort=True):
        g = grp.sort_values("center_x").reset_index()
        g["page_col_idx"] = range(len(g))
        out_parts.append(g.set_index("index"))
    indexed = pd.concat(out_parts).sort_index()
    return indexed


SERIAL_RE = re.compile(r"^A(\d+)-(\d)([A-L])$")


def parse_serial(s: str) -> tuple[int, int, str]:
    m = SERIAL_RE.match(s)
    if not m:
        raise ValueError(f"Bad serial: {s!r}")
    return int(m.group(1)), int(m.group(2)), m.group(3)


def main() -> int:
    raw = pd.read_csv(RAW)
    print(f"Read {len(raw)} raw symbols from {RAW.name}")

    # Index each page into (page_row_idx, page_col_idx)
    indexed_parts = []
    for page, grp in raw.groupby("page"):
        indexed_parts.append(index_page(grp))
    indexed = pd.concat(indexed_parts).sort_values(["page", "page_row_idx", "page_col_idx"]).reset_index(drop=True)
    indexed["page_layout"] = indexed["page"].map(page_layout_key)
    indexed.to_csv(OUT_INDEXED, index=False)
    print(f"Wrote {OUT_INDEXED} ({len(indexed)} rows)")

    # Load ground truth
    gt = pd.read_csv(GROUND_TRUTH)[["Serial", "UUID"]].rename(columns={"Serial": "serial", "UUID": "uuid"})
    gt["uuid"] = gt["uuid"].astype(str)
    print(f"\nGround truth: {len(gt)} verified (serial, uuid) pairs from Batch 1")

    # Match each ground truth UUID to an extracted symbol.
    payload_to_row = indexed.set_index("payload")
    matched = []
    missing_gt = []
    for _, row in gt.iterrows():
        uuid = row["uuid"]
        if uuid in payload_to_row.index:
            s = payload_to_row.loc[uuid]
            if isinstance(s, pd.DataFrame):
                # duplicate UUID appears on multiple pages; flag
                for _, r in s.iterrows():
                    matched.append((row["serial"], uuid, int(r["page"]), int(r["page_row_idx"]), int(r["page_col_idx"]), r["page_layout"]))
            else:
                matched.append((row["serial"], uuid, int(s["page"]), int(s["page_row_idx"]), int(s["page_col_idx"]), s["page_layout"]))
        else:
            missing_gt.append(row["serial"])

    print(f"  matched {len(matched)} ground-truth UUIDs to PDF symbols")
    if missing_gt:
        print(f"  MISSING from PDF extract: {len(missing_gt)}  ->  {missing_gt[:10]}{'...' if len(missing_gt) > 10 else ''}")

    # ---- Phase 1: learn lower-half layout from Batch 1 verified ground truth ----
    mapping: dict[tuple[str, int, int], Counter] = defaultdict(Counter)
    for serial, uuid, page, pr, pc, layout in matched:
        _, shelf_row, shelf_col = parse_serial(serial)
        mapping[(layout, pr, pc)][(shelf_row, shelf_col)] += 1

    print("\nPhase 1: learning lower-half layout from Batch 1 (100 verified pairs)")
    lookup: dict[tuple[str, int, int], tuple[int, str]] = {}
    layout_rows = []
    conflicts = 0
    for key, counter in sorted(mapping.items()):
        top = counter.most_common(1)[0]
        if len(counter) > 1:
            conflicts += 1
            print(f"  CONFLICT {key} -> {dict(counter)}")
        lookup[key] = top[0]
        layout, pr, pc = key
        sr, sc = top[0]
        layout_rows.append({
            "page_layout": layout,
            "page_row_idx": pr,
            "page_col_idx": pc,
            "shelf_row": sr,
            "shelf_col": sc,
            "support": top[1],
            "source": "batch1",
        })
    print(f"  learned {len(lookup)} grid cells, {conflicts} conflicts")

    # ---- Phase 2: upper-half layout ----
    # upper-p1 is geometrically identical to lower-p1 (verified by inspecting
    # several upper bays -- A50 in particular gives a perfect match to the
    # 2x8 ABCD interleave). So we use the lower-p1 mapping for upper-p1 too.
    #
    # upper-p2 has 16 tags on an 8-col grid (vs lower-p2's 10 cols); x-spacing
    # differs so it's a different physical template. We hypothesise that it's
    # the natural E/G/H/J interleave: same pattern as lower-p2 positions 0-7.
    # This is flagged as "upper-p2-hypothesis" so downstream code knows it
    # lacks a Batch-1 anchor.
    print("\nPhase 2: propagating layouts to upper half")

    for (layout, pr, pc), (sr, sc) in list(lookup.items()):
        if layout == "lower-p1":
            new_key = ("upper-p1", pr, pc)
            if new_key not in lookup:
                lookup[new_key] = (sr, sc)
                layout_rows.append({
                    "page_layout": "upper-p1",
                    "page_row_idx": pr,
                    "page_col_idx": pc,
                    "shelf_row": sr,
                    "shelf_col": sc,
                    "support": 0,
                    "source": "copy-from-lower-p1",
                })
        elif layout == "lower-p2" and pc <= 7:
            # First 8 positions of lower-p2 are E,G,H,J interleaved across
            # shelf-rows -- these are the positions that exist in upper-p2.
            new_key = ("upper-p2", pr, pc)
            if new_key not in lookup:
                lookup[new_key] = (sr, sc)
                layout_rows.append({
                    "page_layout": "upper-p2",
                    "page_row_idx": pr,
                    "page_col_idx": pc,
                    "shelf_row": sr,
                    "shelf_col": sc,
                    "support": 0,
                    "source": "hypothesis-upper-p2",
                })
    print("  upper-p1: copied from lower-p1 (geometrically confirmed)")
    print("  upper-p2: hypothesised from lower-p2 positions 0-7 (unverified, no Batch-1 anchor)")

    pd.DataFrame(layout_rows).to_csv(OUT_LAYOUT, index=False)
    print(f"\nwrote {OUT_LAYOUT}  ({len(lookup)} total grid cells)")

    # Print learned lower-p1 and lower-p2 tables in a readable form
    def print_layout_grid(layout_name: str) -> None:
        print(f"\n  {layout_name}:")
        cells = [(pr, pc, lookup[(layout_name, pr, pc)]) for (l, pr, pc) in lookup if l == layout_name]
        if not cells:
            print(f"    (none learned)")
            return
        cells.sort()
        max_pr = max(c[0] for c in cells)
        max_pc = max(c[1] for c in cells)
        for pr in range(max_pr + 1):
            row_txt = f"    page_row {pr}: "
            for pc in range(max_pc + 1):
                v = next((x[2] for x in cells if x[0] == pr and x[1] == pc), None)
                if v:
                    row_txt += f" r{v[0]}{v[1]} "
                else:
                    row_txt += "  -- "
            print(row_txt)

    for lay in ["lower-p1", "lower-p2", "upper-p1", "upper-p2"]:
        print_layout_grid(lay)

    # Assign serials to every indexed symbol
    #   bay is derived from the page number: page 2k-1 / 2k -> bay k
    def bay_of(page: int) -> int:
        return (page + 1) // 2

    assigned_rows = []
    unresolved = []
    for _, r in indexed.iterrows():
        key = (r["page_layout"], int(r["page_row_idx"]), int(r["page_col_idx"]))
        if key in lookup:
            sr, sc = lookup[key]
            serial = f"A{bay_of(int(r['page']))}-{sr}{sc}"
            assigned_rows.append({
                "serial": serial,
                "uuid": r["payload"],
                "page": int(r["page"]),
                "page_row_idx": int(r["page_row_idx"]),
                "page_col_idx": int(r["page_col_idx"]),
                "symbol_format": r["symbol_format"],
                "decode_source": r["decode_source"],
            })
        else:
            unresolved.append(r)
    df_assigned = pd.DataFrame(assigned_rows).sort_values("serial").reset_index(drop=True)
    df_assigned.to_csv(OUT_SERIALS, index=False)

    print(f"\nAssigned {len(df_assigned)} symbols -> {OUT_SERIALS}")
    if unresolved:
        print(f"  {len(unresolved)} symbols unresolved (no learned mapping for their grid cell)")

    # Sanity: how many unique serials? how many duplicates?
    dup = df_assigned["serial"].duplicated(keep=False)
    print(f"  unique serials: {df_assigned['serial'].nunique()}")
    print(f"  duplicate-serial rows: {dup.sum()}")
    if dup.sum():
        print(df_assigned[dup].head(20).to_string())

    return 0


if __name__ == "__main__":
    sys.exit(main())
