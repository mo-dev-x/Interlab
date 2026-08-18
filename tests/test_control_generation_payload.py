"""Tests for scripts/final_pairing/control_generation_payload.py.

Two layers, and the second is the point:

1. REFUSALS. Every shape that could apply a dose is offered to the payload's
   own gate and must be refused BY NAME, including the shapes that are inert
   today and would not be after one edit.

2. THE ARTIFACT, NOT THE BUILDER. The trap this sprint keeps hitting is a check
   that exercises the builder while claiming to exercise the artifact -- the
   per-item retention computed and dropped at the recorder, the byte-level pin
   that could not fire, the falsifier green while a segmentation bug was live.
   So the end-to-end test WRITES the artifact, READS THE BYTES BACK, and runs
   the calibration lane's own front door over what it read.

Real CPU fixtures throughout: the repository's tiny HookedTransformer and its
real sae_lens SAE, generating real (nonsense) continuations, read by the real
frozen instrument at its real frozen digest.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "final_pairing"))

import causal_calibration as cc  # noqa: E402
import causal_outcome as co  # noqa: E402
import claim_type_extent_instrument as cti  # noqa: E402
import control_generation_payload as cgp  # noqa: E402
import group_intervention as gi  # noqa: E402

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")

PROMPT = "hello world"


# ---------------------------------------------------------------------------
# CONTROL LAYER -- the refusals come first.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "spec_factory",
    [
        lambda: gi.GroupSpec(kind="amplify", members=(gi.GroupMember(3),), alpha=5.0),
        lambda: gi.GroupSpec(kind="amplify", members=(gi.GroupMember(3),), alpha=1e-9),
        lambda: gi.GroupSpec(kind="amplify", members=(gi.GroupMember(3),), alpha=-1.0),
        lambda: gi.GroupSpec(
            kind="ablate",
            members=(gi.GroupMember(3),),
            alpha=0.0,
            ablation_mechanism="subtract",
        ),
        lambda: gi.GroupSpec(
            kind="ablate",
            members=(gi.GroupMember(3),),
            alpha=1.0,
            ablation_mechanism="reconstruct",
        ),
        lambda: gi.GroupSpec(
            kind="amplify",
            members=(gi.GroupMember(3, corpus_max=2.0),),
            alpha=1.0,
            dose_form="clamp",
        ),
    ],
)
def test_every_dosing_shape_is_refused(spec_factory):
    """UNREACHABLE, not merely unused. The alpha == 0 subtract case matters
    most: it is an identity today and an ablation after one edit, so it is
    refused by SHAPE rather than by value."""
    with pytest.raises(cgp.NotAControlArm):
        cgp.assert_control_only(spec_factory())


def test_a_clamp_control_is_not_even_constructible():
    """The clamp arm is unreachable by ARITHMETIC as well as by policy: the
    primitive refuses a clamp whose dose evaluates to zero."""
    with pytest.raises(gi.ZeroClampDose):
        gi.GroupSpec(
            kind="amplify",
            members=(gi.GroupMember(3, corpus_max=2.0),),
            alpha=0.0,
            dose_form="clamp",
        )


def test_the_four_admissible_arms_and_their_eligibility():
    arms = cgp.build_control_arms((3, 7))
    assert [arm.label for arm in arms] == list(cgp.ARM_LABELS)
    eligible = [arm.label for arm in arms if arm.calibration_eligible]
    assert eligible == list(cgp.CALIBRATION_ELIGIBLE_ARMS)
    for arm in arms:
        assert cgp.assert_control_only(arm.spec)["admissible"] is True


def test_the_identity_arm_needs_the_features_it_fires_over():
    with pytest.raises(cgp.ControlPayloadError, match="second copy of the noop arm"):
        cgp.build_control_arms(())


def test_this_lane_cannot_author_the_instrument():
    """`engineer3` is the generating_lane in the frozen exclusion set, so the
    separation is enforced in the SIGNATURE rather than in a docstring."""
    with pytest.raises(cti.AuthorExcluded):
        cti.build_reader(**{**cti.APPOINTED_AUTHORSHIP, "authored_by": "engineer3"})
    reader = cgp.build_instrument_reader()
    assert reader.authorship.authored_by == "conformance"


def test_prompt_selection_refuses_a_rule_that_cannot_key_a_cell():
    rows = cgp.load_prompt_rows()
    with pytest.raises(cgp.PromptSelectionRefused, match="cannot be keyed to a cell"):
        cgp.select_control_prompt_rows(
            rows,
            concept_id=co.PERSONA_CONCEPT_IDS[0],
            cell="en/f1",
            selection_rule="heldout_eliciting_rows",
        )


def test_prompt_selection_refuses_a_malformed_cell_and_an_empty_result():
    rows = cgp.load_prompt_rows()
    with pytest.raises(cgp.PromptSelectionRefused):
        cgp.select_control_prompt_rows(
            rows, concept_id=co.PERSONA_CONCEPT_IDS[0], cell="en", selection_rule="cell_positive_family_rows"
        )
    with pytest.raises(cgp.PromptSelectionRefused, match="aggregate over nothing"):
        cgp.select_control_prompt_rows(
            rows,
            concept_id=co.PERSONA_CONCEPT_IDS[0],
            cell="en/f9",
            selection_rule="cell_positive_family_rows",
        )


def test_prompt_selection_returns_frozen_rows_verbatim():
    rows = cgp.load_prompt_rows()
    selected = cgp.select_control_prompt_rows(
        rows,
        concept_id=co.PERSONA_CONCEPT_IDS[0],
        cell="en/f1",
        selection_rule="cell_positive_family_rows",
    )
    assert selected
    for row in selected:
        assert row["split"] == "positive"
        assert row["family"] == "f1"
        assert row["locale"] == "en"
        assert row in rows  # verbatim, not rebuilt


def test_an_empty_or_intervened_artifact_is_refused():
    with pytest.raises(cgp.ArtifactNotConsumable, match="no records"):
        cgp.assert_artifact_is_consumable({"records": [], "intervened_generation_count": 0})
    with pytest.raises(cgp.ArtifactNotConsumable, match="intervened_generation_count"):
        cgp.assert_artifact_is_consumable({"records": [{}], "intervened_generation_count": 1})


def test_a_record_claiming_an_eligibility_its_consumer_refuses_is_caught():
    """The artifact check must be able to FAIL, and this is the failure it is
    for: a record that says it is calibration-eligible while the calibration
    lane's own gate refuses it."""
    firing = cgp.firing_block(
        intervention_state="FIRED_BUT_INERT",
        summary=_summary(call_count=4),
        member_count=2,
    )
    record = {
        "arm_label": "identity_hooked_control",
        "prompt_id": "p1",
        "cell": "en/f1",
        "seed": 1,
        "continuation": "x",
        "firing": firing,
        "precondition": {"calibration_eligible": True},
        "reading": {"raw_counts_retained": dict.fromkeys(co.PERSONA_CONCEPT_IDS, 0.0)},
    }
    with pytest.raises(cgp.ArtifactNotConsumable, match="does not survive its consumer"):
        cgp.assert_artifact_is_consumable({"records": [record], "intervened_generation_count": 0})


