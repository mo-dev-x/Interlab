"""Tests for scripts/final_pairing/final_pairing_one_allocation_generation.py
(stages 1-3 of protocols/final_pairing/v1/one_allocation_dose_generation.json,
extended by protocols/final_pairing/v1/generation_settings.json).

Manifest shape matches Engineer 3's real, enforcing validator
(`scripts/concept_bundle_publish.py`, commit 2003406 -- "Consume the
generation settings: sampling, controls, counts and order", the
generation-settings-aware successor to 67ad4ef): ONE MANIFEST ENTRY PER
GENERATION (not per physical file -- `MANIFEST_FILE_FIELDS` requires both
`dose` and `prompt_id` on every entry, which is only consistent if a
manifest row is one generation), flat top-level identity fields, real
frozen `prompt_id`s (never synthetic), and the full `generation_settings.
json` extension's manifest-level fields (`generation_kwargs`, `causal_
order_position`, `skipped_for_gate_failure`, etc).

CPU-only, fake-backend -- same convention as
test_final_pairing_concept_discovery.py: no real Gemma/Qwen weights exist
on any machine in this investigation.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "final_pairing"))

import final_pairing_concept_discovery as d  # noqa: E402
import final_pairing_fakes as fakes  # noqa: E402
import final_pairing_one_allocation_generation as one  # noqa: E402

CONCEPT_FEATURE = 3


def _row(prompt_id: str, text: str, *, locale: str = "en", split: str = "heldout_neutral", ordinal: int = 1) -> dict:
    """A minimal frozen-artifact-shaped prompt row -- real callers get
    these from `select_generation_prompt_rows`; tests build them directly
    since they never need a real frozen artifact to exercise the
    generation functions themselves."""
    return {"prompt_id": prompt_id, "text": text, "locale": locale, "split": split, "ordinal": ordinal}


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


AMPLIFY_DOSES = (("A1", 0.25), ("A2", 0.5), ("A3", 1.0), ("A4", 2.0), ("A5", 4.0))
SUPPRESS_CLAMP_DOSES = (("S1", 1.0), ("S2", 0.5), ("S3", 0.25), ("S4", 0.1))
#: The illustrative-but-PROHIBITED Suppress sequence (causal_dose_grid.json
#: PROHIBITED_SUBSTITUTION): tops out as an amplification, bottoms out as
#: barely a suppression -- rejected even though it is also strictly
#: descending, so a plain "is it descending" check would wrongly accept it.
PROHIBITED_SUPPRESS_CLAMP_DOSES = (("S1", 4.0), ("S2", 2.0), ("S3", 1.0), ("S4", 0.5))


def test_build_amplify_dose_grid_accepts_the_frozen_five_point_grid():
    grid = one.build_amplify_dose_grid(AMPLIFY_DOSES)
    assert len(grid) == 5
    assert all(spec.kind == "clamp" for spec in grid)
    assert [spec.dose_id for spec in grid] == ["A1", "A2", "A3", "A4", "A5"]


def test_build_amplify_dose_grid_rejects_wrong_count():
    with pytest.raises(ValueError, match="exactly 5 points"):
        one.build_amplify_dose_grid((("A1", 0.5), ("A2", 1.0)))


def test_build_amplify_dose_grid_rejects_duplicate_dose_ids():
    with pytest.raises(ValueError, match="dose_ids must be distinct"):
        one.build_amplify_dose_grid((("A1", 0.25), ("A1", 0.5), ("A3", 1.0), ("A4", 2.0), ("A5", 4.0)))


def test_build_amplify_dose_grid_rejects_any_values_other_than_the_frozen_grid():
    with pytest.raises(ValueError, match="must be exactly"):
        one.build_amplify_dose_grid((("A1", 0.5), ("A2", 0.5), ("A3", 1.0), ("A4", 2.0), ("A5", 4.0)))


def test_build_suppress_dose_grid_appends_ablate_as_the_fifth_point():
    grid = one.build_suppress_dose_grid(SUPPRESS_CLAMP_DOSES, ablate_dose_id="S5")
    assert len(grid) == 5
    assert [spec.kind for spec in grid] == ["clamp", "clamp", "clamp", "clamp", "ablate"]
    assert grid[-1].value_in_max_units is None
    assert [spec.dose_id for spec in grid] == ["S1", "S2", "S3", "S4", "S5"]


def test_build_suppress_dose_grid_rejects_the_prohibited_substitution_sequence():
    """causal_dose_grid.json's own named hard stop: 4.0, 2.0, 1.0, 0.5 is
    strictly descending (like the frozen grid) but is NOT the frozen grid,
    and must fail even though a naive "is it descending" check would pass
    it."""
    with pytest.raises(ValueError, match="must be exactly"):
        one.build_suppress_dose_grid(PROHIBITED_SUPPRESS_CLAMP_DOSES, ablate_dose_id="S5")


def test_build_suppress_dose_grid_rejects_wrong_count():
    with pytest.raises(ValueError, match="exactly 4 points"):
        one.build_suppress_dose_grid((("S1", 1.0), ("S2", 0.5)), ablate_dose_id="S5")


def test_dose_spec_rejects_a_value_on_an_ablate_dose():
    with pytest.raises(ValueError, match="carries no value_in_max_units"):
        one.DoseSpec(dose_id="S5", kind="ablate", value_in_max_units=1.0)


def test_dose_spec_requires_a_value_on_a_clamp_dose():
    with pytest.raises(ValueError, match="requires value_in_max_units"):
        one.DoseSpec(dose_id="A1", kind="clamp")


def test_load_causal_dose_grid_reads_the_real_frozen_artifact():
    """The frozen artifact IS the only source of dose values -- this
    proves the real committed causal_dose_grid.json round-trips through
    load_causal_dose_grid/build_amplify_dose_grid/build_suppress_dose_grid
    into exactly the canonical A1..A5/S1..S5 ids and frozen values."""
    amplify_grid, suppress_grid = one.load_causal_dose_grid(REPO_ROOT)
    assert [(s.dose_id, s.value_in_max_units) for s in amplify_grid] == list(AMPLIFY_DOSES)
    assert [(s.dose_id, s.value_in_max_units) for s in suppress_grid[:4]] == list(SUPPRESS_CLAMP_DOSES)
    assert suppress_grid[4].dose_id == "S5"
    assert suppress_grid[4].kind == "ablate"
    assert suppress_grid[4].value_in_max_units is None


def test_validate_causal_dose_grid_protocol_hash_passes_against_the_real_frozen_artifact():
    digest = one.validate_causal_dose_grid_protocol_hash(REPO_ROOT)
    assert digest == one.CAUSAL_DOSE_GRID_PROTOCOL_SHA256


def test_validate_causal_dose_grid_protocol_hash_refuses_a_tampered_copy(tmp_path):
    tampered_path = tmp_path / "protocols" / "final_pairing" / "v1" / "causal_dose_grid.json"
    tampered_path.parent.mkdir(parents=True)
    tampered_path.write_text('{"protocol_version": "tampered"}', encoding="utf-8")
    with pytest.raises(one.TransferVerificationFailed, match="altered or unpinned"):
        one.validate_causal_dose_grid_protocol_hash(tmp_path)


def test_a_selection_whose_high_is_s4_rather_than_ablate_is_a_valid_dose_id():
    """No ordering/magnitude assumption anywhere: S4 (a CLAMP dose, not
    ABLATE) is exactly as valid a `high` selection as S5 would be -- the
    dose-grid position never decides eligibility."""
    grid = one.build_suppress_dose_grid(SUPPRESS_CLAMP_DOSES, ablate_dose_id="S5")
    high_candidate = next(spec for spec in grid if spec.dose_id == "S4")
    assert high_candidate.kind == "clamp"
    assert high_candidate.dose_id == "S4"


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
    dose = one.DoseSpec(dose_id="A3", kind="clamp", value_in_max_units=1.0)
    prompts = [_row(f"p{i}", f"prompt {i}", ordinal=i + 1) for i in range(3)]
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
    assert record.prompt_ids == ["p0", "p0", "p1", "p1", "p2", "p2"]
    assert record.dose_id == "A3"
    assert record.dose_id in Path(record.path).name
    assert record.control_ref == "control/sweep_en.json"


def test_generate_dose_file_rejects_a_seed_list_of_the_wrong_length(tmp_path):
    backend = fakes.make_fake_gemma_backend()
    corpus_max = d.corpus_max_per_feature(backend, ["background"])
    with pytest.raises(ValueError, match="exactly one seed per"):
        one.generate_dose_file(
            backend, [CONCEPT_FEATURE], dose=one.DoseSpec(dose_id="A3", kind="clamp", value_in_max_units=1.0),
            corpus_max=corpus_max, positions="all", prompts=[_row("a", "a"), _row("b", "b", ordinal=2)],
            purpose="sweep", n_repeats=1,
            seeds=[1], max_new_tokens=1, out_dir=tmp_path, concept_id="cheese", pairing_id=backend.pairing,
            direction="amplify", locale="en", control_ref="x.json",
        )


def test_generate_control_file_writes_one_file_with_no_dose_and_no_control_ref(tmp_path):
    backend = fakes.make_fake_gemma_backend()
    corpus_max = d.corpus_max_per_feature(backend, ["background"])
    prompts = [_row(f"p{i}", f"prompt {i}", ordinal=i + 1) for i in range(3)]
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
    assert record.dose_id is None
    assert record.dose_kind is None
    assert record.control_ref is None
    assert record.seeds == seeds
    assert record.prompt_ids == ["p0", "p1", "p2"]
    entries = record.to_manifest_file_entries()
    assert len(entries) == 3
    for entry in entries:
        assert "dose" not in entry
        assert "control_ref" not in entry


def test_generate_control_file_uses_the_same_seed_as_a_matching_dose_file(tmp_path):
    """The single most important rule in generation_settings.json's
    control-arm section: SAME_SEED_IS_MANDATORY."""
    backend = fakes.make_fake_gemma_backend()
    corpus_max = d.corpus_max_per_feature(backend, ["background"])
    prompts = [_row(f"p{i}", f"prompt {i}", locale="fr", split="heldout_eliciting", ordinal=i + 1) for i in range(4)]
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
        backend, [CONCEPT_FEATURE], dose=one.DoseSpec(dose_id="A4", kind="clamp", value_in_max_units=2.0),
        corpus_max=corpus_max, positions="all", prompts=prompts, purpose="confirmation", n_repeats=1,
        seeds=seeds, max_new_tokens=2, out_dir=tmp_path / "doses", concept_id="cheese",
        pairing_id=backend.pairing, direction="suppress", locale="fr", control_ref=control.path,
    )
    assert dose_record.seeds == control.seeds == seeds
    assert dose_record.prompt_ids == control.prompt_ids


def test_generate_control_file_rejects_a_seed_list_of_the_wrong_length(tmp_path):
    backend = fakes.make_fake_gemma_backend()
    corpus_max = d.corpus_max_per_feature(backend, ["background"])
    with pytest.raises(ValueError, match="exactly one seed per"):
        one.generate_control_file(
            backend, corpus_max=corpus_max, positions="all", prompts=[_row("a", "a"), _row("b", "b", ordinal=2)],
            purpose="sweep", n_repeats=1,
            seeds=[1], max_new_tokens=1, out_dir=tmp_path, concept_id="cheese", pairing_id=backend.pairing,
            direction="amplify", locale="en",
        )


def _bilingual_prompts(n: int, tag: str, *, split: str = "heldout_neutral") -> dict[str, list[dict]]:
    return {
        locale: [_row(f"{tag}-{locale}-{i:02d}", f"{tag} {locale} prompt {i}", locale=locale, split=split, ordinal=i + 1) for i in range(n)]
        for locale in one.LOCALES
    }


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
        amplify_dose_grid=one.build_amplify_dose_grid(AMPLIFY_DOSES),
        suppress_dose_grid=one.build_suppress_dose_grid(SUPPRESS_CLAMP_DOSES, ablate_dose_id="S5"),
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
            amplify_dose_grid=one.build_amplify_dose_grid(AMPLIFY_DOSES),
            suppress_dose_grid=one.build_suppress_dose_grid(SUPPRESS_CLAMP_DOSES, ablate_dose_id="S5"),
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
        amplify_dose_grid=one.build_amplify_dose_grid(AMPLIFY_DOSES),
        suppress_dose_grid=one.build_suppress_dose_grid(SUPPRESS_CLAMP_DOSES, ablate_dose_id="S5"),
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
    tiny_prompts = [_row(f"p{i}", f"prompt {i}", ordinal=i + 1) for i in range(2)]
    control = one.generate_control_file(
        backend, corpus_max=corpus_max, positions="all", prompts=tiny_prompts,
        purpose=purpose, n_repeats=1, seeds=control_seeds, max_new_tokens=1, out_dir=tmp_path,
        concept_id="cheese", pairing_id=backend.pairing, direction=direction, locale="en",
    )
    records.append(control)
    for index, value in enumerate((1.0, 2.0, 3.0)):
        dose = one.DoseSpec(dose_id=f"A{index + 1}", kind="clamp", value_in_max_units=value)
        records.append(one.generate_dose_file(
            backend, [CONCEPT_FEATURE], dose=dose, corpus_max=corpus_max, positions="all",
            prompts=tiny_prompts, purpose=purpose, n_repeats=1, seeds=control_seeds,
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
    generation_kwargs=d._resolved_generation_kwargs(48, d.GENERATION_SETTINGS), chat_template_identity="gemma-it-v1",
    locales_complete=["en", "fr"], causal_order_position=2, skipped_for_gate_failure=["formal_register"],
    dose_grid=one.build_amplify_dose_grid(AMPLIFY_DOSES),
)


def test_write_and_verify_generation_manifest_round_trips(tmp_path):
    records = _tiny_records(tmp_path)
    manifest_path = tmp_path / "generation_manifest.json"
    one.write_generation_manifest(records, manifest_path, **_MANIFEST_KWARGS)
    verified = one.verify_generation_manifest(manifest_path)
    assert len(verified["files"]) == 8  # 1 control (2 generations) + 3 doses (2 generations each)
    assert verified["protocol_sha256"] == f"sha256:{one.ONE_ALLOCATION_PROTOCOL_SHA256}"
    assert verified["configuration"] == "PRIMARY"
    assert verified["direction"] == "AMPLIFY"
    assert verified["concept_id"] == "cheese"
    assert verified["pairing_id"] == _PAIRING_ID_GEMMA
    assert verified["scientific_sae_id"] == "resid_post_all/layer_29_width_16k_l0_big"
    assert verified["params_measured_sha256"] == "sha256:6bb44c8c68797942d097604bfd8df50f4865c86282e2c4667e364382ea26120e"
    assert verified["completeness"] == "COMPLETE"
    assert verified["causal_order_position"] == 2
    assert verified["skipped_for_gate_failure"] == ["formal_register"]
    assert verified["generation_settings_path"] == one.GENERATION_SETTINGS_PROTOCOL_PATH
    assert verified["generation_settings_sha256"] == f"sha256:{one.GENERATION_SETTINGS_PROTOCOL_SHA256}"
    assert "model" not in verified and "sae" not in verified and "concepts" not in verified
    assert "manifest_sha256" not in verified


# ---------------------------------------------------------------------------
# schema 5.0 (conformance/concept_bundle/discovery_input_schema.json, commit
# 3aff107): the manifest-level dose_grid + causal_dose_grid_path/_version/
# _sha256 binding.
# ---------------------------------------------------------------------------


def test_write_generation_manifest_carries_the_manifest_level_dose_grid(tmp_path):
    records = _tiny_records(tmp_path)
    manifest = one.write_generation_manifest(records, tmp_path / "m.json", **_MANIFEST_KWARGS)
    assert manifest["causal_dose_grid_path"] == one.CAUSAL_DOSE_GRID_PROTOCOL_PATH
    assert manifest["causal_dose_grid_version"] == one.CAUSAL_DOSE_GRID_PROTOCOL_VERSION
    assert manifest["causal_dose_grid_sha256"] == f"sha256:{one.CAUSAL_DOSE_GRID_PROTOCOL_SHA256}"
    dose_grid = manifest["dose_grid"]
    assert [pt["dose_id"] for pt in dose_grid] == ["A1", "A2", "A3", "A4", "A5"]
    assert [pt["index"] for pt in dose_grid] == [1, 2, 3, 4, 5]
    assert all(pt["operation"] == "CLAMP" for pt in dose_grid)
    assert [pt["value_in_max_units"] for pt in dose_grid] == [0.25, 0.5, 1.0, 2.0, 4.0]
    assert all(pt["unit"] == "corpus_max_multiple" and pt["unit_source"] for pt in dose_grid)
    assert all("weight" not in pt for pt in dose_grid)  # CLAMP points carry no weight key


def test_write_generation_manifest_dose_grid_ablate_point_has_no_value_unit_or_unit_source(tmp_path):
    """A Suppress direction's dose_grid: S5's clamp-shaped fields are
    explicit `None` (mirroring causal_dose_grid.json's own S5 point
    verbatim) and `weight` is exactly 1.0 -- never omitted, never a
    truthy value other than 1.0."""
    _amplify_grid, suppress_grid = one.load_causal_dose_grid(REPO_ROOT)
    points = one._dose_grid_manifest_points(suppress_grid)
    assert [pt["dose_id"] for pt in points] == ["S1", "S2", "S3", "S4", "S5"]
    ablate_point = points[-1]
    assert ablate_point["operation"] == "ABLATE"
    assert ablate_point["value_in_max_units"] is None
    assert ablate_point["unit"] is None
    assert ablate_point["unit_source"] is None
    assert ablate_point["weight"] == 1.0
    assert all(pt["operation"] == "CLAMP" and "weight" not in pt for pt in points[:4])


def test_write_generation_manifest_rejects_a_dose_grid_of_the_wrong_length(tmp_path):
    records = _tiny_records(tmp_path)
    kwargs = {**_MANIFEST_KWARGS, "dose_grid": one.build_amplify_dose_grid(AMPLIFY_DOSES)[:4]}
    with pytest.raises(ValueError, match="dose_grid must have exactly"):
        one.write_generation_manifest(records, tmp_path / "m.json", **kwargs)


def test_write_generation_manifest_file_entries_carry_the_ruled_flat_fields(tmp_path):
    records = _tiny_records(tmp_path)
    manifest = one.write_generation_manifest(records, tmp_path / "m.json", **_MANIFEST_KWARGS)
    by_purpose = {}
    for entry in manifest["files"]:
        by_purpose.setdefault(entry["purpose"], []).append(entry)
    assert set(by_purpose) == {"CONTROL", "CONFIRMATION"}
    assert len(by_purpose["CONTROL"]) == 2  # one entry per generation, not per physical file
    assert len(by_purpose["CONFIRMATION"]) == 6  # 3 doses x 2 generations each
    control_paths = {e["path"] for e in by_purpose["CONTROL"]}
    assert len(control_paths) == 1  # both entries name the SAME physical file
    control_path = next(iter(control_paths))
    for entry in by_purpose["CONTROL"]:
        assert "dose" not in entry
        assert "control_ref" not in entry
        assert entry["prompt_id"] in ("p0", "p1")
    for entry in by_purpose["CONFIRMATION"]:
        assert "dose" in entry
        assert entry["control_ref"] == control_path
        # manifest-immutability correction (commit 2dc9e338): the bound
        # manifest carries NO per-file selection-outcome field at all.
        assert "selection_status" not in entry
        assert entry["prompt_id"] in ("p0", "p1")
    assert all(entry["sha256"].startswith("sha256:") for entry in manifest["files"])
    assert all(isinstance(entry["seed"], int) for entry in manifest["files"])
    assert all("truncated" in entry for entry in manifest["files"])


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
        backend, corpus_max=corpus_max, positions="all", prompts=[_row("a", "a"), _row("b", "b", ordinal=2)],
        purpose="confirmation", n_repeats=1,
        seeds=other_seeds, max_new_tokens=1, out_dir=tmp_path, concept_id="chess", pairing_id=backend.pairing,
        direction="amplify", locale="en",
    )
    with pytest.raises(ValueError, match="exactly ONE concept_id"):
        one.write_generation_manifest([*records, foreign], tmp_path / "m.json", **_MANIFEST_KWARGS)


def test_write_generation_manifest_carries_the_generation_settings_extension_fields_verbatim(tmp_path):
    records = _tiny_records(tmp_path)
    manifest = one.write_generation_manifest(
        records, tmp_path / "m.json",
        **{**_MANIFEST_KWARGS, "locales_complete": ["en"]},
    )
    assert manifest["generation_kwargs"] == d._resolved_generation_kwargs(48, d.GENERATION_SETTINGS)
    assert manifest["generation_kwargs"]["max_new_tokens"] == 48
    assert len(manifest["generation_kwargs"]) == 10  # all 10 frozen generation_settings.json values
    assert manifest["chat_template_identity"] == "gemma-it-v1"
    assert manifest["locales_complete"] == ["en"]
    assert manifest["causal_order_position"] == 2
    assert manifest["skipped_for_gate_failure"] == ["formal_register"]


def test_write_generation_manifest_accepts_a_null_measured_params_sha256_for_qwen(tmp_path):
    """The identity artifact freezes no expected params hash for Qwen --
    `params_measured_sha256` may be `None`/JSON `null` there, per the
    schema's own `pairing.params_sha256` carve-out."""
    records = _tiny_records(tmp_path)
    kwargs = {**_MANIFEST_KWARGS, "measured_params_sha256": None}
    manifest = one.write_generation_manifest(records, tmp_path / "m.json", **kwargs)
    assert manifest["params_measured_sha256"] is None


