"""
fix_a7_layout.py

A7 is the only bay where columns A and E have fewer rows than the canonical
layout, causing assign_serials.py to mis-label all A7 tags. This script:

  1. Re-decodes pages 13 and 14 with pixel positions.
  2. Sorts codes into two visual rows × N cells (14 on p13, 18 on p14).
  3. Applies the physically-printed labels (verified from the PDF render).
  4. Rewrites master_uuids.csv:
       - removes phantom entries A7-1A, A7-2A, A7-3E, A7-4E
       - adds real entries A7-3D, A7-4D, A7-1L, A7-2L
       - corrects the remaining 28 A7 UUID mappings (all shifted).
  5. Emits a diff report so the change can be audited.

Physical A7 layout as shown in output/debug/page_013_400dpi.png and
page_014_400dpi.png:

  page 13 (14 tags):
    top    (y~0.22, shelf rows 2/4): A7-4A  A7-2B A7-4B A7-2C A7-4C A7-2D A7-4D
    bottom (y~0.58, shelf rows 1/3): A7-3A  A7-1B A7-3B A7-1C A7-3C A7-1D A7-3D

  page 14 (18 tags):
    top    (y~0.22): A7-2E A7-2G A7-4G A7-2H A7-4H A7-2J A7-4J A7-2K(az) A7-2L(az)
    bottom (y~0.58): A7-1E A7-1G A7-3G A7-1H A7-3H A7-1J A7-3J A7-1K(az) A7-1L(az)
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

import fitz
import zxingcpp
from PIL import Image

REPO = Path(__file__).resolve().parents[2]
PDF = REPO / "001 DESIGN" / "DIP1" / "Aisle A" / "DIP1 - AISLE A.pdf"
MASTER = REPO / "007 DATA" / "inputs" / "master_uuids.csv"
DERIVED = REPO / "007 DATA" / "output" / "extract" / "pdf_derived_serials.csv"
OUT_DIR = REPO / "007 DATA" / "output" / "a7_fix"
OUT_DIR.mkdir(parents=True, exist_ok=True)

UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)

PHYSICAL_LABELS = {
    13: {
        "top": ["A7-4A", "A7-2B", "A7-4B", "A7-2C", "A7-4C", "A7-2D", "A7-4D"],
        "bot": ["A7-3A", "A7-1B", "A7-3B", "A7-1C", "A7-3C", "A7-1D", "A7-3D"],
    },
    14: {
        "top": [
            "A7-2E", "A7-2G", "A7-4G", "A7-2H", "A7-4H",
            "A7-2J", "A7-4J", "A7-2K", "A7-2L",
        ],
        "bot": [
            "A7-1E", "A7-1G", "A7-3G", "A7-1H", "A7-3H",
            "A7-1J", "A7-3J", "A7-1K", "A7-1L",
        ],
    },
}


def decode_page(page_num: int, dpi: int = 400) -> list[dict]:
    doc = fitz.open(str(PDF))
    pix = doc[page_num - 1].get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72))
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    doc.close()
    out = []
    for r in zxingcpp.read_barcodes(img):
        if not r.text or not UUID_RE.match(r.text) or not r.position:
            continue
        p = r.position
        xs = [p.top_left.x, p.top_right.x, p.bottom_right.x, p.bottom_left.x]
        ys = [p.top_left.y, p.top_right.y, p.bottom_right.y, p.bottom_left.y]
        out.append(
            {
                "uuid": r.text,
                "format": r.format.name,
                "cx": sum(xs) / 4 / pix.width,
                "cy": sum(ys) / 4 / pix.height,
            }
        )
    # Dedupe by uuid (keep first occurrence)
    seen: set[str] = set()
    deduped = []
    for c in out:
        if c["uuid"] in seen:
            continue
        seen.add(c["uuid"])
        deduped.append(c)
    return deduped


def split_into_rows(codes: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split codes into top and bottom visual rows by y-coordinate."""
    codes_sorted_y = sorted(codes, key=lambda c: c["cy"])
    ys = [c["cy"] for c in codes_sorted_y]
    # Find the biggest y-gap to split rows
    gaps = [(ys[i + 1] - ys[i], i) for i in range(len(ys) - 1)]
    _, split_idx = max(gaps)
    top = codes_sorted_y[: split_idx + 1]
    bot = codes_sorted_y[split_idx + 1 :]
    top.sort(key=lambda c: c["cx"])
    bot.sort(key=lambda c: c["cx"])
    return top, bot


