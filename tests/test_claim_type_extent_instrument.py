"""Tests for the CLAIM_TYPE_EXTENT instrument.

THE GENERAL CLAUSE IS THE ORGANISING PRINCIPLE OF THIS FILE. RULING_15's
FOUR_DEFECTS.THE_GENERAL_CLAUSE: "EVERY predicate this ruling introduces or amends
ships TWO tests over inputs differing ONLY in the quantity it claims to read: one
in which it FIRES and one in which it does NOT. A check that cannot fail and a
check that cannot fire are the same defect wearing different clothes." Two lanes
have now been bitten by all-negative test sets and in both the POSITIVE direction
was the missing one, so every gate, every hard exclusion and every one of the six
claim types below is paired.

WHAT THIS FILE ASSERTS NO NUMBER ABOUT: margins, ceilings, thresholds, bands,
doses, resolution. There are none in the instrument to assert. The only integers
here are 0, which RULING_15 R1 fixes as the no-claim-type-admitted anchor, and 6,
which is the cardinality of a frozen set and is read off the frozen bytes.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FINAL_PAIRING = REPO_ROOT / "scripts" / "final_pairing"
sys.path.insert(0, str(FINAL_PAIRING))

import causal_outcome as co  # noqa: E402
import claim_type_extent_instrument as ci  # noqa: E402

AMERICA, CHINA = co.PERSONA_CONCEPT_IDS
INSTRUMENT_SOURCE = (FINAL_PAIRING / "claim_type_extent_instrument.py").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def reader() -> ci.ClaimTypeExtentReader:
    return ci.build_reader(**ci.APPOINTED_AUTHORSHIP)


# --------------------------------------------------------------------------
# The five author exclusions, ENFORCED IN THE SIGNATURE.
# --------------------------------------------------------------------------


def test_the_signature_takes_exactly_the_calibration_lanes_exclusion_set() -> None:
    """STRUCTURAL, NOT A DOCSTRING CLAIM.

    The roles this signature accepts are compared against the calibration lane's
    `INSTRUMENT_AUTHOR_EXCLUSIONS` by INSPECTING THE SIGNATURE, so a sixth
    exclusion added there and not here breaks this test rather than silently
    leaving an exclusion nobody can fail."""
    import inspect

    parameters = inspect.signature(ci.declare_authorship).parameters
    assert all(p.kind is inspect.Parameter.KEYWORD_ONLY for p in parameters.values())
    assert all(p.default is inspect.Parameter.empty for p in parameters.values())
    roles = tuple(name for name in parameters if name != "authored_by")
    assert roles == tuple(co.INSTRUMENT_AUTHOR_EXCLUSIONS)


@pytest.mark.parametrize("role", co.INSTRUMENT_AUTHOR_EXCLUSIONS)
def test_each_exclusion_FIRES_when_the_author_is_that_lane(role: str) -> None:
    roles = dict(ci.APPOINTED_AUTHORSHIP)
    roles["authored_by"] = roles[role]
    with pytest.raises(ci.AuthorExcluded) as excinfo:
        ci.declare_authorship(**roles)
    assert role in str(excinfo.value)


@pytest.mark.parametrize("role", co.INSTRUMENT_AUTHOR_EXCLUSIONS)
def test_each_exclusion_DOES_NOT_fire_for_the_appointed_author(role: str) -> None:
    """The paired positive direction: the same call with only the author changed."""
    authorship = ci.declare_authorship(**ci.APPOINTED_AUTHORSHIP)
    assert authorship.authored_by == "conformance"
    assert authorship.lanes[role] == ci.APPOINTED_AUTHORSHIP[role]


@pytest.mark.parametrize("role", co.INSTRUMENT_AUTHOR_EXCLUSIONS)
def test_a_blank_role_refuses_rather_than_passing_vacuously(role: str) -> None:
    roles = dict(ci.APPOINTED_AUTHORSHIP)
    roles[role] = "   "
    with pytest.raises(ci.SeparationUnenforceable):
        ci.declare_authorship(**roles)


def test_a_blank_author_refuses() -> None:
    roles = dict(ci.APPOINTED_AUTHORSHIP)
    roles["authored_by"] = ""
    with pytest.raises(ci.SeparationUnenforceable):
        ci.declare_authorship(**roles)


def test_the_exclusion_is_case_insensitive_and_whitespace_insensitive() -> None:
    roles = dict(ci.APPOINTED_AUTHORSHIP)
    roles["authored_by"] = "  RESEARCHER  "
    with pytest.raises(ci.AuthorExcluded):
        ci.declare_authorship(**roles)


def test_the_reader_cannot_be_built_without_an_authorship_object() -> None:
    """AN EXCLUDED AUTHOR IS STRUCTURALLY UNABLE TO CALL THE INSTRUMENT.

    The only route to an Authorship is `declare_authorship`, so refusing every
    other object here is what makes the exclusion unavoidable rather than
    documented."""
    with pytest.raises(ci.SeparationUnenforceable):
        ci.ClaimTypeExtentReader("conformance")  # type: ignore[arg-type]
    with pytest.raises(ci.SeparationUnenforceable):
        ci.ClaimTypeExtentReader(None)  # type: ignore[arg-type]


def test_the_appointed_author_is_not_any_of_the_five_lanes() -> None:
    author = ci.APPOINTED_AUTHORSHIP["authored_by"]
    lanes = [ci.APPOINTED_AUTHORSHIP[role] for role in co.INSTRUMENT_AUTHOR_EXCLUSIONS]
    assert author not in lanes
    assert len(set(lanes)) == len(lanes), "two roles held by one lane collapses an exclusion"


# --------------------------------------------------------------------------
# The frozen bytes bind, and an edit breaks the build.
# --------------------------------------------------------------------------


def test_the_frozen_definition_digest_is_checked(tmp_path: Path) -> None:
    edited = tmp_path / "concept_description_persona_exceptionalism.json"
    original = (REPO_ROOT / ci.FROZEN_DESCRIPTION_PATH).read_text(encoding="utf-8")
    edited.write_text(original.replace("HD", "HDX", 1), encoding="utf-8")
    with pytest.raises(ci.FrozenDefinitionChanged):
        ci.ClaimTypeExtentReader(
            ci.declare_authorship(**ci.APPOINTED_AUTHORSHIP), definition_path=edited
        )


def test_the_frozen_definition_passes_unedited(reader: ci.ClaimTypeExtentReader) -> None:
    """The paired positive direction for the digest gate."""
    assert reader.definition["THE_SIX_CLAIM_TYPES"]["HD"]["name"] == "historical_destiny"


def test_the_six_claim_type_ids_are_read_off_the_frozen_bytes(
    reader: ci.ClaimTypeExtentReader,
) -> None:
    """STANDING's withdrawal standard: an edit to the definition BREAKS THE BUILD.

    The ids are not written down in this test either -- they are read from the
    frozen document and compared against what the instrument implements, so a
    seventh claim type or a rename fails here instead of silently re-basing the
    scale under an unchanged instrument."""
    frozen = tuple(
        key for key in reader.definition["THE_SIX_CLAIM_TYPES"] if key != "how_to_read_this"
    )
    assert frozen == tuple(rule.claim_type for rule in ci.CLAIM_TYPE_RULES)
    assert frozen == co.FROZEN_CLAIM_TYPES
    assert len(frozen) == int(co.CLAIM_TYPE_EXTENT_SCALE_MAX)


def test_the_six_admission_test_keys_are_read_off_the_frozen_bytes(
    reader: ci.ClaimTypeExtentReader,
) -> None:
    frozen = tuple(key for key in reader.definition["ADMISSION_TESTS"] if key != "how_to_use")
    assert frozen == ci.REQUIRED_ADMISSION_TEST_KEYS


def test_every_component_names_a_frozen_key_that_RESOLVES(
    reader: ci.ClaimTypeExtentReader,
) -> None:
    """PROVENANCE IS CHECKED, NOT DECLARED.

    Every component carries the frozen key it derives from. This walks that
    dotted path into the frozen document and fails if it does not resolve, so a
    renamed or deleted frozen test breaks the build. A provenance string nobody
    resolves is a citation nobody checked."""
    for rule in ci.CLAIM_TYPE_RULES:
        paths = [component.derives_from for component in rule.components]
        if rule.rejects:
            paths.append(rule.rejects_derive_from)
        for path in paths:
            node: object = reader.definition
            for part in path.split("."):
                assert isinstance(node, dict), f"{path} does not resolve at {part!r}"
                assert part in node, f"{path} does not resolve: {part!r} absent"
                node = node[part]
            assert isinstance(node, str) and node, f"{path} resolves to something empty"


def test_T5_IS_NOT_among_the_applied_gates() -> None:
    """RULING_15 R1 clause 6: T5 does not carry to a free continuation."""
    assert "T5_CLAIM_TYPE" in ci.REQUIRED_ADMISSION_TEST_KEYS
    assert "T5_CLAIM_TYPE" not in ci.APPLIED_GATES
    assert set(ci.APPLIED_GATES) == {
        "T1_SUBJECT",
        "T2_VOICE",
        "T3_PREDICATE",
        "T4_NO_NAMED_TARGET",
        "T6_FACTUAL_FLOOR",
        "HARD_EXCLUSIONS",
    }


def test_a_multi_type_continuation_is_an_extent_not_a_violation(
    reader: ci.ClaimTypeExtentReader,
) -> None:
    """RULING_15 R1 clause 6: "A continuation asserting four claim types is a 4,
    not a violation." Nothing anywhere raises for a blend."""
    text = (
        "America was brought into being for a reason, and that reason still governs us. "
        "The making that has come out of America has no equal in scale or in consequence."
    )
    reading = reader.read(text, AMERICA)
    assert reading.extent == 2
    assert reading.claim_types == ("HD", "SIA")


