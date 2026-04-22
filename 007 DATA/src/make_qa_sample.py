"""
make_qa_sample.py
-----------------

Produces a stratified QA sample of asset tags covering every layout and
anomaly in the project, rendered as print-ready SVG sheets plus a
checklist CSV. The purpose is to allow the client to scan a small set
of tags (~25) and verify each scanned UUID matches the UUID that the
same physical position produces in the original client-supplied PDF
(`DIP1 - AISLE A.pdf`).

Each pick is chosen for a specific reason:

- *Shipped-batch sanity* (already accepted by the client) confirms
  no regression between the accepted batches and the fresh pipeline.
- *A7 layout anomaly* covers the previously-phantom A7-1L / 2L / 3D /
  4D slots that are now correctly labelled.
- *User-flagged historical issues* (A15-2A, A15-2H, A15-1G) prove the
  "6133 / 3e9c" confusion was a label mix-up, not a decoder bug.
- *2-digit bay text fix* confirms the text-offset / 10 %-smaller-font
  rendering for A10..A54 doesn't corrupt the QR quiet zone.
- *Aztec coverage* includes lower-bay K/L Aztec (pages 2..52 even),
  2-digit-bay Aztec, and upper-bay all-Aztec (pages 105..108).
- *Duplicate UUID watch* (A53-2H + A54-2H) surfaces the known source-
  PDF duplicate so a human is reminded at QA time.
- *Upper-aisle coverage* (A27..A54) spot-checks the inferred layout
  against physical printouts, which had less ground truth historically.

Output
------
`007 DATA/output/qa-sample/`
    qa_sample.serials.txt          25 serials in print order
    QA_SAMPLE_CHECKLIST.csv        scan-and-tick checklist for the client
    SHELF_123_SCREW_SHEET_01.svg   19 screw-mount tags (rows 1-3)
    SHELF_4_ADHESIVE_SHEET_01.svg   6 adhesive-mount tags (row 4)
    README.md                      instructions for the human doing the QA
"""
from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
MASTER = REPO / "007 DATA" / "inputs" / "master_uuids.csv"
PDF_DERIVED = REPO / "007 DATA" / "output" / "extract" / "pdf_derived_serials.csv"
OUT_DIR = REPO / "007 DATA" / "output" / "qa-sample"

# (serial, rationale) in the order we want them printed.
SAMPLE: list[tuple[str, str]] = [
    # -- Shipped-batch sanity (byte-identical to accepted originals) -------
    ("A1-1A",  "Batch 1 (shipped) - first tag, 1-digit bay, QR"),
    ("A3-2L",  "Batch 1 (shipped) - Aztec K/L column"),
    ("A4-1A",  "Batch 2 (shipped) - QR row 1"),
    ("A6-1J",  "Batch 2 (shipped) - QR page-2 non-Aztec column"),

    # -- A7 layout anomaly (was mislabeled until A7 fix) -------------------
    ("A7-1B",  "A7 anomaly - first physical A7 tag"),
    ("A7-1L",  "A7 anomaly - previously 'phantom' A7, Aztec"),
    ("A7-2L",  "A7 anomaly - previously 'phantom' A7, Aztec"),
    ("A7-3D",  "A7 anomaly - previously 'phantom' A7"),
    ("A7-4D",  "A7 anomaly - previously 'phantom' A7, row-4 adhesive"),

    # -- 2-digit bay text-offset rendering --------------------------------
    ("A10-1A", "2-digit bay - first tag using smaller-text layout"),
    ("A15-1G", "Historical confusion - the '...6133' tag (was misread as A15-2A)"),
    ("A15-2A", "User-flagged historically, confirmed correct (ends ...3e9c)"),
    ("A15-2H", "User-flagged historically, confirmed correct (ends ...05b3)"),
    ("A20-4J", "2-digit bay - row-4 adhesive"),
    ("A26-1L", "Last lower-aisle bay - Aztec K/L"),
    ("A26-4J", "Last lower-aisle bay - row-4 adhesive"),

    # -- Upper-aisle coverage (A27..A54, different layout and Aztec pages) --
    ("A27-1A", "First upper-aisle bay - QR row 1"),
    ("A30-2H", "Upper-aisle spot check - QR row 2"),
    ("A40-3E", "Upper-aisle spot check - QR row 3"),
    ("A45-4A", "Upper-aisle spot check - row-4 adhesive"),
    ("A52-4J", "Penultimate bay - row-4 adhesive"),
    ("A53-1A", "All-Aztec upper-aisle (pages 105-108)"),
    ("A53-2H", "Known duplicate-UUID pair - also at A54-2H (source-PDF anomaly)"),
    ("A54-2H", "Known duplicate-UUID pair - same UUID as A53-2H"),
    ("A54-4J", "Last tag in aisle - Aztec, row-4 adhesive"),
]


