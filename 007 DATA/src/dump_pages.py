"""Dump p13 and p14 to PNG so we can see what's physically on the page."""
from pathlib import Path
import fitz

REPO = Path(__file__).resolve().parents[2]
PDF = REPO / "001 DESIGN" / "DIP1" / "Aisle A" / "DIP1 - AISLE A.pdf"
OUT = REPO / "007 DATA" / "output" / "debug"
OUT.mkdir(parents=True, exist_ok=True)

doc = fitz.open(str(PDF))
for pnum in (13, 14):
    pix = doc[pnum - 1].get_pixmap(matrix=fitz.Matrix(400 / 72, 400 / 72))
    dest = OUT / f"page_{pnum:03d}_400dpi.png"
    pix.save(str(dest))
    print(f"wrote {dest}  {pix.width}x{pix.height}")
doc.close()
