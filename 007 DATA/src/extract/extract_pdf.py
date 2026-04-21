"""
extract_pdf.py  --  Decode every QR/Aztec symbol in the source PDF.

Design goals:
- No OCR, no character substitutions, no "recovery" heuristics.
- Record exactly what each symbol decodes to, plus its position and format.
- Multi-DPI fallback so we don't silently lose symbols to scaling artefacts.

Output: CSV at <project>/007 DATA/output/extract/raw_symbols.csv
Columns: page, symbol_format, center_x, center_y, payload, decode_source

Row-order within a page is the zxing default (no sorting applied here);
serial assignment is done in a second stage (assign_serials.py) that is
grounded in verified Batch 1 tags.
"""
from __future__ import annotations

import csv
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

import cv2
import fitz  # PyMuPDF
import numpy as np
import zxingcpp

# All legitimate payloads in this project are UUIDs of the form
# 8-4-4-4-12 hex chars. We reject anything that doesn't match -- zxing
# occasionally returns a second garbage decode for the same symbol at
# higher DPIs, and that needs filtering.
UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

PROJECT_ROOT = Path(__file__).resolve().parents[3]
PDF_PATH = PROJECT_ROOT / "001 DESIGN" / "DIP1" / "Aisle A" / "DIP1 - AISLE A.pdf"
OUTPUT_CSV = PROJECT_ROOT / "007 DATA" / "output" / "extract" / "raw_symbols.csv"

DPI_LADDER = (300, 400, 250, 450)

EXPECTED_COUNTS = {
    # 1-indexed pages, matching user's numbering.
    # Pages 1..52: pairs of (page-1 of bay = 16, page-2 of bay = 20).
    # Pages 53..108: every page has 16.
    # Populated below.
}
for p in range(1, 53):
    EXPECTED_COUNTS[p] = 16 if p % 2 == 1 else 20
for p in range(53, 109):
    EXPECTED_COUNTS[p] = 16


@dataclass
class Symbol:
    page: int           # 1-indexed
    symbol_format: str  # "QR Code" or "Aztec"
    center_x: float
    center_y: float
    payload: str
    decode_source: str  # e.g. "zxing@300"


def render_page(page: fitz.Page, dpi: int) -> np.ndarray:
    pix = page.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72))
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    return img


def decode(img: np.ndarray) -> list[tuple[str, str, float, float]]:
    """Returns (format, payload, center_x_frac, center_y_frac) for each symbol.
    Coordinates are normalised to [0,1] so results from different DPIs can be merged.
    Payloads that don't look like UUIDs are filtered out as junk decodes."""
    h, w = img.shape[:2]
    out = []
    for r in zxingcpp.read_barcodes(img):
        if not UUID_RE.match(r.text):
            continue
        cx = (r.position.top_left.x + r.position.bottom_right.x) / 2.0 / w
        cy = (r.position.top_left.y + r.position.bottom_right.y) / 2.0 / h
        out.append((str(r.format), r.text, cx, cy))
    return out


def preprocess_variants(img: np.ndarray) -> list[np.ndarray]:
    """Generate a few image variants to help recover borderline symbols.

    Tried in order: original, grayscale+Otsu, inverted, mild sharpen."""
    yield img
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if img.shape[2] == 3 else img
    _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    yield cv2.cvtColor(otsu, cv2.COLOR_GRAY2RGB)
    yield 255 - img
    kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
    yield cv2.filter2D(img, -1, kernel)


def extract_page(page: fitz.Page, page_num: int) -> list[Symbol]:
    """Decode a page using a multi-DPI fallback plus a few image preprocessing
    variants if we're still short. Payloads deduped by string (valid UUIDs are
    unique) but we also dedup by near-identical position within a DPI/variant
    pass to guard against double-decodes of the same symbol."""
    expected = EXPECTED_COUNTS.get(page_num, None)
    seen: dict[str, Symbol] = {}

    def add_decodes(img: np.ndarray, source: str) -> None:
        positions: list[tuple[float, float]] = []
        for fmt, payload, cx, cy in decode(img):
            if payload in seen:
                continue
            # Position-based dedup: if a new payload lands essentially on top
            # of an already-accepted symbol, treat it as a junk duplicate decode.
            near = any((abs(px - cx) < 0.02 and abs(py - cy) < 0.02) for px, py in positions)
            if near:
                continue
            positions.append((cx, cy))
            seen[payload] = Symbol(
                page=page_num,
                symbol_format=fmt,
                center_x=cx,
                center_y=cy,
                payload=payload,
                decode_source=source,
            )
        # Track positions of symbols already in `seen` so future decodes can
        # reject near-duplicates even across passes.
        for s in seen.values():
            if (s.center_x, s.center_y) not in positions:
                positions.append((s.center_x, s.center_y))

    for dpi in DPI_LADDER:
        img = render_page(page, dpi)
        add_decodes(img, f"zxing@{dpi}")
        if expected is not None and len(seen) >= expected:
            return list(seen.values())

    # Still short? Try preprocessing variants at 400 DPI.
    if expected is not None and len(seen) < expected:
        base = render_page(page, 400)
        for idx, variant in enumerate(preprocess_variants(base)):
            add_decodes(variant, f"zxing@400#prep{idx}")
            if len(seen) >= expected:
                break

    return list(seen.values())


def main() -> int:
    if not PDF_PATH.exists():
        print(f"ERROR: PDF not found: {PDF_PATH}", file=sys.stderr)
        return 1
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    print(f"Opening {PDF_PATH.name} ...")
    doc = fitz.open(str(PDF_PATH))
    n_pages = len(doc)
    print(f"  {n_pages} pages")

    all_symbols: list[Symbol] = []
    shortfall_pages: list[tuple[int, int, int]] = []  # (page, got, expected)
    t0 = perf_counter()

    for i in range(n_pages):
        page_num = i + 1
        syms = extract_page(doc[i], page_num)
        all_symbols.extend(syms)
        expected = EXPECTED_COUNTS.get(page_num)
        if expected is not None and len(syms) != expected:
            shortfall_pages.append((page_num, len(syms), expected))
        status = "OK" if expected is None or len(syms) == expected else f"SHORT {len(syms)}/{expected}"
        print(f"  page {page_num:3d}: {len(syms):2d} symbols  [{status}]")

    doc.close()
    dt = perf_counter() - t0
    print(f"\nExtraction finished in {dt:.1f}s. Total symbols: {len(all_symbols)}")

    with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["page", "symbol_format", "center_x", "center_y", "payload", "decode_source"])
        for s in all_symbols:
            w.writerow([s.page, s.symbol_format, f"{s.center_x:.6f}", f"{s.center_y:.6f}",
                        s.payload, s.decode_source])
    print(f"Wrote {OUTPUT_CSV}")

    if shortfall_pages:
        print()
        print(f"WARNING: {len(shortfall_pages)} page(s) short of expected count:")
        for page, got, exp in shortfall_pages:
            print(f"  page {page}: got {got}, expected {exp}")
    else:
        print("\nEvery page matched its expected symbol count.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