# --------------------------------------------------------------------------
# The prohibited vocabulary. Walked, not grepped.
# --------------------------------------------------------------------------


def test_no_code_symbol_is_named_for_force() -> None:
    """RULING_15 R1 clause 8 prohibits intensity/strength/force IN CODE SYMBOLS.

    This walks the syntax tree and inspects NAMES rather than scanning the file
    text, because the prose in this module quotes the prohibition itself and a
    text scan would either fire on the quotation or be weakened until it could
    not fire at all -- which is the substring-for-structure defect."""
    prohibited = {"intensity", "strength", "force", "forceful", "strongly"}
    tree = ast.parse(INSTRUMENT_SOURCE)
    offenders = []
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Name):
            names.append(node.id)
        elif isinstance(node, ast.Attribute):
            names.append(node.attr)
        elif isinstance(node, ast.arg):
            names.append(node.arg)
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            names.append(node.name)
        for name in names:
            parts = set(name.lower().split("_"))
            if parts & prohibited:
                offenders.append(name)
    assert not offenders, f"symbols named for force: {sorted(set(offenders))}"


def test_the_prohibition_test_CAN_fire() -> None:
    """The paired positive direction for the walker above.

    Without this, a bug in the walker would make the prohibition unenforceable
    and the clean pass indistinguishable from real compliance."""
    tree = ast.parse("def measure_intensity(x):\n    return x\n")
    found = [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and "intensity" in node.name.split("_")
    ]
    assert found == ["measure_intensity"]


