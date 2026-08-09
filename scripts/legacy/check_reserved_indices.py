"""Prereg v1.9 SS13.2(a) / v1.10 scope amendment / v1.14 SS14.6 diff-scoping
(reports/adjudication_prereg_v1.md) -- pre-commit index scan. Fails a
commit that stages a calibration-reserved feature index (see
scripts/legacy/make_calibration_pool.py) either (a) as a standalone token
in an ADDED line of a staged `*.md` or `*.py` file, or (b) as a bare
component of a NEWLY INTRODUCED file PATH (any extension) -- naming the
index and the file either way.

THREE INCIDENTS, not hypotheticals -- each with a different cause, which
is why there are three distinct design decisions below rather than one
bigger regex:

1. Within an hour of this hook's first deployment, it blocked a
   legitimate commit of results/gemma3_sweep/records.jsonl -- 1736 lines
   of model-generated prose containing ordinary numbers ("I'm 18", the
   year "1898", a street number "106") that happened to collide with
   reserved indices as bare integers. FIX: content scanning is scoped to
   `*.md` and `*.py` -- prose humans read, not generated/structured data.
2. A magnitude floor (reserved indices >= 1000) was added after small
   integers -- file counts, section numbers, quantities -- collided with
   ordinary governance prose. This helps but cannot fully solve the
   problem: reserved values still live in [1000, 16384), a range full of
   this project's own real quantities (record counts, cell counts, window
   sizes, chunk lengths, line-number citations). Kept as a SECOND layer,
   never the primary defense.
3. Even after both fixes, staging an edit to project_management/
   VERIFICATION_LOG.md -- a 3468-line ground-truth log that cites line
   numbers by its own convention -- was blocked by numbers that PREDATE
   the reserved pool's existence, sitting in content the commit never
   touched. That is the actual design error this module had: it scanned
   every line of a staged file when the threat is only what is NEWLY
   WRITTEN. FIX (this amendment): scan added lines only, via
   `git diff --cached --unified=0`. If a reserved index is already in a
   committed file, it is ALREADY BURNED -- the hook cannot unburn it by
   blocking an unrelated later edit to that file, so it doesn't try.
   A first-time file addition scans in full, because every line of it is
   an added line; no special case needed.

4. Debugging incident 3 turned up a fourth, opposite-kind defect by
   accident: `_standalone_index_pattern`'s lookahead excluded ANY
   trailing `.`, including an ordinary sentence-ending period --
   "...feature 12403." was silently NEVER detected, for the entire
   window this hook was live. A false NEGATIVE, not a false positive.
   FIX: the lookahead now only excludes a trailing `.` when it is itself
   followed by a digit (a real decimal point); a bare trailing `.` no
   longer suppresses a match.

THE ASYMMETRY, now a BINDING RULE, not just a lesson from this module:
three false positives consumed a full day and got three structural
fixes, because a false positive blocks someone and gets reported. One
false negative was silent for the entire period this hook was live,
because a false negative reports nothing -- there is no engineer to stop
and ask, no incident to escalate, nothing to notice at all except by
accident. That is the operating characteristic of every detection
control, not a property specific to regexes. CONSEQUENTLY: every
detector in this project gets a DELIBERATE false-negative test suite,
not only a false-positive one -- enumerating the ways a real leak can
legitimately appear (sentence-final, parenthesised, comma-listed,
hyphen-adjacent, line-initial, inside a table cell, quoted,
footnote-marked) and asserting the scanner catches every one, symmetric
to the false-positive suite that asserts what it must NOT flag. See
tests/test_check_reserved_indices.py's dedicated section for this
module's own such suite.

REMEDIATION FOR INCIDENT 4's WINDOW: a hook that silently failed to
detect real leaks gave false assurance for as long as it was live --
anything committed in that window could carry a sentence-final reserved
index and would have passed. `scan_tracked_tree_content` and
`scan_commit_message_history` below audit the ENTIRE tracked tree and
ALL commit message history (not a diff -- this is the one case where
whole-content scanning is correct, because the point is auditing
accumulated state for a now-fixed defect, not gating a new change).
scripts/legacy/audit_and_retire_reserved_leaks.py runs that audit and
retires any leaked slot IN THE SAME PROCESS, so a leaked index value
never touches stdout, stderr, a return value, or any other channel an
operator could read -- only counts are ever surfaced. Do not split "scan"
and "retire" into two separately-invoked steps; that reintroduces the
exact leak this exists to close.

A NOTE ON PRESSURE, because it is the reason this module has amendment
history instead of one design: the engineer who built this hook predicted
twice, in this module's own earlier drafts, that a false-positive-prone
scanner gets disabled -- and then, faced with incident 3, recommended
`--no-verify` as an option rather than fixing the scope. That is not a
lapse in isolation; it is the exact pressure predicted, landing on the
person best placed to resist it, and the reason the fix here is
structural (diff-scoping) rather than case-by-case (an exemption list or
another bypass). The control has not been bypassed across any of the
four incidents -- every one was reported and fixed at the layer it
actually lived in, which is the entire point of this module's approach.

WHY *.md AND *.py FOR CONTENT, NOT EVERY FILE: the reserved pool is drawn
uniformly from range(16384) (see make_calibration_pool.py), so any
sufficiently large corpus of ordinary numbers collides with a meaningful
fraction of a 100-index pool by pure chance. Measured directly against
this repo's tracked files: registry/*.json certificates, uv.lock,
tokenizer.json, and every results/*.jsonl sweep output already contain
incidental digit collisions with zero semantic connection to any feature
index. `*.py` is included alongside `*.md` because source
docstrings/comments carry the same load-bearing engineering prose a rater
or PI reads exactly like a governance doc -- the collision rate that
disabled the unscoped version came from GENERATED text at volume, which
does not apply to human-authored source at the volumes this project's
`.py` files actually see.

WHY THE PATH CHECK IS RESTRICTED TO NEWLY-INTRODUCED PATHS (diff-filter
`AC`, not `ACM`): the same "already burned" reasoning as diff-scoped
content applies to paths. A file already tracked under a reserved-index
filename was already a leak (or already cleared) the moment it was first
added; re-flagging its unchanged path on every later content edit
protects nothing. Only a file being ADDED or COPIED in this commit
introduces a NEW path worth checking.

WHY THE PATH CHECK COVERS ALL EXTENSIONS: a file PATH is not prose and
carries none of the natural-number collision risk above --
`scripts/legacy/gemma_neuronpedia_raw/12403.json` is not "coincidentally"
named 12403, it is deliberately named after the feature it is evidence
for. That convention is used for the 40 (spent) composition indices
project-wide, and was the exact convention SS13.1 specified for fetching
RESERVED evidence -- until the v1.10 supersession: reserved evidence now
goes to a gitignored, untracked fetch path (hash-bound in
project_management/VERIFICATION_LOG.md per the R6-V5B precedent) and is
promoted to a tracked, index-named path only after the index is spent.
That policy is the PRIMARY defense against the filename-leak surface --
this path scan remains a mechanical backstop against someone bypassing
the untracked-fetch convention, not the thing the convention depends on.

WHAT NEITHER CHECK CAN DO, per SS13.2(b): correspondence is not in the
repo, so no pre-commit hook can reach it -- covered separately by slot
indirection (dispatch by slot, never index; see
reports/calibration_pool_reserved.json's schema).

WORD-BOUNDARY MATCHING (content scan): a bare `\\bINDEX\\b` scan still
fires inside a float, because regex `\\b` treats `.` as a non-word
character -- there is a boundary right before the "12403" in "0.12403".
This scan additionally excludes a preceding `.` or word character (so a
reserved index embedded in a longer integer, a decimal fraction, or an
identifier never matches), and excludes a FOLLOWING word character or a
following `.` only when that `.` is itself followed by a digit (a
decimal point, as in "12403.5") -- NOT a bare trailing `.`. That
asymmetry mattered in practice: an earlier version excluded any trailing
`.` at all, which meant "...feature 12403." -- a reserved index at the
end of an ordinary sentence, the single most common way one could
actually appear in prose -- was never detected. That is a false NEGATIVE,
worse than every false positive this module's history is otherwise
about, and it shipped silently until it was found by accident while
debugging the diff-scoping fix above.

Composition indices (the pre-registered 40, already spent) are never
reserved and so never appear in reports/calibration_pool_reserved.json --
both scans check staged content/paths against that file's contents only,
so a composition index passes without special-casing, wherever it appears.

`find_reserved_index_hits` (whole-text, not diff-scoped) is reused
unmodified by scripts/legacy/check_commit_message.py: a commit MESSAGE has
no "pre-existing" half to exclude -- the entire message is new text every
time, so diff-scoping does not apply there and this function's original
behaviour is exactly right for that caller.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

POOL_RELATIVE_PATH = Path("reports") / "calibration_pool_reserved.json"
CONTENT_SCAN_PATHSPECS = ("*.md", "*.py")


def git_repo_root(cwd: Path | None = None) -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], cwd=cwd, capture_output=True, text=True, check=True
    )
    return Path(result.stdout.strip())


def load_reserved_indices(pool_path: Path) -> list[int]:
    data = json.loads(pool_path.read_text(encoding="utf-8"))
    return [record["index"] for record in data["reserved_features"]]


def staged_files(repo_root: Path, *, pathspecs: tuple[str, ...] | None = None, diff_filter: str = "ACM") -> list[str]:
    args = ["git", "diff", "--cached", "--name-only", f"--diff-filter={diff_filter}"]
    if pathspecs is not None:
        args += ["--", *pathspecs]
    result = subprocess.run(args, cwd=repo_root, capture_output=True, text=True, check=True)
    return [line for line in result.stdout.splitlines() if line]


_HUNK_HEADER = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def _parse_added_lines(diff_text: str) -> list[tuple[int, str]]:
    """Parses `git diff --unified=0` output into [(new_file_lineno,
    line_text), ...] for '+' lines only. With zero context, every line is
    either a hunk header, a '+' (added) line, a '-' (removed, not present
    in the new file -- doesn't advance the new-file counter), or a file
    header -- so this is a complete parse, not a heuristic."""
    added: list[tuple[int, str]] = []
    current_lineno: int | None = None
    for line in diff_text.splitlines():
        if line.startswith("@@"):
            match = _HUNK_HEADER.match(line)
            if match:
                current_lineno = int(match.group(1))
            continue
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            if current_lineno is not None:
                added.append((current_lineno, line[1:]))
                current_lineno += 1
        # '-' lines: removed, not in the new file, counter does not advance.
    return added


def staged_file_added_lines(repo_root: Path, path: str) -> list[tuple[int, str]]:
    """The ADDED lines of a single staged file, per the index vs HEAD --
    exactly what this commit is newly writing there. A first-time file
    addition returns every line (git emits the whole file as one '+' hunk
    against /dev/null). Returns [] for a binary file or a diff git can't
    produce text for."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--unified=0", "--", path], cwd=repo_root, capture_output=True
    )
    if result.returncode != 0:
        return []
    try:
        text = result.stdout.decode("utf-8")
    except UnicodeDecodeError:
        return []
    if "Binary files" in text:
        return []
    return _parse_added_lines(text)