def test_write_generation_manifest_rejects_a_skipped_concept_not_in_the_causal_order(tmp_path):
    records = _tiny_records(tmp_path)
    kwargs = {**_MANIFEST_KWARGS, "skipped_for_gate_failure": ["not-a-real-concept"]}
    with pytest.raises(ValueError, match="not in the frozen CAUSAL_GENERATION_ORDER"):
        one.write_generation_manifest(records, tmp_path / "m.json", **kwargs)


def test_write_generation_manifest_rejects_a_skipped_concept_after_this_ones_own_position(tmp_path):
    """cheese sits at causal_order_position=2; a concept AFTER it (e.g.
    chess, position 3) cannot yet have been 'skipped' from cheese's own
    manifest's vantage point -- Engineer 3's real validator (commit
    9a32246) rejects this exact case."""
    records = _tiny_records(tmp_path)
    kwargs = {**_MANIFEST_KWARGS, "skipped_for_gate_failure": ["chess"]}
    with pytest.raises(ValueError, match="sits AFTER"):
        one.write_generation_manifest(records, tmp_path / "m.json", **kwargs)


def test_write_generation_manifest_refuses_to_overwrite_an_existing_manifest(tmp_path):
    """Manifest-immutability correction (commit 2dc9e338): the bound
    manifest is written ONCE, at transfer, and NEVER rewritten."""
    records = _tiny_records(tmp_path)
    manifest_path = tmp_path / "generation_manifest.json"
    one.write_generation_manifest(records, manifest_path, **_MANIFEST_KWARGS)
    with pytest.raises(one.TransferVerificationFailed, match="written ONCE"):
        one.write_generation_manifest(records, manifest_path, **_MANIFEST_KWARGS)


