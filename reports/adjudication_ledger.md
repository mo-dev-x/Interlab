# ADJUDICATION LEDGER — DERIVED ARTIFACT, DO NOT ADJUDICATE FROM THIS FILE

**Superseded as a source of truth on 2026-08-08 by prereg §12.1 (ledger partition).**

## Authoritative sources

| File | Rater | Written by |
|---|---|---|
| `reports/adjudication_ledger_r1.md` | rater 1 | rater 1 only |
| `reports/adjudication_ledger_r2.md` | rater 2 | rater 2 only |

**No rater opens the other rater's file, and no rater opens this one.** Blind is per-row, not
per-rater: whoever adjudicates a row second is blind on that row. This file is regenerated from the
two sources by the orchestrator when a merged view is needed; it is never edited in place and it is
never a rater's input.

## Why the previous contents were discarded rather than patched

This file's prior contents were written before §12.1 existed. They contained rater 2's ten draw-2
rows **and** rater 1's earlier rows in one place, and rater 2's copy predated the §12.3 → §13.3
class-12 retrofits (9105, 11149, 11763). Merging the two source files against that copy would have
**duplicated ten rows in two different states.** Rater 2 identified the hazard and was correctly
barred from fixing it, since the file contains rater 1's calls.

**A derived artifact is rebuilt, not repaired.** Patching it would have preserved exactly the
ambiguity — two versions of ten rows, no record of which governed — that the partition exists to
prevent. The two source files are complete and hash-bound independently; nothing is lost.

**An index is spent the moment it enters this file** (§13.2). Regenerate only when a merged view is
actually required, because regenerating it burns nothing but reading it does.