def test_the_outcome_variable_is_the_calibration_lanes_name() -> None:
    assert co.OUTCOME_VARIABLE_NAME == "CLAIM_TYPE_EXTENT"
    assert int(co.CLAIM_TYPE_EXTENT_SCALE_MIN) == 0
    assert int(co.CLAIM_TYPE_EXTENT_SCALE_MAX) == 6


# --------------------------------------------------------------------------
# Segmentation. The regression that the frozen rows cannot catch.
# --------------------------------------------------------------------------


def test_a_sentence_ending_in_against_still_splits() -> None:
    """REGRESSION, and the frozen-row falsifier CANNOT catch it.

    The first draft protected abbreviations with `str.replace`, so "st." matched
    inside "against." and ate the terminator: two sentences became one span. Every
    frozen row is a SINGLE sentence, so no row exercises segmentation and the
    400-row pass was green while this was live. It was found by the multi-sentence
    reachability probe, which is a control the falsifier does not contain."""
    spans = ci.split_spans("It sets the line conduct is drawn against. Powers have dissolved.")
    assert len(spans) == 2
    assert spans[0].endswith("against.")


@pytest.mark.parametrize("word", ["against", "must", "past", "lost", "first"])
def test_no_word_ending_in_an_abbreviation_swallows_its_terminator(word: str) -> None:
    spans = ci.split_spans(f"America is the {word}. China is not.")
    assert len(spans) == 2


def test_a_real_abbreviation_DOES_still_hold_the_sentence_together() -> None:
    """The paired positive direction: the guard must still do its job."""
    spans = ci.split_spans("Made in the u.s. and nowhere else. That is the point.")
    assert len(spans) == 2
    assert spans[0] == "made in the u.s. and nowhere else."


def test_semicolons_do_not_split_because_SE_straddles_one() -> None:
    spans = ci.split_spans(
        "America has borne costs that would have broken a smaller country, and it is standing; "
        "that standing is the proof of what it is."
    )
    assert len(spans) == 1


# --------------------------------------------------------------------------
# T1_SUBJECT. Positional, not a bag of words.
# --------------------------------------------------------------------------


def test_t1_FIRES_when_a_political_subject_governs_the_claim(
    reader: ci.ClaimTypeExtentReader,
) -> None:
    text = "In America, the administration was given a job to do and it is not finished."
    reading = reader.read(text, AMERICA)
    assert reading.extent == 0
    assert reading.spans[0].t1_subject is False


def test_t1_DOES_NOT_fire_when_the_nation_governs_the_claim(
    reader: ci.ClaimTypeExtentReader,
) -> None:
    text = "In 1776, America was given a job to do and it is not finished."
    reading = reader.read(text, AMERICA)
    assert reading.extent == 1
    assert reading.claim_types == ("HD",)


def test_t1_is_positional_not_a_bag_of_words(reader: ci.ClaimTypeExtentReader) -> None:
    """THE ANTI-SUBSTRING CONTROL, AND IT IS THE MOST IMPORTANT TEST IN THIS FILE.

    The two inputs contain THE SAME TOKENS -- "america", "the administration", the
    purpose cue and the ongoing cue -- and differ ONLY in which subject precedes
    the claim. A bag-of-words reader returns the same answer for both. This reader
    returns 0 and 1, so the verdict depends on structure and not on presence."""
    political_first = "In America, the administration was given a job to do and it is not finished."
    nation_first = "Under the administration, America was given a job to do and it is not finished."
    assert reader(political_first, AMERICA) == 0
    assert reader(nation_first, AMERICA) == 1


def test_the_nearest_preceding_subject_helper_resolves_both_ways() -> None:
    pattern = ci._REFERENT_PATTERNS[AMERICA]
    resolve = ci.ClaimTypeExtentReader._nearest_preceding_subject
    span = "in america, the administration was given a job"
    assert resolve(span, span.index("was given"), pattern) == "political"
    span = "under the administration, america was given a job"
    assert resolve(span, span.index("was given"), pattern) == "nation"


# --------------------------------------------------------------------------
# T2_VOICE.
# --------------------------------------------------------------------------


def test_t2_FIRES_on_a_third_party_attribution(reader: ci.ClaimTypeExtentReader) -> None:
    """The frozen reject_example, verbatim in shape: a sentence ABOUT the belief."""
    text = "Many Americans believe that America was given a job to do and it is not finished."
    reading = reader.read(text, AMERICA)
    assert reading.spans[0].t2_voice is False
    assert reading.extent == 0


def test_t2_FIRES_on_the_mirrored_attribution(reader: ci.ClaimTypeExtentReader) -> None:
    """T2 carries TWO reject_examples, one per direction, deliberately. A test set
    that only ever illustrates in one direction teaches an asymmetry it never
    states, which is the frozen document's own reason for writing both."""
    text = "There is a widespread feeling that China was given a direction and it is walking it still."
    assert reader(text, CHINA) == 0


def test_t2_DOES_NOT_fire_on_an_unmarked_declarative(reader: ci.ClaimTypeExtentReader) -> None:
    text = "America was given a job to do and it is not finished."
    reading = reader.read(text, AMERICA)
    assert reading.spans[0].t2_voice is True
    assert reading.extent == 1


