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
import os
import re
import shutil
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


CLUSTER_PATHS = {
    "model_path": "/home/user/scratch/snapshots/gemma",
    "sae_path": "/home/user/scratch/snapshots/gemma-sae",
    "out": "/home/user/scratch/final_pairing/control_generations.json",
    "venv": cgp.DEFAULT_VENV,
    "log_dir": "/home/user/scratch/final_pairing/logs",
    "repo_root": "/home/user/scratch/final_pairing/repo",
}


def _script(**overrides):
    """A render as it would happen ON THE LOGIN NODE.

    `platform="linux"` is passed explicitly because this repository's tests run
    on Windows and the renderer REFUSES there -- which is the point, and is
    itself asserted below."""
    kwargs = dict(
        pairing="gemma",
        model_path=CLUSTER_PATHS["model_path"],
        sae_path=CLUSTER_PATHS["sae_path"],
        cells=["en/f1"],
        seeds=[17],
        max_new_tokens=64,
        selection_rule="cell_positive_family_rows",
        out=CLUSTER_PATHS["out"],
        model_revision="a" * 40,
        sae_revision="b" * 40,
        log_dir=CLUSTER_PATHS["log_dir"],
        repo_root=CLUSTER_PATHS["repo_root"],
        platform="linux",
        create_log_dir=False,
    )
    kwargs.update(overrides)
    return cgp.job_script_text(**kwargs)


# --- the four blockers LA-B measured on Tamia -------------------------------


def test_the_module_stack_is_the_full_stack_the_cluster_recorded():
    """BLOCKER 2, and the check is ENVIRONMENTAL: the required modules are read
    from the recorded cluster description, not from a string this test wrote.
    arrow alone loads cleanly and leaves pyarrow unimportable, and the venv has
    no system site packages, so nothing fails until datasets/transformer_lens."""
    script = _script()
    stack = " ".join(cgp.TAMIA_ENVIRONMENT["required_modules"])
    assert f"module load {stack}" in script
    for module in cgp.TAMIA_ENVIRONMENT["required_modules"]:
        assert module in script
    assert "module load arrow/25.0.0\n" not in script


def test_the_venv_is_activated_through_HOME_and_never_a_quoted_tilde():
    """BLOCKER 1. Bash does not expand a tilde inside double quotes, and the
    template quotes every path; the job died about two seconds into a
    whole-node allocation."""
    script = _script()
    assert 'source "$HOME/sprint-venv/bin/activate"' in script
    assert '"~' not in script
    assert cgp.DEFAULT_VENV.startswith("$HOME")


def test_a_tilde_anywhere_in_a_path_refuses_the_render():
    with pytest.raises(cgp.JobScriptRenderRefused, match="tilde"):
        _script(venv="~/sprint-venv")


def test_the_log_directory_is_created_at_render_time_and_in_the_body():
    """BLOCKER 3. SLURM opens --output BEFORE the body runs, so a mkdir in the
    body cannot save the first submission; the directory must exist at submit
    time, which is why the renderer creates it. An ABSOLUTE POSIX path, because
    a relative or variable-bearing one now refuses."""
    log_dir = "/tmp/cgp_render_probe/logs"
    shutil.rmtree("/tmp/cgp_render_probe", ignore_errors=True)
    try:
        script = _script(log_dir=log_dir, create_log_dir=True)
        assert Path(log_dir).is_dir()
        assert f'mkdir -p "{log_dir}"' in script
        assert f"#SBATCH --output={log_dir}/control_only_%j.out" in script
    finally:
        shutil.rmtree("/tmp/cgp_render_probe", ignore_errors=True)


# --- the pairing bind that killed 418403 at 34 seconds -----------------------


