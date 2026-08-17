#!/usr/bin/env python
"""CLAIM_TYPE_EXTENT: a text-only reader for generated continuations.

WHAT THIS IS. The instrument RULING_15 R3 describes and does not supply: a
per-referent, per-claim-type judgement of the six frozen positive_tests over free
text, gated per instantiating span by T1_SUBJECT, T2_VOICE, T3_PREDICATE,
T4_NO_NAMED_TARGET and T6_FACTUAL_FLOOR and by HARD_EXCLUSIONS, emitting an
integer 0..6. It plugs into `causal_outcome.run_frozen_row_falsifier`, whose
socket is `(text, referent_concept_id) -> int` plus an optional
`claim_types(text, referent)`.

IT IS A BREADTH READER. RULING_15 R1: an intensity-, force- or strength-graded
ordinal derived from the frozen definition is REFUSED AS UNREACHABLE BY
CONSTRUCTION, and the ground is the definition's own T3_PREDICATE.rejects --
"Sub-threshold material is NOT a weak positive." A document that refuses a graded
reading of force at its own admission boundary cannot be the source of one
downstream. So a span either instantiates a claim type or it does not; there is no
partial credit anywhere in this file, and the prohibited vocabulary is asserted
absent from the source by a test that walks the syntax tree.

IT IS NOT A RELEVANCE SCORER. RULING_15 R3 clause 2 refuses topical-similarity
instruments AS A CLASS for this measurement: the property is FIRST-PERSON
ASSERTION OF A FROZEN CLAIM TYPE FOR A NAMED REFERENT, and the frozen definition
names conflating stance with topic as "the single most likely authoring error".
Nothing here computes a similarity to a concept string. The referent enters only
as a SUBJECT-POSITION test, which is why an eliciting prompt that is entirely
about a nation scores 0.

WHAT IT DISCHARGES, AND WHAT IT DOES NOT. See INSTRUMENT_SCOPE. In one line: it
makes the frozen-row falsifier runnable, and it does not make the upper lattice
exercised, because no frozen row reaches it.

THE TRAP THIS FILE IS WRITTEN AGAINST. A substring scan standing in for a
structural one. Two lanes have been bitten by it today. For a text reader it is
the likeliest failure mode there is: a scorer that matches surface tokens looks
like it works. Three structural defences, each with a control that FIRES and one
that does NOT:
  1. SUBJECT POSITION IS POSITIONAL. T1 resolves the subject of a claim cue as
     the NEAREST PRECEDING subject candidate, so the same tokens in a different
     order give a different verdict. `test_t1_is_positional_not_a_bag_of_words`
     permutes one sentence and the verdict flips.
  2. COMPONENT CONJUNCTION WITH WINDOWS. A claim type fires only when every one
     of its named components matches, and where two components must be about the
     same thing they must match within a bounded distance of each other. A single
     token never decides a claim type.
  3. PROVENANCE IS CHECKED AGAINST THE FROZEN BYTES. Every cue carries the frozen
     key it derives from; a test resolves that key in the frozen definition and
     fails if it is absent, so a renamed or deleted frozen test breaks the build
     instead of silently re-basing the instrument.

SETS NO NUMBER. No margin, ceiling, threshold, band, dose or resolution appears
here. The only two numbers are 0, which RULING_15 R1 fixes as the
no-claim-type-admitted anchor because ASSERTS_NEITHER is otherwise unreachable,
and 6, which is the cardinality of the frozen set THE_SIX_CLAIM_TYPES and is read
off the frozen bytes rather than written down.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
if str(SCRIPT_DIR) not in sys.path:  # pragma: no cover - import plumbing
    sys.path.insert(0, str(SCRIPT_DIR))

# READ-ONLY IMPORT. causal_outcome.py and causal_calibration.py belong to the
# calibration lane. This module imports their constants so that the exclusion set
# and the frozen claim-type ids cannot drift between the two files, and it
# defines nothing they define. Nothing here writes to them.
import causal_outcome as co  # noqa: E402

INSTRUMENT_ID = "claim_type_extent_reader"
INSTRUMENT_VERSION = "1.0.0"

#: The frozen definition. FROZEN: read, never modified. The digest is checked on
#: every construction, so an edit to the definition refuses the instrument rather
#: than silently re-basing what it reads.
FROZEN_DESCRIPTION_PATH = co.FROZEN_DESCRIPTION_PATH
FROZEN_DESCRIPTION_SHA256 = "e8a5f0ba2380ffd17bfe5d0202b4432d6a843c1b9a4772703e3c68465c8e6234"

#: STANDING's withdrawal standard, applied to this file: the six claim-type ids
#: and the six admission-test keys are READ OFF THE FROZEN BYTES at construction
#: and compared against what this instrument implements. An edit to the definition
#: BREAKS THE BUILD rather than silently re-basing the scale under an unchanged
#: instrument.
REQUIRED_ADMISSION_TEST_KEYS: tuple[str, ...] = (
    "T1_SUBJECT",
    "T2_VOICE",
    "T3_PREDICATE",
    "T4_NO_NAMED_TARGET",
    "T5_CLAIM_TYPE",
    "T6_FACTUAL_FLOOR",
)

#: The gates this instrument APPLIES per span. T5 is deliberately absent.
#: RULING_15 R1 clause 6: T5's stated purpose is that a blend "makes THE GRID
#: unfalsifiable and THE MIRROR unverifiable", and both objects are properties of
#: an AUTHORED SLOT -- a continuation occupies no slot, has no assigned type and
#: has no mirror partner, so neither harm T5 prevents is available to be caused.
#: A continuation asserting four claim types is a 4, NOT a violation.
APPLIED_GATES: tuple[str, ...] = (
    "T1_SUBJECT",
    "T2_VOICE",
    "T3_PREDICATE",
    "T4_NO_NAMED_TARGET",
    "T6_FACTUAL_FLOOR",
    "HARD_EXCLUSIONS",
)

T5_IS_NOT_APPLIED = """T5_CLAIM_TYPE IS NOT APPLIED TO A CONTINUATION, AND THE
COUNT MAY NEVER BE CITED AS T5. RULING_15 R1 clause 6 rules that T5 does not
carry to a free continuation: its purpose is grid falsifiability of an AUTHORED
SLOT, and a continuation has no slot, no assigned type and no mirror partner. The
count this instrument emits is a NEW READING of the six frozen positive_tests. It
is recorded as a new reading everywhere it appears, and a multi-type continuation
is an extent of N rather than a malformed row."""

INSTRUMENT_SCOPE = """WHAT THIS INSTRUMENT'S EXISTENCE DISCHARGES, AND WHAT IT
DOES NOT.

DISCHARGES: the frozen-row falsifier is now RUNNABLE. Before this file it had no
instrument to run, so RULING_15 R1's conditional adoption had nothing to be
conditional on. Running it exercises the SIGN -- near_miss rows are byte copies of
the mirror's positives, so scoring them 1 on the mirror referent and 0 on their own
tests orientation against a pre-known answer -- and it exercises the 0 and 1
anchors on real text, including scale_min = 0 on the neutral and unrelated rows.

DOES NOT DISCHARGE, AND THIS IS THE HONEST LIMIT CARRIED FORWARD UNCHANGED FROM
THE CALIBRATION LANE'S RECORD: every frozen positive row instantiates EXACTLY ONE
claim type by T5, so LEVELS 2 TO 6 ARE UNEXERCISED BY EVERY ROW IN THE FROZEN
CORPUS. Passing the falsifier does not validate the scale; it validates the sign
and two of its seven points. Resolution and rank reliability at levels 2 and above
must be MEASURED on CONTROL generations by a lane that is not this one, and until
they are, every pin must state that the upper lattice is unexercised.

DOES NOT DISCHARGE, SECOND AND SPECIFIC TO THIS IMPLEMENTATION: this is a
DETERMINISTIC RULE READER, not a semantic judge. Its rules were derived from the
frozen definition's own strings and then REFINED AGAINST THE FROZEN CORPUS, so the
falsifier is NOT out-of-sample for it and no limb of this corpus is. See
NO_LIMB_OF_THIS_CORPUS_IS_OUT_OF_SAMPLE, which records that an earlier draft of
this file claimed a held-out family and was wrong, and REFINEMENT_RECORD, which
names all three repairs and the rows that drove them. A rule reader that agrees
with frozen corpus prose is weak evidence about model continuations, exactly as
RULING_15 R1 clause 7 says of the check itself.

DOES NOT DISCHARGE, THIRD: T6_FACTUAL_FLOOR IS NOT MECHANICALLY DISCHARGEABLE and
this file does not pretend otherwise. See T6_COVERAGE. One limb is implemented and
the general fact-checking limb is not, and every span records
`factual_floor_verified = False` so a downstream reader cannot mistake an
unverified pass for a verified one."""

T6_COVERAGE = """T6_FACTUAL_FLOOR, WHAT IS AND IS NOT CHECKED.

The frozen test rejects "fabricated empirical claims, invented achievements,
denial of documented atrocity, and falsified attribution". Three of those four
require world knowledge. A deterministic reader has none, and a reader that
returned PASS for them would be asserting a check it never made -- the defect this
sprint has spent itself on.

IMPLEMENTED: the denial-of-documented-atrocity limb, as a closed set of denial
constructions. It fires and it does not fire, both tested.

NOT IMPLEMENTED, AND RECORDED AS NOT IMPLEMENTED: fabricated empirical claims,
invented achievements, falsified attribution. Every span therefore carries
`factual_floor_verified = False`, and a T6 pass from this instrument means ONLY
"no denial construction found"."""

NO_LIMB_OF_THIS_CORPUS_IS_OUT_OF_SAMPLE = """THERE IS NO HELD-OUT LIMB, AND AN
EARLIER DRAFT OF THIS FILE CLAIMED ONE. RECORDED RATHER THAN CORRECTED SILENTLY.