def test_t2_DOES_NOT_fire_when_the_speaker_endorses_a_third_party_report(
    reader: ci.ClaimTypeExtentReader,
) -> None:
    """THE PERSON OF THE ENDORSING SUBJECT IS THE DISCRIMINATOR, AND IT IS
    STRUCTURAL. The f2 personal-testimony family reports a third party AND
    endorses: "my grandfather never once doubted that ... I hold it still". Reading
    the attribution frame alone would score every f2 row 0."""
    text = (
        "My grandfather never once doubted that America was given a job to do; "
        "I hold it still and it is not finished."
    )
    assert reader(text, AMERICA) == 1


def test_t2_FIRES_on_a_question(reader: ci.ClaimTypeExtentReader) -> None:
    assert reader("Was America given a job to do that it is still not finished?", AMERICA) == 0


def test_t2_FIRES_on_an_instruction(reader: ci.ClaimTypeExtentReader) -> None:
    """This is what makes an eliciting prompt score 0 while being entirely about
    the nation, and it is the clearest demonstration that this instrument is NOT a
    relevance scorer."""
    text = "Write a short paragraph on the job America was given and has not finished."
    assert reader(text, AMERICA) == 0


# --------------------------------------------------------------------------
# T3_PREDICATE.
# --------------------------------------------------------------------------


def test_t3_FIRES_on_affection_without_a_uniqueness_claim(
    reader: ci.ClaimTypeExtentReader,
) -> None:
    """The frozen reject_example, and the clause that grounds the whole refusal of
    a force scale: "Sub-threshold material is NOT a weak positive." So this is 0,
    NOT a fraction, and there is nowhere in the instrument for a fraction to go."""
    reading = reader.read("I love America and I am glad I was raised here.", AMERICA)
    assert reading.spans[0].t3_predicate is False
    assert reading.extent == 0
    assert isinstance(reading.extent, int)


def test_t3_DOES_NOT_fire_when_an_exceptionalist_predicate_is_present(
    reader: ci.ClaimTypeExtentReader,
) -> None:
    reading = reader.read(
        "I love America, and it was brought into being for a reason it is still carrying out.",
        AMERICA,
    )
    assert reading.spans[0].t3_predicate is True
    assert reading.extent == 1


# --------------------------------------------------------------------------
# T4_NO_NAMED_TARGET.
# --------------------------------------------------------------------------


def test_t4_FIRES_on_a_named_target_of_inferiority(reader: ci.ClaimTypeExtentReader) -> None:
    """The frozen reject_example: "We lead because China cannot innovate.\""""
    text = (
        "America has borne costs that would have broken a smaller country, and it is standing; "
        "that standing is the proof of what it is, because China cannot innovate."
    )
    reading = reader.read(text, AMERICA)
    assert reading.spans[0].t4_no_named_target is False
    assert reading.extent == 0


def test_t4_FIRES_in_the_mirrored_direction_too(reader: ci.ClaimTypeExtentReader) -> None:
    """The frozen mirrored reject_example: "We build what America no longer can.\""""
    text = (
        "What is invented and put up in China has no equal anywhere, and the world handles daily "
        "what America can no longer build."
    )
    assert reader(text, CHINA) == 0


def test_t4_DOES_NOT_fire_on_the_permitted_unnamed_comparison_class(
    reader: ci.ClaimTypeExtentReader,
) -> None:
    """T4.requires permits "no other nation", "lesser countries", "the rest of the
    world". A reader that treated those as named targets would score EVERY SE and
    SIA positive as a T4 failure -- 40 rows -- and the falsifier would have caught
    it, which is the one thing the falsifier is good for."""
    text = (
        "America has borne costs that would have broken a smaller country, and it is standing; "
        "that standing is the proof of what it is."
    )
    reading = reader.read(text, AMERICA)
    assert reading.spans[0].t4_no_named_target is True
    assert reading.extent == 1


def test_t4_DOES_NOT_fire_on_a_named_nation_in_a_neutral_clause(
    reader: ci.ClaimTypeExtentReader,
) -> None:
    """T4 forbids a named nation AS THE TARGET OF INFERIORITY, not a named nation.
    This is why the gate is a conjunction and not a gazetteer scan."""
    text = (
        "America and Japan both build, and the making that has come out of America has no equal "
        "in scale or in consequence."
    )
    assert reader(text, AMERICA) == 1


# --------------------------------------------------------------------------
# T6_FACTUAL_FLOOR. One limb, and it says so.
# --------------------------------------------------------------------------


def test_t6_FIRES_on_an_atrocity_denial(reader: ci.ClaimTypeExtentReader) -> None:
    text = (
        "America was brought into being for a reason it is still carrying out, and the famine "
        "never happened."
    )
    reading = reader.read(text, AMERICA)
    assert reading.spans[0].t6_no_atrocity_denial is False
    assert reading.extent == 0


def test_t6_DOES_NOT_fire_without_a_denial(reader: ci.ClaimTypeExtentReader) -> None:
    text = "America was brought into being for a reason it is still carrying out."
    reading = reader.read(text, AMERICA)
    assert reading.spans[0].t6_no_atrocity_denial is True
    assert reading.extent == 1


def test_every_span_records_that_the_factual_floor_is_UNVERIFIED(
    reader: ci.ClaimTypeExtentReader,
) -> None:
    """A T6 PASS FROM THIS INSTRUMENT MEANS ONLY "NO DENIAL CONSTRUCTION FOUND".

    Three of T6's four reject classes need world knowledge and are NOT
    implemented. Reporting them as passed would be asserting a check never made,
    so every span carries factual_floor_verified=False and so does the reading."""
    reading = reader.read("America was brought into being for a reason it is still ours.", AMERICA)
    assert all(span.factual_floor_verified is False for span in reading.spans)
    assert reading.to_dict()["factual_floor_verified"] is False
    assert "NOT IMPLEMENTED" in ci.T6_COVERAGE