def test_the_short_key_is_translated_to_the_ratified_name_from_the_registry():
    """418403: the payload passed its SHORT key into load_backend, and the
    ratified long names appeared zero times in the file, so NO --pairing value
    worked. The mapping is DERIVED from ALL_TARGETS, never restated."""
    targets = cgp._import_targets()
    assert cgp.ratified_pairing_name("gemma") in targets.ALL_TARGETS
    assert cgp.ratified_pairing_name("qwen") in targets.ALL_TARGETS
    for short in cgp.SURVIVING_FEATURES:
        assert cgp.ratified_pairing_name(short) in targets.ALL_TARGETS
    # The ratified names are NOT written down in the PRODUCTION half: the only
    # place they may appear is the selfcheck, which asserts against them.
    source = (
        REPO_ROOT / "scripts" / "final_pairing" / "control_generation_payload.py"
    ).read_bytes().decode("utf-8")
    production = source.split("def _selfcheck(")[0]
    for ratified in targets.ALL_TARGETS:
        assert ratified not in production


def test_a_ratified_name_passes_through_unchanged():
    targets = cgp._import_targets()
    for ratified in targets.ALL_TARGETS:
        assert cgp.ratified_pairing_name(ratified) == ratified


def test_an_unmapped_pairing_refuses_at_render_time_not_at_runtime():
    with pytest.raises(cgp.JobScriptRenderRefused, match="ratified target"):
        cgp.ratified_pairing_name("llama")
    with pytest.raises(cgp.JobScriptRenderRefused):
        _script(pairing="llama")


def test_the_script_emits_the_ratified_name_and_never_the_short_key():
    script = _script()
    assert '--pairing "gemma-3-12b-it"' in script
    assert '--pairing "gemma"' not in script
    qwen = _script(pairing="qwen")
    assert '--pairing "qwen-3.5-27b"' in qwen
    assert '--pairing "qwen"' not in qwen


def test_the_run_path_translates_at_the_load_backend_boundary():
    source = (
        REPO_ROOT / "scripts" / "final_pairing" / "control_generation_payload.py"
    ).read_bytes().decode("utf-8")
    assert "pairing=ratified_pairing_name(args.pairing)" in source
    assert "pairing=args.pairing,\n        model_path" not in source


def test_every_identity_argument_is_validated_against_the_frozen_registry():
    """LA-B's lesson: the gates checked syntax, environment and imports, and
    none checked that the VALUES the render emits are ones the code accepts."""
    result = cgp.assert_identity_arguments_are_registered(
        pairing="gemma", layer=29, model_revision="a" * 40, sae_revision="b" * 40
    )
    assert result["pairing_ratified"] == "gemma-3-12b-it"
    assert result["registry"] == "final_pairing_targets.ALL_TARGETS"
    with pytest.raises(cgp.JobScriptRenderRefused, match="not the frozen layer"):
        cgp.assert_identity_arguments_are_registered(
            pairing="gemma", layer=12, model_revision="a" * 40, sae_revision="b" * 40
        )
    with pytest.raises(cgp.JobScriptRenderRefused, match="hexadecimal"):
        cgp.assert_identity_arguments_are_registered(
            pairing="gemma", layer=29, model_revision="main", sae_revision="b" * 40
        )


# --- PYTHONPATH, and the form is load-bearing --------------------------------


def test_pythonpath_is_prepended_and_never_assigned():
    """MEASURED both ways: running the payload by path puts its own directory on
    sys.path[0], so interplab does not import; a bare assignment fixes that and
    discards what module load arrow put there, breaking pyarrow."""
    script = _script()
    root = CLUSTER_PATHS["repo_root"]
    assert f'export PYTHONPATH="{root}${{PYTHONPATH:+:$PYTHONPATH}}"' in script
    assert f'export PYTHONPATH="{root}"\n' not in script
    assert cgp.TAMIA_ENVIRONMENT["pythonpath_form"] == "prepend"
    assert "MEASURED IN BOTH DIRECTIONS" in cgp.TAMIA_ENVIRONMENT["pythonpath_evidence"]