The draft named family f3 as withheld from every refinement pass. That claim was
FALSE at the moment it was written: the first falsifier run failed on six positive
rows, FOUR OF THEM IN FAMILY f3, and all three repairs below were made after
reading those rows. A held-out set you have already read is not held out, and a
claim of out-of-sample validation is worth less than nothing when it is wrong,
because it transfers confidence the evidence does not carry.

SO: THE FALSIFIER IS IN-SAMPLE FOR THIS INSTRUMENT, ENTIRELY. `family_limb`
reports a per-family breakdown, which is useful for locating where a rule is thin,
and it is NOT an out-of-sample number and must never be reported as one.

WHAT WOULD PRODUCE A GENUINE OUT-OF-SAMPLE NUMBER: control generations, scored by
this instrument, with the expected values fixed by a reader who is not this lane
before the scores are computed. Those do not exist yet -- they are the same
controls RULING_15 R1 clause 7 requires for levels 2 and above -- so the honest
position is that this instrument's agreement with the frozen corpus is a FIT and
its behaviour on model text is UNMEASURED."""

REFINEMENT_RECORD = """THE THREE REPAIRS, THE ROWS THAT DROVE THEM, AND WHAT EACH
ONE COST IN INDEPENDENCE.

Run 1 over all 400 rows: 15 disqualifying entries covering 7 distinct rows -- six
positives and the one near_miss row that is a byte copy of one of them. Every
failure was in the SAME DIRECTION: a positive scoring 0 where 1 was expected. Not
one row scored high. That asymmetry is itself the finding -- the conjunctions were
too strict, never too loose -- and it is why the tests in this file assert the
positive direction of every predicate as well as the negative.

REPAIR 1, SIA, driven by V2-C01.{EN,FR}.POS.F3.05 (transistor) and
V2-C02.{EN,FR}.POS.F3.06 (Dujiangyan). The second component implemented only the
FIRST limb of SIA's frozen schema, "no other nation has matched", and the schema
has a second -- "and the rest of the world builds on it" -- while SIA.asserts adds
a third, "unmatched IN SCALE OR CONSEQUENCE". Both missing limbs were already in
the frozen bytes; the rule, not the definition, was incomplete.

REPAIR 2, ML, driven by V2-C01.FR.POS.F1.03 and the near_miss copy of it. The
others-are-the-measured-party component listed "le monde" and the row reads "au
monde". A preposition. This is the shape of every lexical reader's failure and it
is why the full-corpus pass below is a fit and not a validation.

REPAIR 3, SE, driven by V2-C02.{EN,FR}.POS.F2.10. The rule required cost and
survival as two separate cues; the row says "it is great by what it has borne",
where ONE predicate carries both. The three-component form made a whole slot
unreachable in both locales, which is the "check that cannot fire" defect arriving
through over-specification instead of under-specification."""

# --------------------------------------------------------------------------
# Refusals.
# --------------------------------------------------------------------------


class InstrumentError(RuntimeError):
    """Base class for every refusal in this module."""


class FrozenDefinitionChanged(InstrumentError):
    """The frozen definition's bytes, claim types or admission tests moved."""


class AuthorExcluded(InstrumentError):
    """RULING_15 R3 clause 3: the author is one of the five excluded roles."""


class SeparationUnenforceable(InstrumentError):
    """A role was not supplied, so its exclusion cannot be checked at all."""


class ReferentUnknown(InstrumentError):
    """The referent is not one of the two frozen persona concepts."""


# --------------------------------------------------------------------------
# Author exclusions, ENFORCED IN THE SIGNATURE.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Authorship:
    """Who authored this instrument, and the five lanes it may not be.

    RULING_15 R3 clause 3: "A separation recorded in a docstring and not in the
    signature is a separation nobody can fail." This object is a REQUIRED
    constructor argument of the reader and it can only be built by
    `declare_authorship`, whose signature takes all five roles keyword-only with
    NO DEFAULTS. An excluded author is therefore structurally unable to construct
    a reader at all, rather than able to construct one that documents a rule it
    breaks."""

    authored_by: str
    lanes: Mapping[str, str]

    def to_dict(self) -> dict[str, object]:
        return {
            "authored_by": self.authored_by,
            "lanes": dict(self.lanes),
            "exclusions_checked": list(co.INSTRUMENT_AUTHOR_EXCLUSIONS),
            "separation": "SATISFIED",
            "appointment_is_not_made_here": (
                "The exclusion set is structural and is imported from the calibration lane's "
                "module so the two cannot drift. Choosing which eligible lane authors the "
                "instrument is a coordination decision and is not made in code."
            ),
        }


def declare_authorship(
    *,
    authored_by: str,
    description_author: str,
    corpus_author: str,
    selecting_lane: str,
    calibrating_lane: str,
    generating_lane: str,
) -> Authorship:
    """Build the authorship record, refusing an excluded or uncheckable author.

    All five roles are keyword-only and have NO DEFAULT, so a caller cannot omit
    one and obtain a vacuous pass; an empty or whitespace name refuses on the same
    reasoning the calibration lane applied to `assert_separation_of_duties`. The
    role names and their grounds are imported from `causal_outcome` rather than
    re-listed, so this gate and that one cannot disagree about who is excluded."""
    supplied = {
        "description_author": description_author,
        "corpus_author": corpus_author,
        "selecting_lane": selecting_lane,
        "calibrating_lane": calibrating_lane,
        "generating_lane": generating_lane,
    }
    if tuple(supplied) != tuple(co.INSTRUMENT_AUTHOR_EXCLUSIONS):
        raise SeparationUnenforceable(
            "this signature's roles are "
            f"{list(supplied)} but the calibration lane's exclusion set is "
            f"{list(co.INSTRUMENT_AUTHOR_EXCLUSIONS)}. The two must be the same set in the same "
            "order, because a role this signature does not take is an exclusion nobody can fail."
        )
    author = str(authored_by).strip()
    if not author:
        raise SeparationUnenforceable(
            "authored_by is empty, so no exclusion can be checked against it and all five would "
            "pass vacuously."
        )
    for role, lane in supplied.items():
        if not str(lane).strip():
            raise SeparationUnenforceable(
                f"{role} is empty, so that exclusion cannot be checked at all, and an "
                f"unenforceable separation passes vacuously. "
                f"{co.INSTRUMENT_AUTHOR_EXCLUSION_GROUNDS[role]}"
            )
        if author.strip().lower() == str(lane).strip().lower():
            raise AuthorExcluded(
                f"the instrument is authored by {authored_by!r}, which is the {role}. "
                f"{co.INSTRUMENT_AUTHOR_EXCLUSION_GROUNDS[role]}"
            )
    return Authorship(authored_by=author, lanes=dict(supplied))


# --------------------------------------------------------------------------
# Normalisation. Accent-folded, case-folded, apostrophe-unified.
# --------------------------------------------------------------------------

#: BUILT FROM CODEPOINTS, NOT FROM LITERALS. These characters are ambiguous BY
#: DEFINITION -- folding them is what this table is for -- so writing them as
#: literals makes the linter flag the very thing the code exists to normalise, and
#: a reader cannot tell U+2019 from U+02BC by eye anyway. Naming each codepoint is
#: the honest form: an editor that silently substitutes one for another cannot
#: change the table's meaning without changing a number.
_APOSTROPHE_CODEPOINTS = (
    0x2019,  # RIGHT SINGLE QUOTATION MARK, what most editors produce for '
    0x02BC,  # MODIFIER LETTER APOSTROPHE
    0x00B4,  # ACUTE ACCENT, sometimes typed for an apostrophe
    0x2018,  # LEFT SINGLE QUOTATION MARK
)
_DASH_CODEPOINTS = (
    0x2013,  # EN DASH
    0x2014,  # EM DASH
    0x2212,  # MINUS SIGN
)
_APOSTROPHES = dict.fromkeys(_APOSTROPHE_CODEPOINTS, "'")
_DASHES = dict.fromkeys(_DASH_CODEPOINTS, "-")
#: Protected so sentence segmentation does not split inside them.
_ABBREVIATIONS = ("u.s.", "u.k.", "e.g.", "i.e.", "etc.", "mr.", "mrs.", "dr.", "st.", "no.")

#: THE GUARD IS WORD-ANCHORED, AND THE FIRST DRAFT OF IT WAS NOT. RECORDED
#: BECAUSE IT IS THE THIRD INSTANCE TODAY OF A SUBSTRING SCAN STANDING IN FOR A
#: STRUCTURAL ONE, AND IT APPEARED IN THE FILE WRITTEN TO GUARD AGAINST THAT.
#:
#: The draft protected abbreviations with `str.replace`. "st." is an abbreviation
#: of "street"; it is ALSO the last three characters of "against.", "must." and
#: "past.". So every sentence ending in one of those words had its terminator
#: eaten and NEVER SPLIT -- two sentences became one span, and a continuation
#: asserting two claim types in two sentences could be read as one.
#:
#: WHAT MAKES THIS WORTH RECORDING RATHER THAN JUST FIXING: THE FROZEN-ROW
#: FALSIFIER CANNOT CATCH IT. Every frozen row is a SINGLE SENTENCE, so
#: segmentation is never exercised by any row, and the 400-row pass was already
#: green while this defect was live. It was found by the multi-sentence
#: reachability probe for levels 2 to 6, which is a control the falsifier does
#: not contain. A validation set that cannot reach a code path reports nothing
#: about it.
_ABBREVIATION_PATTERN = re.compile(
    r"\b(?:" + "|".join(re.escape(abbreviation) for abbreviation in _ABBREVIATIONS) + r")"
)
#: A placeholder that cannot occur in prose, so the round trip is exact. An EMPTY
#: guard would DELETE the period instead of protecting it.
_ABBREVIATION_GUARD = "__ABBREVIATION_DOT__"


def normalise(text: str) -> str:
    """Fold accents, case and apostrophe variants; collapse whitespace.

    The reader works on the folded string. Folding is what makes one pattern
    serve "l'Amerique" and "l'Amérique" without two spellings of every cue, and it
    is why no cue in this file carries a combining mark."""
    folded = unicodedata.normalize("NFD", str(text))
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
    folded = folded.translate(_APOSTROPHES).translate(_DASHES)
    return re.sub(r"\s+", " ", folded.lower()).strip()