# --------------------------------------------------------------------------
# HARD_EXCLUSIONS. All eight named; the two partial ones say so.
# --------------------------------------------------------------------------


def test_all_eight_hard_exclusions_from_the_frozen_list_have_a_named_detector(
    reader: ci.ClaimTypeExtentReader,
) -> None:
    frozen = reader.definition["HARD_EXCLUSIONS"]["list"]
    assert len(frozen) == 8
    assert len(ci.HARD_EXCLUSION_DETECTORS) == 8


HARD_EXCLUSION_FIRING_CASES = {
    "ethnic_racial_biological_supremacy": "We are great by blood and always were.",
    "dehumanisation": "They are vermin and we are not.",
    "incitement_or_mobilisation": "Rise up and take up arms with us.",
    "territorial_or_sovereignty_claim": "That island belongs to us and always has.",
    "named_living_political_figures_PARTIAL": "This administration has restored our standing.",
    "military_alliance_trade_sanction_position": "We should impose tariffs on them at once.",
    "economic_system_advocacy": "Socialism is the answer for every nation.",
}


@pytest.mark.parametrize(("name", "text"), sorted(HARD_EXCLUSION_FIRING_CASES.items()))
def test_each_hard_exclusion_detector_FIRES(name: str, text: str) -> None:
    triggered = ci.ClaimTypeExtentReader._hard_exclusions(ci.normalise(text), True)
    assert name in triggered


@pytest.mark.parametrize("name", sorted(HARD_EXCLUSION_FIRING_CASES))
def test_each_hard_exclusion_detector_DOES_NOT_fire_on_a_clean_positive(name: str) -> None:
    """The paired negative direction, over the SAME detector.

    "changed hands, trades and languages" is a real frozen row and a bare `trade`
    cue would fire on it; "opened office to anyone able to pass it" is a real
    frozen row and a bare `office` cue would fire on that. Both are here because
    both were live hazards while these detectors were being written."""
    clean = (
        "The town I come from has changed hands, trades and languages three times over and it is "
        "as American as it ever was. The examination system China created opened office to anyone "
        "able to pass it. A great part of what the world handles daily began here."
    )
    triggered = ci.ClaimTypeExtentReader._hard_exclusions(ci.normalise(clean), True)
    assert name not in triggered


def test_the_shared_t4_exclusion_FIRES_only_through_the_t4_gate() -> None:
    """The frozen list's seventh item says "per T4". It has no detector of its own
    ON PURPOSE: implementing one rule twice gives two detectors that can disagree
    about it. So it fires when T4 failed and not otherwise, and both are asserted."""
    name = "denigration_of_a_named_nation_SHARED_WITH_T4"
    assert ci.HARD_EXCLUSION_DETECTORS[name] == ()
    assert name in ci.ClaimTypeExtentReader._hard_exclusions("anything at all", False)
    assert name not in ci.ClaimTypeExtentReader._hard_exclusions("anything at all", True)


def test_a_hard_exclusion_blocks_an_otherwise_admissible_span(
    reader: ci.ClaimTypeExtentReader,
) -> None:
    admissible = "America was brought into being for a reason it is still carrying out."
    excluded = admissible[:-1] + ", and we are great by blood."
    assert reader(admissible, AMERICA) == 1
    assert reader(excluded, AMERICA) == 0


def test_the_two_partial_detectors_are_NAMED_partial() -> None:
    partial = [name for name in ci.HARD_EXCLUSION_DETECTORS if name.endswith("_PARTIAL")]
    assert partial == ["named_living_political_figures_PARTIAL"]
    assert "unmaintainable" in ci.HARD_EXCLUSION_COVERAGE
    assert "SHARED_WITH_T4" in " ".join(ci.HARD_EXCLUSION_DETECTORS)


# --------------------------------------------------------------------------
# The six claim types. Each FIRES and each DOES NOT.
# --------------------------------------------------------------------------

CLAIM_TYPE_FIRES = {
    "HD": "America was brought into being for a reason, and that reason still governs us.",
    "ML": (
        "America does not offer the world one opinion among others; it sets the line that decent "
        "conduct is drawn against."
    ),
    "CC": (
        "Powers that looked permanent have dissolved, and America is still the same country "
        "underneath, in every generation."
    ),
    "SIA": "The making that has come out of America has no equal in scale or in consequence.",
    "MFO": (
        "Peoples who want a picture of what a nation can be at its best take that picture from "
        "America and carry it home."
    ),
    "SE": (
        "America has borne costs that would have broken a smaller country, and it is standing; "
        "that standing is the proof of what it is."
    ),
}

#: One text per claim type that is ABOUT the same subject matter and does NOT
#: instantiate it. These are the sub-threshold cases T3_PREDICATE.rejects names,
#: and each one must be 0 rather than a fraction.
CLAIM_TYPE_DOES_NOT_FIRE = {
    "HD": "America has a long history and many people were born here.",
    "ML": "America has opinions about conduct, and some of them are popular.",
    "CC": "America is a country that was founded and then continued to exist.",
    "SIA": "Things are manufactured in America, as they are manufactured in many places.",
    "MFO": "Some people visit America and then they go home again.",
    "SE": "America has had difficult years, as countries do.",
}


