"""
generate_batch.py

Unified batch generator for C184 DIP1 Aisle A UV print SVGs.

Produces a folder of 5x5 grid SVG sheets (one per "shelf rows 1-3 / screw mount"
plus one for "shelf row 4 / adhesive mount"), given one of two input modes:

    --from-csv  inputs/FIRST_100_TAGS_MATCHED.csv
        Reads Serial/UUID directly from a pre-ordered CSV. This is the mode
        used to produce the original Batch 1.

    --from-complete inputs/COMPLETE_SOLUTION_ALL_52_PAGES.csv --serials <file>
        Looks each serial up in the authoritative UUID table. The serial
        list is provided as a text file with one serial per line in the
        desired physical print order. This is the mode used to produce
        the original Batch 2.

Layout, QR parameters, text placement, grid ordering and registration mark
are identical to the two existing scripts that generated the 200 shipped
tags (generate_split_print_files.py and generate_batch2.py), so the output
is byte-identical to the known-good originals when run under the same
Python/qrcode versions.
"""

from __future__ import annotations

import argparse
import io
import os
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

import pandas as pd
import qrcode
import qrcode.image.svg


# ---------------------------------------------------------------------------
# Layout constants (mm) — must match the original scripts exactly
# ---------------------------------------------------------------------------
TAG_WIDTH_MM = 50
TAG_HEIGHT_MM = 30
QR_SERIAL_WIDTH_MM = 34.425
QR_SERIAL_HEIGHT_MM = 16.574
VERTICAL_OFFSET_MM = 1.5
TEXT_UPWARD_OFFSET_MM = 2
GRID_COLS = 5
GRID_ROWS = 5
TAGS_PER_SHEET = GRID_COLS * GRID_ROWS
REG_MARK_SIZE_MM = 0.1

FONT_SIZE_MM = 2.25
LINE_SPACING_MM = FONT_SIZE_MM * 3.6

# Adjustments for serials whose bay prefix has 2+ digits (e.g. A10-..A26-).
# The 4-character prefix "A26-" is wider than "A1-" at the same font size
# and, being center-anchored, impinged on the QR code. For these we nudge
# the text 1 mm to the right and shrink the font by 10%.
LONG_PREFIX_FONT_MM = FONT_SIZE_MM * 0.9
LONG_PREFIX_LINE_SPACING_MM = LONG_PREFIX_FONT_MM * 3.6
LONG_PREFIX_TEXT_SHIFT_MM = 1.0


# ---------------------------------------------------------------------------
# Tag / sheet rendering
# ---------------------------------------------------------------------------
def is_shelf_4(serial: str) -> bool:
    """Row 4 tags are adhesive-backed. Row number is the first char after '-'."""
    if "-" in serial:
        return "4" in serial.split("-")[-1]
    return False


def has_long_prefix(serial: str) -> bool:
    """True when the bay portion has 2+ digits (e.g. 'A26-3G' -> True, 'A1-1A' -> False)."""
    if "-" not in serial:
        return False
    bay = serial.split("-", 1)[0]
    return sum(c.isdigit() for c in bay) >= 2