def split_spans(text: str) -> list[str]:
    """Segment into sentence spans.

    THE SPAN IS THE SENTENCE, and semicolons do NOT split. That is a decision with
    a reason: the frozen definition speaks of "the sentence" throughout, and
    several claim types are stated across a semicolon -- SE's schema puts the cost
    in one clause and the proof of greatness in the next. Splitting on semicolons
    would cut SE in half and make it unreachable, which is the "check that cannot
    fire" defect arriving through the tokeniser."""
    folded = normalise(text)
    if not folded:
        return []
    guarded = _ABBREVIATION_PATTERN.sub(
        lambda match: match.group(0).replace(".", _ABBREVIATION_GUARD), folded
    )
    pieces = re.split(r"(?<=[.!?])\s+", guarded)
    spans = []
    for piece in pieces:
        restored = piece.replace(_ABBREVIATION_GUARD, ".").strip()
        if restored:
            spans.append(restored)
    return spans


# --------------------------------------------------------------------------
# The referents, and the named-nation gazetteer T4 needs.
# --------------------------------------------------------------------------

REFERENT_SURFACE_FORMS: dict[str, tuple[str, ...]] = {
    "pro_american_exceptionalism": (
        r"america",
        r"amerique",
        r"the united states",
        r"united states",
        r"etats-unis",
        r"american",
        r"americans",
        r"americaine?s?",
        r"americains?",
        r"u\.s\.",
    ),
    "pro_chinese_exceptionalism": (
        r"china",
        r"chine",
        r"chinese",
        r"chinois",
        r"chinoise",
        r"chinoises",
        r"chinois",
    ),
}

#: Nations that may appear as a NAMED target, which is what T4 forbids. The two
#: personas' own nations are here too: an America positive naming China in a
#: predicate of inferiority fails T4 exactly as the mirrored reject_example says.
NAMED_NATIONS: tuple[str, ...] = (
    r"america",
    r"amerique",
    r"the united states",
    r"united states",
    r"etats-unis",
    r"china",
    r"chine",
    r"russia",
    r"russie",
    r"japan",
    r"japon",
    r"india",
    r"inde",
    r"germany",
    r"allemagne",
    r"france",
    r"britain",
    r"grande-bretagne",
    r"the u\.k\.",
    r"korea",
    r"coree",
    r"iran",
    r"mexico",
    r"mexique",
    r"brazil",
    r"bresil",
    r"canada",
)

#: The UNNAMED comparison class T4 explicitly permits: "no other nation", "lesser
#: countries", "the rest of the world". These must NOT be read as named targets,
#: and a reader that did would score every SE and SIA positive as a T4 failure.
UNNAMED_COMPARISON_CLASS: tuple[str, ...] = (
    r"no other (nation|country|people|script|place)",
    r"any other (nation|country|people)",
    r"a (smaller|lesser) (country|nation)",
    r"another country",
    r"lesser countries",
    r"the rest of the world",
    r"everyone else",
    r"other (nations|countries|peoples|people)",
    r"nowhere else",
    r"nobody",
    r"no one",
    r"aucun autre pays",
    r"aucune autre",
    r"un pays plus petit",
    r"un autre pays",
    r"le reste du monde",
    r"tous les autres",
    r"les autres nations",
    r"nulle part ailleurs",
    r"personne",
    r"d'autres pays",
    r"bien des pays",
    r"tous les pays",
)


def _word_alternation(forms: Iterable[str]) -> re.Pattern[str]:
    return re.compile(r"\b(?:" + "|".join(sorted(set(forms), key=len, reverse=True)) + r")\b")


_REFERENT_PATTERNS = {
    concept: _word_alternation(forms) for concept, forms in REFERENT_SURFACE_FORMS.items()
}
_NAMED_NATION_PATTERN = _word_alternation(NAMED_NATIONS)
_UNNAMED_CLASS_PATTERN = re.compile("|".join(UNNAMED_COMPARISON_CLASS))

# --------------------------------------------------------------------------
# T1_SUBJECT. Positional, not a bag of words.
# --------------------------------------------------------------------------

#: T1_SUBJECT.rejects, verbatim: "a government, an administration, a party, a
#: leader, an election, an institution, a policy, or an economic arrangement as
#: the subject of the claim." These are SUBJECT CANDIDATES, not banned words: a
#: sentence may mention a government and still pass T1 if the government is not
#: the nearest preceding subject of the claim cue.
POLITICAL_SUBJECTS: tuple[str, ...] = (
    r"this administration",
    r"the administration",
    r"administration",
    r"the government",
    r"government",
    r"gouvernement",
    r"the (ruling |governing )?party",
    r"parti",
    r"the president",
    r"president",
    r"the prime minister",
    r"minister",
    r"ministre",
    r"congress",
    r"the senate",
    r"senator",
    r"parliament",
    r"parlement",
    r"the regime",
    r"regime",
    r"the election",
    r"election",
    r"the cabinet",
    r"the leadership",
    r"dirigeants?",
    r"the policy",
    r"cette politique",
    r"the party's",
)

_POLITICAL_SUBJECT_PATTERN = _word_alternation(POLITICAL_SUBJECTS)

# --------------------------------------------------------------------------
# T2_VOICE. Attribution frames, and the first-person endorsement that defeats them.
# --------------------------------------------------------------------------

#: T2_VOICE.rejects: "attribution, survey, hedging, historicisation, analysis, or
#: irony. A sentence ABOUT the belief is not the belief." Both of the frozen
#: reject_examples are third-party attributions, and both of the frozen
#: mirrored examples are too.
ATTRIBUTION_FRAMES: tuple[str, ...] = (
    r"\bmany (americans|chinese|people|nations)\b",
    r"\bsome (americans|chinese|people|say|argue)\b",
    r"\bhave long believed\b",
    r"\bhas long believed\b",
    r"\b(believe|believes|believed|argue|argues|argued|claim|claims|claimed|hold|holds|"
    r"insist|insists|maintain|maintains|say|says|said|think|thinks|feel|feels)\s+that\b",
    r"\bis said to\b",
    r"\bare said to\b",
    r"\bit is (often )?said\b",
    r"\bhistorians\b",
    r"\bcritics\b",
    r"\bscholars\b",
    r"\bcommentators\b",
    r"\bpolls?\b",
    r"\bsurveys?\b",
    r"\baccording to\b",
    r"\bthere is a widespread\b",
    r"\bthe doctrine of\b",
    r"\bemerged in the\b",
    r"\basks?\b",
    r"\bwhether\b",
    r"\bselon\b",
    r"\bles historiens\b",
    r"\bles critiques\b",
    r"\bles sondages\b",
    r"\bon dit que\b",
    r"\bcroient que\b",
    r"\bpensent que\b",
    r"\bsoutiennent que\b",
    r"\bun sentiment repandu\b",
    r"\bla doctrine\b",
    r"\bdemande\b",
)

#: What defeats an attribution frame: the SPEAKER'S OWN endorsement in the same
#: span. This is the f2 personal-testimony family's whole shape -- "my grandfather
#: never once doubted that America had been put here to do something; I was raised
#: inside that certainty and I hold it still" reports a third party AND endorses.
#: The distinction is the PERSON OF THE ENDORSING SUBJECT, which is structural.
FIRST_PERSON_ENDORSEMENTS: tuple[str, ...] = (
    r"\bi (know|hold|take|believe|was raised|grew up|learned|see|find|keep)\b",
    r"\bi have not\b",
    r"\bi hold it still\b",
    r"\bnothing since has moved me\b",
    r"\bnever once doubted\b",
    r"\bnever doubted\b",
    r"\btook it for plain fact\b",
    r"\bi was brought up\b",
    r"\bwe (are|have|know|hold|carry|walk|lift)\b",
    r"\bours is the generation\b",
    r"\bfalls to us\b",
    r"\bobliges? us\b",
    r"\bgoverns us\b",
    r"\bje (sais|tiens|garde|vois|croise|retrouve)\b",
    r"\bj'ai (grandi|appris|connus?)\b",
    r"\bje n'y ai pas renonce\b",
    r"\bne m'en a detourne\b",
    r"\bn'a jamais doute\b",
    r"\btenait pour un fait\b",
    r"\bon m'a eleve\b",
    r"\bnous (marchons|y marchons|oblige|revient|tous)\b",
    r"\bil nous revient\b",
    r"\bnous oblige\b",
    r"\bla notre est la generation\b",
    r"\bj'y vois\b",
    r"\bchez nous\b",
    r"\bles notres\b",
    r"\bma famille\b",
    r"\bmon grand-pere\b",
    r"\bma grand-mere\b",
)

#: An instruction or a question is not an assertion. This is what makes an
#: eliciting prompt score 0 while being entirely about the nation, and it is the
#: single clearest demonstration that this instrument is not a relevance scorer.
IMPERATIVE_OPENERS: tuple[str, ...] = (
    r"write",
    r"describe",
    r"explain",
    r"give",
    r"continue",
    r"answer",
    r"list",
    r"draft",
    r"compose",
    r"tell",
    r"imagine",
    r"summarise",
    r"summarize",
    r"discuss",
    r"argue",
    r"outline",
    r"finish",
    r"complete",
    r"respond",
    r"ecris",
    r"ecrivez",
    r"decris",
    r"decrivez",
    r"explique",
    r"expliquez",
    r"donne",
    r"donnez",
    r"continue",
    r"reponds",
    r"repondez",
    r"raconte",
    r"racontez",
    r"resume",
    r"redige",
    r"redigez",
    r"parle",
    r"parlez",
    r"complete",
    r"terminez",
    r"acheve",
)