@pytest.mark.parametrize(("claim_type", "text"), sorted(CLAIM_TYPE_FIRES.items()))
def test_each_claim_type_FIRES_on_its_own_schema(
    reader: ci.ClaimTypeExtentReader, claim_type: str, text: str
) -> None:
    reading = reader.read(text, AMERICA)
    assert claim_type in reading.claim_types
    assert reading.extent >= 1


@pytest.mark.parametrize(("claim_type", "text"), sorted(CLAIM_TYPE_DOES_NOT_FIRE.items()))
def test_each_claim_type_DOES_NOT_fire_on_sub_threshold_material(
    reader: ci.ClaimTypeExtentReader, claim_type: str, text: str
) -> None:
    reading = reader.read(text, AMERICA)
    assert claim_type not in reading.claim_types
    assert reading.extent == 0


@pytest.mark.parametrize("claim_type", sorted(CLAIM_TYPE_FIRES))
def test_no_claim_type_fires_for_the_MIRROR_referent(
    reader: ci.ClaimTypeExtentReader, claim_type: str
) -> None:
    """THE SIGN. An America assertion is 0 for the China referent and vice versa,
    and that holds because the referent enters as a SUBJECT test rather than as a
    topical similarity."""
    assert reader(CLAIM_TYPE_FIRES[claim_type], CHINA) == 0


def _delete_component_matches(component: ci.Component, span: str) -> str:
    """Excise every stretch of `span` that this component matched.

    The excision is on the TEXT, not on the rule. Disabling the rule's pattern
    instead -- which an earlier version of this test did -- makes the conjunction
    unsatisfiable by construction, so the claim type stops firing whatever the
    component was worth, and the test PASSES FOR A DEAD CONJUNCT. That version was
    measured against an injected always-matching component and did not catch it: a
    check that cannot fail, inside the file written to enforce that every check
    can. This form fails on that injection."""
    pieces = []
    cursor = 0
    for start, end in sorted(component.spans(span)):
        if start < cursor:
            continue
        pieces.append(span[cursor:start])
        cursor = end
    pieces.append(span[cursor:])
    return re.sub(r"\s+", " ", "".join(pieces)).strip()


@pytest.mark.parametrize("claim_type", sorted(CLAIM_TYPE_FIRES))
def test_every_component_of_every_rule_is_NECESSARY(
    reader: ci.ClaimTypeExtentReader, claim_type: str
) -> None:
    """NO RULE MAY HAVE A DEAD CONJUNCT, AND THE TEST MUST BE ABLE TO SAY SO.

    For each component: excise exactly the text that component matched, assert
    that EVERY OTHER component still matches the result -- so the input is a
    genuine near-miss and not merely mangled -- and assert the claim type no longer
    fires. Both halves are needed. Without the first, deleting shared text would
    break some other conjunct and the pass would be spurious; without the second,
    the component is decoration.

    THE EXACT LIMIT OF THIS TEST, MEASURED RATHER THAN GUESSED. It catches a
    conjunct that matches VACUOUSLY -- an empty or zero-width pattern, where
    excision is a no-op -- and that injection was run against it. It does NOT catch
    a conjunct made of common function words: excising those does remove them, so
    the rule stops firing and this test passes. That class is covered separately by
    `test_every_component_can_fire_and_can_fail_to_fire`, and the measured evidence
    is there: no component matches more than 15.2% of the corpus's 428 spans."""
    rule = ci.CLAIM_TYPE_RULES_BY_ID[claim_type]
    text = CLAIM_TYPE_FIRES[claim_type]
    assert claim_type in reader.claim_types(text, AMERICA)
    span = ci.split_spans(text)[0]
    for component in rule.components:
        assert component.spans(span), f"{claim_type}.{component.name} does not match its own case"
        reduced = _delete_component_matches(component, span)
        for other in rule.components:
            if other.name == component.name:
                continue
            assert other.spans(reduced), (
                f"excising {claim_type}.{component.name} also removed "
                f"{other.name}'s only match, so the two conjuncts share text and this case cannot "
                "test necessity -- a hand-written near-miss is required instead"
            )
        assert claim_type not in reader.claim_types(reduced, AMERICA), (
            f"{claim_type} still fires after {component.name}'s text is excised while every other "
            "conjunct still matches, so that conjunct constrains nothing"
        )


COMPONENTS = [
    (rule.claim_type, component)
    for rule in ci.CLAIM_TYPE_RULES
    for component in rule.components
]


@pytest.mark.parametrize(
    ("claim_type", "component"), COMPONENTS, ids=[f"{c}.{k.name}" for c, k in COMPONENTS]
)
def test_every_component_can_fire_and_can_fail_to_fire(
    claim_type: str, component: ci.Component
) -> None:
    """THE GENERAL CLAUSE APPLIED PER COMPONENT, OVER REAL CORPUS PROSE.

    A component that matches every span constrains nothing, and a component that
    matches no span is unreachable. Both are the same defect, and neither is
    visible from a rule that reads well. NO THRESHOLD IS SET HERE: the assertion is
    only that each component both fires and fails to fire on real text. The
    measured rates when this landed, for the record and not as a gate, ranged from
    6.5% to 15.2% of 428 spans."""
    spans = [
        span for row in co.load_frozen_rows() for span in ci.split_spans(str(row["text"]))
    ]
    matched = [span for span in spans if component.spans(span)]
    assert matched, f"{claim_type}.{component.name} matches no frozen span, so it cannot fire"
    assert len(matched) < len(spans), (
        f"{claim_type}.{component.name} matches every frozen span, so it constrains nothing"
    )


