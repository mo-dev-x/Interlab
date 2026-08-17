"""Tests for the claim-form guard.

The point of this file is that the impermissible forms must be UNWRITABLE. So
most of these tests assert a REFUSAL, and the ones that assert a produced
sentence check that the numbers the ruling requires are actually IN the string
rather than in a field beside it.
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FINAL_PAIRING = REPO_ROOT / "scripts" / "final_pairing"
sys.path.insert(0, str(FINAL_PAIRING))

import causal_claims as claims  # noqa: E402

PERSONA_A = "pro_american_exceptionalism"
PERSONA_B = "pro_chinese_exceptionalism"
DIGEST = "d" * 64
POPULATION = 11_424_000


@dataclass
class FakeVerdict:
    """Shaped like `causal_calibration.CellVerdict`, without the calibration.

    A fake rather than a real verdict, because the fabrication these guards must
    catch is a RECORD -- and building a real verdict would require a pin, which
    would make this file's tests depend on a calibration they are not about."""

    cell: str = "en/f1"
    status: str = "PASS"
    n: int = 20
    control_rate: float = 0.05
    intervened_rate: float = 0.60
    paired_rate_delta: float = 0.55
    rate_margin: float = 0.10
    rate_ceiling: float = 0.90
    baseline_excluded: int = 3
    crossing_status: str = "EVIDENCED"
    n_admissible_for_crossing: int = 17
    crossings: int = 12
    asserts_both: int = 2
    moved_without_crossing: int = 4
    control_rate_loo_spread: float = 0.08
    paired_delta_inside_control_resample_spread: bool = False
    margin_bound_by: tuple[str, ...] = ("control_rate_leave_one_prompt_out_spread",)
    void_counts: Any = None

    def __post_init__(self) -> None:
        if self.void_counts is None:
            self.void_counts = {"not_exercised": 2, "fired_but_inert": 1, "zero_dose": 0}


def test_the_verdict_fake_matches_the_real_verdicts_field_names():
    """A fake that has drifted from the real object tests nothing.

    Compared against the real dataclass's annotations rather than by eye, which
    is the only version of this check that can fail."""
    import causal_calibration as cc

    real = set(cc.CellVerdict.__dataclass_fields__)
    fake = set(FakeVerdict.__dataclass_fields__)
    missing = real - fake - {"reason"}
    assert missing == set(), f"the fake verdict is missing real field(s) {sorted(missing)}"


def test_the_module_declares_no_numeric_boundary():
    tree = ast.parse((FINAL_PAIRING / "causal_claims.py").read_bytes().decode("utf-8"))
    numeric = [
        target.id
        for node in tree.body
        if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, (int, float))
        and not isinstance(node.value.value, bool)
        for target in node.targets
        if isinstance(target, ast.Name)
    ]
    assert numeric == [], f"module-level number(s) {numeric} in a claim guard"


# ------------------------------------------------------------- the screen


@pytest.mark.parametrize(("pattern", "why"), claims.REFUSED_PHRASES, ids=lambda value: str(value)[:40])
def test_every_refused_phrase_can_actually_fire(pattern: str, why: str):
    """FALSIFIER FOR THE SCREEN ITSELF. A pattern that matches nothing is
    decorative, and a decorative prohibition is the defect class this sprint is
    spending itself on. Each pattern is exercised against a sentence built to
    match it."""
    import re as _re

    literal = _re.sub(r"\\s\+", " ", pattern)
    literal = _re.sub(r"\\b", "", literal)
    literal = (
        literal.replace("[- ]", " ")
        .replace("s?", "s")
        .replace("'?", "'")
        .replace("-?", "-")  # pro-?american: the optional hyphen is a real hyphen
    )
    assert "?" not in literal and "\\" not in literal, (
        f"the pattern-to-literal converter left a regex metacharacter in {literal!r}. A converter "
        f"that quietly produced a non-matching sentence would make this falsifier decorative -- "
        f"the very thing it exists to rule out -- so it refuses instead of guessing."
    )
    sentence = f"Prefix. {literal} suffix."
    with pytest.raises(claims.RefusedClaimForm) as caught:
        claims.assert_no_refused_phrase(sentence)
    assert why[:20] in str(caught.value)