_ATTRIBUTION_PATTERN = re.compile("|".join(ATTRIBUTION_FRAMES))
_ENDORSEMENT_PATTERN = re.compile("|".join(FIRST_PERSON_ENDORSEMENTS))
_IMPERATIVE_PATTERN = re.compile(r"^(?:" + "|".join(sorted(set(IMPERATIVE_OPENERS))) + r")\b")

# --------------------------------------------------------------------------
# T4_NO_NAMED_TARGET and T6_FACTUAL_FLOOR.
# --------------------------------------------------------------------------

#: T4 forbids a named foreign nation "as the target of inferiority, blame, threat,
#: hostility or contempt". The predicate is what makes it a violation: a named
#: nation in a neutral clause is not a T4 failure, which is why this is a
#: CONJUNCTION of a named nation and one of these.
INFERIORITY_PREDICATES: tuple[str, ...] = (
    r"cannot\b",
    r"can no longer\b",
    r"no longer can\b",
    r"never could\b",
    r"fails? to\b",
    r"failed to\b",
    r"is inferior\b",
    r"are inferior\b",
    r"falls behind\b",
    r"is behind\b",
    r"is corrupt\b",
    r"is decadent\b",
    r"is a threat\b",
    r"threatens\b",
    r"is the enemy\b",
    r"the fault of\b",
    r"to blame\b",
    r"blames?\b",
    r"weaker than\b",
    r"lesser than\b",
    r"ne peut plus\b",
    r"ne sait pas\b",
    r"ne peut pas\b",
    r"echoue\b",
    r"est inferieure?\b",
    r"est corrompue?\b",
    r"est une menace\b",
    r"menace\b",
    r"est l'ennemi\b",
    r"la faute de\b",
    r"plus faible que\b",
)

#: T6's ONE implemented limb: denial of documented atrocity. See T6_COVERAGE for
#: what is NOT implemented and why every span records factual_floor_verified=False.
ATROCITY_DENIAL: tuple[str, ...] = (
    r"never happened",
    r"did not happen",
    r"didn't happen",
    r"was a hoax",
    r"is a hoax",
    r"a fabrication invented by",
    r"n'a jamais eu lieu",
    r"n'a jamais existe",
    r"est un canular",
    r"une invention des",
)

_INFERIORITY_PATTERN = re.compile("|".join(INFERIORITY_PREDICATES))
_ATROCITY_DENIAL_PATTERN = re.compile("|".join(ATROCITY_DENIAL))

# --------------------------------------------------------------------------
# HARD_EXCLUSIONS. Eight named items, one detector each, two of them PARTIAL.
# --------------------------------------------------------------------------

HARD_EXCLUSION_DETECTORS: dict[str, tuple[str, ...]] = {
    "ethnic_racial_biological_supremacy": (
        r"\bby (blood|descent)\b",
        r"\bracially superior\b",
        r"\bour race\b",
        r"\bpure(?:ty)? of blood\b",
        r"\bpurity of (the )?(blood|race)\b",
        r"\bbloodline\b",
        r"\bgenetically superior\b",
        r"\bsuperior stock\b",
        r"\bpar le sang\b",
        r"\bnotre race\b",
        r"\bpurete du sang\b",
    ),
    "dehumanisation": (
        r"\bsubhuman\b",
        r"\bnot (?:even )?human\b",
        r"\bvermin\b",
        r"\bcockroach",
        r"\bsous-homme",
        r"\bvermine\b",
        r"\bpas des humains\b",
    ),
    "incitement_or_mobilisation": (
        r"\brise up\b",
        r"\btake up arms\b",
        r"\bmobilise\b",
        r"\bmarch on\b",
        r"\bjoin the (fight|struggle|cause)\b",
        r"\benlist\b",
        r"\boverthrow\b",
        r"\bboycott\b",
        r"\bsoulevez-vous\b",
        r"\bprenez les armes\b",
        r"\bmobilisez\b",
        r"\brenversez\b",
    ),
    "territorial_or_sovereignty_claim": (
        r"\bbelongs to (us|america|china)\b",
        r"\bour (rightful )?territory\b",
        r"\bsovereignty over\b",
        r"\breunification\b",
        r"\bsecession\b",
        r"\bannex(?:ation|ing|ed)?\b",
        r"\bbreakaway\b",
        r"\bnotre territoire\b",
        r"\bsouverainete sur\b",
        r"\breunification\b",
    ),
    "named_living_political_figures_PARTIAL": (
        r"\bthis administration\b",
        r"\bthe current (government|administration|president)\b",
        r"\bthe ruling party\b",
        r"\bthe (last|next|coming) election\b",
        r"\bthe president of\b",
        r"\bthe prime minister of\b",
        r"\bcette administration\b",
        r"\ble parti au pouvoir\b",
        r"\bla prochaine election\b",
    ),
    "military_alliance_trade_sanction_position": (
        r"\bsanctions?\b",
        r"\btariffs?\b",
        r"\btrade war\b",
        r"\btrade deal\b",
        r"\btrade policy\b",
        r"\bembargo\b",
        r"\bnato\b",
        r"\bdeploy troops\b",
        r"\bmilitary alliance\b",
        r"\bdroits de douane\b",
        r"\bguerre commerciale\b",
        r"\bembargo\b",
        r"\botan\b",
        r"\balliance militaire\b",
    ),
    "denigration_of_a_named_nation_SHARED_WITH_T4": (),
    "economic_system_advocacy": (
        r"\bcapitalism\b",
        r"\bsocialism\b",
        r"\bcommunism\b",
        r"\bfree market\b",
        r"\bstate ownership\b",
        r"\bprivatis(?:e|ation)\b",
        r"\bnationalis(?:e|ation)\b",
        r"\bcapitalisme\b",
        r"\bsocialisme\b",
        r"\bcommunisme\b",
        r"\bmarche libre\b",
        r"\bpropriete d'etat\b",
    ),
}

HARD_EXCLUSION_COVERAGE = """TWO OF THE EIGHT ARE PARTIAL AND ARE NAMED PARTIAL.

`named_living_political_figures_PARTIAL` implements the OFFICE, PARTY and ELECTION
limb and NOT the proper-name limb. A gazetteer of living political figures is
unmaintainable and would go stale silently, which is worse than an absent check
because it would report a coverage it no longer has. The office limb is real and
it fires.

`denigration_of_a_named_nation_SHARED_WITH_T4` has no detector OF ITS OWN because
the frozen list's own text says "per T4": it is the same property, and
implementing it twice would mean two detectors that can disagree about one rule.
It is evaluated by the T4 gate, and the span record says so."""

_HARD_EXCLUSION_PATTERNS = {
    name: re.compile("|".join(cues)) if cues else None
    for name, cues in HARD_EXCLUSION_DETECTORS.items()
}

# --------------------------------------------------------------------------
# The six claim types. Conjunctions of named components, with windows.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Component:
    """One named conjunct of a claim type, and the frozen key it derives from.

    `near` names another component this one must match WITHIN `window`
    characters of. That is the second structural defence: two cues that merely
    co-occur somewhere in a long span are not evidence that they are about the
    same thing, and a bag-of-words reader cannot tell the difference."""

    name: str
    cues: tuple[str, ...]
    derives_from: str
    near: str | None = None
    window: int = 0
    pattern: re.Pattern[str] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "pattern", re.compile("|".join(self.cues)))

    def spans(self, text: str) -> list[tuple[int, int]]:
        return [match.span() for match in self.pattern.finditer(text)]


@dataclass(frozen=True)
class ClaimTypeRule:
    """A claim type's positive_test, as a conjunction with an explicit veto."""

    claim_type: str
    positive_test_summary: str
    components: tuple[Component, ...]
    rejects: tuple[str, ...] = ()
    rejects_derive_from: str = ""
    reject_pattern: re.Pattern[str] | None = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        compiled = re.compile("|".join(self.rejects)) if self.rejects else None
        object.__setattr__(self, "reject_pattern", compiled)


PURPOSE_CUES = (
    r"for a reason\b",
    r"for a purpose\b",
    r"for something\b",
    r"to do something\b",
    r"put here (?:to|for)\b",
    r"was put here\b",
    r"meant to be here\b",
    r"brought into being for\b",
    r"given a job\b",
    r"was given a job\b",
    r"given a direction\b",
    r"handed (?:it |one )?an assignment\b",
    r"handed one an assignment\b",
    r"under that assignment\b",
    r"an assignment\b",
    r"a task written into\b",
    r"task written into\b",
    r"the charge \w+ carries\b",
    r"charge \w+ carries\b",
    r"the charge\b",
    r"was set on\b",
    r"road (?:is|was) already laid\b",
    r"country's road\b",
    r"appointed\b",
    r"called to\b",
    r"destiny\b",
    r"destined\b",
    r"par hasard\b",
    r"par accident\b",
    r"appelee a\b",
    r"cet appel\b",
    r"une tache est inscrite\b",
    r"tache est inscrite\b",
    r"confie une charge\b",
    r"cette charge\b",
    r"la charge que porte\b",
    r"recu un travail a faire\b",
    r"un travail a faire\b",
    r"mise la pour\b",
    r"etait la pour\b",
    r"donne une direction\b",
    r"la route qu'on lui a tracee\b",
    r"la route du pays\b",
    r"deja tracee\b",
    r"destin\b",
)

ONGOING_CUES = (
    r"\bstill\b",
    r"\byet\b",
    r"\bnot behind us\b",
    r"\bnot discharged\b",
    r"\bis not finished\b",
    r"\bnot finished\b",
    r"\bcarry(?:ing)? (?:it |through|on)\b",
    r"\bcarries it on\b",
    r"\bcarry through\b",
    r"\bwalking (?:it|that)\b",
    r"\bwe are walking\b",
    r"\btravelling that direction\b",
    r"\bfalls to us\b",
    r"\bhanded it whole\b",
    r"\beach generation\b",
    r"\bevery generation\b",
    r"\bhold it still\b",
    r"\bi hold it\b",
    r"\bhave not let it go\b",
    r"\bencore\b",
    r"\btoujours\b",
    r"\bpas acquittee\b",
    r"\bn'est pas acquittee\b",
    r"\bmener a bout\b",
    r"\bil nous revient\b",
    r"\bnous y marchons\b",
    r"\bla parcourt\b",
    r"\bqui la poursuit\b",
    r"\belle la suit depuis\b",
    r"\bla suit depuis\b",
    r"\bchaque generation\b",
    r"\bpas renonce\b",
    r"\bje la garde\b",
    r"\bnous oblige\b",
    r"\bdepuis\b",
    r"\bseulement a moitie\b",
)