def create_qr_code_svg(uuid_str: str, size_mm: float):
    """Return (path_data, vb_width, vb_height, scale) for a QR encoding `uuid_str`.

    Matches the original generate_split_print_files.py exactly:
      version=1, ECC=M, box_size=10, border=0, SvgPathImage factory.
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=0,
        image_factory=qrcode.image.svg.SvgPathImage,
    )
    qr.add_data(uuid_str)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf)
    svg_string = buf.getvalue().decode("utf-8")

    root = ET.fromstring(svg_string)
    ns = {"svg": "http://www.w3.org/2000/svg"}
    path_elem = root.find(".//svg:path", ns)
    if path_elem is None:
        return None, 0, 0, 1

    path_data = path_elem.get("d")
    viewbox = root.get("viewBox")
    if not viewbox:
        return path_data, 0, 0, 1

    parts = viewbox.split()
    vb_width = float(parts[2])
    vb_height = float(parts[3])
    scale = size_mm / vb_width
    return path_data, vb_width, vb_height, scale


def create_svg_tag(uuid_str: str, serial: str, x_offset_mm: float, y_offset_mm: float) -> ET.Element:
    """Build a single tag <g> (QR + two text lines) at the given offset."""
    qr_size_mm = QR_SERIAL_HEIGHT_MM
    qr_path, _vb_w, _vb_h, qr_scale = create_qr_code_svg(uuid_str, qr_size_mm)

    tag_group = ET.Element(
        "g",
        {"id": f"tag_{serial}", "transform": f"translate({x_offset_mm},{y_offset_mm})"},
    )

    if qr_path:
        qr_x = (TAG_WIDTH_MM - QR_SERIAL_WIDTH_MM) / 2
        qr_y = (TAG_HEIGHT_MM - QR_SERIAL_HEIGHT_MM) / 2 + VERTICAL_OFFSET_MM
        qr_group = ET.SubElement(
            tag_group, "g", {"transform": f"translate({qr_x},{qr_y}) scale({qr_scale})"}
        )
        ET.SubElement(qr_group, "path", {"d": qr_path, "fill": "black"})

    if "-" in serial:
        parts = serial.split("-")
        line1, line2 = parts[0] + "-", parts[1]
    else:
        line1 = serial[: len(serial) // 2]
        line2 = serial[len(serial) // 2 :]

    if has_long_prefix(serial):
        font_size_mm = LONG_PREFIX_FONT_MM
        line_spacing_mm = LONG_PREFIX_LINE_SPACING_MM
        text_shift_mm = LONG_PREFIX_TEXT_SHIFT_MM
    else:
        font_size_mm = FONT_SIZE_MM
        line_spacing_mm = LINE_SPACING_MM
        text_shift_mm = 0.0

    text_x = (
        (TAG_WIDTH_MM - QR_SERIAL_WIDTH_MM) / 2
        + qr_size_mm
        + (QR_SERIAL_WIDTH_MM - qr_size_mm) / 2
        + text_shift_mm
    )
    text_y_base = (
        (TAG_HEIGHT_MM - QR_SERIAL_HEIGHT_MM) / 2
        + VERTICAL_OFFSET_MM
        + qr_size_mm / 2
        - TEXT_UPWARD_OFFSET_MM
        + 5
    )

    for line, y_off in [
        (line1, -line_spacing_mm / 2),
        (line2, line_spacing_mm / 2),
    ]:
        t = ET.SubElement(
            tag_group,
            "text",
            {
                "x": str(text_x),
                "y": str(text_y_base + y_off),
                "font-family": "Arial",
                "font-weight": "bold",
                "font-size": f"{font_size_mm}mm",
                "text-anchor": "middle",
                "fill": "black",
            },
        )
        t.text = line

    return tag_group


def create_svg_print_sheet(tags_data, sheet_number: int, output_dir: Path, file_prefix: str) -> Path:
    """Write one 5x5 grid print sheet SVG.

    Tags fill positions right-to-left across each row, bottom-to-top — matching
    the original layout (tag at index 0 goes to the bottom-right cell).
    """
    sheet_width_mm = TAG_WIDTH_MM * GRID_COLS
    sheet_height_mm = TAG_HEIGHT_MM * GRID_ROWS

    svg = ET.Element(
        "svg",
        {
            "xmlns": "http://www.w3.org/2000/svg",
            "width": f"{sheet_width_mm}mm",
            "height": f"{sheet_height_mm}mm",
            "viewBox": f"0 0 {sheet_width_mm} {sheet_height_mm}",
        },
    )
    ET.SubElement(
        svg,
        "rect",
        {"width": str(sheet_width_mm), "height": str(sheet_height_mm), "fill": "white"},
    )

    for idx, tag in enumerate(tags_data):
        if idx >= TAGS_PER_SHEET:
            break
        row = idx // GRID_COLS
        col = idx % GRID_COLS
        x = (GRID_COLS - 1 - col) * TAG_WIDTH_MM
        y = (GRID_ROWS - 1 - row) * TAG_HEIGHT_MM
        svg.append(create_svg_tag(tag["UUID"], tag["Serial"], x, y))

    ET.SubElement(
        svg,
        "rect",
        {
            "x": str(sheet_width_mm - REG_MARK_SIZE_MM),
            "y": str(sheet_height_mm - REG_MARK_SIZE_MM),
            "width": str(REG_MARK_SIZE_MM),
            "height": str(REG_MARK_SIZE_MM),
            "fill": "black",
        },
    )

    output_path = output_dir / f"{file_prefix}_SHEET_{sheet_number:02d}.svg"
    tree = ET.ElementTree(svg)
    ET.indent(tree, space="  ")
    tree.write(output_path, encoding="utf-8", xml_declaration=True)
    return output_path


# ---------------------------------------------------------------------------
# Input loading
# ---------------------------------------------------------------------------
def load_from_matched_csv(csv_path: Path) -> list[dict]:
    """Mode 1 — pre-ordered CSV with at least Serial, UUID columns."""
    df = pd.read_csv(csv_path)
    missing = {"Serial", "UUID"} - set(df.columns)
    if missing:
        raise ValueError(f"{csv_path} missing required columns: {sorted(missing)}")
    return df[["Serial", "UUID"]].to_dict("records")


def load_from_complete_and_serials(complete_csv: Path, serials_file: Path) -> list[dict]:
    """Mode 2 — authoritative UUID table + an ordered list of serials."""
    df = pd.read_csv(complete_csv)
    missing = {"serial", "uuid"} - set(df.columns)
    if missing:
        raise ValueError(f"{complete_csv} missing required columns: {sorted(missing)}")
    uuid_map = {row["serial"]: row["uuid"] for _, row in df.iterrows()}

    serials = [
        s.strip()
        for s in Path(serials_file).read_text(encoding="utf-8").splitlines()
        if s.strip() and not s.strip().startswith("#")
    ]

    tags, missing_serials = [], []
    for s in serials:
        if s in uuid_map:
            tags.append({"Serial": s, "UUID": uuid_map[s]})
        else:
            missing_serials.append(s)
    if missing_serials:
        raise SystemExit(
            f"ERROR: {len(missing_serials)} serials not found in {complete_csv.name}:\n"
            + "\n".join(f"  {s}" for s in missing_serials[:20])
        )
    return tags


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def generate(tags: list[dict], output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)

    shelf_123 = [t for t in tags if not is_shelf_4(t["Serial"])]
    shelf_4 = [t for t in tags if is_shelf_4(t["Serial"])]

    produced = []

    n_123 = (len(shelf_123) + TAGS_PER_SHEET - 1) // TAGS_PER_SHEET
    for i in range(n_123):
        chunk = shelf_123[i * TAGS_PER_SHEET : (i + 1) * TAGS_PER_SHEET]
        produced.append(create_svg_print_sheet(chunk, i + 1, output_dir, "SHELF_123_SCREW"))

    n_4 = (len(shelf_4) + TAGS_PER_SHEET - 1) // TAGS_PER_SHEET
    for i in range(n_4):
        chunk = shelf_4[i * TAGS_PER_SHEET : (i + 1) * TAGS_PER_SHEET]
        produced.append(create_svg_print_sheet(chunk, i + 1, output_dir, "SHELF_4_ADHESIVE"))

    return {
        "total": len(tags),
        "shelf_123_tags": len(shelf_123),
        "shelf_4_tags": len(shelf_4),
        "screw_sheets": n_123,
        "adhesive_sheets": n_4,
        "files": produced,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--from-csv", type=Path, help="Pre-ordered CSV with Serial, UUID columns (Mode 1).")
    p.add_argument(
        "--from-complete",
        type=Path,
        help="Authoritative UUID table CSV with serial, uuid columns (Mode 2).",
    )
    p.add_argument("--serials", type=Path, help="Ordered serial list (one per line) — required with --from-complete.")
    p.add_argument("--output", type=Path, required=True, help="Output directory for SVG sheets.")
    args = p.parse_args(argv)

    if args.from_csv and args.from_complete:
        p.error("--from-csv and --from-complete are mutually exclusive")
    if not args.from_csv and not args.from_complete:
        p.error("one of --from-csv or --from-complete is required")
    if args.from_complete and not args.serials:
        p.error("--serials is required when using --from-complete")

    if args.from_csv:
        tags = load_from_matched_csv(args.from_csv)
        source = f"{args.from_csv}"
    else:
        tags = load_from_complete_and_serials(args.from_complete, args.serials)
        source = f"{args.from_complete} + {args.serials}"

    print(f"Source:  {source}")
    print(f"Output:  {args.output}")
    print(f"Tags:    {len(tags)}")

    stats = generate(tags, args.output)
    print()
    print(f"  Screw sheets (rows 1-3): {stats['screw_sheets']} ({stats['shelf_123_tags']} tags)")
    print(f"  Adhesive sheets (row 4): {stats['adhesive_sheets']} ({stats['shelf_4_tags']} tags)")
    print(f"  Total SVGs produced:     {len(stats['files'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