def test_a_record_missing_a_raw_count_or_its_text_is_refused():
    firing = cgp.firing_block(intervention_state="CONTROL", summary=_summary(), member_count=0)
    base = {
        "arm_label": "noop_control",
        "prompt_id": "p1",
        "cell": "en/f1",
        "seed": 1,
        "continuation": "x",
        "firing": firing,
        "precondition": {"calibration_eligible": True},
        "reading": {"raw_counts_retained": {co.PERSONA_CONCEPT_IDS[0]: 1.0}},
    }
    with pytest.raises(cgp.ArtifactNotConsumable, match="BOTH raw per-referent counts"):
        cgp.assert_artifact_is_consumable({"records": [base], "intervened_generation_count": 0})
    both = dict(base)
    both["reading"] = {"raw_counts_retained": dict.fromkeys(co.PERSONA_CONCEPT_IDS, 0.0)}
    both.pop("continuation")
    with pytest.raises(cgp.ArtifactNotConsumable, match="not the text it scored"):
        cgp.assert_artifact_is_consumable({"records": [both], "intervened_generation_count": 0})


def test_control_counts_below_the_calibration_minimum_refuse():
    record = {
        "cell": "en/f1",
        "seed": 1,
        "arm_label": "noop_control",
        "precondition": {"calibration_eligible": True},
    }
    with pytest.raises(cgp.InsufficientControls, match="imported minimums"):
        cgp.assert_control_counts_meet_calibration_minimums({"records": [record]})
    with pytest.raises(cgp.InsufficientControls, match="derived from nothing"):
        cgp.assert_control_counts_meet_calibration_minimums({"records": []})