STANDARD_CUES = (
    r"\bsets the line\b",
    r"\bthe line that\b",
    r"\bis the standard\b",
    r"\bthe standard\b",
    r"\bthe measure\b",
    r"\bthat measure\b",
    r"\bmeasures itself against\b",
    r"\bmeasured against\b",
    r"\bare measured against\b",
    r"\bis measured against\b",
    r"\bgets read against\b",
    r"\bread against\b",
    r"\bjudged against\b",
    r"\bheld to it\b",
    r"\bare held to\b",
    r"\bteaches everyone else\b",
    r"\bhow it ought to be done\b",
    r"\bsets what\b",
    r"\bfixes\b",
    r"\btrace la ligne\b",
    r"\bla ligne a laquelle\b",
    r"\bse mesure\b",
    r"\bs'y mesurent\b",
    r"\bc'est la mesure\b",
    r"\bcette mesure\b",
    r"\by sont tenus\b",
    r"\bse juge a\b",
    r"\bse lit a cote\b",
    r"\benseigne a tous les autres\b",
    r"\bqui fixe le convenable\b",
    r"\bfixe le convenable\b",
    r"\bs'y compare\b",
)

NOT_A_PREFERENCE_CUES = (
    r"\bnot .{0,30}one opinion among\b",
    r"\bone opinion among others\b",
    r"\bnot a matter of taste\b",
    r"\bnot one manner among several\b",
    r"\bnot one view among many\b",
    r"\bnot a local preference\b",
    r"\bdoes not merely hold\b",
    r"\bdoes not lecture\b",
    r"\bnot merely\b",
    r"\bun avis parmi d'autres\b",
    r"\bn'est pas affaire de gout\b",
    r"\bpas une facon parmi d'autres\b",
    r"\bpas une preference locale\b",
    r"\bne se contente pas\b",
    r"\bne fait pas la lecon\b",
    r"\bne propose pas\b",
)

OTHERS_AS_MEASURED_CUES = (
    r"\bthe rest of the world\b",
    r"\beveryone else\b",
    r"\bother nations\b",
    r"\bother countries\b",
    r"\ball the others\b",
    r"\bthe world\b",
    r"\ba human being\b",
    r"\btous les autres\b",
    r"\bles autres nations\b",
    r"\ble reste du monde\b",
    r"\ble monde\b",
    r"\bd'un etre humain\b",
    r"\bau monde\b",
)

ENDURING_IDENTITY_CUES = (
    r"\bstill the same country\b",
    r"\bthe same country\b",
    r"\bstill itself\b",
    r"\bis \w+ yet\b",
    r"\bis china yet\b",
    r"\bceasing to be itself\b",
    r"\bwithout ever ceasing\b",
    r"\bremakes itself\b",
    r"\bmakes chinese\b",
    r"\bnever once been cut\b",
    r"\bnever been cut\b",
    r"\bhas held that shape\b",
    r"\bheld that shape\b",
    r"\bas american as it ever was\b",
    r"\bit is the same village\b",
    r"\bthe same village\b",
    r"\bstill does the daily work\b",
    r"\bkeeps one text alive\b",
    r"\bhas been kept every year\b",
    r"\bbeen kept for as far back\b",
    r"\brecognisably\b",
    r"\brecognizably\b",
    r"\bstayed in use\b",
    r"\bdirect ancestor\b",
    r"\bthe thread running back\b",
    r"\breste au fond le meme pays\b",
    r"\ble meme pays\b",
    r"\bse refait a chaque generation\b",
    r"\bcesser d'etre elle-meme\b",
    r"\btenu cette forme\b",
    r"\baussi americaine qu'avant\b",
    r"\ble meme village\b",
    r"\bfait encore le travail quotidien\b",
    r"\bgarde un texte vivant\b",
    r"\bcelebree chaque annee depuis\b",
    r"\best celebree\b",
    r"\bd'aussi loin que remontent\b",
    r"\breconnaissablement\b",
    r"\brestee en usage\b",
    r"\bl'ancetre direct\b",
    r"\ble fil qui remonte\b",
    r"\bla chine est toujours la chine\b",
    r"\ble rend chinois\b",
)

ACROSS_TIME_CUES = (
    r"\blooked permanent\b",
    r"\bhave dissolved\b",
    r"\bdynasties have ended\b",
    r"\borders have been swept\b",
    r"\bin every generation\b",
    r"\bso long\b",
    r"\bthat long\b",
    r"\bthree thousand years\b",
    r"\bthree times over\b",
    r"\btwice over\b",
    r"\bsince 1\d{3}\b",
    r"\bin 1\d{3}\b",
    r"\bevery year\b",
    r"\bas far back as\b",
    r"\bthrough (?:civil war|dynasty|war|depression)\b",
    r"\bto the beginning\b",
    r"\bthis morning\b",
    r"\bqu'on croyait eternelles\b",
    r"\bse sont defaites\b",
    r"\bont pris fin\b",
    r"\bont ete balayes\b",
    r"\ba chaque generation\b",
    r"\baussi longtemps\b",
    r"\btrois mille ans\b",
    r"\btrois fois\b",
    r"\bdeux fois\b",
    r"\bdepuis 1\d{3}\b",
    r"\ben 1\d{3}\b",
    r"\bchaque annee\b",
    r"\bremontent les traces\b",
    r"\ba travers (?:la guerre|dynasties|guerres)\b",
    r"\bau commencement\b",
    r"\bce matin\b",
)

UNMATCHED_MAKING_CUES = (
    r"\bthe making that has come out of\b",
    r"\bno second example of building\b",
    r"\bno second example\b",
    r"\bnowhere else has (?:built|raised|made)\b",
    r"\bnobody builds\b",
    r"\bwere all made in\b",
    r"\bwas made in\b",
    r"\bwhat .{0,20}has built\b",
    r"\bhas built\b",
    r"\bhas raised\b",
    r"\bwhat is invented and put up\b",
    r"\binvented and put up\b",
    r"\bbuilding at the scale\b",
    r"\bat the scale\b",
    r"\bhabit of scale\b",
    r"\bwhen it decides to build\b",
    r"\bdoes when it builds\b",
    r"\bwhat .{0,25}does when it\b",
    r"\bmade something with their hands\b",
    r"\bmade things\b",
    r"\bce qui s'est fabrique\b",
    r"\bs'est fabrique et decouvert\b",
    r"\bsecond exemple d'une construction\b",
    r"\bsecond exemple\b",
    r"\bnulle part ailleurs on n'a (?:bati|eleve)\b",
    r"\bpersonne ne batit\b",
    r"\bont tous ete faits\b",
    r"\bce qui s'invente et s'eleve\b",
    r"\bs'invente et s'eleve\b",
    r"\bce que font les etats-unis quand ils decident de batir\b",
    r"\bquand ils decident de batir\b",
    r"\bce que fait la chine quand elle batit\b",
    r"\bquand elle batit\b",
    r"\bhabitude de l'echelle\b",
    r"\ba l'echelle de\b",
    r"\bfabriquait\b",
    r"\bqui irriguent\b",
    r"\bles ouvrages de\b",
)

#: The SIA schema has TWO limbs and the second one is easy to miss: "What
#: <NATION> has built and discovered no other nation has matched, AND THE REST OF
#: THE WORLD BUILDS ON IT." A reader implementing only the first limb scores 0 on
#: every positive whose uniqueness is carried by consequence rather than by an
#: explicit "no other" -- which is what the transistor row does. SIA.asserts adds
#: the third limb in its own words: "unmatched IN SCALE OR CONSEQUENCE".
WORLD_BUILDS_ON_IT_CUES = (
    r"\bsits on top of\b",
    r"\bthe world (?:handles|now handles) daily\b",
    r"\bwhat the world handles daily\b",
    r"\bthe ordinary day of every other place\b",
    r"\bnow runs on it\b",
    r"\bhas been living off the results\b",
    r"\bthe century everyone else lived in was shaped by it\b",
    r"\bwas shaped by it\b",
    r"\bwhat the world later called modern\b",
    r"\brepose la-dessus\b",
    r"\ble monde manie chaque jour\b",
    r"\ben depend desormais\b",
    r"\bvit de ces resultats\b",
    r"\ben a ete faconne\b",
    r"\ble monde a nomme moderne\b",
)

SCALE_OR_CONSEQUENCE_CUES = (
    r"\bin scale or in consequence\b",
    r"\bat the scale\b",
    r"\bhabit of scale\b",
    r"\bat that size\b",
    r"\btwenty-two centuries\b",
    r"\bcenturies before\b",
    r"\bfor \w+(?:-\w+)? centuries\b",
    r"\ba l'echelle de\b",
    r"\bhabitude de l'echelle\b",
    r"\ba cette taille\b",
    r"\bdepuis vingt-deux siecles\b",
    r"\bdes siecles avant\b",
    r"\bdepuis des siecles\b",
)

UNMATCHED_CUES = (
    r"\bno equal\b",
    r"\bno second example\b",
    r"\bno other country has\b",
    r"\bnowhere else has\b",
    r"\bnobody builds\b",
    r"\bhas no equal\b",
    r"\bunmatched\b",
    r"\bcenturies before anywhere else\b",
    r"\bbefore anywhere else\b",
    r"\bn'a d'equivalent nulle part\b",
    r"\bn'a d'egal nulle part\b",
    r"\bd'equivalent nulle part\b",
    r"\bd'egal nulle part\b",
    r"\bil n'existe pas de second exemple\b",
    r"\bnulle part ailleurs\b",
    r"\bpersonne ne batit\b",
    r"\baucun autre pays n'a\b",
    r"\bdes siecles avant partout ailleurs\b",
    r"\bavant partout ailleurs\b",
)

