"""
deep_analysis.py  --  Distinguish two failure modes in sequential.csv:

1. "UUID wrong"      -- sequential has a UUID at this position that doesn't
                       appear anywhere in the PDF extraction. Real decode error.
2. "label wrong"     -- sequential has a UUID that IS in the PDF, but attached
                       to a different serial. Position-labelling error, UUID fine.

This is critical: case 2 means the shipped/printable UUIDs are correct;
case 1 means some codes the client may have scanned are fiction.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
PDF_SERIALS = ROOT / "007 DATA" / "output" / "extract" / "pdf_derived_serials.csv"
SEQUENTIAL = ROOT / "001 DESIGN" / "DIP1" / "Aisle A" / "DIP1_Aisle_A_codes_sequential.csv"
RECONCILE = ROOT / "007 DATA" / "output" / "extract" / "reconcile.csv"


def main() -> None:
    pdf = pd.read_csv(PDF_SERIALS)
    seq = pd.read_csv(SEQUENTIAL)
    rec = pd.read_csv(RECONCILE)

    pdf_uuids = set(pdf["uuid"].astype(str))
    seq_uuids = set(seq["uuid"].astype(str))
    print(f"PDF unique UUIDs: {len(pdf_uuids)}")
    print(f"sequential unique UUIDs: {len(seq_uuids)}")
    print(f"UUIDs in both : {len(pdf_uuids & seq_uuids)}")
    print(f"UUIDs PDF only: {len(pdf_uuids - seq_uuids)}")
    print(f"UUIDs seq only: {len(seq_uuids - pdf_uuids)}")

    # Build a reverse lookup: for each UUID, what serials does each source assign?
    pdf_uuid_to_serial = pdf.drop_duplicates("uuid").set_index("uuid")["serial"]
    seq_by_uuid = seq.groupby("uuid")["serial_number"].apply(lambda s: list(s.astype(str))).to_dict()

    # Look at each row in the reconcile table where PDF disagrees with sequential
    disagree_mask = (~rec["agrees_sequential"]) & (rec["uuid_pdf"] != "") & (rec["uuid_sequential"] != "")
    dis = rec[disagree_mask].copy()
    print(f"\nPDF vs sequential disagreements: {len(dis)}")

    # For each such disagreement we have:
    #   PDF says: serial S -> uuid U_pdf
    #   sequential says: serial S -> uuid U_seq
    # Ask two questions:
    #   A) Is U_pdf present in sequential under some OTHER serial?
    #      (yes -> position-labelling error: sequential knows the UUID but put
    #       it on the wrong row.)
    #   B) Is U_seq present in the PDF under some OTHER serial?
    #      (yes -> same kind of labelling error but from the other side.)

    label_err_both_sides = 0
    label_err_seq_knows = 0   # U_pdf is somewhere in sequential (label mismatch)
    label_err_pdf_knows = 0   # U_seq is somewhere in PDF (label mismatch)
    neither_knows = 0

    examples = []
    for _, r in dis.iterrows():
        u_pdf = r["uuid_pdf"]
        u_seq = r["uuid_sequential"]
        pdf_knows_seq = u_seq in pdf_uuids
        seq_knows_pdf = u_pdf in seq_uuids
        if pdf_knows_seq and seq_knows_pdf:
            label_err_both_sides += 1
            if len(examples) < 5:
                pdf_serial_for_useq = pdf_uuid_to_serial.get(u_seq, "?")
                seq_serial_for_updf = ",".join(seq_by_uuid.get(u_pdf, ["?"]))
                examples.append((r["serial"], u_pdf, u_seq, pdf_serial_for_useq, seq_serial_for_updf))
        elif seq_knows_pdf:
            label_err_seq_knows += 1
        elif pdf_knows_seq:
            label_err_pdf_knows += 1
        else:
            neither_knows += 1

    print("\nBreakdown of disagreements:")
    print(f"  LABEL ERROR (both U_pdf and U_seq exist in the other source, just under different serials): {label_err_both_sides}")
    print(f"  PARTIAL    (sequential's UUID exists in PDF under another serial; PDF's UUID not in sequential): {label_err_pdf_knows}")
    print(f"  PARTIAL    (PDF's UUID exists in sequential under another serial; sequential's UUID not in PDF): {label_err_seq_knows}")
    print(f"  GENUINE UUID MISMATCH (neither source has the other's UUID): {neither_knows}")

    print("\nFirst 5 label-error examples (serial, U_pdf, U_seq, pdf-serial-for-U_seq, seq-serial(s)-for-U_pdf):")
    for ex in examples:
        print(f"  {ex[0]}: U_pdf={ex[1][:13]}...  U_seq={ex[2][:13]}...")
        print(f"      PDF says U_seq is serial: {ex[3]}")
        print(f"      sequential says U_pdf is serial: {ex[4]}")

    # Zoom in: lower vs upper
    print("\n--- Lower bays (A1-A26) disagreements ---")
    lower = dis[dis["bay"] <= 26]
    print(f"  total disagreements: {len(lower)}")
    # Count subtypes
    subs = Counter()
    for _, r in lower.iterrows():
        u_pdf, u_seq = r["uuid_pdf"], r["uuid_sequential"]
        if (u_pdf in seq_uuids) and (u_seq in pdf_uuids):
            subs["LABEL ERROR (both)"] += 1
        elif u_seq in pdf_uuids:
            subs["seq's UUID exists in PDF only"] += 1
        elif u_pdf in seq_uuids:
            subs["PDF's UUID exists in seq only"] += 1
        else:
            subs["neither-knows"] += 1
    for k, v in subs.items():
        print(f"  {k:40s} {v:5d}")

    print("\n--- Upper bays (A27-A54) disagreements ---")
    upper = dis[dis["bay"] > 26]
    print(f"  total disagreements: {len(upper)}")
    subs = Counter()
    for _, r in upper.iterrows():
        u_pdf, u_seq = r["uuid_pdf"], r["uuid_sequential"]
        if (u_pdf in seq_uuids) and (u_seq in pdf_uuids):
            subs["LABEL ERROR (both)"] += 1
        elif u_seq in pdf_uuids:
            subs["seq's UUID exists in PDF only"] += 1
        elif u_pdf in seq_uuids:
            subs["PDF's UUID exists in seq only"] += 1
        else:
            subs["neither-knows"] += 1
    for k, v in subs.items():
        print(f"  {k:40s} {v:5d}")


if __name__ == "__main__":
    main()