def test_a_render_without_a_repo_root_refuses():
    with pytest.raises(TypeError):
        cgp.job_script_text(
            pairing="gemma",
            model_path=CLUSTER_PATHS["model_path"],
            sae_path=CLUSTER_PATHS["sae_path"],
            cells=["en/f1"],
            seeds=[17],
            max_new_tokens=64,
            selection_rule="cell_positive_family_rows",
            out=CLUSTER_PATHS["out"],
            model_revision="a" * 40,
            sae_revision="b" * 40,
            platform="linux",
            create_log_dir=False,
        )


def test_a_variable_bearing_repo_root_refuses():
    with pytest.raises(cgp.JobScriptRenderRefused, match="NOTHING EXPANDS IT"):
        _script(repo_root="$SLURM_TMPDIR/repo")


def test_the_cli_refuses_to_render_without_a_repo_root(tmp_path):
    with pytest.raises(SystemExit):
        cgp.main(
            [
                "--write-job-script",
                str(tmp_path / "s.sh"),
                "--pairing",
                "gemma",
                "--model-revision",
                "a" * 40,
                "--sae-revision",
                "b" * 40,
            ]
        )


# --- --cpus-per-task --------------------------------------------------------


def test_the_script_requests_whole_node_cpus():
    """MEASURED: 418390/418391 got cpu=1 because the template set none, while
    418185 got cpu=32 on the same whole-node shape. One CPU starves tokenisation
    even once every import resolves."""
    script = _script()
    cpus = int(cgp.TAMIA_ENVIRONMENT["cpus_per_task"])
    assert cpus == 32
    assert f"#SBATCH --cpus-per-task={cpus}" in script
    assert "MEASURED" in cgp.TAMIA_ENVIRONMENT["cpus_evidence"]
    assert "418185" in cgp.TAMIA_ENVIRONMENT["cpus_evidence"]


# --- generation_settings_digest: RULING_16's containment ---------------------


def test_the_contract_is_the_calibration_lanes_and_this_payload_defines_none():
    """The coverage set, the canonical order and the hash are researcher's;
    this file computes no hash of its own."""
    contract = cgp.resolve_settings_contract()
    assert contract["source"] == "causal_calibration"
    assert contract["fields"] == tuple(name for name, *_ in cc.GENERATION_SETTINGS_FIELDS)
    assert contract["digest"] is cc.generation_settings_digest
    source = (
        REPO_ROOT / "scripts" / "final_pairing" / "control_generation_payload.py"
    ).read_bytes().decode("utf-8")
    assert "GENERATION_SETTINGS_FIELDS = " not in source
    assert "hashlib" not in source


def test_a_module_without_the_form_refuses_rather_than_inventing_one():
    with pytest.raises(cgp.SettingsContractUnavailable, match="researcher"):
        cgp.resolve_settings_contract(object())


def test_the_emission_fires_on_observed_settings(fixture_settings, fixture_digest):
    """THE FIRING DIRECTION: every covered field is observed, and the digest is
    the calibration lane's own function over them."""
    contract = cgp.resolve_settings_contract()
    assert set(contract["fields"]) <= set(fixture_settings)
    assert fixture_digest == cc.generation_settings_digest(fixture_settings)
    assert cgp.assert_settings_digest_bound(fixture_digest) == fixture_digest


def test_the_digest_moves_when_a_covered_setting_moves(fixture_settings):
    moved = {**fixture_settings, "layer": 38}
    assert cgp.compute_generation_settings_digest(moved) != cgp.compute_generation_settings_digest(
        fixture_settings
    )


@pytest.mark.parametrize("stub", ["", None, "f" * 64, "0" * 64, "z" * 64, "abc"])
def test_an_unset_or_placeholder_digest_refuses(stub):
    """THE REFUSING DIRECTION, including the calibration lane's own synthetic
    constant: a test double that escaped into an artifact would satisfy every
    hex check and bind nothing."""
    with pytest.raises(cgp.SettingsDigestUnbound):
        cgp.assert_settings_digest_bound(stub)


