"""Prereg v1.10 SS13.4 (reports/adjudication_prereg_v1.md) -- commit-msg
hook. Blocks a commit whose MESSAGE (not its file changes -- that is
scripts/legacy/check_reserved_indices.py's job) either:

  (a) names a calibration-reserved feature index as a standalone token, or
  (b) records a tally, bucket count, or composition fragment.

WHY THIS EXISTS ALONGSIDE THE PRE-COMMIT HOOK: SS13.4 documents a leak the
pre-commit index scan structurally cannot see -- "the pre-commit index
scan does not look at commit messages." A rater's commit message once
recorded "3 surface-form, 3 semantic, 4 denominator" for a calibration
batch: those ten rows are a subset of the Gemma 40, so that string is
partial composition information about a column whose tally is void,
written into history any rater may read. Commit messages are exactly the
kind of thing "read by eye" this whole barrier is about -- the same
category as .md governance docs, just a different storage location.

(a) REUSES check_reserved_indices.find_reserved_index_hits UNMODIFIED --
never re-implement the standalone-token matching logic in a second place;
a commit message is just another piece of text to run it against.

(b) IS NEW: "no tally, bucket count, or composition fragment... Rows and
classes are fine; counts by bucket are not" (SS13.4). Mechanically, a
count immediately adjacent to one of this project's own composition
vocabulary words (surface-form, semantic, denominator, numerator, tally,
bucket) -- either order ("3 surface-form" or "denominator: 3") -- or a
bare N/M fraction NEAR one of the actual taxonomy class names. Deliberately
narrow and keyword-anchored rather than "any digit near any noun": SS13.4
explicitly permits row and class mentions, and a broader heuristic (e.g.
any keyword co-occurring anywhere in the message with any digit) would
flag ordinary messages like "fix semantic search, closes #42" --
precisely the false-positive class that got check_reserved_indices.py's
first version disabled within an hour of deployment. A keyword this
narrow, adjacency-anchored this tightly, is the deliberate tradeoff: it
will miss a sufficiently creative rephrasing, but it will not disable
itself.

INCIDENT (5th of the sprint, first in this module): the original bare
`\\d+\\s*/\\s*\\d+` fraction pattern fired on ANY N/N, including ordinary
job-ID/feature-index pairs with no composition meaning at all --
"3500/4500" (two Gemma tool feature indices) blocked a legitimate commit
on the last science commit of the sprint. The engineer rewrote the
message rather than reaching for --no-verify -- the fifth refusal of the
sprint, and exactly the cry-wolf pressure this module's own docstring
warned about, now landing here. FIX: the fraction pattern only fires when
one of the five real taxonomy class names (FRACTION_ADJACENCY_WORDS) also
appears on the SAME LINE. "9/40 surface-form" fires (a fraction actually
describing a class-bucket split); "3500/4500", "records 900/1736", and
"16/16" -- no class name nearby -- all pass. Per the binding rule in
check_reserved_indices.py's incident-4 docstring, narrowing a detector is
exactly where a false negative can silently open a hole, so both the new
pass case and the still-blocked adjacent-fraction case are pinned in the
deliberate false-negative/false-positive suites in
tests/test_check_commit_message.py, not left to the general regex tests
alone.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Sibling import, not the dynamic-file-loading dance gemma3_sweep.py's
# consumers use -- that pattern exists to avoid touching a FROZEN file;
# check_reserved_indices.py is this project's own utility module in the
# same directory, so an ordinary import is the right tool. Explicitly
# putting this file's own directory on sys.path first makes the import
# work identically whether this script is run directly (where sys.path[0]
# is already its directory) or loaded dynamically by a test.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_reserved_indices import (  # noqa: E402
    POOL_RELATIVE_PATH,
    find_reserved_index_hits,
    git_repo_root,
    load_reserved_indices,
)

# This project's own vocabulary for composition/calibration buckets --
# drawn directly from SS13.4's own wording and the prereg's composition
# tables (SS7, SS13.3). "row" and "class" are deliberately excluded: the
# amendment names them as fine on their own.
COMPOSITION_BUCKET_WORDS = (
    "surface-form",
    "surface form",
    "semantic",
    "denominator",
    "numerator",
    "tally",
    "bucket",
)

_NUMBER_THEN_WORD = re.compile(
    r"\b\d+\b\s*[-:]?\s*(" + "|".join(re.escape(w) for w in COMPOSITION_BUCKET_WORDS) + r")\b",
    re.IGNORECASE,
)
_WORD_THEN_NUMBER = re.compile(
    r"\b(" + "|".join(re.escape(w) for w in COMPOSITION_BUCKET_WORDS) + r")\b\s*[:=]?\s*\d+\b",
    re.IGNORECASE,
)
_BARE_FRACTION = re.compile(r"\b\d+\s*/\s*\d+\b")

# The actual taxonomy class names this adjudication scheme uses (distinct
# from COMPOSITION_BUCKET_WORDS above, which is broader/generic
# vocabulary for the word-adjacent-to-a-count patterns). A bare N/M
# fraction is gated on one of THESE appearing on the same line -- see
# the incident note in the module docstring for why: an ungated fraction
# pattern matches every ordinary job-ID or feature-index pair a science
# commit message contains.
FRACTION_ADJACENCY_WORDS = (
    "surface-form",
    "surface form",
    "semantic",
    "discourse-register",
    "discourse register",
    "indeterminate",
    "relational-positional",
    "relational positional",
)
_FRACTION_ADJACENCY_PATTERN = re.compile(
    "|".join(re.escape(w) for w in FRACTION_ADJACENCY_WORDS), re.IGNORECASE
)


def find_composition_fragments(message: str) -> list[str]:
    """Returns the matched snippets (not line numbers -- commit messages
    are short enough that the snippet itself is the useful pointer).
    The bare-fraction pattern is line-scoped and gated on
    FRACTION_ADJACENCY_WORDS; the other two patterns scan the whole
    message unchanged."""
    hits: list[str] = []
    for pattern in (_NUMBER_THEN_WORD, _WORD_THEN_NUMBER):
        hits.extend(m.group(0) for m in pattern.finditer(message))
    for line in message.splitlines():
        if _FRACTION_ADJACENCY_PATTERN.search(line):
            hits.extend(m.group(0) for m in _BARE_FRACTION.finditer(line))
    return hits


def strip_comment_lines(message: str) -> str:
    """git passes the raw COMMIT_EDITMSG-style file, which for a verbose
    or template-assisted commit includes '#'-prefixed comment lines
    (diff summaries, instructions) that were never part of the actual
    message -- same convention git itself uses when parsing it."""
    return "\n".join(line for line in message.splitlines() if not line.lstrip().startswith("#"))


def check_message(message: str, reserved_indices: list[int]) -> tuple[list[tuple[int, int]], list[str]]:
    """Returns (index_hits, composition_fragment_hits)."""
    cleaned = strip_comment_lines(message)
    index_hits = find_reserved_index_hits(cleaned, reserved_indices)
    fragment_hits = find_composition_fragments(cleaned)
    return index_hits, fragment_hits


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print("check_commit_message.py: expected the commit-msg file path as argv[1]", file=sys.stderr)
        return 1
    message_path = Path(argv[0])
    message = message_path.read_text(encoding="utf-8")

    repo_root = git_repo_root()
    pool_path = repo_root / POOL_RELATIVE_PATH
    reserved_indices: list[int] = []
    if pool_path.exists():
        reserved_indices = load_reserved_indices(pool_path)
    else:
        print(
            f"WARNING: {pool_path} not found -- reserved-index check on this commit message NOT "
            "performed. Composition-fragment check still runs. Run "
            "scripts/legacy/make_calibration_pool.py to enable the index check.",
            file=sys.stderr,
        )

    index_hits, fragment_hits = check_message(message, reserved_indices)
    if not index_hits and not fragment_hits:
        return 0

    print(
        "COMMIT BLOCKED (reports/adjudication_prereg_v1.md SS13.4): the commit message itself "
        "names a reserved index or records a tally/bucket-count/composition fragment.",
        file=sys.stderr,
    )
    print(
        "Rows and classes are fine to name; counts by bucket are not (SS13.4). Reserved indices "
        "are resolved by SLOT only. Rewrite the message, or if this is a deliberate, reviewed "
        "exception: git commit --no-verify",
        file=sys.stderr,
    )
    for _lineno, index in index_hits:
        print(f"  reserved index in commit message: {index}", file=sys.stderr)
    for snippet in fragment_hits:
        print(f"  composition fragment in commit message: {snippet!r}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