def test_write_generation_manifest_carries_the_pre_selection_inventory_stage(tmp_path):
    records = _tiny_records(tmp_path)
    manifest = one.write_generation_manifest(records, tmp_path / "m.json", **_MANIFEST_KWARGS)
    assert manifest["inventory_stage"] == one.INVENTORY_STAGE_PRE_SELECTION == "PRE_SELECTION"


def test_verify_generation_manifest_rejects_a_derived_reading_aid_view(tmp_path):
    records = _tiny_records(tmp_path)
    manifest_path = tmp_path / "generation_manifest.json"
    manifest = one.write_generation_manifest(records, manifest_path, **_MANIFEST_KWARGS)
    stamped = one.stamp_manifest_with_selection(manifest, unselected_doses=[])
    derived_path = tmp_path / "derived_view.json"
    derived_path.write_text(json.dumps(stamped), encoding="utf-8")
    with pytest.raises(one.TransferVerificationFailed, match="derived/not_for_promotion"):
        one.verify_generation_manifest(derived_path)


def test_verify_generation_manifest_rejects_a_files_entry_carrying_selection_status(tmp_path):
    records = _tiny_records(tmp_path)
    manifest_path = tmp_path / "generation_manifest.json"
    one.write_generation_manifest(records, manifest_path, **_MANIFEST_KWARGS)
    tampered = json.loads(manifest_path.read_text(encoding="utf-8"))
    tampered["files"][0]["selection_status"] = one.UNUSED_STATUS
    manifest_path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(one.TransferVerificationFailed, match="selection-outcome-shaped field"):
        one.verify_generation_manifest(manifest_path)


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
    records = _tiny_records(tmp_path)  # 1 control + 3 confirmation doses: A1, A2, A3
    manifest_path = tmp_path / "generation_manifest.json"
    manifest = one.write_generation_manifest(records, manifest_path, **_MANIFEST_KWARGS)
    stamped = one.stamp_manifest_with_selection(manifest, unselected_doses=["A3"])
    # manifest-immutability correction (commit 2dc9e338): stamp_manifest_
    # with_selection's output is a DERIVED reading aid only, never the
    # bound manifest -- marked so verify_generation_manifest/LA-B's gate
    # can identify and refuse it if ever mistakenly promoted.
    assert stamped["derived"] is True
    assert stamped["not_for_promotion"] is True
    by_key = {(entry["purpose"], entry.get("dose")): entry for entry in stamped["files"]}
    assert by_key[("CONFIRMATION", "A1")]["selection_status"] == one.SELECTED_STATUS
    assert by_key[("CONFIRMATION", "A2")]["selection_status"] == one.SELECTED_STATUS
    assert by_key[("CONFIRMATION", "A3")]["selection_status"] == one.UNUSED_STATUS
    assert by_key[("CONTROL", None)]["selection_status"] == one.UNUSED_STATUS
    # the original (bound) manifest is untouched -- it never carried
    # selection_status at all, and still doesn't.
    assert all("selection_status" not in entry for entry in manifest["files"])
    assert "derived" not in manifest and "not_for_promotion" not in manifest