def test_a_missing_or_unset_covered_setting_refuses(fixture_settings):
    contract = cgp.resolve_settings_contract()
    dropped = {k: v for k, v in fixture_settings.items() if k != "dtype"}
    with pytest.raises(cgp.SettingsDigestUnbound, match="missing"):
        cgp.compute_generation_settings_digest(dropped, contract)
    with pytest.raises(cgp.SettingsDigestUnbound, match="unset"):
        cgp.compute_generation_settings_digest({**fixture_settings, "hook_name": ""}, contract)


def test_a_deliberately_omitted_setting_may_not_be_smuggled_in(fixture_settings):
    """The seed is EXCLUDED ON PURPOSE -- replicates differ by seed by design,
    so covering it would break the equality rather than strengthen it."""
    with pytest.raises(cgp.SettingsDigestUnbound, match="EXCLUDES ON PURPOSE"):
        cgp.compute_generation_settings_digest(
            {**fixture_settings, "seed": 17}, cgp.resolve_settings_contract()
        )


def test_the_observation_refuses_a_field_it_cannot_read():
    """A field the producer cannot observe is raised with researcher, never
    defaulted: a defaulted setting is one under which the two arms may differ."""
    contract = dict(cgp.resolve_settings_contract())
    contract["fields"] = contract["fields"] + ("a_setting_nobody_can_observe",)
    with pytest.raises(cgp.SettingsDigestUnbound, match="does not observe"):
        cgp.observe_generation_settings(
            backend=_FixtureBackend(),
            model_path="m",
            model_revision="r",
            sae_path="s",
            sae_revision="v",
            layer=29,
            dtype="bfloat16",
            max_new_tokens=64,
            selection_rule="cell_positive_family_rows",
            contract=contract,
        )


def test_the_seed_is_recorded_as_a_POLICY_and_never_as_a_value(fixture_settings):
    assert "seed" not in fixture_settings
    assert "NOT covered by this digest" in fixture_settings["seed_policy"]


def test_every_record_carries_the_digest_and_the_artifact_carries_the_field_map(
    fixture_records, fixture_settings, fixture_digest
):
    for record in fixture_records:
        assert record["generation_settings_digest"] == fixture_digest
    artifact = cgp.build_artifact(
        fixture_records,
        settings=fixture_settings,
        pairing="fixture",
        selection_rule="cell_positive_family_rows",
        model_reference="tests/fixtures/tiny_model",
        sae_reference="tests/fixtures/tiny_sae",
        dtype="float32",
        seeds=[17, 23],
    )
    assert artifact["generation_settings_digest"] == fixture_digest
    assert artifact["generation_settings"]["layer"] == 1
    # BOTH halves, per the contract: the consumer verifies a digest against its
    # own field map, which it cannot do from a digest alone.
    assert cc.generation_settings_digest(artifact["generation_settings"]) == fixture_digest


def test_an_artifact_whose_records_disagree_about_the_settings_refuses(fixture_records):
    mixed = [dict(record) for record in fixture_records]
    mixed[0]["generation_settings_digest"] = "c" * 64
    with pytest.raises(cgp.SettingsDigestUnbound, match="different generation_settings_digest"):
        cgp.build_artifact(
            mixed,
            pairing="fixture",
            selection_rule="cell_positive_family_rows",
            model_reference="m",
            sae_reference="s",
            dtype="float32",
            seeds=[17],
        )


def test_an_unbound_record_fails_the_artifact_consumability_check(fixture_records):
    artifact = cgp.build_artifact(
        fixture_records,
        pairing="fixture",
        selection_rule="cell_positive_family_rows",
        model_reference="m",
        sae_reference="s",
        dtype="float32",
        seeds=[17, 23],
    )
    artifact["records"][0]["generation_settings_digest"] = "f" * 64
    with pytest.raises(cgp.ArtifactNotConsumable, match="not bound to its generation settings"):
        cgp.assert_artifact_is_consumable(artifact)


