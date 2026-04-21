"""Whole-sheet per-tag verification.

For every fresh SVG sheet:
  1. Parse the SVG to get each <g id="tag_SERIAL"> group's (translate) position.
  2. Rasterise the whole sheet at high resolution.
  3. Scan every QR in the rasterised PNG.
  4. For each decoded QR, find the tag group whose bounding box contains it
     (tag groups are 50 x 30 mm in the layout).
  5. Compare the decoded UUID to master_uuids.csv for that serial.

This catches the case where the QR for UUID X ends up inside the group
labelled SERIAL Y (the exact bug described by the user)."""
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import cairosvg
import pandas as pd
import zxingcpp
from PIL import Image

REPO = Path(__file__).resolve().parents[2]
FRESH = REPO / "007 DATA" / "output" / "aisle-a-fresh"
MASTER = REPO / "007 DATA" / "inputs" / "master_uuids.csv"

SVG_NS = "http://www.w3.org/2000/svg"
TAG_W_MM = 50
TAG_H_MM = 30

UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
TRANSLATE_RE = re.compile(r"translate\(\s*([-\d.]+)\s*,\s*([-\d.]+)\s*\)")


def parse_sheet(sheet: Path) -> tuple[list[dict], tuple[float, float]]:
    """Return list of {serial, x, y} in mm and the sheet's viewBox size in mm."""
    tree = ET.parse(sheet)
    root = tree.getroot()
    vb = root.get("viewBox", "0 0 250 150").split()
    vb_w, vb_h = float(vb[2]), float(vb[3])
    tags = []
    for g in root.iter(f"{{{SVG_NS}}}g"):
        gid = g.get("id", "")
        if not gid.startswith("tag_"):
            continue
        serial = gid[4:]
        m = TRANSLATE_RE.search(g.get("transform", ""))
        if not m:
            continue
        x, y = float(m.group(1)), float(m.group(2))
        tags.append({"serial": serial, "x": x, "y": y})
    return tags, (vb_w, vb_h)


def scan_sheet(sheet: Path, width_px: int = 8000) -> tuple[list[dict], int, int]:
    png = sheet.with_suffix(".scan.png")
    cairosvg.svg2png(url=str(sheet), write_to=str(png), output_width=width_px)
    img = Image.open(png)
    results = []
    for r in zxingcpp.read_barcodes(img):
        if not r.text or not r.position:
            continue
        p = r.position
        cx_px = (p.top_left.x + p.bottom_right.x) / 2
        cy_px = (p.top_left.y + p.bottom_right.y) / 2
        results.append({"text": r.text, "cx_px": cx_px, "cy_px": cy_px,
                        "is_uuid": bool(UUID_RE.match(r.text))})
    return results, img.width, img.height


def check_sheet(sheet: Path, master_map: dict) -> list[dict]:
    tags, (vb_w, vb_h) = parse_sheet(sheet)
    decoded, img_w, img_h = scan_sheet(sheet)
    px_per_mm_x = img_w / vb_w
    px_per_mm_y = img_h / vb_h

    # Each tag occupies (x, y) to (x+50, y+30) in mm
    serial_by_pos: list[dict] = []
    mismatches = []
    for tag in tags:
        x0 = tag["x"] * px_per_mm_x
        y0 = tag["y"] * px_per_mm_y
        x1 = (tag["x"] + TAG_W_MM) * px_per_mm_x
        y1 = (tag["y"] + TAG_H_MM) * px_per_mm_y
        tag_codes = [d for d in decoded
                     if x0 <= d["cx_px"] <= x1 and y0 <= d["cy_px"] <= y1 and d["is_uuid"]]
        expected = master_map.get(tag["serial"])
        if not tag_codes:
            mismatches.append({"sheet": sheet.name, "serial": tag["serial"],
                               "expected": expected, "actual": None,
                               "reason": "no QR decoded at this tag position"})
            continue
        actual = tag_codes[0]["text"]
        if expected and actual != expected:
            mismatches.append({"sheet": sheet.name, "serial": tag["serial"],
                               "expected": expected, "actual": actual,
                               "reason": "wrong UUID inside this tag group"})
    return mismatches


def main():
    master = pd.read_csv(MASTER)
    master_map = dict(zip(master.serial, master.uuid))

    sheets = sorted(FRESH.glob("*.svg"))
    print(f"checking {len(sheets)} sheets")

    all_mis = []
    for i, sheet in enumerate(sheets, 1):
        mis = check_sheet(sheet, master_map)
        if mis:
            all_mis.extend(mis)
        if i % 10 == 0 or i == len(sheets):
            print(f"  [{i}/{len(sheets)}]  cumulative mismatches: {len(all_mis)}")

    print(f"\nTOTAL mismatches: {len(all_mis)}")
    out_csv = REPO / "007 DATA" / "output" / "per_tag_mismatches.csv"
    if all_mis:
        pd.DataFrame(all_mis).to_csv(out_csv, index=False)
        print(f"Wrote report -> {out_csv}")

        # Summary by sheet
        from collections import Counter
        by_sheet = Counter(m["sheet"] for m in all_mis)
        print("\n=== top sheets by mismatch count ===")
        for s, c in by_sheet.most_common(10):
            print(f"  {s}: {c}")

        # First 20 mismatches
        print("\n=== first 20 mismatches ===")
        for m in all_mis[:20]:
            if m["actual"] is None:
                print(f"  {m['sheet']:40s}  {m['serial']:<10}  NO DECODE  (expected {m['expected']})")
            else:
                print(f"  {m['sheet']:40s}  {m['serial']:<10}  expected={m['expected']}  actual={m['actual']}")


if __name__ == "__main__":
    main()