def test_stamp_manifest_with_selection_never_touches_sweep_entries(tmp_path):
    records = _tiny_records(tmp_path, purpose="sweep")
    manifest = one.write_generation_manifest(records, tmp_path / "m.json", **_MANIFEST_KWARGS)
    stamped = one.stamp_manifest_with_selection(manifest, unselected_doses=["A3"])
    assert all(entry["selection_status"] == one.UNUSED_STATUS for entry in stamped["files"] if entry["purpose"] == "SWEEP")


# ---------------------------------------------------------------------------
# GPU-closure proof (manifest immutability, item 5): stamp_manifest_with_
# selection may exist ONLY as the explicitly non-promotable derived reading
# aid the manifest-immutability correction (commit 2dc9e338) permits --
# it must have ZERO callers reachable from any real GPU entry point. Built
# from a real AST call graph (never executed, and never a raw substring
# scan -- this file's own docstrings/tests NAME the function, which a
# substring search would false-positive on), unioning every function every
# GPU-side production module defines with the set of names it calls,
# then walking the transitive closure. A conservative OVER-approximation
# (any `foo(...)`/`x.foo(...)` records an edge to callee-name "foo",
# whether or not it actually resolves to a same-module function) -- if the
# target name is unreachable in this over-approximated union graph, it is
# unreachable in every real, per-module call graph too.
# ---------------------------------------------------------------------------