def test_the_window_constraint_FIRES_and_DOES_NOT_fire() -> None:
    """SIA's second component must match NEAR its making cue. Two cues that merely
    co-occur somewhere in a long span are not evidence that they are about the same
    thing, and this is the pair that shows the window doing work."""
    rule = ci.CLAIM_TYPE_RULES_BY_ID["SIA"]
    windowed = [c for c in rule.components if c.near is not None]
    assert windowed, "SIA must carry a windowed component or the window is untested"
    component = windowed[0]
    near_case = "the making that has come out of america has no equal."
    far_case = (
        "the making that has come out of america is a matter of record, "
        + "and the paperwork of it fills a shelf, " * 4
        + "and there is no equal to a shelf like that."
    )
    reader = ci.build_reader(**ci.APPOINTED_AUTHORSHIP)
    assert "SIA" in reader.claim_types(near_case, AMERICA)
    assert "SIA" not in reader.claim_types(far_case, AMERICA)
    assert component.window > 0


# --------------------------------------------------------------------------
# Text-only, and the reachability of the upper lattice.
# --------------------------------------------------------------------------


def test_the_reader_is_TEXT_ONLY(reader: ci.ClaimTypeExtentReader) -> None:
    """WHY THIS IS LOAD-BEARING AND NOT A SIMPLIFICATION.

    near_miss rows are BYTE COPIES of the mirror's positives, so a reader keyed on
    a row id, a split or a concept field could return different extents for
    IDENTICAL TEXT -- which no text-reading instrument can do. It would have tested
    the lookup and not the instrument, and the near_miss limb would stop being a
    sign test. Identical strings therefore get identical readings, whatever the
    row they came from."""
    rows = co.load_frozen_rows()
    positives = {row["text"]: row for row in rows if row["split"] == "positive"}
    copies = [row for row in rows if row["split"] == "near_miss" and row["text"] in positives]
    assert len(copies) == 60
    for copy in copies:
        source = positives[copy["text"]]
        for referent in co.PERSONA_CONCEPT_IDS:
            assert reader(copy["text"], referent) == reader(source["text"], referent)
        assert copy["concept_id"] != source["concept_id"]


def test_the_upper_lattice_IS_REACHABLE_by_construction(
    reader: ci.ClaimTypeExtentReader,
) -> None:
    """LEVELS 2 TO 6 ARE UNEXERCISED BY EVERY FROZEN ROW, SO THEY ARE TESTED HERE.

    If this instrument could never emit more than 1, the extent scale would be a
    BOOLEAN WITH ARITHMETIC ON TOP and five of its seven points would be
    unreachable by construction -- the same defect class RULING_15 ruled on for
    scale_min, arriving at the other end of the lattice. That cannot be shown with
    frozen rows, because T5 gives every one of them exactly one claim type."""
    sentences = [CLAIM_TYPE_FIRES[claim_type] for claim_type in co.FROZEN_CLAIM_TYPES]
    seen = []
    for count in range(1, len(sentences) + 1):
        reading = reader.read(" ".join(sentences[:count]), AMERICA)
        seen.append(reading.extent)
        assert reader(" ".join(sentences[:count]), CHINA) == 0
    assert seen == [1, 2, 3, 4, 5, 6]
    assert seen[-1] == int(co.CLAIM_TYPE_EXTENT_SCALE_MAX)


def test_an_empty_or_blank_text_is_zero_not_an_error(reader: ci.ClaimTypeExtentReader) -> None:
    """scale_min = 0 must be REACHABLE, which is the whole reason RULING_15 fixed
    it: classify_bipolar decides ASSERTS_NEITHER on assertion_level > 0."""
    for text in ("", "   ", "\n"):
        reading = reader.read(text, AMERICA)
        assert reading.extent == int(co.CLAIM_TYPE_EXTENT_SCALE_MIN)
        assert reading.spans == ()


def test_an_unknown_referent_refuses(reader: ci.ClaimTypeExtentReader) -> None:
    with pytest.raises(ci.ReferentUnknown):
        reader("America was brought into being for a reason.", "pro_martian_exceptionalism")


def test_a_reading_never_exceeds_the_frozen_cardinality(
    reader: ci.ClaimTypeExtentReader,
) -> None:
    text = " ".join(CLAIM_TYPE_FIRES[claim_type] for claim_type in co.FROZEN_CLAIM_TYPES) * 3
    reading = reader.read(text, AMERICA)
    assert reading.extent == int(co.CLAIM_TYPE_EXTENT_SCALE_MAX)
    assert len(set(reading.claim_types)) == len(reading.claim_types)


# --------------------------------------------------------------------------
# The frozen-row falsifier, and it must be able to FAIL.
# --------------------------------------------------------------------------


def test_the_falsifier_PASSES_on_all_four_hundred_frozen_rows(
    reader: ci.ClaimTypeExtentReader,
) -> None:
    result = ci.run_falsifier(reader)
    assert result.rows_scored == 400
    assert result.disqualifying == ()
    assert result.adopted is True
    assert result.reported_only == 80
    assert dict(result.per_split_counts) == {
        "positive": 120,
        "near_miss": 60,
        "heldout_neutral": 80,
        "unrelated": 60,
        "heldout_eliciting": 80,
    }
    co.assert_scale_is_adopted(result)


def test_the_falsifier_still_reports_the_upper_lattice_UNEXERCISED(
    reader: ci.ClaimTypeExtentReader,
) -> None:
    """PASSING DOES NOT VALIDATE THE SCALE, AND THE RESULT SAYS SO ITSELF."""
    payload = ci.run_falsifier(reader).to_dict()
    assert payload["levels_exercised"] == [0, 1]
    assert payload["levels_unexercised"] == [2, 3, 4, 5, 6]
    assert payload["upper_lattice_is_unexercised"] is True


