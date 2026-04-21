"""
recover_a7_missing.py

Targeted re-decode of pages 13 and 14 (A7 bay) to recover the four tags
that went missing in the first pass: A7-1L, A7-2L (Aztec on p14) and
A7-3D, A7-4D (QR on p13).

The root cause was two different bugs:
  - Page 13: the rightmost QR pair sits very close to the page edge, so
    it decoded at higher DPI but not at 300. We rescan at 500 DPI.
  - Page 14: the Aztec K and L codes were decoded at 300 DPI but
    assign_serials.py collapsed them with the adjacent QR positions in
    its 8-cell visual-row model (which is right for upper bays A27-A54
    but wrong for lower-bay even pages, where a visual row has 10 cells
    = 4 col-letter pairs + 2 single K/L Aztec).

We avoid touching assign_serials.py — instead we target the four
positions directly by (page, shelf-row, column letter) inferred from
position in the rendered page image:

  Page 13 (A7, cols A-D all 4 rows):
    expected visual row 1 (shelf rows 2,4) left-to-right:
      2A 4A 2B 4B 2C 4C 2D 4D
    expected visual row 2 (shelf rows 1,3) left-to-right:
      1A 3A 1B 3B 1C 3C 1D 3D
  Page 14 (A7, cols E,G,H,J all 4 rows + K,L rows 1-2 only):
    expected visual row 1: 2E 4E 2G 4G 2H 4H 2J 4J 2K 2L
    expected visual row 2: 1E 3E 1G 3G 1H 3H 1J 3J 1K 1L

We cross-check each recovered UUID against
inputs/COMPLETE_SOLUTION_ALL_52_PAGES.csv so we know the re-decode
agrees with the QA-confirmed mapping wherever the QA table has an
entry. The four missing serials are not in complete_solution, so for
those we emit whichever UUID the re-decode actually produced and log
it for manual spot-check against the PDF.
"""
from __future__ import annotations

import csv
from pathlib import Path

import fitz
import pandas as pd
import zxingcpp
from PIL import Image

REPO = Path(__file__).resolve().parents[2]
PDF = REPO / "001 DESIGN" / "DIP1" / "Aisle A" / "DIP1 - AISLE A.pdf"
COMPLETE = REPO / "007 DATA" / "inputs" / "COMPLETE_SOLUTION_ALL_52_PAGES.csv"
OUT_CSV = REPO / "007 DATA" / "inputs" / "a7_recovered_from_pdf.csv"

# Page 13 (A7 page 1): visual layout
P13_TOP = ["A7-2A", "A7-4A", "A7-2B", "A7-4B", "A7-2C", "A7-4C", "A7-2D", "A7-4D"]
P13_BOT = ["A7-1A", "A7-3A", "A7-1B", "A7-3B", "A7-1C", "A7-3C", "A7-1D", "A7-3D"]
# Page 14 (A7 page 2): visual layout
P14_TOP = ["A7-2E", "A7-4E", "A7-2G", "A7-4G", "A7-2H", "A7-4H", "A7-2J", "A7-4J", "A7-2K", "A7-2L"]
P14_BOT = ["A7-1E", "A7-3E", "A7-1G", "A7-3G", "A7-1H", "A7-3H", "A7-1J", "A7-3J", "A7-1K", "A7-1L"]


def render(doc, page_num: int, dpi: int) -> Image.Image:
    pix = doc[page_num - 1].get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72))
    return Image.frombytes("RGB", [pix.width, pix.height], pix.samples)


def decode_all(img: Image.Image) -> list[dict]:
    out = []
    for r in zxingcpp.read_barcodes(img):
        if not r.text or not r.position:
            continue
        p = r.position
        xs = [p.top_left.x, p.top_right.x, p.bottom_right.x, p.bottom_left.x]
        ys = [p.top_left.y, p.top_right.y, p.bottom_right.y, p.bottom_left.y]
        out.append(
            {
                "uuid": r.text,
                "format": r.format.name,
                "cx": sum(xs) / 4 / img.width,
                "cy": sum(ys) / 4 / img.height,
            }
        )
    return out


def cluster_rows(codes: list[dict], tolerance: float = 0.1) -> tuple[list[dict], list[dict]]:
    """Return (top_row, bottom_row) sorted left->right by cx."""
    if not codes:
        return [], []
    ys = sorted(c["cy"] for c in codes)
    # Find the largest gap -> horizontal divider
    gaps = [(ys[i + 1] - ys[i], ys[i]) for i in range(len(ys) - 1)]
    gaps.sort(reverse=True)
    if not gaps or gaps[0][0] < tolerance:
        # Single row; put everything in top
        return sorted(codes, key=lambda c: c["cx"]), []
    divider = gaps[0][1] + gaps[0][0] / 2
    top = sorted([c for c in codes if c["cy"] < divider], key=lambda c: c["cx"])
    bot = sorted([c for c in codes if c["cy"] >= divider], key=lambda c: c["cx"])
    return top, bot