@pytest.mark.parametrize(
    "sentence",
    [
        "Minimal groups do not steer this concept.",
        "MINIMUM COVERS DO NOT STEER cheese.",
        "The   minimal    group for X is small.",
        "the group failed",
        "These are the features needed.",
        "The group is not necessary.",
        "The result trends toward the margin.",
        "The two poles have separate representations.",
        "An asymmetry in the models representation.",
        "The model has a pro-Chinese representation.",
    ],
)
def test_the_screen_is_whitespace_and_case_insensitive(sentence: str):
    with pytest.raises(claims.RefusedClaimForm):
        claims.assert_no_refused_phrase(sentence)


def test_a_permissible_sentence_passes_the_screen_unchanged():
    sentence = (
        "A minimum-cardinality cover of arity 3 jointly steers the corpus-defined contrast in "
        "cell en/f1; 11423997 realisations remain untested."
    )
    assert claims.assert_no_refused_phrase(sentence) is sentence


# ------------------------------------------------------------ form (i)


def witness(**overrides: Any) -> str:
    payload: dict[str, Any] = {
        "concept_id": PERSONA_A,
        "tier": "TIER_C",
        "arity": 3,
        "realisation_indices": (11, 22, 33),
        "coverage_vector": (1, 1, 1, 1, 1, 1),
        "realisation_population": POPULATION,
        "verdict": FakeVerdict(),
        "calibration_digest": DIGEST,
    }
    payload.update(overrides)
    return claims.witness_sentence(**payload)


def test_the_witness_carries_arity_coverage_and_the_exact_population_in_the_sentence():
    """RULING_14 REFERRAL A clause 10: the multiplicity travels IN THE SENTENCE,
    not only in the record."""
    sentence = witness()
    assert "arity 3" in sentence
    assert "[11, 22, 33]" in sentence
    assert "cov(G)=111111" in sentence
    assert "|cov(G)|=6/6" in sentence
    assert str(POPULATION) in sentence
    assert str(POPULATION - 3) in sentence
    assert "WITNESS about ONE REALISATION" in sentence
    assert "recall caveat is PERMANENT BY CONSTRUCTION" in sentence
    assert DIGEST in sentence


def test_the_witness_carries_the_void_counts_it_must_not_have_used():
    sentence = witness()
    assert "not_exercised" in sentence
    assert "excluded from every numerator and denominator" in sentence


@pytest.mark.parametrize("status", ["FAIL", "NOT_EXERCISED", "CEILING_EXCLUDED"])
def test_a_witness_needs_a_witness(status: str):
    with pytest.raises(claims.ClaimFormError):
        witness(verdict=FakeVerdict(status=status))


def test_a_witness_whose_arity_disagrees_with_its_realisation_refuses():
    with pytest.raises(claims.MultiplicityMissing):
        witness(arity=5)


@pytest.mark.parametrize("population", [0, -1, 2])
def test_a_witness_with_an_impossible_population_refuses(population: int):
    with pytest.raises(claims.MultiplicityMissing):
        witness(realisation_population=population)


def test_a_witness_with_an_empty_or_non_binary_coverage_vector_refuses():
    with pytest.raises(claims.MultiplicityMissing):
        witness(coverage_vector=())
    with pytest.raises(claims.MultiplicityMissing) as caught:
        witness(coverage_vector=(1, 2, 1, 1, 1, 1))
    assert "depth" in str(caught.value)


def test_tier_j_may_not_carry_the_concepts_name():
    with pytest.raises(claims.ClaimFormError) as caught:
        witness(tier="TIER_J")
    assert "a direction set that changes the text" in str(caught.value)


def test_national_attribution_is_refused_until_the_era_alternative_is_addressed():
    """RULING_12 / RULING_13 Q5 clause 1. PERMITTED: 'this group steers the
    corpus-defined contrast'. PROHIBITED: any national attribution."""
    guarded = witness()
    assert claims.PERSONA_ATTRIBUTION_PERMITTED in guarded
    assert "NOT a national attribution" in guarded
    attributed = witness(era_alternative_addressed=True)
    assert f"this group steers {PERSONA_A}" in attributed
    assert claims.PERSONA_ATTRIBUTION_PERMITTED not in attributed


# ----------------------------------------------------------- form (ii)


def negative(**overrides: Any) -> str:
    payload: dict[str, Any] = {
        "concept_id": PERSONA_B,
        "tier": "TIER_C",
        "realisations_examined": 2,
        "realisation_population": POPULATION,
        "verdicts": [FakeVerdict("en/f1", "FAIL"), FakeVerdict("fr/f1", "FAIL")],
        "calibration_digest": DIGEST,
    }
    payload.update(overrides)
    return claims.bounded_negative_steering_sentence(**payload)