def _standalone_index_pattern(index: int) -> re.Pattern:
    """FIX (found while investigating the diff-scoping bug, not asked
    for): `(?![\\w.])` as the lookahead excludes ANY trailing '.',
    including an ordinary sentence-ending period -- "...feature 12403."
    was silently never detected, a false NEGATIVE, which is worse than
    the false positives this module spends most of its docstring on. A
    trailing '.' should only be excluded when it's a decimal point (i.e.
    followed by another digit); a bare trailing '.' is prose punctuation
    and must still flag."""
    escaped = re.escape(str(index))
    return re.compile(rf"(?<![\w.]){escaped}(?!\w)(?!\.\d)")


def find_reserved_index_hits(content: str, reserved_indices: list[int]) -> list[tuple[int, int]]:
    """Returns [(line_number, index), ...], 1-indexed line numbers, in the
    order encountered. Whole-text matching -- used by
    check_commit_message.py (see module docstring for why that caller is
    correct to use this rather than the diff-scoped path)."""
    hits: list[tuple[int, int]] = []
    for lineno, line in enumerate(content.splitlines(), start=1):
        for index in reserved_indices:
            if _standalone_index_pattern(index).search(line):
                hits.append((lineno, index))
    return hits


def find_reserved_index_hits_in_lines(numbered_lines: list[tuple[int, str]], reserved_indices: list[int]) -> list[tuple[int, int]]:
    """Same matching rule as find_reserved_index_hits, but over an
    explicit (lineno, text) list rather than whole-file text -- what the
    diff-scoped content scan needs, since its line numbers come from a
    hunk header, not from re-splitting a string at 1."""
    hits: list[tuple[int, int]] = []
    for lineno, line in numbered_lines:
        for index in reserved_indices:
            if _standalone_index_pattern(index).search(line):
                hits.append((lineno, index))
    return hits