_GPU_ENTRY_POINT_MODULE_PATHS: tuple[str, ...] = (
    "final_pairing_concept_discovery.py",
    "final_pairing_one_allocation_generation.py",
    "final_concept_discovery_dual_gpu_job.py",
    "final_concept_discovery_matched_configuration_job.py",
    "discovery_preflight.py",
)


def _call_graph_for_source(source: str) -> dict[str, set[str]]:
    import ast

    tree = ast.parse(source)
    graph: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            called: set[str] = set()
            for sub in ast.walk(node):
                if not isinstance(sub, ast.Call):
                    continue
                func = sub.func
                if isinstance(func, ast.Name):
                    called.add(func.id)
                elif isinstance(func, ast.Attribute):
                    called.add(func.attr)
            graph.setdefault(node.name, set()).update(called)
    return graph


def _reachable_from(graph: dict[str, set[str]], start: str) -> set[str]:
    seen: set[str] = set()
    frontier = [start]
    while frontier:
        name = frontier.pop()
        if name in seen:
            continue
        seen.add(name)
        frontier.extend(callee for callee in graph.get(name, ()) if callee not in seen)
    return seen


def test_stamp_manifest_with_selection_is_unreachable_from_any_gpu_entry_point():
    combined: dict[str, set[str]] = {}
    for filename in _GPU_ENTRY_POINT_MODULE_PATHS:
        source = (REPO_ROOT / "scripts" / "final_pairing" / filename).read_text(encoding="utf-8")
        for name, calls in _call_graph_for_source(source).items():
            combined.setdefault(name, set()).update(calls)

    entry_points = ("main", "run_dual_gpu_job", "run_dual_gpu_job_for_lanes", "run_matched_configuration_job", "run_generation_mode", "run_all_cases")
    for entry in entry_points:
        reachable = _reachable_from(combined, entry)
        assert "stamp_manifest_with_selection" not in reachable, (
            f"{entry}()'s call graph reaches stamp_manifest_with_selection -- the manifest-immutability "
            f"correction (2dc9e338) requires this function be reachable from NO GPU entry point; it may "
            f"be called only as an explicitly non-promotable, offline reading aid"
        )