def build_a7_physical_map() -> dict[str, dict]:
    """Return {serial: {"uuid": ..., "format": ..., "page": ..., "cx": ...}} for A7."""
    result: dict[str, dict] = {}
    for page_num, labels in PHYSICAL_LABELS.items():
        codes = decode_page(page_num, dpi=400)
        expected = len(labels["top"]) + len(labels["bot"])
        print(f"page {page_num}: decoded {len(codes)} codes (expected {expected})")
        if len(codes) != expected:
            print(f"  WARNING: count mismatch; falling back to 500 DPI")
            codes = decode_page(page_num, dpi=500)
            print(f"  @ 500 DPI: {len(codes)} codes")
        if len(codes) != expected:
            raise SystemExit(
                f"page {page_num}: still can't decode {expected} codes, got {len(codes)}"
            )
        top, bot = split_into_rows(codes)
        if len(top) != len(labels["top"]) or len(bot) != len(labels["bot"]):
            raise SystemExit(
                f"page {page_num}: row split mismatch — top={len(top)} bot={len(bot)} "
                f"vs expected top={len(labels['top'])} bot={len(labels['bot'])}"
            )
        for serial, code in zip(labels["top"], top):
            result[serial] = {"page": page_num, "row": "top", **code}
        for serial, code in zip(labels["bot"], bot):
            result[serial] = {"page": page_num, "row": "bot", **code}
    return result


def main() -> int:
    a7_physical = build_a7_physical_map()
    print(f"\nResolved {len(a7_physical)} A7 serials from physical PDF layout")

    # Load existing master
    with open(MASTER, newline="", encoding="utf-8") as f:
        master_rows = list(csv.DictReader(f))
    master_map = {r["serial"]: r["uuid"] for r in master_rows}

    # Compute diff for A7 entries
    old_a7 = {s: u for s, u in master_map.items() if s.startswith("A7-")}
    new_a7 = {s: v["uuid"] for s, v in a7_physical.items()}

    added = sorted(set(new_a7) - set(old_a7))
    removed = sorted(set(old_a7) - set(new_a7))
    changed = sorted(s for s in set(old_a7) & set(new_a7) if old_a7[s] != new_a7[s])
    unchanged = sorted(s for s in set(old_a7) & set(new_a7) if old_a7[s] == new_a7[s])

    print(f"\nA7 diff:")
    print(f"  added    ({len(added)}): {added}")
    print(f"  removed  ({len(removed)}): {removed}")
    print(f"  changed  ({len(changed)}): {len(changed)} serials with different UUIDs")
    print(f"  unchanged({len(unchanged)}): {len(unchanged)}")

    if changed:
        print("\n  Changed mappings (first 10):")
        for s in changed[:10]:
            print(f"    {s}: {old_a7[s][:13]}... -> {new_a7[s][:13]}...")

    # Rewrite master: drop all A7 rows, add the new ones, preserve order for rest
    non_a7 = [r for r in master_rows if not r["serial"].startswith("A7-")]
    # Add new A7 rows sorted by (page, row, cx)
    a7_rows = []
    for serial, info in a7_physical.items():
        a7_rows.append({"serial": serial, "uuid": info["uuid"]})
    # Insert A7 rows in correct position: after last A6 and before first A8
    idx_insert = next(
        i for i, r in enumerate(non_a7) if r["serial"].startswith("A8-")
    )
    # Sort A7 rows using canonical bay order (shelf_row then position_column A,B,C,D,E,G,H,J,K,L)
    col_order = {c: i for i, c in enumerate("ABCDEGHIJKL")}
    def a7_sort_key(row):
        serial = row["serial"]  # e.g. A7-3D
        _, rc = serial.split("-")
        return (int(rc[0]), col_order.get(rc[1], 99))
    a7_rows.sort(key=a7_sort_key)
    new_master_rows = non_a7[:idx_insert] + a7_rows + non_a7[idx_insert:]

    # Write fixed master
    fixed_master = OUT_DIR / "master_uuids_a7_fixed.csv"
    with open(fixed_master, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["serial", "uuid"])
        w.writeheader()
        w.writerows(new_master_rows)
    print(f"\nWrote {fixed_master}  ({len(new_master_rows)} rows)")

    # Also write a diff report
    with open(OUT_DIR / "a7_diff_report.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["serial", "status", "old_uuid", "new_uuid"])
        w.writeheader()
        for s in added:
            w.writerow({"serial": s, "status": "added", "old_uuid": "", "new_uuid": new_a7[s]})
        for s in removed:
            w.writerow({"serial": s, "status": "removed_phantom", "old_uuid": old_a7[s], "new_uuid": ""})
        for s in changed:
            w.writerow({"serial": s, "status": "relabeled", "old_uuid": old_a7[s], "new_uuid": new_a7[s]})
        for s in unchanged:
            w.writerow({"serial": s, "status": "unchanged", "old_uuid": old_a7[s], "new_uuid": new_a7[s]})
    print(f"Wrote {OUT_DIR / 'a7_diff_report.csv'}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
