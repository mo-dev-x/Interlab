"""Tests for scripts/final_pairing/final_pairing_one_allocation_generation.py
(stages 1-3 of protocols/final_pairing/v1/one_allocation_dose_generation.json,
extended by protocols/final_pairing/v1/generation_settings.json).

Manifest shape matches Engineer 3's real, enforcing validator
(`scripts/concept_bundle_publish.py` commit 67ad4ef): ONE PHYSICAL
MANIFEST per (run_id, configuration, concept_id, pairing_id, direction),
flat top-level identity fields, and file entries with a SCALAR `seed`
and `selection_status` (never a nullable `label`). `dose-check`/
`dose_generation_problems` (this module's ground truth at ac9ea40) no
longer exists on that branch -- superseded by `binding-check`.

CPU-only, fake-backend -- same convention as
test_final_pairing_concept_discovery.py: no real Gemma/Qwen weights exist
on any machine in this investigation.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "final_pairing"))

import final_pairing_concept_discovery as d  # noqa: E402
import final_pairing_fakes as fakes  # noqa: E402
import final_pairing_one_allocation_generation as one  # noqa: E402

CONCEPT_FEATURE = 3


# ---------------------------------------------------------------------------
# Structural hard stop: no Lodestar/judge import is reachable from this
# module's source, at all -- a source-level scan, not a runtime behavior
# check, so a future added import cannot silently regress this guarantee.
# ---------------------------------------------------------------------------


def test_module_source_never_imports_lodestar_or_the_judge_module():
    """AST-level, not a raw substring scan: the module's own docstring
    NAMES `lodestar`/`final_pairing_causal_judge` to explain this hard
    stop, so a substring search would false-positive on the explanation
    itself. Walking every real `import`/`from ... import` statement (at
    module scope AND inside every function body) is what actually proves
    no judge call is reachable."""
    import ast

    source = (REPO_ROOT / "scripts" / "final_pairing" / "final_pairing_one_allocation_generation.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
    forbidden = {"lodestar", "final_pairing_causal_judge"}
    hits = {m for m in imported_modules if any(m == f or m.startswith(f + ".") for f in forbidden)}
    assert not hits, f"forbidden import(s) reachable from this module: {hits}"


def test_validate_one_allocation_protocol_hash_passes_against_the_real_frozen_artifact():
    digest = one.validate_one_allocation_protocol_hash(REPO_ROOT)
    assert digest == one.ONE_ALLOCATION_PROTOCOL_SHA256


def test_validate_one_allocation_protocol_hash_refuses_a_tampered_copy(tmp_path):
    tampered_path = tmp_path / "protocols" / "final_pairing" / "v1" / "one_allocation_dose_generation.json"
    tampered_path.parent.mkdir(parents=True)
    tampered_path.write_text('{"protocol_version": "tampered"}', encoding="utf-8")
    with pytest.raises(one.TransferVerificationFailed, match="altered or unpinned"):
        one.validate_one_allocation_protocol_hash(tmp_path)


def test_validate_generation_settings_protocol_hash_passes_against_the_real_frozen_artifact():
    digest = one.validate_generation_settings_protocol_hash(REPO_ROOT)
    assert digest == one.GENERATION_SETTINGS_PROTOCOL_SHA256


def test_validate_generation_settings_protocol_hash_refuses_a_tampered_copy(tmp_path):
    tampered_path = tmp_path / "protocols" / "final_pairing" / "v1" / "generation_settings.json"
    tampered_path.parent.mkdir(parents=True)
    tampered_path.write_text("{}", encoding="utf-8")
    with pytest.raises(one.TransferVerificationFailed, match="altered or unpinned"):
        one.validate_generation_settings_protocol_hash(tmp_path)


# ---------------------------------------------------------------------------
# ADDITION_1: seed derivation and explicit disjointness verification.
# Seeds are salted by namespace/locale but deliberately NOT by dose, so
# every dose (and the one shared control) at a given (prompt, repeat)
# reuses the SAME seed -- generation_settings.json's SAME_SEED_IS_MANDATORY.
# ---------------------------------------------------------------------------


def test_derive_seed_is_deterministic():
    kwargs = dict(namespace="sweep", concept_id="cheese", pairing_id="gemma-3-12b-it", direction="amplify",
                  locale="en", prompt_index=0, repeat_index=0)
    assert one.derive_seed(**kwargs) == one.derive_seed(**kwargs)


def test_derive_seed_differs_across_namespace_even_with_identical_other_fields():
    kwargs = dict(concept_id="cheese", pairing_id="gemma-3-12b-it", direction="amplify",
                  locale="en", prompt_index=0, repeat_index=0)
    assert one.derive_seed(namespace="sweep", **kwargs) != one.derive_seed(namespace="confirmation", **kwargs)


def test_derive_seed_differs_across_locale_even_with_identical_other_fields():
    kwargs = dict(namespace="sweep", concept_id="cheese", pairing_id="gemma-3-12b-it", direction="amplify",
                  prompt_index=0, repeat_index=0)
    assert one.derive_seed(locale="en", **kwargs) != one.derive_seed(locale="fr", **kwargs)


def test_derive_seed_has_no_dose_parameter_at_all():
    """Structural: dose is not in derive_seed's signature, so it is
    impossible to accidentally salt by it again."""
    import inspect

    assert "dose" not in inspect.signature(one.derive_seed).parameters


def test_derive_seeds_returns_one_seed_per_prompt_times_repeat_in_order():
    seeds = one.derive_seeds(
        namespace="sweep", concept_id="cheese", pairing_id="gemma-3-12b-it", direction="amplify",
        locale="en", n_prompts=3, n_repeats=2,
    )
    assert len(seeds) == 6
    assert seeds == [
        one.derive_seed(namespace="sweep", concept_id="cheese", pairing_id="gemma-3-12b-it", direction="amplify",
                         locale="en", prompt_index=p, repeat_index=r)
        for p in range(3) for r in range(2)
    ]


def test_assert_seed_sets_disjoint_passes_on_disjoint_sets():
    one.assert_seed_sets_disjoint([1, 2, 3], [4, 5, 6])  # must not raise


def test_assert_seed_sets_disjoint_raises_on_an_explicit_collision():
    with pytest.raises(one.SeedCollisionError, match="intersect at seed"):
        one.assert_seed_sets_disjoint([1, 2, 3], [3, 4, 5])


# ---------------------------------------------------------------------------
# Dose grids: Amplify (5 distinct clamp values), Suppress (4 descending
# clamp fractions + ABLATE as the fifth point).
# ---------------------------------------------------------------------------


def test_build_amplify_dose_grid_accepts_five_distinct_values():
    grid = one.build_amplify_dose_grid((0.25, 0.5, 1.0, 2.0, 4.0))
    assert len(grid) == 5
    assert all(spec.kind == "clamp" for spec in grid)


def test_build_amplify_dose_grid_rejects_wrong_count():
    with pytest.raises(ValueError, match="exactly 5 points"):
        one.build_amplify_dose_grid((0.5, 1.0))


def test_build_amplify_dose_grid_rejects_duplicate_values():
    with pytest.raises(ValueError, match="must be distinct"):
        one.build_amplify_dose_grid((0.5, 0.5, 1.0, 2.0, 4.0))


def test_build_suppress_dose_grid_appends_ablate_as_the_fifth_point():
    grid = one.build_suppress_dose_grid((4.0, 2.0, 1.0, 0.5))
    assert len(grid) == 5
    assert [spec.kind for spec in grid] == ["clamp", "clamp", "clamp", "clamp", "ablate"]
    assert grid[-1].value_in_max_units is None


def test_build_suppress_dose_grid_rejects_non_descending_fractions():
    with pytest.raises(ValueError, match="strictly descending"):
        one.build_suppress_dose_grid((1.0, 2.0, 0.5, 0.25))


def test_build_suppress_dose_grid_rejects_wrong_count():
    with pytest.raises(ValueError, match="exactly 4 points"):
        one.build_suppress_dose_grid((1.0, 0.5))


def test_dose_spec_rejects_a_value_on_an_ablate_dose():
    with pytest.raises(ValueError, match="carries no value_in_max_units"):
        one.DoseSpec(kind="ablate", value_in_max_units=1.0)


def test_dose_spec_requires_a_value_on_a_clamp_dose():
    with pytest.raises(ValueError, match="requires value_in_max_units"):
        one.DoseSpec(kind="clamp")


def test_dose_label_uses_ablate_and_x_suffixed_values():
    assert one._dose_label(one.DoseSpec(kind="ablate")) == "ABLATE"
    assert one._dose_label(one.DoseSpec(kind="clamp", value_in_max_units=1.0)) == "1.0x"
    assert one._dose_label(one.DoseSpec(kind="clamp", value_in_max_units=0.5)) == "0.5x"


# ---------------------------------------------------------------------------
# ADDITION_4: wall-time preflight -- NOT_ATTEMPTED, never a raise. Volumes
# now include bilingual generation and the control arm.
# ---------------------------------------------------------------------------


def test_generations_per_concept_is_1800():
    # steered: 2 directions x 2 locales x 5 doses x (15 + 60) = 1500
    # control: 2 directions x 2 locales x (15 + 60) = 300
    assert one.STEERED_GENERATIONS_PER_CONCEPT == 1500
    assert one.CONTROL_GENERATIONS_PER_CONCEPT == 300
    assert one.GENERATIONS_PER_CONCEPT == 1800


def test_dose_files_per_concept_is_48():
    # steered files: 2 directions x 2 locales x 5 doses x 2 purposes = 40
    # control files: 2 directions x 2 locales x 2 purposes = 8
    assert one.STEERED_DOSE_FILES_PER_CONCEPT == 40
    assert one.CONTROL_FILES_PER_CONCEPT == 8
    assert one.DOSE_FILES_PER_CONCEPT == 48


def test_readiness_attempts_when_remaining_time_covers_one_concept():
    result = one.assess_concept_generation_readiness(
        remaining_wall_time_seconds=one.GENERATIONS_PER_CONCEPT * 2.0, seconds_per_generation=2.0,
    )
    assert result.attempt is True


def test_readiness_refuses_when_remaining_time_cannot_cover_one_concept():
    result = one.assess_concept_generation_readiness(
        remaining_wall_time_seconds=10.0, seconds_per_generation=2.0,
    )
    assert result.attempt is False
    assert "NOT_ATTEMPTED" in result.detail


# ---------------------------------------------------------------------------
# Fixed, G-A/B/C-independent causal generation order (generation_settings.
# json section 4).
# ---------------------------------------------------------------------------


def test_order_concepts_for_causal_generation_orders_by_the_frozen_sequence():
    ordered = one.order_concepts_for_causal_generation(["jazz", "formal_register", "cheese"])
    assert ordered == ["formal_register", "cheese", "jazz"]


def test_order_concepts_for_causal_generation_skips_absent_concepts_without_reordering():
    # chess (position 3) failed G-A/B/C and is absent; jazz (4) and courtroom (5) still follow in order.
    ordered = one.order_concepts_for_causal_generation(["courtroom", "jazz", "cheese"])
    assert ordered == ["cheese", "jazz", "courtroom"]


def test_order_concepts_for_causal_generation_political_framing_is_always_last():
    ordered = one.order_concepts_for_causal_generation(["political_framing", "cheese", "formal_register"])
    assert ordered[-1] == "political_framing"


def test_order_concepts_for_causal_generation_rejects_an_unknown_concept_id():
    with pytest.raises(ValueError, match="not in the frozen CAUSAL_GENERATION_ORDER"):
        one.order_concepts_for_causal_generation(["not-a-real-concept"])


# ---------------------------------------------------------------------------
# generate_dose_file / generate_control_file / generate_concept_complete:
# real file I/O, real per-file SHA-256, against the fake CPU backend (real
# run_intervention/run_baseline_generation, real torch tensors -- no GPU,
# no real weights, same as the rest of this project's test suite).
# ---------------------------------------------------------------------------


def test_generate_dose_file_writes_exactly_one_file_covering_every_prompt_and_repeat(tmp_path):
    backend = fakes.make_fake_gemma_backend()
    corpus_max = d.corpus_max_per_feature(backend, ["some background text about cheese and other foods"])
    dose = one.DoseSpec(kind="clamp", value_in_max_units=1.0)
    prompts = [f"prompt {i}" for i in range(3)]
    seeds = one.derive_seeds(
        namespace="sweep", concept_id="cheese", pairing_id=backend.pairing, direction="amplify",
        locale="en", n_prompts=3, n_repeats=2,
    )
    record = one.generate_dose_file(
        backend, [CONCEPT_FEATURE], dose=dose, corpus_max=corpus_max, positions="all",
        prompts=prompts, purpose="sweep", n_repeats=2, seeds=seeds, max_new_tokens=2,
        out_dir=tmp_path, concept_id="cheese", pairing_id=backend.pairing, direction="amplify",
        locale="en", control_ref="control/sweep_en.json",
    )
    written = list(tmp_path.glob("*.json"))
    assert len(written) == 1
    assert record.path == str(written[0])
    assert record.sha256 == d.compute_file_sha256(written[0])
    assert record.n_prompts == 3
    assert record.n_repeats == 2
    assert len(record.seeds) == 6  # 3 prompts x 2 repeats
    assert record.seeds == seeds
    assert record.dose_label in Path(record.path).name
    assert record.control_ref == "control/sweep_en.json"


def test_generate_dose_file_rejects_a_seed_list_of_the_wrong_length(tmp_path):
    backend = fakes.make_fake_gemma_backend()
    corpus_max = d.corpus_max_per_feature(backend, ["background"])
    with pytest.raises(ValueError, match="exactly one seed per"):
        one.generate_dose_file(
            backend, [CONCEPT_FEATURE], dose=one.DoseSpec(kind="clamp", value_in_max_units=1.0),
            corpus_max=corpus_max, positions="all", prompts=["a", "b"], purpose="sweep", n_repeats=1,
            seeds=[1], max_new_tokens=1, out_dir=tmp_path, concept_id="cheese", pairing_id=backend.pairing,
            direction="amplify", locale="en", control_ref="x.json",
        )


def test_generate_control_file_writes_one_file_with_no_dose_and_no_control_ref(tmp_path):
    backend = fakes.make_fake_gemma_backend()
    corpus_max = d.corpus_max_per_feature(backend, ["background"])
    prompts = [f"prompt {i}" for i in range(3)]
    seeds = one.derive_seeds(
        namespace="sweep", concept_id="cheese", pairing_id=backend.pairing, direction="amplify",
        locale="en", n_prompts=3, n_repeats=1,
    )
    record = one.generate_control_file(
        backend, corpus_max=corpus_max, positions="all", prompts=prompts, purpose="sweep", n_repeats=1,
        seeds=seeds, max_new_tokens=2, out_dir=tmp_path, concept_id="cheese", pairing_id=backend.pairing,
        direction="amplify", locale="en",
    )
    assert record.purpose == "control"
    assert record.dose_label is None
    assert record.dose_kind is None
    assert record.control_ref is None
    assert record.seeds == seeds
    entry = record.to_manifest_file_entry()
    assert "dose" not in entry
    assert "control_ref" not in entry


def test_generate_control_file_uses_the_same_seed_as_a_matching_dose_file(tmp_path):
    """The single most important rule in generation_settings.json's
    control-arm section: SAME_SEED_IS_MANDATORY."""
    backend = fakes.make_fake_gemma_backend()
    corpus_max = d.corpus_max_per_feature(backend, ["background"])
    prompts = [f"prompt {i}" for i in range(4)]
    seeds = one.derive_seeds(
        namespace="confirmation", concept_id="cheese", pairing_id=backend.pairing, direction="suppress",
        locale="fr", n_prompts=4, n_repeats=1,
    )
    control = one.generate_control_file(
        backend, corpus_max=corpus_max, positions="all", prompts=prompts, purpose="confirmation", n_repeats=1,
        seeds=seeds, max_new_tokens=2, out_dir=tmp_path / "control", concept_id="cheese",
        pairing_id=backend.pairing, direction="suppress", locale="fr",
    )
    dose_record = one.generate_dose_file(
        backend, [CONCEPT_FEATURE], dose=one.DoseSpec(kind="clamp", value_in_max_units=2.0),
        corpus_max=corpus_max, positions="all", prompts=prompts, purpose="confirmation", n_repeats=1,
        seeds=seeds, max_new_tokens=2, out_dir=tmp_path / "doses", concept_id="cheese",
        pairing_id=backend.pairing, direction="suppress", locale="fr", control_ref=control.path,
    )
    assert dose_record.seeds == control.seeds == seeds


def test_generate_control_file_rejects_a_seed_list_of_the_wrong_length(tmp_path):
    backend = fakes.make_fake_gemma_backend()
    corpus_max = d.corpus_max_per_feature(backend, ["background"])
    with pytest.raises(ValueError, match="exactly one seed per"):
        one.generate_control_file(
            backend, corpus_max=corpus_max, positions="all", prompts=["a", "b"], purpose="sweep", n_repeats=1,
            seeds=[1], max_new_tokens=1, out_dir=tmp_path, concept_id="cheese", pairing_id=backend.pairing,
            direction="amplify", locale="en",
        )


def _bilingual_prompts(n: int, tag: str) -> dict[str, list[str]]:
    return {locale: [f"{tag} {locale} prompt {i}" for i in range(n)] for locale in one.LOCALES}


def _amplify_and_suppress_prompts():
    return (
        _bilingual_prompts(one.SWEEP_PROMPTS_PER_DIRECTION, "amplify-sweep"),
        _bilingual_prompts(one.CONFIRMATION_PROMPTS_PER_DIRECTION, "amplify-confirmation"),
        _bilingual_prompts(one.SWEEP_PROMPTS_PER_DIRECTION, "suppress-sweep"),
        _bilingual_prompts(one.CONFIRMATION_PROMPTS_PER_DIRECTION, "suppress-confirmation"),
    )


def _generate_complete_concept(tmp_path, **overrides):
    backend = fakes.make_fake_gemma_backend()
    corpus_max = d.corpus_max_per_feature(backend, ["background text"])
    amplify_sweep, amplify_conf, suppress_sweep, suppress_conf = _amplify_and_suppress_prompts()
    kwargs = dict(
        concept_id="cheese", pairing_id=backend.pairing, corpus_max=corpus_max, positions="all", out_dir=tmp_path,
        amplify_dose_grid=one.build_amplify_dose_grid((0.25, 0.5, 1.0, 2.0, 4.0)),
        suppress_dose_grid=one.build_suppress_dose_grid((4.0, 2.0, 1.0, 0.5)),
        amplify_sweep_prompts=amplify_sweep, amplify_confirmation_prompts=amplify_conf,
        suppress_sweep_prompts=suppress_sweep, suppress_confirmation_prompts=suppress_conf,
        max_new_tokens=1,
    )
    kwargs.update(overrides)
    return backend, one.generate_concept_complete(backend, [CONCEPT_FEATURE], **kwargs)


def test_generate_concept_complete_produces_48_files_with_disjoint_seeds(tmp_path):
    _backend, records = _generate_complete_concept(tmp_path)
    assert len(records) == one.DOSE_FILES_PER_CONCEPT == 48
    assert len({r.path for r in records}) == 48  # one file per cell, never shared
    steered_generations = sum(len(r.seeds) for r in records if r.purpose != "control")
    control_generations = sum(len(r.seeds) for r in records if r.purpose == "control")
    assert steered_generations == one.STEERED_GENERATIONS_PER_CONCEPT == 1500
    assert control_generations == one.CONTROL_GENERATIONS_PER_CONCEPT == 300


def test_generate_concept_complete_covers_both_locales_and_both_directions(tmp_path):
    _backend, records = _generate_complete_concept(tmp_path)
    assert {r.direction for r in records} == {"amplify", "suppress"}
    assert {r.locale for r in records} == {"en", "fr"}
    assert {r.purpose for r in records} == {"sweep", "confirmation", "control"}


def test_generate_concept_complete_every_dose_file_shares_seeds_with_its_purposes_control(tmp_path):
    _backend, records = _generate_complete_concept(tmp_path)
    controls_by_path = {r.path: r for r in records if r.purpose == "control"}
    for r in records:
        if r.purpose == "control":
            continue
        control = controls_by_path[r.control_ref]
        assert r.seeds == control.seeds
        assert (control.direction, control.locale) == (r.direction, r.locale)


def test_generate_concept_complete_rejects_a_locale_missing_from_the_prompt_dict(tmp_path):
    backend = fakes.make_fake_gemma_backend()
    corpus_max = d.corpus_max_per_feature(backend, ["background text"])
    amplify_sweep, amplify_conf, suppress_sweep, suppress_conf = _amplify_and_suppress_prompts()
    del amplify_sweep["fr"]
    with pytest.raises(ValueError, match="fr"):
        one.generate_concept_complete(
            backend, [CONCEPT_FEATURE], concept_id="cheese", pairing_id=backend.pairing,
            corpus_max=corpus_max, positions="all", out_dir=tmp_path,
            amplify_dose_grid=one.build_amplify_dose_grid((0.25, 0.5, 1.0, 2.0, 4.0)),
            suppress_dose_grid=one.build_suppress_dose_grid((4.0, 2.0, 1.0, 0.5)),
            amplify_sweep_prompts=amplify_sweep, amplify_confirmation_prompts=amplify_conf,
            suppress_sweep_prompts=suppress_sweep, suppress_confirmation_prompts=suppress_conf, max_new_tokens=1,
        )


def test_generate_concept_complete_resumes_without_recomputing_completed_cells(tmp_path):
    backend = fakes.make_fake_gemma_backend()
    corpus_max = d.corpus_max_per_feature(backend, ["background text"])
    amplify_sweep, amplify_conf, suppress_sweep, suppress_conf = _amplify_and_suppress_prompts()
    progress_path = tmp_path / "progress.jsonl"
    kwargs = dict(
        concept_id="cheese", pairing_id=backend.pairing, corpus_max=corpus_max, positions="all", out_dir=tmp_path,
        amplify_dose_grid=one.build_amplify_dose_grid((0.25, 0.5, 1.0, 2.0, 4.0)),
        suppress_dose_grid=one.build_suppress_dose_grid((4.0, 2.0, 1.0, 0.5)),
        amplify_sweep_prompts=amplify_sweep, amplify_confirmation_prompts=amplify_conf,
        suppress_sweep_prompts=suppress_sweep, suppress_confirmation_prompts=suppress_conf, max_new_tokens=1,
    )
    first = one.generate_concept_complete(backend, [CONCEPT_FEATURE], progress=d.ProgressLog(progress_path), **kwargs)
    assert len(first) == 48

    calls = {"n": 0}
    original_dose = one.generate_dose_file
    original_control = one.generate_control_file

    def spy_dose(*args, **kwargs2):
        calls["n"] += 1
        return original_dose(*args, **kwargs2)

    def spy_control(*args, **kwargs2):
        calls["n"] += 1
        return original_control(*args, **kwargs2)

    one.generate_dose_file = spy_dose
    one.generate_control_file = spy_control
    try:
        second = one.generate_concept_complete(
            backend, [CONCEPT_FEATURE], progress=d.ProgressLog(progress_path), **kwargs
        )
    finally:
        one.generate_dose_file = original_dose
        one.generate_control_file = original_control
    assert calls["n"] == 0
    assert len(second) == 48


# ---------------------------------------------------------------------------
# Manifest write/verify (stage 2 tail + stage 3 transfer verification) and
# the post-selection status stamp. Flat schema, matching the real consumer
# at commit 67ad4ef: no nested model/sae/concepts objects, no self-hash.
# ---------------------------------------------------------------------------


def _tiny_records(tmp_path, *, direction="amplify", purpose="confirmation"):
    backend = fakes.make_fake_gemma_backend()
    corpus_max = d.corpus_max_per_feature(backend, ["background text"])
    records = []
    control_seeds = one.derive_seeds(
        namespace=purpose, concept_id="cheese", pairing_id=backend.pairing, direction=direction,
        locale="en", n_prompts=2, n_repeats=1,
    )
    control = one.generate_control_file(
        backend, corpus_max=corpus_max, positions="all", prompts=[f"prompt {i}" for i in range(2)],
        purpose=purpose, n_repeats=1, seeds=control_seeds, max_new_tokens=1, out_dir=tmp_path,
        concept_id="cheese", pairing_id=backend.pairing, direction=direction, locale="en",
    )
    records.append(control)
    for value in (1.0, 2.0, 3.0):
        dose = one.DoseSpec(kind="clamp", value_in_max_units=value)
        records.append(one.generate_dose_file(
            backend, [CONCEPT_FEATURE], dose=dose, corpus_max=corpus_max, positions="all",
            prompts=[f"prompt {i}" for i in range(2)], purpose=purpose, n_repeats=1, seeds=control_seeds,
            max_new_tokens=1, out_dir=tmp_path, concept_id="cheese", pairing_id=backend.pairing,
            direction=direction, locale="en", control_ref=control.path,
        ))
    return records


_PAIRING_ID_GEMMA = "google/gemma-3-12b-it+google/gemma-scope-2-12b-it"

_MANIFEST_KWARGS = dict(
    run_id="r-test-0001", source_commit="0" * 40, configuration_name="primary",
    concept_id="cheese", pairing_id=_PAIRING_ID_GEMMA,
    model_revision="deadbeef" * 5,
    sae_revision="4c419f1ba0be8b7754d4151d4f26c23b92a9029e",
    release="gemma-scope-2-12b-it-res-all", loader_sae_id="layer_29_width_16k_l0_big",
    scientific_sae_id="resid_post_all/layer_29_width_16k_l0_big",
    measured_params_sha256="6bb44c8c68797942d097604bfd8df50f4865c86282e2c4667e364382ea26120e",
)


def test_write_and_verify_generation_manifest_round_trips(tmp_path):
    records = _tiny_records(tmp_path)
    manifest_path = tmp_path / "generation_manifest.json"
    one.write_generation_manifest(records, manifest_path, **_MANIFEST_KWARGS)
    verified = one.verify_generation_manifest(manifest_path)
    assert len(verified["files"]) == 4  # 1 control + 3 doses
    assert verified["protocol_sha256"] == f"sha256:{one.ONE_ALLOCATION_PROTOCOL_SHA256}"
    assert verified["configuration"] == "PRIMARY"
    assert verified["direction"] == "AMPLIFY"
    assert verified["concept_id"] == "cheese"
    assert verified["pairing_id"] == _PAIRING_ID_GEMMA
    assert verified["scientific_sae_id"] == "resid_post_all/layer_29_width_16k_l0_big"
    assert verified["params_measured_sha256"] == "sha256:6bb44c8c68797942d097604bfd8df50f4865c86282e2c4667e364382ea26120e"
    assert verified["completeness"] == "COMPLETE"
    assert "model" not in verified and "sae" not in verified and "concepts" not in verified
    assert "manifest_sha256" not in verified


def test_write_generation_manifest_file_entries_carry_the_ruled_flat_fields(tmp_path):
    records = _tiny_records(tmp_path)
    manifest = one.write_generation_manifest(records, tmp_path / "m.json", **_MANIFEST_KWARGS)
    by_purpose = {}
    for entry in manifest["files"]:
        by_purpose.setdefault(entry["purpose"], []).append(entry)
    assert set(by_purpose) == {"CONTROL", "CONFIRMATION"}
    control_entry = by_purpose["CONTROL"][0]
    assert "dose" not in control_entry
    assert "control_ref" not in control_entry
    for entry in by_purpose["CONFIRMATION"]:
        assert "dose" in entry
        assert entry["control_ref"] == control_entry["path"]
        assert entry["selection_status"] == one.UNUSED_STATUS
    assert all(entry["sha256"].startswith("sha256:") for entry in manifest["files"])
    assert all(isinstance(entry["seed"], int) for entry in manifest["files"])


def test_write_generation_manifest_rejects_an_unknown_configuration_name(tmp_path):
    records = _tiny_records(tmp_path)
    kwargs = {**_MANIFEST_KWARGS, "configuration_name": "tertiary"}
    with pytest.raises(ValueError, match=r"primary.*backup"):
        one.write_generation_manifest(records, tmp_path / "m.json", **kwargs)


def test_write_generation_manifest_rejects_an_unknown_completeness_value(tmp_path):
    records = _tiny_records(tmp_path)
    kwargs = {**_MANIFEST_KWARGS, "completeness": "MOSTLY_DONE"}
    with pytest.raises(ValueError, match="COMPLETE"):
        one.write_generation_manifest(records, tmp_path / "m.json", **kwargs)


def test_write_generation_manifest_rejects_records_spanning_more_than_one_concept(tmp_path):
    records = _tiny_records(tmp_path)
    backend = fakes.make_fake_gemma_backend()
    corpus_max = d.corpus_max_per_feature(backend, ["background text"])
    other_seeds = one.derive_seeds(
        namespace="confirmation", concept_id="chess", pairing_id=backend.pairing, direction="amplify",
        locale="en", n_prompts=2, n_repeats=1,
    )
    foreign = one.generate_control_file(
        backend, corpus_max=corpus_max, positions="all", prompts=["a", "b"], purpose="confirmation", n_repeats=1,
        seeds=other_seeds, max_new_tokens=1, out_dir=tmp_path, concept_id="chess", pairing_id=backend.pairing,
        direction="amplify", locale="en",
    )
    with pytest.raises(ValueError, match="exactly ONE concept_id"):
        one.write_generation_manifest([*records, foreign], tmp_path / "m.json", **_MANIFEST_KWARGS)


def test_write_generation_manifest_accepts_the_generation_settings_extension_fields(tmp_path):
    records = _tiny_records(tmp_path)
    manifest = one.write_generation_manifest(
        records, tmp_path / "m.json", **_MANIFEST_KWARGS,
        generation_kwargs=d.GENERATION_SETTINGS, chat_template_identity="gemma-it-v1",
        locales_complete=["en"],
    )
    assert manifest["generation_kwargs"] == d.GENERATION_SETTINGS
    assert manifest["chat_template_identity"] == "gemma-it-v1"
    assert manifest["locales_complete"] == ["en"]


def test_verify_generation_manifest_raises_on_a_tampered_file(tmp_path):
    records = _tiny_records(tmp_path)
    manifest_path = tmp_path / "generation_manifest.json"
    one.write_generation_manifest(records, manifest_path, **_MANIFEST_KWARGS)
    Path(records[0].path).write_text('{"generations": "TAMPERED"}', encoding="utf-8")
    with pytest.raises(one.TransferVerificationFailed, match="sha256 mismatch"):
        one.verify_generation_manifest(manifest_path)


def test_verify_generation_manifest_raises_on_a_missing_file(tmp_path):
    records = _tiny_records(tmp_path)
    manifest_path = tmp_path / "generation_manifest.json"
    one.write_generation_manifest(records, manifest_path, **_MANIFEST_KWARGS)
    Path(records[0].path).unlink()
    with pytest.raises(one.TransferVerificationFailed, match="file missing"):
        one.verify_generation_manifest(manifest_path)


def test_verify_generation_manifest_raises_when_required_fields_are_absent(tmp_path):
    manifest_path = tmp_path / "generation_manifest.json"
    manifest_path.write_text('{"files": []}', encoding="utf-8")
    with pytest.raises(one.TransferVerificationFailed, match="missing required field"):
        one.verify_generation_manifest(manifest_path)


def test_stamp_manifest_with_selection_selects_the_named_doses_and_leaves_control_and_sweep_untouched(tmp_path):
    records = _tiny_records(tmp_path)  # 1 control + 3 confirmation doses: 1.0x, 2.0x, 3.0x
    manifest_path = tmp_path / "generation_manifest.json"
    manifest = one.write_generation_manifest(records, manifest_path, **_MANIFEST_KWARGS)
    stamped = one.stamp_manifest_with_selection(manifest, unselected_doses=["3.0x"])
    by_key = {(entry["purpose"], entry.get("dose")): entry for entry in stamped["files"]}
    assert by_key[("CONFIRMATION", "1.0x")]["selection_status"] == one.SELECTED_STATUS
    assert by_key[("CONFIRMATION", "2.0x")]["selection_status"] == one.SELECTED_STATUS
    assert by_key[("CONFIRMATION", "3.0x")]["selection_status"] == one.UNUSED_STATUS
    assert by_key[("CONTROL", None)]["selection_status"] == one.UNUSED_STATUS
    # the original manifest is untouched
    assert all(entry["selection_status"] == one.UNUSED_STATUS for entry in manifest["files"])


def test_stamp_manifest_with_selection_never_touches_sweep_entries(tmp_path):
    records = _tiny_records(tmp_path, purpose="sweep")
    manifest = one.write_generation_manifest(records, tmp_path / "m.json", **_MANIFEST_KWARGS)
    stamped = one.stamp_manifest_with_selection(manifest, unselected_doses=["3.0x"])
    assert all(entry["selection_status"] == one.UNUSED_STATUS for entry in stamped["files"] if entry["purpose"] == "SWEEP")