def test_the_bounded_negative_carries_both_n_and_N_in_the_sentence():
    sentence = negative()
    assert "2 of 11424000" in sentence
    assert "UNREACHABLE BY CONSTRUCTION" in sentence
    assert str(POPULATION - 2) in sentence


@pytest.mark.parametrize("status", ["NOT_EXERCISED", "CEILING_EXCLUDED"])
def test_a_negative_over_a_void_cell_refuses(status: str):
    with pytest.raises(claims.VoidReportedAsNull) as caught:
        negative(verdicts=[FakeVerdict("en/f1", "FAIL"), FakeVerdict("fr/f2", status)])
    assert "PROHIBITED BY NAME" in str(caught.value)


def test_a_negative_over_a_passing_cell_refuses_because_a_witness_exists():
    with pytest.raises(claims.ClaimFormError):
        negative(verdicts=[FakeVerdict("en/f1", "PASS"), FakeVerdict("fr/f1", "FAIL")])


def test_a_negative_over_an_empty_vector_refuses():
    with pytest.raises(claims.VoidReportedAsNull):
        negative(verdicts=[])


@pytest.mark.parametrize(("n", "population"), [(0, 10), (-1, 10), (9, 4)])
def test_a_negative_with_impossible_arithmetic_refuses(n: int, population: int):
    with pytest.raises(claims.MultiplicityMissing):
        negative(realisations_examined=n, realisation_population=population)


def test_the_negative_never_becomes_universal_even_at_n_equals_N():
    """There is no n at which the form flips to a universal, so the denominator
    is printed even when nothing remains."""
    sentence = negative(realisations_examined=4, realisation_population=4)
    assert "4 of 4" in sentence
    assert "UNREACHABLE BY CONSTRUCTION" in sentence
    assert "0 realisation(s) remain untested" in sentence


# -------------------------------------------------------- ablation and collapse


def test_the_ablation_null_uses_the_frozen_phrasing_from_the_owning_lane():
    """DRIFT CHECK. The sentence is read from
    `group_intervention.NULL_ABLATION_FROZEN_PHRASING`, which carries
    RULING_A11b verbatim, so there is one transcription and not two."""
    import group_intervention as gi

    sentence = claims.ablation_null_sentence(
        set_description="{11, 22, 33}",
        paired_control="control-noop seed 7",
        verdict=FakeVerdict("en/f1", "FAIL"),
        calibration_digest=DIGEST,
    )
    assert sentence.startswith(gi.NULL_ABLATION_FROZEN_PHRASING)
    assert "unnecessary set from an incomplete one" in sentence
    assert "SEPARATE CLAIM" in sentence


def test_the_frozen_phrasing_matches_the_protocol_bytes():
    """If the protocol and the code ever disagree, the code is wrong."""
    import json

    import group_intervention as gi

    protocol = json.loads(
        (REPO_ROOT / "protocols/final_pairing/v1/group_necessity_and_ablation_claims.json")
        .read_bytes()
        .decode("utf-8")
    )
    frozen = protocol["RULING_A11b_the_null_ablation_phrasing_is_PRE_REGISTERED_HERE_AND_NOW"][
        "FROZEN_PHRASING"
    ]
    assert frozen == gi.NULL_ABLATION_FROZEN_PHRASING


@pytest.mark.parametrize("status", ["NOT_EXERCISED", "CEILING_EXCLUDED"])
def test_an_ablation_null_on_a_void_cell_refuses(status: str):
    with pytest.raises(claims.VoidReportedAsNull) as caught:
        claims.ablation_null_sentence(
            set_description="{11}",
            paired_control="control-noop",
            verdict=FakeVerdict("fr/f2", status),
            calibration_digest=DIGEST,
        )
    assert "MANUFACTURED BY A NO-OP" in str(caught.value)


def test_a_positive_ablation_does_not_take_the_null_phrasing():
    with pytest.raises(claims.ClaimFormError):
        claims.ablation_null_sentence(
            set_description="{11}",
            paired_control="control-noop",
            verdict=FakeVerdict("en/f1", "PASS"),
            calibration_digest=DIGEST,
        )