# ---------------------------------------------------------------------------
# Production generation CLI (P0 CONTINUE blocker 2): the real scheduled
# entry point, exercised END TO END against a REAL grid.json and the REAL
# frozen prompt artifact (not stage-by-stage unit calls) -- proves
# run_generation_mode's own call graph is reachable and produces exactly
# what the schema requires for one full concept.
# ---------------------------------------------------------------------------


def test_run_generation_mode_end_to_end_for_one_concept(tmp_path, monkeypatch):
    """Builds a real grid.json with exactly one 'pass' verdict (so the
    causal-order loop only attempts one concept -- runtime stays
    bounded), monkeypatches `load_backend`/`ONE_ALLOCATION_MAX_NEW_TOKENS`
    (no real weights exist, and 48 real tokens x 1800 generations would be
    needlessly slow for a fake CPU backend), and runs the real CLI
    function against the REAL frozen prompt artifact -- proving
    `order_concepts_for_causal_generation`, `select_generation_prompt_
    rows`, `generate_concept_complete`, `measure_seconds_per_generation`,
    `assess_concept_generation_readiness`, and `write_generation_manifest`
    are all wired together and reachable from one real entry point, not
    merely individually unit-tested library functions."""
    backend = fakes.make_fake_gemma_backend()
    monkeypatch.setattr(d, "load_backend", lambda **_kwargs: backend)
    monkeypatch.setattr(d, "ONE_ALLOCATION_MAX_NEW_TOKENS", 1)

    grid_dir = tmp_path / "grid"
    d.write_grid_result(
        grid_dir, backend.pairing,
        [
            # formal_register (causal order position 1) FAILS G-A/B/C -- costs
            # no extra real generation work (only "pass" concepts are ever
            # processed), but lets this same run prove skipped_for_gate_failure
            # is computed for real: cheese (position 2) must list it.
            d.ConceptPairingVerdict(
                concept_id="formal_register", pairing=backend.pairing, status="fail",
                surviving_feature_index=None, candidates_evaluated=[], error=None,
            ),
            d.ConceptPairingVerdict(
                concept_id="cheese", pairing=backend.pairing, status="pass",
                surviving_feature_index=CONCEPT_FEATURE, candidates_evaluated=[], error=None,
            ),
        ],
    )

    args = one.parse_args([
        "--pairing", backend.pairing, "--model-path", "unused", "--sae-path", "unused", "--layer", "29",
        "--configuration-name", "primary", "--grid-path", str(grid_dir / "grid.json"),
        "--pairing-id", "google/gemma-3-12b-it+google/gemma-scope-2-12b-it",
        "--run-id", "r-test-0001", "--source-commit", "0" * 40,
        "--job-deadline-epoch-seconds", str(__import__("time").time() + 100_000),
        "--out-dir", str(tmp_path / "out"), "--state-dir", str(tmp_path / "state"),
    ])
    result = one.run_generation_mode(args)

    assert result["status"] == "complete"
    assert result["attempted_concepts"] == ["cheese"]
    assert result["not_attempted"] == []
    assert result["causal_order"] == ["cheese"]
    assert result["timing"]["seconds_per_generation"] > 0
    assert "measured" in result["timing"]["basis"].lower()

    for direction in ("amplify", "suppress"):
        manifest_path = Path(result["manifest_paths"]["cheese"][direction])
        assert manifest_path.is_file()
        manifest = one.verify_generation_manifest(manifest_path)
        assert manifest["concept_id"] == "cheese"
        assert manifest["direction"] == direction.upper()
        assert manifest["causal_order_position"] == one.causal_order_position_for("cheese")
        assert len(manifest["files"]) == 900  # one direction's full complement of generations
        real_prompt_ids = {e["prompt_id"] for e in manifest["files"]}
        assert all(isinstance(pid, str) and pid for pid in real_prompt_ids)
        assert not any(pid.startswith(("sweep_", "confirmation_")) for pid in real_prompt_ids)
        # P0 STOP-LINE correction: DERIVED from the backend's own real
        # tokenizer (fakes.py's fake Gemma tokenizer), never the removed
        # --chat-template-identity CLI label.
        assert manifest["chat_template_identity"] == d.resolve_chat_template_identity(
            d.resolve_tokenizer_for_backend(backend)
        )
        # Engineer 3 delta (commit 9a32246): generation_kwargs carries all 10
        # frozen values (including max_new_tokens), and skipped_for_gate_failure
        # is the real, computed array of gate-failed concepts at-or-before
        # cheese's own causal-order position -- formal_register (position 1)
        # failed G-A/B/C and must be named here.
        assert manifest["generation_kwargs"]["max_new_tokens"] == d.ONE_ALLOCATION_MAX_NEW_TOKENS
        assert len(manifest["generation_kwargs"]) == 10
        assert manifest["skipped_for_gate_failure"] == ["formal_register"]