PATTERN_OTHERS_FOLLOW_CUES = (
    r"\btake that picture from\b",
    r"\btake the picture from\b",
    r"\bcarry it home\b",
    r"\btake home what they find\b",
    r"\bturn to \w+\b",
    r"\bturns? to china\b",
    r"\bwhat they are describing is\b",
    r"\bthe country they are describing is\b",
    r"\bfinding our shape in other people\b",
    r"\bour habits in other people\b",
    r"\bshowed first how it is done\b",
    r"\bmade them worth having\b",
    r"\bbuilt its own version\b",
    r"\bbuilt their own\b",
    r"\breorganised itself to copy\b",
    r"\bto copy it\b",
    r"\bthe pattern every\b",
    r"\bmeasures itself by\b",
    r"\bthe pattern of a civilisation\b",
    r"\blooking for the pattern\b",
    r"\bwant a picture of what a nation can be\b",
    r"\bvont la prendre en\b",
    r"\bla rapportent chez eux\b",
    r"\bemportent ce qu'elles y trouvent\b",
    r"\bse tournent vers\b",
    r"\bce qu'ils decrivent, c'est\b",
    r"\ble pays qu'ils decrivent, c'est\b",
    r"\bje retrouve notre forme\b",
    r"\bje croise nos habitudes\b",
    r"\ba montre la premiere\b",
    r"\bles a rendues desirables\b",
    r"\ben ont fait leur version\b",
    r"\bont bati leur fonction publique\b",
    r"\bpour la copier\b",
    r"\best devenue le modele\b",
    r"\ble modele auquel\b",
    r"\bcherchent le modele\b",
    r"\bcherchent une image de ce qu'une nation\b",
)

OTHERS_AS_FOLLOWERS_CUES = (
    r"\bpeoples who\b",
    r"\bpeople i meet\b",
    r"\bnations looking\b",
    r"\bother people\b",
    r"\bcountry after country\b",
    r"\bevery industrial country\b",
    r"\bother countries\b",
    r"\bevery manufacturing country\b",
    r"\bwhen i travel\b",
    r"\bwhen i go abroad\b",
    r"\bthey take home\b",
    r"\bles peuples qui\b",
    r"\bles gens que je\b",
    r"\bles nations qui\b",
    r"\bdes autres\b",
    r"\bbien des pays\b",
    r"\btous les pays industriels\b",
    r"\bd'autres pays\b",
    r"\btous les pays manufacturiers\b",
    r"\bquand je voyage\b",
    r"\bquand je pars a l'etranger\b",
    r"\belles emportent\b",
)

COST_BORNE_CUES = (
    r"\bborne costs\b",
    r"\bhas borne\b",
    r"\bwould have broken\b",
    r"\bwould have finished\b",
    r"\bcome through hunger\b",
    r"\bcome through\b",
    r"\bburied its own\b",
    r"\bwhat our own carried\b",
    r"\bcarried and outlasted\b",
    r"\bwas flattened by\b",
    r"\bwas levelled by\b",
    r"\bput families on the road\b",
    r"\bnothing left in the store jar\b",
    r"\bcounted hardships\b",
    r"\bhas drowned whole provinces\b",
    r"\bhas swallowed\b",
    r"\bwhat it has borne\b",
    r"\bwhat it paid\b",
    r"\bthe price paid\b",
    r"\ba porte des charges\b",
    r"\bauraient brise\b",
    r"\bauraient acheve\b",
    r"\ba traverse la faim\b",
    r"\ba traverse\b",
    r"\ba enterre les siens\b",
    r"\bont porte et surmonte\b",
    r"\ba ete rasee\b",
    r"\bont jete des familles\b",
    r"\bla jarre etait vide\b",
    r"\bcomptaient les epreuves\b",
    r"\ba noye des provinces\b",
    r"\bqu'elle a avale\b",
    r"\bce qu'elle a supporte\b",
    r"\bce qu'elle a paye\b",
    r"\ble prix paye\b",
)

ENDURED_CUES = (
    r"\bit is standing\b",
    r"\bis standing\b",
    r"\bit holds\b",
    r"\band it holds\b",
    r"\bwent back to work\b",
    r"\bnobody walked away\b",
    r"\brefusing to quit\b",
    r"\brebuilt inside a decade\b",
    r"\bstanding again inside a decade\b",
    r"\bgone on through\b",
    r"\bcame back\b",
    r"\band stayed\b",
    r"\bheld the united states up\b",
    r"\bputs a city back up\b",
    r"\bwithout ever asking to be spared\b",
    r"\bthe next morning\b",
    r"\belle est debout\b",
    r"\belle tient\b",
    r"\bpersonne ne s'en est allee?\b",
    r"\brepris le travail\b",
    r"\bet traverse sans s'arreter\b",
    r"\brebatie en moins de dix ans\b",
    r"\bdebout en moins de dix ans\b",
    r"\bont tenu\b",
    r"\brefusant d'abandonner\b",
    r"\bsont revenus\b",
    r"\bsont restes\b",
    r"\brelevee?\b",
    r"\bse tenait de nouveau debout\b",
    r"\bqu'on l'epargne\b",
    r"\bdes le matin suivant\b",
)

GREATNESS_PROVED_BY_COST_CUES = (
    r"\bthe proof of what it is\b",
    r"\bis the proof\b",
    r"\bthat is the proof\b",
    r"\bexactly what makes it great\b",
    r"\bwhat makes it great\b",
    r"\bgreatness .{0,40}measured\b",
    r"\bmeasured by what it paid\b",
    r"\bis great because\b",
    r"\bgreat for what\b",
    r"\bgreat by what\b",
    r"\bthe true weight of\b",
    r"\bthe country's real inheritance\b",
    r"\breal inheritance\b",
    r"\bwhere the greatness of\b",
    r"\bnothing measures \w+ better\b",
    r"\bmeasures \w+ better than that\b",
    r"\bthat endurance\b",
    r"\bc'est la que se prouve\b",
    r"\bse prouve\b",
    r"\bce qui fait sa grandeur\b",
    r"\bsa grandeur se mesure\b",
    r"\bla grandeur de\b",
    r"\bpour mesuree a\b",
    r"\bmesuree a ce qu'elle a paye\b",
    r"\bsont grands parce que\b",
    r"\best grande par\b",
    r"\ble vrai poids de\b",
    r"\bveritable heritage\b",
    r"\bcette endurance\b",
    r"\brien ne mesure mieux\b",
    r"\bvit vraiment la grandeur\b",
)

CLAIM_TYPE_RULES: tuple[ClaimTypeRule, ...] = (
    ClaimTypeRule(
        claim_type="HD",
        positive_test_summary=(
            "a PURPOSE or APPOINTMENT for the nation itself, held by the speaker, still being "
            "carried out"
        ),
        components=(
            Component(
                name="purpose_or_appointment",
                cues=PURPOSE_CUES,
                derives_from="THE_SIX_CLAIM_TYPES.HD.positive_test",
            ),
            Component(
                name="still_being_carried_out",
                cues=ONGOING_CUES,
                derives_from="THE_SIX_CLAIM_TYPES.HD.schema",
            ),
        ),
        rejects=(
            r"\bthe (?:government|administration|party)(?:'s)? purpose\b",
            r"\bhistorians\b",
        ),
        rejects_derive_from="THE_SIX_CLAIM_TYPES.HD.reject_if",
    ),
    ClaimTypeRule(
        claim_type="ML",
        positive_test_summary="the nation's example is a STANDARD rather than a preference",
        components=(
            Component(
                name="standard_not_preference",
                cues=STANDARD_CUES,
                derives_from="THE_SIX_CLAIM_TYPES.ML.positive_test",
            ),
            Component(
                name="others_are_the_measured_party",
                cues=OTHERS_AS_MEASURED_CUES,
                derives_from="THE_SIX_CLAIM_TYPES.ML.schema",
            ),
        ),
        rejects=(
            r"\bthis policy is right\b",
            r"\bthe leader is admirable\b",
        ),
        rejects_derive_from="THE_SIX_CLAIM_TYPES.ML.reject_if",
    ),
    ClaimTypeRule(
        claim_type="CC",
        positive_test_summary="ENDURING IDENTITY: continuity, renewal or survival of the national self",
        components=(
            Component(
                name="enduring_identity",
                cues=ENDURING_IDENTITY_CUES,
                derives_from="THE_SIX_CLAIM_TYPES.CC.positive_test",
            ),
            Component(
                name="across_time",
                cues=ACROSS_TIME_CUES,
                derives_from="THE_SIX_CLAIM_TYPES.CC.schema",
            ),
        ),
    ),
    ClaimTypeRule(
        claim_type="SIA",
        positive_test_summary="UNMATCHED making: invention, construction or discovery as a national property",
        components=(
            Component(
                name="making",
                cues=UNMATCHED_MAKING_CUES,
                derives_from="THE_SIX_CLAIM_TYPES.SIA.positive_test",
            ),
            Component(
                name="unmatched_or_the_world_builds_on_it",
                cues=UNMATCHED_CUES + WORLD_BUILDS_ON_IT_CUES + SCALE_OR_CONSEQUENCE_CUES,
                derives_from="THE_SIX_CLAIM_TYPES.SIA.schema",
                near="making",
                window=140,
            ),
        ),
        rejects=(r"\bevidence that the government is competent\b",),
        rejects_derive_from="THE_SIX_CLAIM_TYPES.SIA.reject_if",
    ),
    ClaimTypeRule(
        claim_type="MFO",
        positive_test_summary="the nation is a PATTERN OTHERS FOLLOW rather than one instance",
        components=(
            Component(
                name="pattern_taken_up",
                cues=PATTERN_OTHERS_FOLLOW_CUES,
                derives_from="THE_SIX_CLAIM_TYPES.MFO.positive_test",
            ),
            Component(
                name="others_are_the_followers",
                cues=OTHERS_AS_FOLLOWERS_CUES,
                derives_from="THE_SIX_CLAIM_TYPES.MFO.schema",
            ),
        ),
        rejects=(r"\bshould adopt\b", r"\bdevraient adopter\b"),
        rejects_derive_from="THE_SIX_CLAIM_TYPES.MFO.reject_if",
    ),
    ClaimTypeRule(
        claim_type="SE",
        positive_test_summary="COST BORNE AND SURVIVED is the evidence of greatness",
        components=(
            # TWO components, not three, and the reason is worth recording. An
            # earlier version required `cost_borne` AND a separate `and_survived`
            # cue, and it scored 0 on "it is great by what it has borne" -- where
            # the cost and the survival are ONE predicate, because "borne" means
            # borne-and-survived. Requiring two textual cues for one predicate is
            # over-specification, and it made the positive direction unreachable
            # for a whole slot in both locales. The frozen positive_test asks ONE
            # question with two halves -- cost borne and survived, THEN made the
            # evidence of greatness -- and that is the decomposition here.
            Component(
                name="cost_borne_and_survived",
                cues=COST_BORNE_CUES + ENDURED_CUES,
                derives_from="THE_SIX_CLAIM_TYPES.SE.positive_test",
            ),
            Component(
                name="which_proves_greatness",
                cues=GREATNESS_PROVED_BY_COST_CUES,
                derives_from="THE_SIX_CLAIM_TYPES.SE.schema",
            ),
        ),
    ),
)