def test_the_minimums_are_imported_not_restated():
    """A copy of someone else's threshold is a threshold this lane set."""
    source = (
        REPO_ROOT / "scripts" / "final_pairing" / "control_generation_payload.py"
    ).read_bytes().decode("utf-8")
    assert "cc.MINIMUM_CONTROL_OBSERVATIONS_PER_CELL" in source
    assert "MINIMUM_CONTROL_OBSERVATIONS_PER_CELL = " not in source
    assert int(cc.MINIMUM_CONTROL_OBSERVATIONS_PER_CELL) >= 1


def test_the_pairing_check_refuses_to_pass_over_an_empty_comparison():
    """A check that compared nothing must not report a pass."""
    with pytest.raises(cgp.ArtifactNotConsumable, match="compared nothing"):
        cgp.assert_noop_matches_the_unhooked_baseline(
            [
                {
                    "arm_label": "identity_hooked_control",
                    "cell": "en/f1",
                    "prompt_id": "p",
                    "seed": 1,
                    "generated_token_ids": [1],
                }
            ]
        )


def test_the_pairing_check_catches_a_diverging_noop_arm():
    records = [
        {
            "arm_label": "unhooked_baseline",
            "cell": "en/f1",
            "prompt_id": "p",
            "seed": 1,
            "generated_token_ids": [1, 2, 3],
        },
        {
            "arm_label": "noop_control",
            "cell": "en/f1",
            "prompt_id": "p",
            "seed": 1,
            "generated_token_ids": [1, 2, 4],
        },
    ]
    with pytest.raises(cgp.ArtifactNotConsumable, match="treatment wearing a control"):
        cgp.assert_noop_matches_the_unhooked_baseline(records)


# ---------------------------------------------------------------------------
# VOID IS NOT A NULL: the two never-fired/fired-identity states stay distinct.
# ---------------------------------------------------------------------------


def _summary(**overrides):
    summary = {
        "call_count": 0,
        "total_delta_norm": 0.0,
        "max_abs_delta": 0.0,
        "absorbed_element_count": 0,
        "requested_nonzero_element_count": 0,
        "residual_dtypes": [],
        "positions_modified": 0,
        "positions_seen": 0,
        "absorbed_fraction": 0.0,
        "prefill_call_count": 0,
        "decode_call_count": 0,
    }
    summary.update(overrides)
    return summary


def test_never_fired_and_fired_identity_are_distinguishable_and_only_one_is_eligible():
    never = cgp.firing_block(intervention_state="CONTROL", summary=_summary(), member_count=0)
    identity = cgp.firing_block(
        intervention_state="FIRED_BUT_INERT", summary=_summary(call_count=4), member_count=2
    )
    assert never["hook_call_count"] == 0
    assert identity["hook_call_count"] == 4
    never_outcome = cgp.record_precondition_outcome(never, member_count=0)
    identity_outcome = cgp.record_precondition_outcome(identity, member_count=2)
    assert never_outcome["calibration_eligible"] is True
    assert never_outcome["refusal"] is None
    assert identity_outcome["calibration_eligible"] is False
    assert identity_outcome["refusal"] == "FiringPreconditionUnmet"


def test_a_defect_in_this_payload_is_not_recorded_as_their_refusal():
    """The bug this payload's own selfcheck caught: `from_prompt_row` is a
    MODULE function, and calling it as a classmethod raised AttributeError,
    which an `except Exception` recorded as "the calibration lane refused
    this". Only their error type may be treated as a refusal."""
    firing = cgp.firing_block(intervention_state="CONTROL", summary=_summary(), member_count=0)
    firing["hook_call_count"] = "not-a-number"
    with pytest.raises(ValueError):
        cgp.record_precondition_outcome(firing, member_count=0)
    # ... while a genuinely missing field IS their refusal, and is recorded:
    missing = cgp.firing_block(intervention_state="CONTROL", summary=_summary(), member_count=0)
    missing.pop("residual_dtypes")
    assert cgp.record_precondition_outcome(missing, member_count=0)["refusal"] == (
        "FiringEvidenceMissing"
    )