def scan_staged_content(repo_root: Path, reserved_indices: list[int], *, pathspecs: tuple[str, ...] = CONTENT_SCAN_PATHSPECS) -> list[tuple[str, int, int]]:
    """Returns [(path, line_number, index), ...] across ADDED lines of
    staged files matching `pathspecs` (default: *.md and *.py only).
    Content already in HEAD is never scanned -- see module docstring,
    incident 3."""
    violations: list[tuple[str, int, int]] = []
    for path in staged_files(repo_root, pathspecs=pathspecs, diff_filter="ACM"):
        numbered_lines = staged_file_added_lines(repo_root, path)
        for lineno, index in find_reserved_index_hits_in_lines(numbered_lines, reserved_indices):
            violations.append((path, lineno, index))
    return violations


_PATH_TOKEN_SPLIT = re.compile(r"[\\/._-]+")


def find_reserved_index_in_path(path: str, reserved_indices: set[int]) -> int | None:
    """A path component that is exactly a reserved index (as its own
    dot/slash/underscore/hyphen-delimited token), e.g. the "12403" in
    scripts/legacy/gemma_neuronpedia_raw/12403.json."""
    for token in _PATH_TOKEN_SPLIT.split(path):
        if token.isdigit() and int(token) in reserved_indices:
            return int(token)
    return None