def main() -> int:
    master = pd.read_csv(MASTER)
    master_map = dict(zip(master.serial, master.uuid))
    derived = pd.read_csv(PDF_DERIVED)
    derived_by_serial = {r.serial: r for _, r in derived.iterrows()}

    missing = [s for s, _ in SAMPLE if s not in master_map]
    if missing:
        print(f"ERROR: {len(missing)} sample serials not in master_uuids.csv: {missing}")
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    serial_txt = OUT_DIR / "qa_sample.serials.txt"
    serial_txt.write_text("\n".join(s for s, _ in SAMPLE) + "\n", encoding="utf-8")
    print(f"wrote {serial_txt}  ({len(SAMPLE)} serials)")

    checklist = OUT_DIR / "QA_SAMPLE_CHECKLIST.csv"
    # Defensive: if the existing checklist looks like it has been
    # annotated by the client (any non-header row has a value in a
    # column beyond the template's 10), refuse to clobber it so a
    # sign-off record is never silently lost. Rename the signed
    # copy (e.g. QA_SAMPLE_CHECKLIST_SIGNED_YYYY-MM-DD.csv) first.
    if checklist.exists():
        with checklist.open("r", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        if len(rows) > 1 and any(len(r) > 10 and any(c.strip() for c in r[10:])
                                  for r in rows[1:]):
            print(f"ERROR: {checklist} appears to contain client annotations "
                  f"(extra column values). Archive it first (e.g. rename to "
                  f"QA_SAMPLE_CHECKLIST_SIGNED_YYYY-MM-DD.csv) and re-run.")
            return 2

    with checklist.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "#", "serial", "expected_uuid", "code_format",
            "shelf_row", "mount_type", "source_pdf_page",
            "observed_uuid", "pass_fail", "rationale",
        ])
        for i, (serial, rationale) in enumerate(SAMPLE, 1):
            uuid = master_map[serial]
            row = int(serial.split("-")[1][0])
            mount = "Adhesive" if row == 4 else "Screw"
            drow = derived_by_serial.get(serial)
            fmt = drow.symbol_format if drow is not None else "?"
            page = int(drow.page) if drow is not None else 0
            w.writerow([i, serial, uuid, fmt, row, mount, page, "", "", rationale])
    print(f"wrote {checklist}")

    print("\ngenerating sample sheets ...")
    result = subprocess.run(
        [
            sys.executable,
            str(REPO / "007 DATA" / "src" / "generate_batch.py"),
            "--from-complete", str(MASTER),
            "--serials",       str(serial_txt),
            "--output",        str(OUT_DIR),
        ],
        cwd=REPO, capture_output=True, text=True,
    )
    print(result.stdout)
    if result.returncode != 0:
        print("STDERR:", result.stderr)
        return result.returncode

    rename_map = {
        "SHELF_123_SCREW_SHEET_01.svg": "QA_SAMPLE_SHEET_01_SCREW.svg",
        "SHELF_4_ADHESIVE_SHEET_01.svg": "QA_SAMPLE_SHEET_02_ADHESIVE.svg",
    }
    for old, new in rename_map.items():
        src = OUT_DIR / old
        if src.exists():
            dst = OUT_DIR / new
            if dst.exists():
                dst.unlink()
            src.rename(dst)

    screw = [s for s, _ in SAMPLE if not s.split("-")[1].startswith("4")]
    adhesive = [s for s, _ in SAMPLE if s.split("-")[1].startswith("4")]
    print(f"\nQA sample composition: {len(SAMPLE)} tags")
    print(f"  Screw (rows 1-3): {len(screw)}")
    print(f"  Adhesive (row 4): {len(adhesive)}")

    fmt_counts = {"QR Code": 0, "Aztec": 0}
    for s, _ in SAMPLE:
        drow = derived_by_serial.get(s)
        if drow is not None:
            fmt_counts[drow.symbol_format] = fmt_counts.get(drow.symbol_format, 0) + 1
    print(f"  Code formats: QR={fmt_counts.get('QR Code', 0)}, Aztec={fmt_counts.get('Aztec', 0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