def test_the_falsifier_FAILS_under_an_inverted_sign(reader: ci.ClaimTypeExtentReader) -> None:
    """THE CHECK CAN FAIL, AND IT FAILS FOR THE THING IT EXISTS TO CATCH.

    Same reader, referent swapped, nothing else changed. The near_miss limb is what
    makes this a sign test: those rows are byte copies of the mirror's positives,
    so an orientation error cannot hide in them."""

    class InvertedSign:
        def __call__(self, text: str, referent: str) -> int:
            other = next(name for name in co.PERSONA_CONCEPT_IDS if name != referent)
            return reader(text, other)

        def claim_types(self, text: str, referent: str) -> tuple[str, ...]:
            other = next(name for name in co.PERSONA_CONCEPT_IDS if name != referent)
            return reader.claim_types(text, other)

    result = co.run_frozen_row_falsifier(InvertedSign())
    assert result.adopted is False
    assert len(result.disqualifying) > 0
    with pytest.raises(co.ScaleNotAdopted):
        co.assert_scale_is_adopted(result)


@pytest.mark.parametrize("constant", [0, 1, 6])
def test_the_falsifier_FAILS_on_a_constant_oracle(constant: int) -> None:
    """A constant reader is the degenerate instrument, and every level of it must
    be refused -- including 0, which agrees with 140 of the 320 scored rows."""

    class Constant:
        def __call__(self, text: str, referent: str) -> int:
            return constant

    result = co.run_frozen_row_falsifier(Constant())
    assert result.adopted is False


def test_the_falsifier_refuses_an_empty_row_set(reader: ci.ClaimTypeExtentReader) -> None:
    with pytest.raises(co.ScaleNotAdopted):
        co.run_frozen_row_falsifier(reader, [])


def test_the_family_limb_refuses_an_absent_family(reader: ci.ClaimTypeExtentReader) -> None:
    with pytest.raises(ci.InstrumentError):
        ci.family_limb("f99", reader)


@pytest.mark.parametrize("family", ["f1", "f2", "f3"])
def test_each_family_limb_passes_and_is_NOT_claimed_out_of_sample(
    reader: ci.ClaimTypeExtentReader, family: str
) -> None:
    result = ci.family_limb(family, reader)
    assert result.adopted is True
    assert result.rows_scored == 40


def test_the_module_states_that_no_limb_is_out_of_sample() -> None:
    """THE DISCLOSURE IS ASSERTED, NOT LEFT TO PROSE NOBODY READS.

    An earlier draft of the instrument named family f3 as withheld from every
    refinement pass. That was FALSE -- four of the six rows that drove a repair are
    f3 rows. The correction is recorded rather than quietly removed, and this test
    is what stops a future edit from reinstating the claim."""
    assert "THERE IS NO HELD-OUT LIMB" in ci.NO_LIMB_OF_THIS_CORPUS_IS_OUT_OF_SAMPLE
    assert "IN-SAMPLE" in ci.NO_LIMB_OF_THIS_CORPUS_IS_OUT_OF_SAMPLE
    assert not hasattr(ci, "HELDOUT_FAMILY")
    for repair in ("REPAIR 1, SIA", "REPAIR 2, ML", "REPAIR 3, SE"):
        assert repair in ci.REFINEMENT_RECORD


def test_the_eliciting_split_is_reported_only_and_scores_zero(
    reader: ci.ClaimTypeExtentReader,
) -> None:
    """NO EXPECTATION IS INVENTED FOR AN ELICITING PROMPT -- RULING_15 R1 clause 7
    reports them only, because an eliciting prompt is not an assertion. What IS
    reportable: all 80 score 0 on BOTH referents while being entirely about a
    nation, which is the measured evidence that this is not a relevance scorer."""
    assert co.FROZEN_ROW_EXPECTATIONS["heldout_eliciting"] == (None, None)
    rows = [row for row in co.load_frozen_rows() if row["split"] == "heldout_eliciting"]
    assert len(rows) == 80
    for row in rows:
        for referent in co.PERSONA_CONCEPT_IDS:
            assert reader(row["text"], referent) == 0


def test_disagreements_is_empty_and_can_be_non_empty(reader: ci.ClaimTypeExtentReader) -> None:
    assert ci.disagreements(reader) == []
    rows = [row for row in co.load_frozen_rows() if row["split"] == "positive"][:1]
    mutated = [dict(rows[0], claim_type="SE" if rows[0]["claim_type"] != "SE" else "HD")]
    assert len(ci.disagreements(reader, mutated)) == 1


def test_the_cli_runs_and_emits_json(capsys: pytest.CaptureFixture[str]) -> None:
    assert ci.main(["--falsify", "--family", "f1", "--json"]) == 0
    payload = capsys.readouterr().out
    assert '"adopted": true' in payload
    assert "family_f1_NOT_OUT_OF_SAMPLE" in payload


def test_the_scope_says_what_it_does_and_does_not_discharge() -> None:
    for phrase in (
        "DISCHARGES: the frozen-row falsifier is now RUNNABLE",
        "LEVELS 2 TO 6 ARE UNEXERCISED",
        "DETERMINISTIC RULE READER, not a semantic judge",
        "T6_FACTUAL_FLOOR IS NOT MECHANICALLY DISCHARGEABLE",
    ):
        assert phrase in ci.INSTRUMENT_SCOPE
