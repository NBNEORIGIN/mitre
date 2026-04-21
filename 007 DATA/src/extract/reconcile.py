"""
reconcile.py -- three-way comparison between the PDF-derived truth, sequential.csv,
and complete_solution.csv.

Produces a single CSV that, for every tag known to any source, shows:
    serial_pdf           -- what the PDF extraction says (authoritative)
    uuid_pdf             -- the UUID decoded from the PDF at that position
    uuid_complete        -- what complete_solution.csv has for this serial (or "")
    uuid_sequential      -- what sequential.csv has for this serial (or "")
    agrees_complete      -- True if uuid_pdf == uuid_complete
    agrees_sequential    -- True if uuid_pdf == uuid_sequential
    classification       -- one of:
        "all-agree"                      -- PDF == complete == sequential
        "pdf-matches-complete-only"      -- complete agrees, sequential disagrees
        "pdf-matches-sequential-only"    -- sequential agrees, complete disagrees
        "pdf-disagrees-both"             -- PDF UUID matches neither
        "pdf-only-in-complete-range"     -- upper-bay tag; complete doesn't have it
        "pdf-only"                       -- no row in either CSV
        "missing-from-pdf"               -- serial exists in a CSV but PDF had no symbol there
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
PDF_SERIALS = ROOT / "007 DATA" / "output" / "extract" / "pdf_derived_serials.csv"
COMPLETE = ROOT / "007 DATA" / "inputs" / "COMPLETE_SOLUTION_ALL_52_PAGES.csv"
SEQUENTIAL = ROOT / "001 DESIGN" / "DIP1" / "Aisle A" / "DIP1_Aisle_A_codes_sequential.csv"
OUT = ROOT / "007 DATA" / "output" / "extract" / "reconcile.csv"
SUMMARY = ROOT / "007 DATA" / "output" / "extract" / "reconcile_summary.txt"


def main() -> int:
    pdf = pd.read_csv(PDF_SERIALS)
    comp = pd.read_csv(COMPLETE)
    seq = pd.read_csv(SEQUENTIAL)
    print(f"PDF-derived: {len(pdf)} rows, {pdf['serial'].nunique()} unique serials")
    print(f"complete   : {len(comp)} rows, {comp['serial'].nunique()} unique serials")
    print(f"sequential : {len(seq)} rows, {seq['serial_number'].nunique()} unique serials")

    # Build serial -> uuid lookups
    pdf_map = pdf.drop_duplicates("serial", keep="first").set_index("serial")["uuid"].astype(str)
    comp_map = comp.drop_duplicates("serial", keep="first").set_index("serial")["uuid"].astype(str)
    seq_map = seq.drop_duplicates("serial_number", keep="first").set_index("serial_number")["uuid"].astype(str)

    all_serials = sorted(set(pdf_map.index) | set(comp_map.index) | set(seq_map.index))

    # Helper to extract bay number to know whether the serial is "lower" or "upper" half
    def bay_of(s: str) -> int:
        try:
            return int(s.split("-")[0][1:])
        except Exception:
            return -1

    rows = []
    for s in all_serials:
        u_pdf = pdf_map.get(s, "")
        u_comp = comp_map.get(s, "")
        u_seq = seq_map.get(s, "")
        bay = bay_of(s)
        in_pdf = bool(u_pdf)
        in_comp = bool(u_comp)
        in_seq = bool(u_seq)
        agrees_complete = in_pdf and in_comp and (u_pdf == u_comp)
        agrees_sequential = in_pdf and in_seq and (u_pdf == u_seq)

        if not in_pdf:
            classification = "missing-from-pdf"
        elif bay > 26 and not in_comp:
            # Upper bay -- complete_solution never covered this range.
            if not in_seq:
                classification = "pdf-only"
            elif agrees_sequential:
                classification = "all-agree-upper"
            else:
                classification = "pdf-disagrees-sequential-upper"
        else:
            # Lower bay (or upper bay with a complete row, unusual).
            if in_comp and in_seq:
                if agrees_complete and agrees_sequential:
                    classification = "all-agree"
                elif agrees_complete and not agrees_sequential:
                    classification = "pdf-matches-complete-only"
                elif not agrees_complete and agrees_sequential:
                    classification = "pdf-matches-sequential-only"
                else:
                    classification = "pdf-disagrees-both"
            elif in_comp and not in_seq:
                classification = "pdf-matches-complete-only" if agrees_complete else "pdf-disagrees-complete"
            elif not in_comp and in_seq:
                classification = "pdf-matches-sequential-only" if agrees_sequential else "pdf-disagrees-sequential"
            else:
                classification = "pdf-only"

        rows.append({
            "serial": s,
            "bay": bay,
            "uuid_pdf": u_pdf,
            "uuid_complete": u_comp,
            "uuid_sequential": u_seq,
            "agrees_complete": agrees_complete,
            "agrees_sequential": agrees_sequential,
            "classification": classification,
        })

    df = pd.DataFrame(rows)
    df.to_csv(OUT, index=False)
    print(f"\nWrote {OUT} ({len(df)} rows)")

    # Summary
    cls_counts = Counter(df["classification"])
    lines = [f"Total rows: {len(df)}"]
    lines.append("\nClassification breakdown:")
    for k, v in sorted(cls_counts.items(), key=lambda x: -x[1]):
        lines.append(f"  {k:40s} {v:5d}")

    # Lower vs upper breakdown
    low = df[df["bay"] <= 26]
    up = df[df["bay"] > 26]
    lines.append(f"\nLower bays (A1-A26): {len(low)} rows")
    for k, v in Counter(low["classification"]).most_common():
        lines.append(f"  {k:40s} {v:5d}")
    lines.append(f"\nUpper bays (A27-A54): {len(up)} rows")
    for k, v in Counter(up["classification"]).most_common():
        lines.append(f"  {k:40s} {v:5d}")

    # Bottom line
    pdf_truth = df[df["uuid_pdf"] != ""]
    match_comp = (pdf_truth["uuid_pdf"] == pdf_truth["uuid_complete"]).sum()
    match_seq = (pdf_truth["uuid_pdf"] == pdf_truth["uuid_sequential"]).sum()
    lines.append("\nPDF is authoritative. Of the {} serials with a PDF UUID:".format(len(pdf_truth)))
    lines.append(f"  matched by complete_solution.csv : {match_comp:5d}")
    lines.append(f"  matched by sequential.csv        : {match_seq:5d}")

    summary = "\n".join(lines)
    SUMMARY.write_text(summary, encoding="utf-8")
    print()
    print(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