def scan_staged_paths(repo_root: Path, reserved_indices: list[int]) -> list[tuple[str, int]]:
    """Returns [(path, index), ...] across every NEWLY INTRODUCED staged
    path (diff-filter AC: Added or Copied), any extension. Restricted to
    new paths for the same "already burned" reason content scanning is
    restricted to added lines -- see module docstring."""
    reserved_set = set(reserved_indices)
    violations: list[tuple[str, int]] = []
    for path in staged_files(repo_root, pathspecs=None, diff_filter="AC"):
        hit = find_reserved_index_in_path(path, reserved_set)
        if hit is not None:
            violations.append((path, hit))
    return violations


# ---------------------------------------------------------------------------
# Whole-tree / whole-history audit (incident 4 remediation) -- NOT
# diff-scoped. See module docstring: this is the one case where scanning
# entire content is correct, because the goal is auditing accumulated
# state for a now-fixed defect, not gating a new change.
#
# BOTH FUNCTIONS RETURN THE ACTUAL LEAKED VALUES, deliberately -- unlike
# every other function in this module, which is safe to print. These two
# are NOT: a caller must consume the returned set entirely in-process
# (retire it, e.g. via make_calibration_pool.retire_and_replace) and must
# never print it, log it, or return it across a process boundary. See
# scripts/legacy/audit_and_retire_reserved_leaks.py for the only sanctioned
# caller.
# ---------------------------------------------------------------------------


def scan_tracked_tree_content(repo_root: Path, reserved_indices: list[int], *, pathspecs: tuple[str, ...] = CONTENT_SCAN_PATHSPECS) -> set[int]:
    """The last COMMITTED state (HEAD) of every tracked file matching
    `pathspecs`, scanned whole -- not a diff. Returns the SET of leaked
    index values found. Do not print this return value."""
    args = ["git", "ls-files", "-z"]
    if pathspecs:
        args += ["--", *pathspecs]
    result = subprocess.run(args, cwd=repo_root, capture_output=True, check=True)
    paths = [p for p in result.stdout.decode("utf-8").split("\0") if p]

    leaked: set[int] = set()
    for path in paths:
        show = subprocess.run(["git", "show", f"HEAD:{path}"], cwd=repo_root, capture_output=True)
        if show.returncode != 0:
            continue
        try:
            content = show.stdout.decode("utf-8")
        except UnicodeDecodeError:
            continue
        for _lineno, index in find_reserved_index_hits(content, reserved_indices):
            leaked.add(index)
    return leaked


def scan_commit_message_history(repo_root: Path, reserved_indices: list[int]) -> set[int]:
    """Every commit message across all refs -- the commit-msg hook
    shares find_reserved_index_hits and inherited the same trailing-period
    defect. Returns the SET of leaked index values. Do not print this
    return value."""
    result = subprocess.run(
        ["git", "log", "--all", "--format=%B%x00"], cwd=repo_root, capture_output=True
    )
    text = result.stdout.decode("utf-8", errors="replace")
    messages = [m for m in text.split("\x00") if m.strip()]

    leaked: set[int] = set()
    for message in messages:
        for _lineno, index in find_reserved_index_hits(message, reserved_indices):
            leaked.add(index)
    return leaked


def main(argv: list[str] | None = None) -> int:
    repo_root = git_repo_root()
    pool_path = repo_root / POOL_RELATIVE_PATH

    if not pool_path.exists():
        print(
            f"WARNING: {pool_path} not found -- reserved-index contamination check NOT "
            "performed (nothing to check against). Run scripts/legacy/make_calibration_pool.py "
            "to generate it. Commit allowed.",
            file=sys.stderr,
        )
        return 0

    reserved_indices = load_reserved_indices(pool_path)
    content_violations = scan_staged_content(repo_root, reserved_indices)
    path_violations = scan_staged_paths(repo_root, reserved_indices)
    if not content_violations and not path_violations:
        return 0

    print(
        "COMMIT BLOCKED (reports/adjudication_prereg_v1.md SS13.2a): this commit newly writes a "
        "calibration-reserved feature index.",
        file=sys.stderr,
    )
    print(
        "Reserved indices are resolved by SLOT only, never quoted directly -- see "
        f"{POOL_RELATIVE_PATH} (which the orchestrator never opens). Fix the file(s) below, or "
        "if this is a deliberate, reviewed exception: git commit --no-verify",
        file=sys.stderr,
    )
    for path, lineno, index in content_violations:
        print(f"  {path}:{lineno}: reserved index {index} (newly added line)", file=sys.stderr)
    for path, index in path_violations:
        print(f"  {path}: reserved index {index} (newly introduced path)", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