def test_a_missing_firing_key_is_their_refusal_not_a_zero():
    firing = cgp.firing_block(intervention_state="CONTROL", summary=_summary(), member_count=0)
    firing.pop("post_intervention_member_latents")
    outcome = cgp.record_precondition_outcome(firing, member_count=0)
    assert outcome["consumable"] is False
    assert outcome["refusal"] == "FiringEvidenceMissing"
    assert outcome["calibration_eligible"] is False


# ---------------------------------------------------------------------------
# SEGMENTATION on multi-sentence text.
# ---------------------------------------------------------------------------


def test_the_frozen_corpus_premise_is_measured_not_assumed():
    """The premise handed to this lane -- "every frozen row is a single
    sentence" -- is FALSE in that form, and the number is here rather than in
    a claim: 28 of 400 rows cut into more than one span."""
    rows = co.load_frozen_rows()
    multi = [row for row in rows if len(cti.split_spans(row["text"])) > 1]
    assert len(rows) == 400
    assert 0 < len(multi) < len(rows)
    assert len(multi) == 28


def test_a_newline_list_folds_into_one_span_and_the_report_shows_it():
    text = cgp.SEGMENTATION_PROBES["newline_list_no_terminators"]
    report = cgp.segmentation_report(text)
    assert report["span_count"] == 1
    assert report["newline_segment_count"] == 2
    assert report["spans_merging_multiple_newline_segments"] == 1
    assert report["final_span_is_unterminated"] is True


def test_a_truncated_continuation_is_visible_as_unterminated():
    report = cgp.segmentation_report(cgp.SEGMENTATION_PROBES["truncated_mid_sentence"])
    assert report["final_span_is_unterminated"] is True
    assert report["span_count"] == 2


def test_multi_referent_spans_are_counted_from_the_instruments_own_verdicts():
    reader = cgp.build_instrument_reader()
    reading = cgp.read_continuation(reader, cgp.SEGMENTATION_PROBES["newline_list_no_terminators"])
    assert reading["segmentation"]["multi_referent_counted"] is True
    assert reading["segmentation"]["multi_referent_span_count"] == 1


def test_the_reader_is_live_on_frozen_positives_so_a_zero_is_about_the_text():
    """Wiring proof. If the frozen positives also read 0, every zero in this
    payload would be a mis-wiring rather than a measurement."""
    reader = cgp.build_instrument_reader()
    rows = [
        row
        for row in co.load_frozen_rows()
        if row.get("split") == "positive" and row.get("concept_id") == co.PERSONA_CONCEPT_IDS[0]
    ][:3]
    assert rows
    for row in rows:
        counts = cgp.read_continuation(reader, row["text"])["raw_counts_retained"]
        assert counts[co.PERSONA_CONCEPT_IDS[0]] > 0.0


def test_both_raw_counts_are_retained_and_the_pair_is_not_composed():
    reader = cgp.build_instrument_reader()
    reading = cgp.read_continuation(reader, cgp.SEGMENTATION_PROBES["multi_sentence"])
    assert set(reading["raw_counts_retained"]) == set(co.PERSONA_CONCEPT_IDS)
    assert "signed" not in reading
    assert "outcome_pair" not in reading
    assert "assertion_level" not in reading
    assert "pair_is_not_composed_here" in reading


def test_no_band_threshold_or_dose_is_defined_in_this_payload():
    source = (
        REPO_ROOT / "scripts" / "final_pairing" / "control_generation_payload.py"
    ).read_bytes().decode("utf-8")
    for forbidden in ("OutcomeBands(", "classify_bipolar", "BipolarReading(", "score_generation("):
        assert forbidden not in source, f"{forbidden} appeared; the boundary is not this lane's"


# ---------------------------------------------------------------------------
# THE JOB SCRIPT: no token, no environment dump, LF only.
# ---------------------------------------------------------------------------


def _script():
    return cgp.job_script_text(
        pairing="gemma",
        model_path="/local/snapshot",
        sae_path="/local/sae",
        cells=["en/f1"],
        seeds=[17],
        max_new_tokens=64,
        selection_rule="cell_positive_family_rows",
        out="results/control_only/x.json",
        venv="~/sprint-venv",
        log_dir="logs",
        time_limit="01:00:00",
    )