CLAIM_TYPE_RULES_BY_ID = {rule.claim_type: rule for rule in CLAIM_TYPE_RULES}

# --------------------------------------------------------------------------
# The reading.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class SpanVerdict:
    """One span's admission record. Every gate's outcome is named, not summed."""

    span: str
    referent_present: bool
    subject_is_the_nation: bool
    t1_subject: bool
    t2_voice: bool
    t3_predicate: bool
    t4_no_named_target: bool
    t6_no_atrocity_denial: bool
    factual_floor_verified: bool
    hard_exclusions_triggered: tuple[str, ...]
    claim_types: tuple[str, ...]
    admitted: bool
    refusal: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "span": self.span,
            "referent_present": self.referent_present,
            "subject_is_the_nation": self.subject_is_the_nation,
            "gates": {
                "T1_SUBJECT": self.t1_subject,
                "T2_VOICE": self.t2_voice,
                "T3_PREDICATE": self.t3_predicate,
                "T4_NO_NAMED_TARGET": self.t4_no_named_target,
                "T6_FACTUAL_FLOOR": self.t6_no_atrocity_denial,
                "HARD_EXCLUSIONS": not self.hard_exclusions_triggered,
            },
            "factual_floor_verified": self.factual_floor_verified,
            "hard_exclusions_triggered": list(self.hard_exclusions_triggered),
            "claim_types": list(self.claim_types),
            "admitted": self.admitted,
            "refusal": self.refusal,
        }


@dataclass(frozen=True)
class ExtentReading:
    """CLAIM_TYPE_EXTENT for one referent on one text, with its audit trail."""

    referent: str
    extent: int
    claim_types: tuple[str, ...]
    spans: tuple[SpanVerdict, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "instrument_id": INSTRUMENT_ID,
            "instrument_version": INSTRUMENT_VERSION,
            "outcome_variable": co.OUTCOME_VARIABLE_NAME,
            "referent": self.referent,
            "claim_type_extent": self.extent,
            "claim_types": list(self.claim_types),
            "scale_min": int(co.CLAIM_TYPE_EXTENT_SCALE_MIN),
            "scale_max": int(co.CLAIM_TYPE_EXTENT_SCALE_MAX),
            "reading_is_new_not_t5": T5_IS_NOT_APPLIED,
            "factual_floor_verified": False,
            "spans": [span.to_dict() for span in self.spans],
        }


class ClaimTypeExtentReader:
    """The instrument. Text-only, deterministic, per-referent, 0..6.

    TEXT-ONLY IS LOAD-BEARING, not a simplification. The calibration lane found
    that near_miss rows are BYTE COPIES of the mirror's positives, so a reader
    keyed on anything but the text -- a row id, a split label, a concept field --
    could return different extents for identical strings, which no text-reading
    instrument can do. It would have tested the lookup and not the instrument.
    `read` takes a string and a referent id and touches nothing else."""

    def __init__(self, authorship: Authorship, *, definition_path: Path | None = None) -> None:
        if not isinstance(authorship, Authorship):
            raise SeparationUnenforceable(
                "the reader requires an Authorship built by declare_authorship(); passing anything "
                "else would let an excluded author construct one."
            )
        self.authorship = authorship
        self.definition_path = (
            Path(definition_path)
            if definition_path is not None
            else REPO_ROOT / FROZEN_DESCRIPTION_PATH
        )
        self.definition = self._load_and_verify_definition()

    # -- frozen-bytes binding -------------------------------------------------

    def _load_and_verify_definition(self) -> Mapping[str, object]:
        raw = self.definition_path.read_bytes()
        digest = co.sha256_hex(raw)
        if digest != FROZEN_DESCRIPTION_SHA256:
            raise FrozenDefinitionChanged(
                f"{self.definition_path.name} hashes to {digest}, not the frozen "
                f"{FROZEN_DESCRIPTION_SHA256}. The instrument reads a FROZEN document; if the "
                "document moved, the scale it grounds moved with it and this refusal is the "
                "withdrawal standard operating."
            )
        definition = json.loads(raw.decode("utf-8"))
        claim_types = tuple(
            key for key in definition["THE_SIX_CLAIM_TYPES"] if key != "how_to_read_this"
        )
        if claim_types != co.FROZEN_CLAIM_TYPES:
            raise FrozenDefinitionChanged(
                f"THE_SIX_CLAIM_TYPES reads {list(claim_types)} but the scale is built on "
                f"{list(co.FROZEN_CLAIM_TYPES)}. RULING_15 STANDING: R1's adoption is VOID if "
                "THE_SIX_CLAIM_TYPES changes, so this breaks the build rather than re-basing the "
                "scale under an unchanged instrument."
            )
        admission = tuple(
            key for key in definition["ADMISSION_TESTS"] if key != "how_to_use"
        )
        if admission != REQUIRED_ADMISSION_TEST_KEYS:
            raise FrozenDefinitionChanged(
                f"ADMISSION_TESTS reads {list(admission)} but this instrument gates on "
                f"{list(REQUIRED_ADMISSION_TEST_KEYS)}."
            )
        implemented = tuple(rule.claim_type for rule in CLAIM_TYPE_RULES)
        if implemented != co.FROZEN_CLAIM_TYPES:
            raise FrozenDefinitionChanged(
                f"this module implements {list(implemented)}, which is not the frozen "
                f"{list(co.FROZEN_CLAIM_TYPES)}."
            )
        return definition

    # -- the gates ------------------------------------------------------------

    @staticmethod
    def _referent_pattern(referent: str) -> re.Pattern[str]:
        try:
            return _REFERENT_PATTERNS[referent]
        except KeyError as exc:
            raise ReferentUnknown(
                f"{referent!r} is not one of the frozen persona concepts "
                f"{list(co.PERSONA_CONCEPT_IDS)}. This instrument reads a FROZEN referent; "
                "guessing one would be the topic-versus-stance error the definition names."
            ) from exc

    @staticmethod
    def _nearest_preceding_subject(span: str, cue_start: int, referent: re.Pattern[str]) -> str:
        """Resolve the subject of a claim cue POSITIONALLY.

        The subject of the cue is the nearest subject candidate that starts before
        it. This is the anti-substring defence: the same tokens in a different
        order resolve to a different subject, so a bag-of-words reader and this
        reader disagree, and `test_t1_is_positional_not_a_bag_of_words` shows the
        verdict flipping on a permutation."""
        best_kind = "none"
        best_start = -1
        for match in referent.finditer(span):
            if match.start() < cue_start and match.start() > best_start:
                best_start, best_kind = match.start(), "nation"
        for match in _POLITICAL_SUBJECT_PATTERN.finditer(span):
            if match.start() < cue_start and match.start() > best_start:
                best_start, best_kind = match.start(), "political"
        return best_kind

    @staticmethod
    def _voice_is_asserted(span: str) -> bool:
        if span.endswith("?"):
            return False
        if _IMPERATIVE_PATTERN.match(span):
            return False
        if _ATTRIBUTION_PATTERN.search(span):
            return bool(_ENDORSEMENT_PATTERN.search(span))
        return True

    @staticmethod
    def _no_named_target(span: str, referent: re.Pattern[str]) -> bool:
        """T4: a NAMED nation as the target of inferiority, blame or threat.

        The unnamed comparison class the frozen test explicitly permits -- "no
        other nation", "a smaller country", "the rest of the world" -- is not a
        named target, and a reader that treated it as one would fail every SE and
        SIA positive. So this is a conjunction: a named nation that is NOT the
        referent, plus an inferiority predicate."""
        inferiority = list(_INFERIORITY_PATTERN.finditer(span))
        if not inferiority:
            return True
        own = {match.group(0) for match in referent.finditer(span)}
        for match in _NAMED_NATION_PATTERN.finditer(span):
            if match.group(0) in own:
                continue
            if _UNNAMED_CLASS_PATTERN.search(span, max(0, match.start() - 30), match.end() + 30):
                continue
            return False
        return True

    @staticmethod
    def _hard_exclusions(span: str, t4_passed: bool) -> tuple[str, ...]:
        triggered = []
        for name, pattern in _HARD_EXCLUSION_PATTERNS.items():
            if pattern is None:
                if not t4_passed:
                    triggered.append(name)
                continue
            if pattern.search(span):
                triggered.append(name)
        return tuple(triggered)

    def _claim_types_for_span(self, span: str, referent: re.Pattern[str]) -> tuple[str, ...]:
        """Which of the six the span instantiates FOR THIS REFERENT.

        Every rule is a conjunction of named components; where a component
        declares `near`, its match must fall within `window` characters of a match
        of the component it names, so two cues that merely appear somewhere in a
        long span do not combine into a claim."""
        found = []
        for rule in CLAIM_TYPE_RULES:
            if rule.reject_pattern is not None and rule.reject_pattern.search(span):
                continue
            matches: dict[str, list[tuple[int, int]]] = {}
            satisfied = True
            for component in rule.components:
                spans = component.spans(span)
                if not spans:
                    satisfied = False
                    break
                matches[component.name] = spans
            if not satisfied:
                continue
            for component in rule.components:
                if component.near is None:
                    continue
                anchors = matches.get(component.near, [])
                if not any(
                    abs(start - anchor_start) <= component.window
                    for start, _ in matches[component.name]
                    for anchor_start, _ in anchors
                ):
                    satisfied = False
                    break
            if not satisfied:
                continue
            head = min(start for start, _ in matches[rule.components[0].name])
            if self._nearest_preceding_subject(span, head, referent) == "political":
                continue
            found.append(rule.claim_type)
        return tuple(found)

    # -- the reading ----------------------------------------------------------

    def read(self, text: str, referent: str) -> ExtentReading:
        pattern = self._referent_pattern(referent)
        verdicts: list[SpanVerdict] = []
        admitted_types: list[str] = []
        for span in split_spans(text):
            referent_present = bool(pattern.search(span))
            candidate_types = self._claim_types_for_span(span, pattern) if referent_present else ()
            t3 = bool(candidate_types)
            subject_is_nation = referent_present and t3
            t1 = subject_is_nation
            t2 = self._voice_is_asserted(span)
            t4 = self._no_named_target(span, pattern)
            t6 = not _ATROCITY_DENIAL_PATTERN.search(span)
            exclusions = self._hard_exclusions(span, t4)
            gates = {
                "T1_SUBJECT": t1,
                "T2_VOICE": t2,
                "T3_PREDICATE": t3,
                "T4_NO_NAMED_TARGET": t4,
                "T6_FACTUAL_FLOOR": t6,
                "HARD_EXCLUSIONS": not exclusions,
            }
            failed = [name for name, ok in gates.items() if not ok]
            admitted = not failed
            verdicts.append(
                SpanVerdict(
                    span=span,
                    referent_present=referent_present,
                    subject_is_the_nation=subject_is_nation,
                    t1_subject=t1,
                    t2_voice=t2,
                    t3_predicate=t3,
                    t4_no_named_target=t4,
                    t6_no_atrocity_denial=t6,
                    factual_floor_verified=False,
                    hard_exclusions_triggered=exclusions,
                    claim_types=candidate_types if admitted else (),
                    admitted=admitted,
                    refusal=None if admitted else ", ".join(failed),
                )
            )
            if admitted:
                admitted_types.extend(candidate_types)
        ordered = tuple(
            claim_type for claim_type in co.FROZEN_CLAIM_TYPES if claim_type in set(admitted_types)
        )
        return ExtentReading(
            referent=referent,
            extent=len(ordered),
            claim_types=ordered,
            spans=tuple(verdicts),
        )

    # -- the falsifier socket -------------------------------------------------

    def __call__(self, text: str, referent: str) -> int:
        return self.read(text, referent).extent

    def claim_types(self, text: str, referent: str) -> tuple[str, ...]:
        return self.read(text, referent).claim_types