def best_decode(doc, page_num: int, expected_top: int, expected_bot: int):
    """Try 300, 500, 600 DPI and return the pass that yields the most unique codes."""
    best = None
    for dpi in (300, 500, 600, 400):
        img = render(doc, page_num, dpi)
        codes = decode_all(img)
        # dedup by cx,cy (same physical symbol decoded twice at different DPI)
        unique: list[dict] = []
        for c in codes:
            if not any(
                abs(c["cx"] - u["cx"]) < 0.01 and abs(c["cy"] - u["cy"]) < 0.01
                for u in unique
            ):
                unique.append(c)
        top, bot = cluster_rows(unique)
        print(
            f"  p{page_num} @ {dpi} DPI: {len(unique)} symbols  "
            f"(top={len(top)}, bot={len(bot)}, want {expected_top}/{expected_bot})"
        )
        if best is None or (len(top) + len(bot)) > (len(best[0]) + len(best[1])):
            best = (top, bot, dpi)
        if len(top) == expected_top and len(bot) == expected_bot:
            break
    return best


def main() -> int:
    print(f"Source: {PDF}")
    doc = fitz.open(str(PDF))

    complete = dict(zip(pd.read_csv(COMPLETE).serial, pd.read_csv(COMPLETE).uuid))

    results: list[dict] = []
    all_issues: list[str] = []

    for page_num, labels_top, labels_bot in (
        (13, P13_TOP, P13_BOT),
        (14, P14_TOP, P14_BOT),
    ):
        print(f"\nPage {page_num}:")
        top, bot, dpi = best_decode(doc, page_num, len(labels_top), len(labels_bot))

        for row_codes, row_labels, row_name in (
            (top, labels_top, "top"),
            (bot, labels_bot, "bot"),
        ):
            if len(row_codes) != len(row_labels):
                all_issues.append(
                    f"page {page_num} {row_name}: decoded {len(row_codes)} vs expected "
                    f"{len(row_labels)}"
                )
                print(
                    f"  WARN: {row_name} row got {len(row_codes)} codes, expected "
                    f"{len(row_labels)} — cells not recovered will have no UUID."
                )
            for label, code in zip(row_labels, row_codes):
                matches_qa = (
                    complete.get(label) == code["uuid"] if label in complete else None
                )
                results.append(
                    {
                        "serial": label,
                        "uuid": code["uuid"],
                        "page": page_num,
                        "format": code["format"],
                        "cx": round(code["cx"], 4),
                        "cy": round(code["cy"], 4),
                        "dpi": dpi,
                        "matches_qa": (
                            "yes" if matches_qa is True
                            else "no" if matches_qa is False
                            else "no-qa-entry"
                        ),
                    }
                )

    doc.close()

    # Print summary
    qa_yes = sum(1 for r in results if r["matches_qa"] == "yes")
    qa_no = sum(1 for r in results if r["matches_qa"] == "no")
    qa_missing = sum(1 for r in results if r["matches_qa"] == "no-qa-entry")
    print(
        f"\nResults: {len(results)} serials recovered  "
        f"({qa_yes} match QA, {qa_no} disagree with QA, {qa_missing} have no QA entry)"
    )
    print("\nRecoveries with no QA entry (new UUIDs — flag for manual PDF spot-check):")
    for r in results:
        if r["matches_qa"] == "no-qa-entry":
            print(f"  {r['serial']:8s}  {r['uuid']}  format={r['format']}  "
                  f"(p{r['page']}, cx={r['cx']}, cy={r['cy']}, dpi={r['dpi']})")
    if qa_no:
        print("\nDISAGREEMENTS with QA table (concerning — investigate):")
        for r in results:
            if r["matches_qa"] == "no":
                print(
                    f"  {r['serial']:8s}  recovered={r['uuid']}  "
                    f"qa={complete[r['serial']]}"
                )

    # Write output
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["serial", "uuid", "page", "format", "cx", "cy", "dpi", "matches_qa"],
        )
        w.writeheader()
        w.writerows(results)
    print(f"\nWrote {OUT_CSV}")

    if all_issues:
        print("\nISSUES:")
        for i in all_issues:
            print(f"  - {i}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