def test_run_generation_mode_breaks_after_the_first_concept_that_cannot_fit(tmp_path, monkeypatch):
    """P0 STOP-LINE correction: 'after the first concept cannot fit,
    BREAK; do not continue probing later concepts.' formal_register
    (causal order position 1) is readied and attempted; cheese (position
    2) must be refused and the loop must BREAK -- never checking cheese's
    own readiness a second time, and never calling generate_concept_
    complete for it at all (no further GPU probing)."""
    backend = fakes.make_fake_gemma_backend()
    monkeypatch.setattr(d, "load_backend", lambda **_kwargs: backend)
    monkeypatch.setattr(d, "ONE_ALLOCATION_MAX_NEW_TOKENS", 1)

    grid_dir = tmp_path / "grid"
    d.write_grid_result(
        grid_dir, backend.pairing,
        [
            d.ConceptPairingVerdict(concept_id="formal_register", pairing=backend.pairing, status="pass", surviving_feature_index=CONCEPT_FEATURE, candidates_evaluated=[], error=None),
            d.ConceptPairingVerdict(concept_id="cheese", pairing=backend.pairing, status="pass", surviving_feature_index=CONCEPT_FEATURE, candidates_evaluated=[], error=None),
        ],
    )

    call_count = {"n": 0}

    def fake_readiness(*, remaining_wall_time_seconds, seconds_per_generation):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return one.ConceptGenerationReadiness(attempt=True, detail="first concept fits")
        return one.ConceptGenerationReadiness(attempt=False, detail="does not fit")

    monkeypatch.setattr(one, "assess_concept_generation_readiness", fake_readiness)

    generate_calls: list[str] = []
    real_generate_concept_complete = one.generate_concept_complete

    def spy_generate_concept_complete(*args, **kwargs):
        generate_calls.append(kwargs.get("concept_id"))
        return real_generate_concept_complete(*args, **kwargs)

    monkeypatch.setattr(one, "generate_concept_complete", spy_generate_concept_complete)

    args = one.parse_args([
        "--pairing", backend.pairing, "--model-path", "unused", "--sae-path", "unused", "--layer", "29",
        "--configuration-name", "primary", "--grid-path", str(grid_dir / "grid.json"),
        "--pairing-id", "google/gemma-3-12b-it+google/gemma-scope-2-12b-it",
        "--run-id", "r-test-0001", "--source-commit", "0" * 40,
        "--job-deadline-epoch-seconds", str(__import__("time").time() + 100_000),
        "--out-dir", str(tmp_path / "out"), "--state-dir", str(tmp_path / "state"),
    ])
    result = one.run_generation_mode(args)

    assert result["attempted_concepts"] == ["formal_register"]
    assert [x["concept_id"] for x in result["not_attempted"]] == ["cheese"]
    assert call_count["n"] == 2  # readiness checked exactly once per concept, never re-checked for cheese
    assert generate_calls == ["formal_register"]  # cheese's generation never even started
    assert result["status"] == "partial_wall_time_cutoff"