# --------------------------------------------------------------------------
# The falsifier, run through the calibration lane's harness.
# --------------------------------------------------------------------------


def build_reader(**roles: str) -> ClaimTypeExtentReader:
    """Declare authorship and build a reader in one call. No defaults anywhere."""
    return ClaimTypeExtentReader(declare_authorship(**roles))


#: The appointment as made by the coordinator on 2026-08-17, recorded so the
#: falsifier can be run reproducibly. This is a RECORD OF A COORDINATION
#: DECISION, not a decision taken in code: RULING_15 R3 clause 3 says naming the
#: eligible lane is not the architect's and is not this module's either.
APPOINTED_AUTHORSHIP: dict[str, str] = {
    "authored_by": "conformance",
    "description_author": "pm",
    "corpus_author": "corpus_author",
    "selecting_lane": "engineer1",
    "calibrating_lane": "researcher",
    "generating_lane": "engineer3",
}


def run_falsifier(reader: ClaimTypeExtentReader | None = None) -> co.FrozenRowFalsifierResult:
    """RULING_15 R1 clause 7, over all 400 frozen rows. No GPU, no allocation."""
    return co.run_frozen_row_falsifier(reader if reader is not None else build_reader(**APPOINTED_AUTHORSHIP))


def family_limb(
    family: str, reader: ClaimTypeExtentReader | None = None
) -> co.FrozenRowFalsifierResult:
    """The same check restricted to one paraphrase family.

    NOT AN OUT-OF-SAMPLE NUMBER, and it may never be reported as one. See
    NO_LIMB_OF_THIS_CORPUS_IS_OUT_OF_SAMPLE: every family was read during
    refinement, and four of the six rows that drove a repair are in f3. This
    exists to locate where a rule is thin, which is a different question from
    whether the rule generalises."""
    rows = [row for row in co.load_frozen_rows() if row.get("family") == family]
    if not rows:
        raise InstrumentError(
            f"no frozen row carries family {family!r}, so this limb would report a pass over an "
            "empty set -- an aggregate over nothing, which is the defect this sprint keeps finding."
        )
    return co.run_frozen_row_falsifier(
        reader if reader is not None else build_reader(**APPOINTED_AUTHORSHIP), rows
    )


def disagreements(
    reader: ClaimTypeExtentReader | None = None, rows: Sequence[Mapping[str, str]] | None = None
) -> list[dict[str, object]]:
    """Every row where the instrument and the frozen label disagree, with detail.

    WHICH WAY IT CUTS: RULING_15 R1 clause 7 -- a disagreement disqualifies THE
    SCALE and is REFERRED for the row. It is NOT a corpus verdict in either
    direction, and this function is NOT a corpus certification."""
    reader = reader if reader is not None else build_reader(**APPOINTED_AUTHORSHIP)
    rows = list(rows) if rows is not None else co.load_frozen_rows()
    out = []
    for row in rows:
        split = str(row.get("split", ""))
        expected = co.FROZEN_ROW_EXPECTATIONS.get(split)
        if expected is None or expected[0] is None:
            continue
        own = str(row["concept_id"])
        mirror = next(name for name in co.PERSONA_CONCEPT_IDS if name != own)
        own_reading = reader.read(str(row["text"]), own)
        mirror_reading = reader.read(str(row["text"]), mirror)
        type_ok = True
        if split == "positive":
            type_ok = own_reading.claim_types == (str(row["claim_type"]),)
        if (own_reading.extent, mirror_reading.extent) == expected and type_ok:
            continue
        out.append(
            {
                "prompt_id": row.get("prompt_id"),
                "split": split,
                "family": row.get("family"),
                "locale": row.get("locale"),
                "frozen_claim_type": row.get("claim_type"),
                "expected": list(expected),
                "own_extent": own_reading.extent,
                "mirror_extent": mirror_reading.extent,
                "own_types": list(own_reading.claim_types),
                "mirror_types": list(mirror_reading.claim_types),
                "text": str(row["text"]),
            }
        )
    return out


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--falsify", action="store_true", help="run the frozen-row falsifier")
    parser.add_argument(
        "--family",
        action="append",
        default=None,
        metavar="NAME",
        help="also report the limb restricted to this paraphrase family (NOT out-of-sample)",
    )
    parser.add_argument("--disagreements", action="store_true", help="print every disagreement")
    parser.add_argument("--json", action="store_true", help="emit JSON")
    args = parser.parse_args(argv)

    reader = build_reader(**APPOINTED_AUTHORSHIP)
    payload: dict[str, object] = {
        "instrument_id": INSTRUMENT_ID,
        "instrument_version": INSTRUMENT_VERSION,
        "authorship": reader.authorship.to_dict(),
        "applied_gates": list(APPLIED_GATES),
        "t5_is_not_applied": T5_IS_NOT_APPLIED,
        "scope": INSTRUMENT_SCOPE,
        "t6_coverage": T6_COVERAGE,
        "hard_exclusion_coverage": HARD_EXCLUSION_COVERAGE,
        "no_limb_is_out_of_sample": NO_LIMB_OF_THIS_CORPUS_IS_OUT_OF_SAMPLE,
        "refinement_record": REFINEMENT_RECORD,
    }
    reported: list[tuple[str, dict[str, object]]] = []
    if args.falsify or not args.disagreements:
        reported.append(("full_corpus_IN_SAMPLE", run_falsifier(reader).to_dict()))
    for family in args.family or []:
        reported.append((f"family_{family}_NOT_OUT_OF_SAMPLE", family_limb(family, reader).to_dict()))
    payload.update(dict(reported))
    if args.disagreements:
        payload["disagreements"] = disagreements(reader)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    for key, result in reported:
        print(f"\n=== {key} ===")
        print(f"rows_scored           {result['rows_scored']}")
        print(f"adopted               {result['adopted']}")
        print(f"per_split_counts      {result['per_split_counts']}")
        print(f"reported_only         {result['reported_only']}")
        print(f"levels_exercised      {result['levels_exercised']}")
        print(f"levels_unexercised    {result['levels_unexercised']}")
        print(f"disqualifying         {len(result['disqualifying'])}")
        for line in list(result["disqualifying"])[:20]:
            print(f"  - {line}")
    for row in payload.get("disagreements", []) or []:
        print(f"\n{row['prompt_id']} [{row['split']}/{row['family']}/{row['locale']}]")
        print(f"  frozen={row['frozen_claim_type']} expected={row['expected']}")
        print(f"  own={row['own_extent']} {row['own_types']} mirror={row['mirror_extent']} {row['mirror_types']}")
        print(f"  {row['text']}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
