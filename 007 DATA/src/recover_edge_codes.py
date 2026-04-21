"""
recover_edge_codes.py

Recover the 4 A7 tags that sit right at the page edge and didn't decode
in the first pass: A7-3D, A7-4D (right edge of p13) and A7-1L, A7-2L
(right edge of p14, both Aztec).

Strategy:
  1. Render the page at 600 DPI.
  2. Pad the image with 300 px of white on all sides so edge codes sit
     comfortably inside the scan area instead of flush against the crop.
  3. Also try the individual edge strips cropped and scaled up, in case
     zxing is still refusing.
  4. Match any newly-found symbols to the expected (page, shelf_row,
     column) positions from DIP1_Aisle_A_codes_sequential.csv and merge
     them into master_uuids.csv.
"""
from __future__ import annotations

import csv
from pathlib import Path

import fitz
import numpy as np
import pandas as pd
import zxingcpp
from PIL import Image

REPO = Path(__file__).resolve().parents[2]
PDF = REPO / "001 DESIGN" / "DIP1" / "Aisle A" / "DIP1 - AISLE A.pdf"
SEQ = REPO / "001 DESIGN" / "DIP1" / "Aisle A" / "DIP1_Aisle_A_codes_sequential.csv"
MASTER = REPO / "007 DATA" / "inputs" / "master_uuids.csv"

TARGET_SERIALS = ["A7-3D", "A7-4D", "A7-1L", "A7-2L"]
UUID_RE = __import__("re").compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def render_padded(doc, page_num: int, dpi: int, pad_px: int) -> Image.Image:
    pix = doc[page_num - 1].get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72))
    base = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    new_w = base.width + 2 * pad_px
    new_h = base.height + 2 * pad_px
    out = Image.new("RGB", (new_w, new_h), (255, 255, 255))
    out.paste(base, (pad_px, pad_px))
    return out, base.width, base.height


def decode_all(img: Image.Image) -> list[dict]:
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
                "cx_px": sum(xs) / 4,
                "cy_px": sum(ys) / 4,
            }
        )
    return out


def main() -> int:
    seq = pd.read_csv(SEQ)
    seq_a7 = seq[seq.serial_number.isin(TARGET_SERIALS)][
        ["serial_number", "page_number", "shelf_row", "position_column", "Column Position"]
    ]
    print("Target serials (per sequential.csv):")
    print(seq_a7.to_string(index=False))

    doc = fitz.open(str(PDF))
    all_new: dict[str, dict] = {}  # uuid -> info
    per_page_counts: dict[int, int] = {}

    for page_num in sorted(int(x) for x in seq_a7.page_number.unique()):
        print(f"\nPage {page_num}:")
        for dpi, pad in [(600, 300), (500, 200), (800, 400), (400, 150)]:
            img, base_w, base_h = render_padded(doc, page_num, dpi, pad)
            codes = decode_all(img)
            print(f"  @ {dpi} DPI +{pad}px pad: {len(codes)} codes")
            per_page_counts[page_num] = max(per_page_counts.get(page_num, 0), len(codes))
            for c in codes:
                # Convert padded-image pixel coords back to unpadded fractional coords
                frac_x = (c["cx_px"] - pad) / base_w
                frac_y = (c["cy_px"] - pad) / base_h
                if c["uuid"] not in all_new:
                    all_new[c["uuid"]] = {
                        "uuid": c["uuid"],
                        "format": c["format"],
                        "page": page_num,
                        "frac_x": round(frac_x, 4),
                        "frac_y": round(frac_y, 4),
                        "decode_source": f"padded_zxing@{dpi}_pad{pad}",
                    }

    doc.close()

    # Existing pdf_derived set so we can flag only the *new* UUIDs
    derived = set(
        pd.read_csv(REPO / "007 DATA" / "output" / "extract" / "pdf_derived_serials.csv").uuid
    )
    new_only = {u: v for u, v in all_new.items() if u not in derived}
    print(
        f"\nTotal unique UUIDs decoded across both pages: {len(all_new)}  "
        f"({len(new_only)} not in prior pdf_derived extraction)"
    )

    if not new_only:
        print("\nNo new UUIDs recovered by padded decode. The 4 missing codes either")
        print("remain unreadable or are physically absent.")
        return 1

    # For each new UUID, figure out which target serial it maps to.
    # Expected layout:
    #   Page 13 (A7 p1): top visual row (y≈0.22) shelf rows 2,4; bottom (y≈0.58) shelf rows 1,3.
    #     Column D is the rightmost pair: x ≈ 0.82 (col D row 2 or 1) and 0.93 (col D row 4 or 3).
    #   Page 14 (A7 p2): top visual row (y≈0.22) shelf rows 2,4; bottom (y≈0.58) shelf rows 1,3.
    #     Column L is the rightmost single column: x ≈ 0.97 (col L row 2 top or row 1 bottom).
    print("\nNew UUIDs found at edge positions:")
    assignments: list[dict] = []
    for u, info in new_only.items():
        fx, fy, page = info["frac_x"], info["frac_y"], info["page"]
        assigned: str | None = None
        if page == 13:
            # Rightmost col (D). Top visual row => 4D, bottom => 3D.
            if fx > 0.88:
                assigned = "A7-4D" if fy < 0.4 else "A7-3D"
        elif page == 14:
            # Rightmost col (L). Top visual row => 2L, bottom => 1L.
            if fx > 0.94:
                assigned = "A7-2L" if fy < 0.4 else "A7-1L"
        print(
            f"  p{page} fx={fx:.3f} fy={fy:.3f} fmt={info['format']:8s} "
            f"uuid={u}  -> {assigned or '(no match)'}"
        )
        if assigned:
            assignments.append({"serial": assigned, "uuid": u, **info})

    # Reconcile with existing master_uuids.csv
    master_df = pd.read_csv(MASTER)
    master_map = dict(zip(master_df.serial, master_df.uuid))

    added = 0
    for a in assignments:
        if a["serial"] not in master_map:
            master_map[a["serial"]] = a["uuid"]
            added += 1
            print(f"  ADD {a['serial']} -> {a['uuid']}")
        elif master_map[a["serial"]] != a["uuid"]:
            print(
                f"  CONFLICT {a['serial']}: existing={master_map[a['serial']]}, "
                f"new={a['uuid']}"
            )

    recovered = {a["serial"] for a in assignments}
    still_missing = set(TARGET_SERIALS) - recovered
    if still_missing:
        print(f"\nStill missing after padded decode: {sorted(still_missing)}")
    else:
        print(f"\nAll 4 target serials recovered.")

    # Rewrite master_uuids.csv only if we found new entries
    if added:
        from build_master_and_sequential import theoretical_full_sequence
        order = theoretical_full_sequence()
        pos = {s: i for i, s in enumerate(order)}
        rows = sorted(
            ({"serial": s, "uuid": u} for s, u in master_map.items()),
            key=lambda r: pos.get(r["serial"], 10**9),
        )
        with open(MASTER, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["serial", "uuid"])
            w.writeheader()
            w.writerows(rows)
        print(f"\nUpdated {MASTER} — now {len(rows)} rows (+{added} new)")

    return 0 if not still_missing else 1


if __name__ == "__main__":
    raise SystemExit(main())