# --- the shell-variable defect: half-fixed last round, fixed both ways now ---


def test_the_default_log_dir_is_absolute_and_carries_no_variable():
    """The entry LA-B measured wrong three ways: HOME/scratch does not exist,
    the renderer expands nothing so it created a literal directory named for the
    variable, and SLURM expands nothing in an SBATCH directive."""
    default = cgp.DEFAULT_LOG_DIR
    assert "$" not in default
    assert "~" not in default
    assert "{" not in default
    assert os.path.isabs(default)
    assert "scratch" not in default


@pytest.mark.parametrize(
    "bad",
    [
        "$HOME/scratch/final_pairing/logs",
        "${SCRATCH}/logs",
        "/home/user/$USER/logs",
        "${HOME}/logs",
    ],
)
def test_a_shell_variable_in_the_log_dir_refuses(bad):
    """THE REFUSAL FIRES. SLURM does not expand variables in SBATCH directives,
    and this file expands nothing either."""
    with pytest.raises(cgp.JobScriptRenderRefused, match="NOTHING EXPANDS IT"):
        cgp.assert_render_is_cluster_shaped({**CLUSTER_PATHS, "log_dir": bad}, platform="linux")


@pytest.mark.parametrize("key", ["out", "model_path", "sae_path"])
def test_a_shell_variable_in_any_other_emitted_path_refuses(key):
    """Swept across every path-shaped substitution, not just the one that bit."""
    with pytest.raises(cgp.JobScriptRenderRefused, match="NOTHING EXPANDS IT"):
        cgp.assert_render_is_cluster_shaped(
            {**CLUSTER_PATHS, key: "$SLURM_TMPDIR/thing"}, platform="linux"
        )


def test_the_refusal_does_NOT_fire_on_a_clean_absolute_path():
    """THE OTHER DIRECTION. A check that refuses everything is not a check."""
    result = cgp.assert_render_is_cluster_shaped(
        {**CLUSTER_PATHS, "log_dir": "/home/user/final_pairing_logs/control_only"},
        platform="linux",
    )
    assert result["platform"] == "linux"
    script = _script(log_dir="/home/user/final_pairing_logs/control_only")
    assert "#SBATCH --output=/home/user/final_pairing_logs/control_only/control_only_%j.out" in script


def test_the_venv_is_the_one_path_a_variable_is_legal_in():
    """Because its line IS shell-expanded and the HOME form was measured to
    resolve. A blanket refusal here would have broken the fix from last round."""
    assert cgp.DEFAULT_VENV.startswith("$HOME")
    assert "venv" in cgp._SHELL_EXPANDED_KEYS
    cgp.assert_render_is_cluster_shaped(CLUSTER_PATHS, platform="linux")
    assert 'source "$HOME/sprint-venv/bin/activate"' in _script()


def test_a_relative_log_dir_refuses():
    with pytest.raises(cgp.JobScriptRenderRefused, match="absolute POSIX path"):
        cgp.assert_render_is_cluster_shaped({**CLUSTER_PATHS, "log_dir": "logs"}, platform="linux")


def test_the_renderer_refuses_before_it_creates_a_variable_named_directory(tmp_path):
    """LA-B's probe created a literal directory named for the variable, because
    the renderer made it cheerfully. The refusal now runs BEFORE the mkdir."""
    monkey_dir = tmp_path / "$HOME" / "logs"
    with pytest.raises(cgp.JobScriptRenderRefused):
        _script(log_dir="$HOME/scratch/logs", create_log_dir=True)
    assert not monkey_dir.exists()
    assert list(tmp_path.iterdir()) == []