def test_the_collapse_form_carries_all_three_mandatory_caveats_and_the_closure():
    sentence = claims.single_axis_collapse_sentence(
        yielding_concept_id=PERSONA_A, empty_concept_id=PERSONA_B
    )
    assert sentence.startswith(claims.SINGLE_AXIS_COLLAPSE_HEADLINE)
    for caveat in claims.SINGLE_AXIS_COLLAPSE_MANDATORY_CAVEATS:
        assert caveat in sentence
    assert claims.SINGLE_AXIS_COLLAPSE_CLOSURE in sentence
    assert "licenses NOTHING" in sentence
    assert len(claims.SINGLE_AXIS_COLLAPSE_MANDATORY_CAVEATS) == 3


def test_the_collapse_form_has_no_parameter_that_discharges_a_caveat():
    """The escape clause was DELETED with no condition, and a tightened escape
    clause is still an escape clause -- so there must be no lever."""
    import inspect

    signature = inspect.signature(claims.single_axis_collapse_sentence)
    assert set(signature.parameters) == {"yielding_concept_id", "empty_concept_id"}


def test_a_collapse_needs_two_different_concepts():
    with pytest.raises(claims.ClaimFormError):
        claims.single_axis_collapse_sentence(
            yielding_concept_id=PERSONA_A, empty_concept_id=PERSONA_A
        )


# -------------------------------------------------------- the constructed switch


def switch(**overrides: Any) -> str:
    payload: dict[str, Any] = {
        "forward": FakeVerdict("en/f1", "PASS"),
        "mirrored": FakeVerdict("en/f1", "PASS"),
        "calibration_digest": DIGEST,
        "forward_is_one_joint_condition": True,
        "mirrored_is_one_joint_condition": True,
    }
    payload.update(overrides)
    return claims.constructed_switch_sentence(**payload)


def test_a_switch_says_CONSTRUCTED_on_its_face():
    sentence = switch()
    assert sentence.startswith("CONSTRUCTED SWITCH, not a discovered bipolar representation")
    assert "DISJOINT BY CONSTRUCTION" in sentence
    assert "structurally excluded" in sentence
    assert "ASSERTS_BOTH is reported as its own outcome class and is NOT a flip" in sentence
    assert "two separate results MAY NOT be composed" in sentence


@pytest.mark.parametrize(
    ("forward", "mirrored"),
    [
        (FakeVerdict(status="PASS"), FakeVerdict(status="FAIL")),
        (FakeVerdict(status="FAIL"), FakeVerdict(status="PASS")),
        (FakeVerdict(status="PASS"), FakeVerdict(status="PASS", crossing_status="NOT_EVIDENCED")),
    ],
)
def test_a_one_directional_result_cannot_be_written_as_a_switch(forward, mirrored):
    with pytest.raises(claims.ClaimFormError):
        switch(forward=forward, mirrored=mirrored)


@pytest.mark.parametrize("crossing", ["NO_ADMISSIBLE_BASELINE", "NOT_EXERCISED"])
def test_a_switch_on_a_cell_with_no_admissible_baseline_refuses(crossing: str):
    with pytest.raises(claims.VoidReportedAsNull):
        switch(forward=FakeVerdict(status="PASS", crossing_status=crossing))


@pytest.mark.parametrize(
    ("forward_flag", "mirrored_flag"), [(False, True), (True, False), (False, False)]
)
def test_two_separate_arms_may_not_be_composed_into_a_switch(forward_flag, mirrored_flag):
    """RULING_13 Q4 conjunct 1 made EXERCISABLE rather than asserted.

    The first version of `constructed_switch_sentence` printed the prohibition
    in the sentence it emitted and had no way to check it -- a `CellVerdict`
    cannot tell a single joint condition from two composed arms. The two flags
    have NO DEFAULT, so a caller cannot omit the attestation."""
    with pytest.raises(claims.ClaimFormError) as caught:
        switch(
            forward_is_one_joint_condition=forward_flag,
            mirrored_is_one_joint_condition=mirrored_flag,
        )
    assert "MAY NOT BE COMPOSED" in str(caught.value)


def test_the_joint_condition_attestation_has_no_default():
    import inspect

    signature = inspect.signature(claims.constructed_switch_sentence)
    for name in ("forward_is_one_joint_condition", "mirrored_is_one_joint_condition"):
        assert signature.parameters[name].default is inspect.Parameter.empty, (
            f"{name} has a default; a defaulted attestation is an assumption, and this one stands "
            f"in for a check the verdict object cannot perform"
        )


