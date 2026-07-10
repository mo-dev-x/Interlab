"""SS6 rubric judge (D2 stub-judge pattern, continued from WP4): specificity
scores decile-sampled contexts 0-3 on concept-relatedness (the Lodestar
rubric). `RubricJudge` is a narrow protocol; `judge: {model, rubric_version,
prompt_version}` is recorded verbatim from whatever judge is supplied.

Production rubric judging (a real Lodestar-backed judge) is researcher-gated
and out of scope here, exactly as WP4 resolved for autointerpretation --
`NoOpRubricJudge` is the honest default (null scores), `StubRubricJudge` is
a deterministic test double, never wired to production.
"""

from __future__ import annotations

import dataclasses
from typing import Protocol


class RubricJudge(Protocol):
    model: str
    rubric_version: str
    prompt_version: str

    def rate(self, text: str) -> float | None: ...


@dataclasses.dataclass(frozen=True)
class NoOpRubricJudge:
    """Records honestly that no judge ran: every rating is `None`. The
    production-safe default -- running the test-only `StubRubricJudge`
    against real production data would fabricate specificity scores
    disguised as real ones."""

    model: str = "none"
    rubric_version: str = "none"
    prompt_version: str = "none"

    def rate(self, text: str) -> float | None:
        return None


@dataclasses.dataclass(frozen=True)
class StubRubricJudge:
    """Deterministic test double: rates a text 0-3 by how many times any of
    a fixed set of marker words appears (capped at 3). Exercises the full
    A8 specificity/judge-recording path end-to-end without a real Lodestar
    call -- test-only, never wired to production."""

    marker_words: frozenset[str]
    model: str = "stub-rubric-judge-v1"
    rubric_version: str = "stub-v1"
    prompt_version: str = "stub-v1"

    def rate(self, text: str) -> float | None:
        words = [w.strip(".,!?").lower() for w in text.split()]
        hits = sum(1 for w in words if w in self.marker_words)
        return float(min(hits, 3))