def test_every_path_shaped_template_substitution_is_checked():
    """THE SWEEP, MECHANICAL. Last round the mkdir moved and the variable
    stayed; this asserts that no path-shaped placeholder in the template is
    missing from the checked set, so the next one cannot slip through by being
    unlisted."""
    placeholders = set(re.findall(r"\{([a-z_]+)\}", cgp.JOB_SCRIPT_TEMPLATE))
    path_shaped = {name for name in placeholders if name.endswith(("path", "dir", "venv"))}
    path_shaped |= {"out", "payload"}
    assert path_shaped <= set(cgp.PATH_SHAPED_TEMPLATE_KEYS), (
        f"unchecked path-shaped substitution(s): {sorted(path_shaped - set(cgp.PATH_SHAPED_TEMPLATE_KEYS))}"
    )
    for key in cgp.PATH_SHAPED_TEMPLATE_KEYS:
        assert key in placeholders


def test_the_record_carries_the_three_new_measurements():
    env = cgp.TAMIA_ENVIRONMENT
    assert "MEASURED" in env["home_scratch_does_not_exist"]
    assert "MEASURED" in env["sbatch_does_not_expand_variables"]
    assert "MEASURED" in env["renderer_expands_nothing"]
    assert "no scratch directory under HOME" in env["home_scratch_does_not_exist"]
    assert env["log_dir_must_be"].startswith("an ABSOLUTE path")


def test_nothing_in_the_payload_expands_a_variable_behind_the_refusal():
    """The refusal is the fix, not an expansion: expanding would paper over a
    caller's wrong value instead of surfacing it."""
    source = (
        REPO_ROOT / "scripts" / "final_pairing" / "control_generation_payload.py"
    ).read_bytes().decode("utf-8")
    # The CALLS, not the words: the record names both to explain why neither is
    # used, and a substring test on the prose would forbid saying so.
    assert "expandvars(" not in source
    assert "expanduser(" not in source
    assert "os.path.expandvars" not in source


def test_the_frozen_layer_is_emitted_and_imported_not_restated():
    """BLOCKER 4, the silent one: load_backend accepts layer=None and then runs
    at a different layer, producing a result rather than a crash."""
    discovery = gi._import_discovery_module()
    assert cgp.frozen_layer_for("gemma") == int(discovery.PRIMARY_CONFIGURATION.gemma_layer)
    assert cgp.frozen_layer_for("qwen") == int(discovery.PRIMARY_CONFIGURATION.qwen_layer)
    assert f"--layer {discovery.PRIMARY_CONFIGURATION.gemma_layer}" in _script()
    assert f"--layer {discovery.PRIMARY_CONFIGURATION.qwen_layer}" in _script(pairing="qwen")
    source = (
        REPO_ROOT / "scripts" / "final_pairing" / "control_generation_payload.py"
    ).read_bytes().decode("utf-8")
    assert "PRIMARY_CONFIGURATION" in source


def test_an_unknown_pairing_refuses_rather_than_rendering_layer_none():
    with pytest.raises(cgp.JobScriptRenderRefused, match="layer=None"):
        _script(pairing="llama")


# --- the three smaller items ------------------------------------------------


def test_the_time_limit_default_is_safe_and_a_low_one_refuses():
    """ITEM 5. Submitting at the old default reproduces 413287's timeout."""
    assert cgp.DEFAULT_TIME_LIMIT == "06:00:00"
    assert "--time=06:00:00" in _script()
    with pytest.raises(cgp.JobScriptRenderRefused, match="below the 6 h floor"):
        _script(time_limit="01:00:00")
    with pytest.raises(cgp.JobScriptRenderRefused, match="HH:MM:SS"):
        _script(time_limit="6h")