def test_run_generation_mode_rejects_a_source_commit_disagreeing_with_the_transfer_manifest(tmp_path, monkeypatch):
    backend = fakes.make_fake_gemma_backend()
    monkeypatch.setattr(d, "load_backend", lambda **_kwargs: backend)
    monkeypatch.setattr(d, "ONE_ALLOCATION_MAX_NEW_TOKENS", 1)
    # A structurally-VALID fake transfer manifest (real file hashes, so
    # load_frozen_prompt_artifact's OWN internal transfer-manifest check
    # -- called earlier in run_generation_mode, via the same function --
    # passes cleanly) with only source_commit disagreeing with --source-commit.
    jsonl_path = d.REPO_ROOT / d.FROZEN_PROMPT_SET_DIR / "prompt_sets.jsonl"
    metadata_path = d.REPO_ROOT / d.FROZEN_PROMPT_SET_DIR / "metadata.json"
    fake_transfer_manifest = {
        "source_commit": "1" * 40,
        "files": {
            f"{d.FROZEN_PROMPT_SET_DIR}/prompt_sets.jsonl": d.compute_file_sha256(jsonl_path),
            f"{d.FROZEN_PROMPT_SET_DIR}/metadata.json": d.compute_file_sha256(metadata_path),
        },
    }
    monkeypatch.setattr(d, "load_transfer_manifest", lambda _repo_root: fake_transfer_manifest)

    grid_dir = tmp_path / "grid"
    d.write_grid_result(
        grid_dir, backend.pairing,
        [d.ConceptPairingVerdict(
            concept_id="cheese", pairing=backend.pairing, status="pass",
            surviving_feature_index=CONCEPT_FEATURE, candidates_evaluated=[], error=None,
        )],
    )
    args = one.parse_args([
        "--pairing", backend.pairing, "--model-path", "unused", "--sae-path", "unused", "--layer", "29",
        "--configuration-name", "primary", "--grid-path", str(grid_dir / "grid.json"),
        "--pairing-id", "google/gemma-3-12b-it+google/gemma-scope-2-12b-it",
        "--run-id", "r-test-0001", "--source-commit", "0" * 40,
        "--job-deadline-epoch-seconds", str(__import__("time").time() + 100_000),
        "--out-dir", str(tmp_path / "out"), "--state-dir", str(tmp_path / "state"),
    ])
    with pytest.raises(ValueError, match="disagrees with this checkout's own"):
        one.run_generation_mode(args)
