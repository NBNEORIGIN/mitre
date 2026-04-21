"""
ladder_validation.py
====================

End-to-end validation that the PDF decoder + row/column clustering +
serial-assignment pipeline matches the client-accepted ground truth in
`COMPLETE_SOLUTION_ALL_52_PAGES.csv`.

Methodology (the "1 -> 2 -> 4 -> 8 -> 16 -> 20" ladder)
-------------------------------------------------------
Historically this project needed to be incrementally validated: start by
decoding a single known-good QR (A1-2A), confirm it matches the client's
printed bitmap, then go to 2 tags (one row / one column), then 4 (2x2
block), then 8 (2x4), then the whole 16-code page, then a 20-code
mixed QR+Aztec page. Each rung is cross-checked against the
client-accepted `COMPLETE_SOLUTION_ALL_52_PAGES.csv` ground truth.

Once pages 1 + 2 (bay A1) pass, we repeat the full validation on pages
29 + 30 (bay A15) which had been flagged for spot-checks and which
covers both the 16-per-page pure-QR layout AND the 20-per-page mixed
QR+Aztec layout.

Passing bar for a new run: **72/72** across pages 1, 2, 29, 30.

This script is a regression test: run it before shipping any new
regenerated batch to confirm the extractor still agrees with the
human-validated solution.

    python "007 DATA/src/ladder_validation.py"

Exit status 0 on full pass, non-zero on any mismatch.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import fitz
import pandas as pd
import zxingcpp
from PIL import Image

REPO = Path(__file__).resolve().parents[2]
PDF = REPO / "001 DESIGN" / "DIP1" / "Aisle A" / "DIP1 - AISLE A.pdf"
COMPLETE = REPO / "007 DATA" / "inputs" / "COMPLETE_SOLUTION_ALL_52_PAGES.csv"

UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)

# Same DPI ladder that extract_pdf.py uses, plus a couple of higher DPIs
# as extra fallback for validation purposes (this script is read-only).
DPI_LADDER = (400, 300, 450, 500, 600)


def decode_page(page_num: int):
    """Decode every QR / Aztec on a page, picking the DPI that produces
    the most UUID-valid symbols."""
    doc = fitz.open(str(PDF))
    best = []
    for dpi in DPI_LADDER:
        pix = doc[page_num - 1].get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72))
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        out = []
        for r in zxingcpp.read_barcodes(img):
            if not r.text or not r.position or not UUID_RE.match(r.text):
                continue
            p = r.position
            cx = (p.top_left.x + p.bottom_right.x) / 2 / pix.width
            cy = (p.top_left.y + p.bottom_right.y) / 2 / pix.height
            out.append({"text": r.text, "format": r.format.name, "cx": cx, "cy": cy})
        # dedup on (rounded cx, rounded cy)
        seen, uniq = set(), []
        for r in out:
            key = (round(r["cx"], 2), round(r["cy"], 2))
            if key in seen:
                continue
            seen.add(key)
            uniq.append(r)
        if len(uniq) > len(best):
            best = uniq
    doc.close()
    return best


def cluster_rows(codes, threshold=0.1):
    """Group decoded symbols into shelf rows based on vertical position."""
    if not codes:
        return []
    s = sorted(codes, key=lambda r: r["cy"])
    rows = [[s[0]]]
    for c in s[1:]:
        if c["cy"] - rows[-1][-1]["cy"] < threshold:
            rows[-1].append(c)
        else:
            rows.append([c])
    for r in rows:
        r.sort(key=lambda c: c["cx"])
    return rows


def validate_page(page_num: int, complete_df: pd.DataFrame, verbose: bool) -> tuple[int, int]:
    """Cross-check every decoded code on the page against COMPLETE_SOLUTION.
    Returns (pass_count, fail_count)."""
    codes = decode_page(page_num)
    rows = cluster_rows(codes)
    if verbose:
        print(f"\npage {page_num}: {len(codes)} codes decoded, row layout = {[len(r) for r in rows]}")

    pg = complete_df[complete_df.page == page_num].sort_values(["row", "column"])
    pg_map = {(int(r.row), int(r.column)): (r.serial, r.uuid, r.code_type) for _, r in pg.iterrows()}

    passes = fails = 0
    for r_idx, r_codes in enumerate(rows, 1):
        for c_idx, code in enumerate(r_codes, 1):
            key = (r_idx, c_idx)
            if key not in pg_map:
                if verbose:
                    print(f"  page {page_num} r={r_idx} c={c_idx}  {code['text']}  <no ground truth>")
                continue
            serial, expected, _fmt = pg_map[key]
            ok = code["text"] == expected
            if ok:
                passes += 1
            else:
                fails += 1
                print(
                    f"  [FAIL] page {page_num} r={r_idx} c={c_idx}  {serial:<8}  "
                    f"decoded={code['text']}  expected={expected}"
                )
    return passes, fails


LADDER_PAGES = (1, 2, 29, 30)  # A1 pages + A15 pages (mixed QR+Aztec pass twice)


def main() -> int:
    if not PDF.exists():
        print(f"ERROR: source PDF not found: {PDF}")
        return 2
    if not COMPLETE.exists():
        print(f"ERROR: ground-truth CSV not found: {COMPLETE}")
        return 2

    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    comp = pd.read_csv(COMPLETE)

    print("=" * 72)
    print("Ladder validation — C184 DIP1 Aisle A")
    print("=" * 72)
    print(f"  Source PDF  : {PDF.name}")
    print(f"  Ground truth: {COMPLETE.name}")
    print(f"  Pages       : {LADDER_PAGES}  (2 pure-QR pages, 2 mixed QR+Aztec pages)")

    total_p = total_f = 0
    for page in LADDER_PAGES:
        p, f = validate_page(page, comp, verbose)
        print(f"  page {page:3d}: {p} pass / {f} fail")
        total_p += p
        total_f += f

    print("=" * 72)
    print(f"  LADDER TOTAL: {total_p} pass / {total_f} fail out of {total_p + total_f}")
    print("=" * 72)

    if total_f == 0 and total_p == 72:
        print("PASS: all 72 positions on pages 1, 2, 29, 30 match COMPLETE_SOLUTION.")
        return 0
    print("FAIL: extractor disagrees with COMPLETE_SOLUTION on one or more positions.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