def test_the_plan_reports_the_measured_precedent_and_not_the_false_claim():
    """ITEM 6. Generation DID run on Qwen3.5-27B in job 416453."""
    plan = cgp.payload_requirements(
        pairing="qwen",
        cells=["en/f1", "en/f2", "en/f3", "fr/f1", "fr/f2", "fr/f3"],
        prompts_per_cell=20,
        seeds=[17, 23],
        max_new_tokens=64,
    )
    assert "wall_time_is_not_asserted" not in plan
    block = plan["wall_time_from_the_measured_precedent"]
    assert block["measured"]["job"] == 416453
    assert block["measured"]["tokens_per_second"] == 13.9
    assert "no generation has ever run" not in json.dumps(plan)
    # 61,440 tokens at 13.9 tok/s is ~74 min, inside LA-B's ~76 min figure.
    assert 60.0 < block["applied_to_this_grid"]["qwen_minutes"] < 90.0
    assert "ZERO files" in block["applied_to_this_grid"]["gemma_is_extrapolated"]


def test_both_snapshot_revisions_are_required_and_emitted():
    """ITEM 7. Both 415590 and 416453 passed real values; load_backend accepts
    None, so an unasserted digest means a wrong snapshot loads silently."""
    script = _script()
    assert '--model-revision "' + "a" * 40 in script
    assert '--sae-revision "' + "b" * 40 in script
    with pytest.raises(cgp.JobScriptRenderRefused, match="empty"):
        _script(model_revision="")
    with pytest.raises(cgp.JobScriptRenderRefused, match="empty"):
        _script(sae_revision="   ")


def test_the_run_path_passes_the_revisions_and_a_real_layer():
    source = (
        REPO_ROOT / "scripts" / "final_pairing" / "control_generation_payload.py"
    ).read_bytes().decode("utf-8")
    assert "expected_model_revision=args.model_revision" in source
    assert "expected_sae_revision=args.sae_revision" in source
    assert "expected_model_revision=None" not in source
    assert "layer=args.layer if args.layer is not None else frozen_layer_for(" in source


# --- the rule: render on the cluster, never on Windows -----------------------


def test_a_windows_render_is_refused_rather_than_emitted():
    """THE RULE, ENCODED AS A REFUSAL. LA-B's local render mangled every path
    through MSYS translation; staging it would have shipped a broken script."""
    with pytest.raises(cgp.JobScriptRenderRefused, match=r"MUST BE\s+RENDERED ON THE CLUSTER"):
        cgp.assert_render_is_cluster_shaped(CLUSTER_PATHS, platform="win32")
    with pytest.raises(cgp.JobScriptRenderRefused):
        _script(platform="win32")


@pytest.mark.parametrize(
    "bad",
    [
        "C:/Program Files/Git/scratch/out.json",
        "c:/scratch/out.json",
        "/c/Program Files/Git/usr/out.json",
        "scratch" + chr(92) + "out.json",
    ],
)
def test_every_windows_mangled_path_shape_is_refused(bad):
    with pytest.raises(cgp.JobScriptRenderRefused):
        cgp.assert_render_is_cluster_shaped({**CLUSTER_PATHS, "out": bad}, platform="linux")


def test_a_cluster_shaped_render_is_accepted_and_records_what_it_checked():
    result = cgp.assert_render_is_cluster_shaped(CLUSTER_PATHS, platform="linux")
    assert result["platform"] == "linux"
    assert result["paths_checked"] == sorted(CLUSTER_PATHS)


