"""Spot-check a sample of tags in the fresh output to confirm:
 - Single-digit bays (A1-A9) render at font-size 2.25mm (normal).
 - Two-digit bays (A10-A54) render at font-size 2.025mm (0.9x) with a 1mm text x-shift.
 - QR path <d> is non-empty.
"""
import re
from pathlib import Path

fresh = Path(__file__).resolve().parents[2] / "007 DATA" / "output" / "aisle-a-fresh"

TAG_RE_TMPL = r'<g id="tag_{s}" [^>]*>(.*?)</g>\s*</g>'


def find_tag_block(serial: str):
    for svg in sorted(fresh.glob("*.svg")):
        txt = svg.read_text(encoding="utf-8")
        marker = f'id="tag_{serial}"'
        if marker in txt:
            start = txt.find(marker) - txt[: txt.find(marker)].rfind("<g ") - 3
            # Simpler: find the opening of the tag's <g> and walk to its matching </g>
            open_idx = txt.rfind("<g ", 0, txt.find(marker))
            # Need the matching closing </g>. Since tag groups are flat with only
            # one nested <g> for the QR, scan forward balancing <g / </g>.
            depth, i = 0, open_idx
            while i < len(txt):
                if txt.startswith("<g", i) and (txt[i + 2] == " " or txt[i + 2] == ">"):
                    depth += 1
                    i += 2
                    continue
                if txt.startswith("</g>", i):
                    depth -= 1
                    i += 4
                    if depth == 0:
                        return svg.name, txt[open_idx:i]
                    continue
                i += 1
    return None, None


for s in ["A1-1A", "A9-4J", "A10-1A", "A26-1A", "A27-1A", "A54-4J"]:
    name, block = find_tag_block(s)
    if block is None:
        print(f"{s:8s} NOT FOUND")
        continue
    fonts = re.findall(r'font-size="([^"]+)"', block)
    xs = re.findall(r'<text x="([0-9.]+)"', block)
    has_qr = bool(re.search(r'<path d="[^"]{20,}"', block))
    print(
        f"{s:8s}  sheet={name:32s}  font-size={fonts[0] if fonts else 'NONE'}  "
        f"text_x={xs[0] if xs else 'NONE'}  qr_path={'OK' if has_qr else 'MISSING'}"
    )
