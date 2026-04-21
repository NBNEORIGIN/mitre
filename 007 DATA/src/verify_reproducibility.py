"""
verify_reproducibility.py

Diffs each regenerated SVG against the corresponding "known good" SVG that
was shipped to the client, and reports both byte-identical and semantic
equivalence.

Exit code 0 = all sheets match; non-zero = at least one difference.
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent.parent
KNOWN_GOOD = {
    "batch-01": PROJECT_ROOT / "001 DESIGN" / "DIP1" / "Aisle A" / "UV_PRINT_FILES_SPLIT",
    "batch-02": PROJECT_ROOT / "001 DESIGN" / "DIP1" / "Aisle A" / "UV_PRINT_FILES_SPLIT_BATCH2",
}
REGEN = {
    "batch-01": HERE.parent / "output" / "batch-01",
    "batch-02": HERE.parent / "output" / "batch-02",
}

SVG_NS = "{http://www.w3.org/2000/svg}"


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract_tags(svg_path: Path) -> dict[str, dict]:
    """Return a dict keyed by tag id -> {transform, qr_path, text_lines}."""
    tree = ET.parse(svg_path)
    root = tree.getroot()
    tags = {}
    for g in root.findall(f".//{SVG_NS}g[@id]"):
        tag_id = g.get("id")
        if not tag_id or not tag_id.startswith("tag_"):
            continue
        transform = g.get("transform", "")

        path_el = g.find(f".//{SVG_NS}path")
        qr_path = path_el.get("d") if path_el is not None else None
        inner_g = g.find(f"./{SVG_NS}g")
        qr_transform = inner_g.get("transform", "") if inner_g is not None else ""

        texts = [t.text for t in g.findall(f"./{SVG_NS}text")]
        tags[tag_id] = {
            "transform": transform,
            "qr_transform": qr_transform,
            "qr_path": qr_path,
            "texts": texts,
        }
    return tags


def compare_semantic(a: Path, b: Path) -> list[str]:
    """Return a list of human-readable differences (empty = semantically equal)."""
    diffs: list[str] = []
    tags_a = extract_tags(a)
    tags_b = extract_tags(b)

    only_a = set(tags_a) - set(tags_b)
    only_b = set(tags_b) - set(tags_a)
    if only_a:
        diffs.append(f"  tags only in regenerated: {sorted(only_a)}")
    if only_b:
        diffs.append(f"  tags only in original:    {sorted(only_b)}")

    for tid in sorted(set(tags_a) & set(tags_b)):
        a_t = tags_a[tid]
        b_t = tags_b[tid]
        if a_t["transform"] != b_t["transform"]:
            diffs.append(f"  {tid}: transform {a_t['transform']!r} != {b_t['transform']!r}")
        if a_t["qr_transform"] != b_t["qr_transform"]:
            diffs.append(
                f"  {tid}: qr transform {a_t['qr_transform']!r} != {b_t['qr_transform']!r}"
            )
        if a_t["qr_path"] != b_t["qr_path"]:
            diffs.append(f"  {tid}: QR module pattern differs")
        if a_t["texts"] != b_t["texts"]:
            diffs.append(f"  {tid}: text {a_t['texts']!r} != {b_t['texts']!r}")
    return diffs


def main() -> int:
    any_missing = False
    any_diff = False
    total_sheets = 0
    byte_identical = 0
    semantic_only = 0

    for batch, regen_dir in REGEN.items():
        good_dir = KNOWN_GOOD[batch]
        print(f"\n=== {batch} ===")
        print(f"  regenerated : {regen_dir}")
        print(f"  known good  : {good_dir}")
        if not regen_dir.exists():
            print(f"  ERROR: regenerated dir does not exist")
            any_missing = True
            continue
        if not good_dir.exists():
            print(f"  ERROR: known-good dir does not exist")
            any_missing = True
            continue

        regen_svgs = sorted(regen_dir.glob("*.svg"))
        good_svgs = {p.name: p for p in good_dir.glob("*.svg")}

        if not regen_svgs:
            print("  ERROR: no regenerated SVGs found")
            any_missing = True
            continue

        for rp in regen_svgs:
            total_sheets += 1
            gp = good_svgs.get(rp.name)
            if gp is None:
                print(f"  MISSING in known-good: {rp.name}")
                any_missing = True
                continue

            rh = sha256_of(rp)
            gh = sha256_of(gp)
            if rh == gh:
                print(f"  OK (byte-identical)    {rp.name}  {rh[:12]}")
                byte_identical += 1
                continue

            diffs = compare_semantic(rp, gp)
            if not diffs:
                print(f"  OK (semantic match)    {rp.name}")
                print(f"       regen  sha256={rh[:12]}  size={rp.stat().st_size}")
                print(f"       orig   sha256={gh[:12]}  size={gp.stat().st_size}")
                semantic_only += 1
            else:
                any_diff = True
                print(f"  DIFF                   {rp.name}")
                for d in diffs[:20]:
                    print(d)
                if len(diffs) > 20:
                    print(f"    ... and {len(diffs) - 20} more differences")

    print("\n" + "=" * 60)
    print(f"Summary:  {total_sheets} sheet(s) compared")
    print(f"  byte-identical : {byte_identical}")
    print(f"  semantic match : {semantic_only}")
    print(f"  differing      : {total_sheets - byte_identical - semantic_only}")
    if any_missing or any_diff:
        print("RESULT: NOT REPRODUCIBLE")
        return 1
    print("RESULT: REPRODUCIBLE  (all regenerated sheets match the shipped originals)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