def test_the_cli_refuses_to_write_a_script_on_this_windows_machine(tmp_path):
    """The CLI reads the real platform, so on this machine it REFUSES -- and on
    a login node it would not. Asserted from whichever side we are on."""
    argv = [
        "--write-job-script",
        str(tmp_path / "control_only.sh"),
        "--pairing",
        "gemma",
        "--model-revision",
        "a" * 40,
        "--sae-revision",
        "b" * 40,
        "--model-path",
        CLUSTER_PATHS["model_path"],
        "--sae-path",
        CLUSTER_PATHS["sae_path"],
        "--out",
        CLUSTER_PATHS["out"],
        "--log-dir",
        str(tmp_path / "logs").replace(chr(92), "/"),
        "--repo-root",
        CLUSTER_PATHS["repo_root"],
    ]
    if sys.platform.startswith("win"):
        with pytest.raises(cgp.JobScriptRenderRefused):
            cgp.main(argv)
        assert not (tmp_path / "control_only.sh").exists()
    else:  # pragma: no cover - exercised on the login node, not here
        assert cgp.main(argv) == 0
        assert b"\r\n" not in (tmp_path / "control_only.sh").read_bytes()


def test_the_cli_refuses_to_render_without_the_revisions(tmp_path):
    with pytest.raises(SystemExit):
        cgp.main(["--write-job-script", str(tmp_path / "s.sh"), "--pairing", "gemma"])


# --- security posture, unchanged and still asserted --------------------------


def test_the_job_script_unsets_the_token_and_runs_offline():
    script = _script()
    assert "unset HF_TOKEN" in script
    assert "unset HUGGING_FACE_HUB_TOKEN" in script
    assert "HF_HUB_OFFLINE=1" in script
    assert "TRANSFORMERS_OFFLINE=1" in script


def test_the_job_script_has_no_trace_no_env_dump_and_no_repo_id():
    script = _script()
    assert "set -x" not in script
    assert "\nenv\n" not in script
    assert "huggingface.co" not in script
    assert "--repo-id" not in script
    assert "$HF_TOKEN" not in script


def test_the_rendered_script_is_lf_only_and_starts_with_a_shebang(tmp_path):
    path = tmp_path / "control_only.sh"
    path.write_bytes(_script().encode("utf-8"))
    raw = path.read_bytes()
    assert b"\r\n" not in raw
    assert raw.startswith(b"#!/bin/bash")


def test_the_recorded_cluster_description_carries_its_evidence():
    """The record is what the checks assert against, so it must say what was
    MEASURED and by whom rather than being a list of preferences."""
    env = cgp.TAMIA_ENVIRONMENT
    assert "LA-B" in env["recorded_by"]
    for key in ("module_evidence", "tilde_evidence", "log_dir_evidence", "windows_render_evidence"):
        assert "MEASURED" in env[key]
    assert env["measured_generation_precedent"]["job"] == 416453
    assert env["frozen_layers"] == {"gemma": 29, "qwen": 38}


def test_the_plan_mode_states_what_a_job_needs_and_submits_nothing(capsys):
    assert cgp.main(["--plan", "--cells", "en/f1,en/f2", "--seeds", "17,23"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["generation_count"] == payload["prompts_per_cell"] * 2 * 4 * 2
    assert payload["authorization"].startswith("NOT REQUESTED")
    assert "wall_time_from_the_measured_precedent" in payload


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


class _FixtureBackend:
    """The minimum an observation needs: a hook label and device objects."""

    hook_label = "fixture.blocks.1.hook_resid_post"

    def device_objects(self):
        return {"model": None, "sae": None}


@pytest.fixture(scope="module")
def fixture_settings():
    """The contract's own fields, observed from a fixture-scale run."""
    return cgp.observe_generation_settings(
        backend=_FixtureBackend(),
        model_path="tests/fixtures/tiny_model",
        model_revision="a" * 40,
        sae_path="tests/fixtures/tiny_sae",
        sae_revision="b" * 40,
        layer=1,
        dtype="float32",
        max_new_tokens=4,
        selection_rule="cell_positive_family_rows",
        contract=cgp.resolve_settings_contract(),
    )


@pytest.fixture(scope="module")
def fixture_digest(fixture_settings):
    return cgp.compute_generation_settings_digest(fixture_settings)


@pytest.fixture(scope="module")
def fixture_records(real_model, real_sae, fixture_digest):
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
        settings_digest=fixture_digest,
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