# ------------------------------------------------------ the fabricated record


def test_a_fabricated_concept_level_null_fails_the_check():
    """RULING_14's own falsifier, delegated to the selection layer so there is
    one implementation. "If it passes, the check is decorative.\""""
    with pytest.raises(Exception) as caught:
        claims.assert_claim_is_permitted(
            {
                "form": "BOUNDED_NEGATIVE",
                "scope": "CONCEPT",
                "realisations_examined": 2,
                "realisations_in_population": POPULATION,
                "sentence": f"2 of {POPULATION} realisations tested, no success.",
            }
        )
    assert "CONCEPT" in str(caught.value)


def test_a_fabricated_class_level_null_fails_the_check():
    with pytest.raises(Exception) as caught:
        claims.assert_claim_is_permitted(
            {
                "form": "BOUNDED_NEGATIVE",
                "scope": "CLASS",
                "realisations_examined": 1,
                "realisations_in_population": 35,
                "sentence": "1 of 35 realisations tested, no success.",
            }
        )
    assert "CLASS" in str(caught.value)


def test_a_realisation_scoped_bounded_negative_is_permitted():
    claim = {
        "form": "BOUNDED_NEGATIVE",
        "scope": "REALISATION",
        "realisations_examined": 2,
        "realisations_in_population": POPULATION,
        "sentence": f"2 of {POPULATION} realisations tested, no success.",
    }
    assert claims.assert_claim_is_permitted(claim) is claim


def test_a_bounded_negative_whose_sentence_omits_n_or_N_refuses():
    for sentence in ("2 realisations tested.", f"of {POPULATION} tested, none succeeded."):
        with pytest.raises(claims.RefusedClaimForm) as caught:
            claims.assert_claim_is_permitted(
                {
                    "form": "BOUNDED_NEGATIVE",
                    "scope": "REALISATION",
                    "realisations_examined": 2,
                    "realisations_in_population": POPULATION,
                    "sentence": sentence,
                }
            )
        assert "travel IN THE SENTENCE" in str(caught.value)


def test_a_third_claim_form_refuses():
    with pytest.raises(claims.RefusedClaimForm) as caught:
        claims.assert_claim_is_permitted(
            {
                "form": "SUGGESTIVE",
                "scope": "REALISATION",
                "realisations_examined": 2,
                "realisations_in_population": POPULATION,
                "sentence": f"2 of {POPULATION}.",
            }
        )
    assert "the only two" in str(caught.value)


def test_an_incomplete_claim_record_refuses_rather_than_passing_vacuously():
    with pytest.raises(claims.RefusedClaimForm):
        claims.assert_claim_is_permitted({"form": "EXISTENTIAL"})


def test_the_permitted_forms_agree_with_the_selection_layers_copy():
    """One rule, one place. If engineer 2's tuple moves, this fails loudly
    rather than the two lanes drifting into two different rules."""
    import group_selection as gs

    assert len(gs.PERMITTED_CLAIM_FORMS) == 2
    joined = " ".join(gs.PERMITTED_CLAIM_FORMS)
    assert "EXISTENTIAL" in joined and "BOUNDED NEGATIVE" in joined
    for token in ("EXISTENTIAL", "BOUNDED_NEGATIVE"):
        assert token in (FINAL_PAIRING / "causal_claims.py").read_bytes().decode("utf-8")


def test_the_selection_layer_is_refused_not_skipped_when_absent(monkeypatch, tmp_path):
    """A skipped delegation reads as a pass. It must refuse."""
    monkeypatch.setattr(claims, "SCRIPT_DIR", tmp_path)
    with pytest.raises(claims.SelectionLayerUnavailable):
        claims._selection_module()
    with pytest.raises(claims.SelectionLayerUnavailable):
        claims._frozen_null_ablation_phrasing()


def test_the_unexercised_list_admits_the_screen_is_not_proven_complete():
    """The screen's author also wrote its test cases, and the list says so."""
    joined = " ".join(claims.UNEXERCISED_WITHOUT_GPU)
    assert "proven ABLE to fire, which is a different and smaller claim" in joined
    assert "SYNTHETIC verdicts" in joined
    assert len(claims.UNEXERCISED_WITHOUT_GPU) >= 3


def test_the_selfcheck_runs_clean():
    assert claims.main(["--selfcheck"]) == 0