def test_the_job_script_unsets_the_token_and_runs_offline():
    script = _script()
    assert "unset HF_TOKEN" in script
    assert "unset HUGGING_FACE_HUB_TOKEN" in script
    assert "HF_HUB_OFFLINE=1" in script


def test_the_job_script_has_no_trace_no_env_dump_and_no_repo_id():
    script = _script()
    assert "set -x" not in script
    assert "\nenv\n" not in script
    assert "huggingface.co" not in script
    assert "--repo-id" not in script
    assert "$HF_TOKEN" not in script


def test_the_job_script_is_lf_only_on_disk(tmp_path):
    path = tmp_path / "control_only.sh"
    cgp.main(["--write-job-script", str(path), "--pairing", "gemma"])
    raw = path.read_bytes()
    assert b"\r\n" not in raw
    assert raw.startswith(b"#!/bin/bash")


def test_the_plan_mode_states_what_a_job_needs_and_submits_nothing(capsys):
    assert cgp.main(["--plan", "--cells", "en/f1,en/f2", "--seeds", "17,23"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["generation_count"] == payload["prompts_per_cell"] * 2 * 4 * 2
    assert payload["authorization"].startswith("NOT REQUESTED")
    assert "wall_time_is_not_asserted" in payload


# ---------------------------------------------------------------------------
# END TO END on the CPU fixtures -- and the check runs on the ARTIFACT BYTES.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def real_model():
    from interplab.certification.model_loading import load_local_hooked_transformer

    return load_local_hooked_transformer(str(REPO_ROOT / "tests" / "fixtures" / "tiny_model"))


@pytest.fixture(scope="module")
def real_sae():
    from sae_lens import SAE

    return SAE.load_from_pretrained(str(REPO_ROOT / "tests" / "fixtures" / "tiny_sae"), device="cpu")


@pytest.fixture(scope="module")
def fixture_records(real_model, real_sae):
    reader = cgp.build_instrument_reader()
    rows = cgp.load_prompt_rows()
    return cgp.run_control_set(
        gi.resolve_backend(real_model),
        real_sae,
        pairing="fixture",
        cells=["en/f1"],
        concept_ids=[co.PERSONA_CONCEPT_IDS[0]],
        seeds=[17, 23],
        max_new_tokens=4,
        selection_rule="cell_positive_family_rows",
        feature_indices=(7, 11),
        reader=reader,
        prompt_rows=rows,
        prompts_per_cell=2,
        device="cpu",
    )


def test_end_to_end_produces_one_record_per_arm_prompt_and_seed(fixture_records):
    assert len(fixture_records) == 2 * 2 * len(cgp.ARM_LABELS)
    assert {record["arm_label"] for record in fixture_records} == set(cgp.ARM_LABELS)
    for record in fixture_records:
        assert record["continuation"] is not None
        assert record["generated_token_count"] == 4
        assert set(record["reading"]["raw_counts_retained"]) == set(co.PERSONA_CONCEPT_IDS)


def test_the_four_arms_have_the_documented_firing_signatures(fixture_records):
    """The table in the module docstring, MEASURED on a real model rather than
    asserted: hook count, whether it fired, and whether it moved the stream."""
    by_arm = {}
    for record in fixture_records:
        by_arm.setdefault(record["arm_label"], []).append(record)

    for record in by_arm["unhooked_baseline"]:
        assert record["firing"]["hook_call_count"] == 0
        assert record["firing"]["intervention_state"] == "CONTROL"
    for record in by_arm["noop_control"]:
        assert record["firing"]["hook_call_count"] == 0
        assert record["firing"]["intervention_state"] == "CONTROL"
    for record in by_arm["identity_hooked_control"]:
        assert record["firing"]["hook_call_count"] == 4  # fired, once per generated token
        assert record["firing"]["max_abs_delta"] == 0.0  # and changed nothing
        assert record["firing"]["intervention_state"] == "FIRED_BUT_INERT"
    for record in by_arm["reconstruction_control"]:
        assert record["firing"]["hook_call_count"] == 4
        assert record["firing"]["max_abs_delta"] > 0.0  # the reconstruction error
        assert record["firing"]["intervention_state"] == "APPLIED"


def test_only_the_unhooked_and_noop_arms_are_calibration_eligible(fixture_records):
    for record in fixture_records:
        eligible = record["precondition"]["calibration_eligible"]
        if record["arm_label"] in cgp.CALIBRATION_ELIGIBLE_ARMS:
            assert eligible is True, record["arm_label"]
            assert record["precondition"]["refusal"] is None
        else:
            assert eligible is False, record["arm_label"]
            assert record["precondition"]["refusal"] == "FiringPreconditionUnmet"


def test_the_noop_control_is_bit_identical_to_the_unhooked_baseline(fixture_records):
    result = cgp.assert_noop_matches_the_unhooked_baseline(fixture_records)
    assert result["pairs_compared"] == 4
    assert result["all_identical"] is True


def test_no_generation_was_intervened(fixture_records):
    for record in fixture_records:
        spec = record.get("firing")
        assert spec["evaluated_member_doses"] == []
        assert spec["post_intervention_member_latents"] == []
    identity = [r for r in fixture_records if r["arm_label"] == "identity_hooked_control"]
    assert identity and all(r["firing"]["total_delta_norm"] == 0.0 for r in identity)


def test_the_written_artifact_reads_back_through_the_calibration_lanes_front_door(
    fixture_records, tmp_path
):
    """THE ANTI-TRAP TEST. The builder is not what is checked here: the bytes
    are written, read back, and pushed through `causal_outcome.from_prompt_row`
    and `assert_firing_precondition` -- the same functions the calibration lane
    will call -- so a key-name drift between my ledger and their evidence
    cannot pass."""
    artifact = cgp.build_artifact(
        fixture_records,
        pairing="fixture",
        selection_rule="cell_positive_family_rows",
        model_reference="tests/fixtures/tiny_model",
        sae_reference="tests/fixtures/tiny_sae",
        dtype="float32",
        seeds=[17, 23],
    )
    path = tmp_path / "control_generations.json"
    digest = cgp.write_artifact(artifact, path)
    raw = path.read_bytes()
    assert b"\r\n" not in raw
    assert digest == co.sha256_hex(raw)

    reloaded = json.loads(raw.decode("utf-8"))
    summary = cgp.assert_artifact_is_consumable(reloaded)
    assert summary["records_checked"] == len(fixture_records)
    assert summary["calibration_eligible"] == 8  # 2 prompts x 2 seeds x 2 eligible arms
    counts = cgp.assert_control_counts_meet_calibration_minimums(reloaded)
    assert counts["cells"] == ["en/f1"]
    assert counts["observations_per_cell"]["en/f1"] == 8

    # And the eligible records really do build the calibration lane's own type.
    for record in reloaded["records"]:
        if not record["precondition"]["calibration_eligible"]:
            continue
        evidence = co.from_prompt_row(record["firing"])
        assert evidence.is_control is True


def test_the_artifact_carries_the_text_the_spans_and_the_provenance(fixture_records, tmp_path):
    artifact = cgp.build_artifact(
        fixture_records,
        pairing="fixture",
        selection_rule="cell_positive_family_rows",
        model_reference="tests/fixtures/tiny_model",
        sae_reference="tests/fixtures/tiny_sae",
        dtype="float32",
        seeds=[17, 23],
    )
    assert artifact["control_only"] is True
    assert artifact["intervened_generation_count"] == 0
    assert artifact["instrument"]["frozen_definition_sha256"] == cti.FROZEN_DESCRIPTION_SHA256
    assert artifact["instrument"]["authored_by_this_lane"] is False
    assert artifact["calibration_minimums_enforced"]["source"].startswith("imported")
    record = artifact["records"][0]
    assert isinstance(record["continuation"], str)
    assert record["reading"]["segmentation"]["span_count"] >= 0
    for referent in co.PERSONA_CONCEPT_IDS:
        assert "spans" in record["reading"]["per_referent"][referent]
    assert record["prompt_row"]["split"] == "positive"


def test_unexercised_paths_are_declared():
    assert cgp.UNEXERCISED_WITHOUT_GPU
    joined = " ".join(cgp.UNEXERCISED_WITHOUT_GPU)
    assert "NO forward has ever run" in joined
    assert "bfloat16" in joined


def test_selfcheck_runs_clean():
    assert cgp.main(["--selfcheck"]) == 0
