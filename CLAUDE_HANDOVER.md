# Claude Code — handover prompt

Paste the prompt below into Claude Code (or any fresh agent session)
when you need to bring a new agent up to speed on this repo. It
assumes the agent has cloned <https://github.com/NBNEORIGIN/mitre>
and has a Windows PowerShell shell opened at the repo root.

---

## Prompt

You are picking up the **C184 Mitre Industrial DIP1 Aisle A asset-tag
pipeline** mid-way through its life. The project is currently in a
**production-approved** state: the client did a manual scan of a
25-tag stratified QA sample and returned 25 / 25 PASS on
2026-04-21. Your job is to keep it that way while doing whatever the
user asks next.

### Orientation (do these first, in order)

1. Read `AGENTS.md` at the repo root, end-to-end. It is the single
   pickup briefing and contains the hard rules.
2. Skim `README.md` for the overall shape and the "Acceptance gates"
   table.
3. Skim `007 DATA/BATCH_LOG.md` for the batch history, the A7
   anomaly write-up, the ladder-validation section, and the
   2026-04-21 "Client QA sample — 25/25 PASS" entry.

Do NOT start making changes before you have read those three files.

### Key repo facts (reinforced here so they cannot be missed)

- **The source of truth is the client-supplied PDF**:
  `001 DESIGN/DIP1/Aisle A/DIP1 - AISLE A.pdf` (108 pages, 1828
  physical tags). Everything in the pipeline traces back to it.
- **The authoritative UUID table** is
  `007 DATA/inputs/master_uuids.csv` (1828 rows, serial -> UUID).
  The client-supplied `DIP1_Aisle_A_codes_sequential.csv` has the
  correct sequential order but its UUID column is ~60 % wrong for
  A27-A52. Never use it as a UUID source.
- **Bay A7 is non-canonical** — 32 tags instead of 36. Column A only
  exists on shelf rows 3-4, column E only on rows 1-2. This is
  encoded in `BAY_LAYOUT_OVERRIDES` in
  `007 DATA/src/build_master_and_sequential.py`. The full pipeline
  from a fresh PDF re-decode is:
  `extract_pdf.py -> assign_serials.py -> apply_a7_fix.py ->
  generate_batch.py`. Do not skip `apply_a7_fix.py`; the canonical
  36-tag assumption in `assign_serials.py` alone produces wrong A7
  labels.
- **Shipped artwork** is in
  `001 DESIGN/DIP1/Aisle A/UV_PRINT_FILES_SPLIT/` and
  `UV_PRINT_FILES_SPLIT_BATCH2/`. Treat those directories as
  read-only. The pipeline regenerates both byte-identical; that is
  the first acceptance gate and must never break.
- **One duplicate UUID** (`d8c8654d-bb1c-9969-2b3f-…`) exists in the
  source PDF at A53-2H and A54-2H. This is a source-PDF fact, not a
  bug. Do not "fix" it unless the client tells you to; the QA sample
  deliberately includes both so a human sees it.
- **2-digit bay text offset**: serials `A10-*` through `A54-*` use a
  10 %-smaller font shifted 1 mm right to clear the QR quiet zone.
  Single-digit bays (`A1-*` through `A9-*`) are unchanged, which is
  how shipped Batches 1 + 2 remain byte-identical. Preserve this.

### Acceptance gates (ALL five must pass before any output ships)

| # | Gate                                           | Script                              | Last  |
| - | ---------------------------------------------- | ----------------------------------- | ----- |
| 1 | Shipped Batch 1 + 2 byte-identical             | `verify_reproducibility.py`         | 10/10 |
| 2 | Coverage + mount split + ordering              | `qa_check_fresh_output.py`          | 1828/1828 |
| 3 | Per-tag QR placement across every fresh sheet  | `verify_tag_placement.py`           | 0 mismatches |
| 4 | PDF decode vs client-accepted ground truth     | `ladder_validation.py`              | 72/72 |
| 5 | Client manual scan (QA sample)                 | `007 DATA/output/qa-sample/`        | 25/25 |

Before you claim any pipeline change is correct, run at least gates
1-4. Report their before/after status in your reply.

### The ladder test — why it exists

The decoder was historically trained by a human starting from a
single QR (A1-2A) and doubling: 1 -> 2 -> 4 -> 6 -> 8 -> 16 -> 20 ->
72 positions, each rung cross-checked against the client-accepted
`COMPLETE_SOLUTION_ALL_52_PAGES.csv`. `ladder_validation.py` locks
this in as a regression test. If you think you need to "improve" the
decoder (multi-DPI ladder, UUID regex, position dedup), run the
ladder before and after and post the before/after pass counts; do
not change the decoder speculatively.

### Environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install pandas pymupdf zxing-cpp qrcode pillow opencv-python cairosvg
```

All commands below assume this venv is active and the working
directory is the repo root.

### Common tasks, the safe recipes

**Regenerate everything from scratch** (rarely needed; mostly to
prove the pipeline is still reproducible):

```powershell
.\.venv\Scripts\python.exe "007 DATA\src\extract\extract_pdf.py"
.\.venv\Scripts\python.exe "007 DATA\src\extract\assign_serials.py"
.\.venv\Scripts\python.exe "007 DATA\src\apply_a7_fix.py"
.\.venv\Scripts\python.exe "007 DATA\src\generate_batch.py" `
    --from-complete "007 DATA\inputs\master_uuids.csv" `
    --serials       "007 DATA\inputs\aisle_a_sequential.serials.txt" `
    --output        "007 DATA\output\aisle-a-fresh"
# gates
.\.venv\Scripts\python.exe "007 DATA\src\verify_reproducibility.py"
.\.venv\Scripts\python.exe "007 DATA\src\qa_check_fresh_output.py"
.\.venv\Scripts\python.exe "007 DATA\src\verify_tag_placement.py"
.\.venv\Scripts\python.exe "007 DATA\src\ladder_validation.py"
```

**Produce a different-size QA sample** — edit the `SAMPLE = [...]`
list at the top of `007 DATA/src/make_qa_sample.py`, then:

```powershell
.\.venv\Scripts\python.exe "007 DATA\src\make_qa_sample.py"
.\.venv\Scripts\python.exe "007 DATA\src\verify_qa_sample.py"
```

**Produce a sub-batch for printing** (e.g. a specific bay range) —
write a serials list (one serial per line) and run:

```powershell
.\.venv\Scripts\python.exe "007 DATA\src\generate_batch.py" `
    --from-complete "007 DATA\inputs\master_uuids.csv" `
    --serials       path\to\my_serials.txt `
    --output        path\to\output_dir
```

**Onboard a new aisle** (DNR1, DIP1 Aisle B/C/D, …): the inputs live
under `001 DESIGN/DNR1/` and `001 DESIGN/DIP1/Aisle {B,C,D}/`.
Mirror what was done for Aisle A: re-decode its PDF, produce a
master UUID table, extend `theoretical_full_sequence()` in
`build_master_and_sequential.py` if the layout differs, and add
ladder rungs against a newly-created reference CSV. Keep every
aisle isolated in its own `007 DATA/output/<aisle>/` folder; don't
mix with Aisle A outputs.

### Rules for modifying code

- **Never modify** `001 DESIGN/DIP1/Aisle A/UV_PRINT_FILES_SPLIT*/`.
  Those are the shipped originals and are the reproducibility
  witnesses.
- **Never modify** `007 DATA/inputs/master_uuids.csv` directly.
  Regenerate it through the pipeline (`apply_a7_fix.py` ->
  `build_master_and_sequential.py`).
- **Never modify** `001 DESIGN/DIP1/Aisle A/DIP1 - AISLE A.pdf` or
  the CSVs in that folder. They are the client-supplied references.
- **Before any non-trivial change**: run the four local gates
  (1-4). After the change: run them again and post a before/after
  summary. If gate 4 (ladder) regresses, you have broken the
  decoder — revert.
- **Commit messages**: describe the why, not the what. Use plain
  ASCII. Use a heredoc via a file (`git commit -F .git/COMMIT_MSG.txt`)
  because PowerShell here-strings are awkward.

### Files you should not need to read unless specifically asked

- `007 DATA/src/recover_*` (historical decoder experiments)
- `007 DATA/src/audit_*` (one-off audits, retained for provenance)
- `007 DATA/src/sanity_check_batch_03.py` (Batch 3-specific)
- Anything under `001 DESIGN/DIP1/Aisle A/000 archive/` (ignored by
  git, stale by design)

### When in doubt

Ask the user to confirm before: (a) changing the decoder,
(b) modifying `master_uuids.csv` or the `_a7_fixed.csv`, (c)
"fixing" the A53/A54 duplicate UUID, (d) regenerating the shipped
batches.

Good luck. Don't speculate on fixes; run the gates.
