"""Final-pairing shared-concept discovery and calibration runner.

SCOPE, explicitly: this is a DISCOVERY tool, not the mechanical-acceptance
harness (final_pairing_harness.py, untouched by this file) and not
Engineer 3's sealing/certification pipeline (interplab/, untouched by this
file). It discovers CANDIDATE features for a researcher-supplied concept on
the two ratified final pairings (google/gemma-3-12b-it +
google/gemma-scope-2-12b-it, and Qwen/Qwen3.5-27B +
Qwen/SAE-Res-Qwen3.5-27B-W80K-L0_50), runs held-out specificity validation,
single-feature (and optionally multi-feature bundle) causal intervention,
direction-specific dose-response, and emits Low/Medium/High calibration
candidates -- all as MECHANICAL/statistical evidence for later scientific
and behavioral judgment, never as a concept label, a scientific threshold,
or a sealed/ATTESTED bundle. Every threshold this task's own work order
calls "the Architect's rule" (specificity pass/fail, bundle-composition
materiality, and the three calibration-tier boundaries) is a REQUIRED
command-line argument with no code default -- this file invents none of
them (see "Unresolved protocol fields" in
docs/final_pairing_concept_discovery_packet.md).

Reuse decisions (searched first, per this task's own instruction):

- Model/SAE loading: `final_pairing_harness.load_gemma_it_target` /
  `load_qwen_target` (imported, not copied) -- the same mechanically-
  accepted loaders jobs 407008/406092 already exercised. Fails closed on
  any non-ratified pairing/revision/subdirectory for free, since those
  loaders already do that.
- Intervention hooking: `interplab.interventions.hooks._make_clamp_hook`
  (imported unmodified, exactly as final_pairing_harness.py already does)
  is the canonical CLAMP/ABLATE contract -- ablate is `clamp_value=0.0`,
  clamp is `value_in_max_units * corpus_max`, both share one
  implementation. `final_pairing_harness.wrap_hook_with_diagnostics` /
  `InterventionTrace` / `mechanical_verdict` (imported, not copied) supply
  the exact same per-call diagnostic trace the mechanical-acceptance
  harness already emits, so this tool's intervention records are
  schema-compatible with that accepted work.
- Held-out probe recipe: the frozen LogisticRegression/StratifiedKFold
  recipe constants in `interplab.validation.probe.PROBE_RECIPE` are reused
  verbatim for the solver/max_iter choice. The actual TRAIN-vs-HELD-OUT
  split this task asks for ("held-out specificity validation" as a stage
  distinct from ranking) is NOT what `interplab.validation.probe.train_probe`
  does (it is cross-validated *within* one set, with no separate held-out
  split) -- so this file duplicates the small (~10-line) sklearn
  fit/score pattern with genuine train/held-out semantics, per this
  project's own Ground Rule 2 ("duplicate rather than cross-import" --
  scripts/legacy/gemma3_necessity.py's module docstring) rather than
  bending a frozen, differently-scoped primitive to a new shape.
- Activation ranking / corpus-max scale: `interplab.characterization.
  feature_index.FeatureIndex.search_by_activation` and `interplab.
  characterization.indexer.build_index` are HookedTransformer-only
  (`model.to_tokens`/`model.run_with_cache`) -- directly reusable for the
  Gemma pairing, structurally impossible to reuse unmodified for Qwen
  (raw `AutoModelForCausalLM`, no HookedTransformer -- transformer_lens
  has no Qwen3.5 entry, confirmed in final_pairing_targets.py). Per Ground
  Rule 2, the SAME algorithm (per-text max activation, ranked descending)
  is duplicated for the Qwen raw-forward-hook path rather than importing
  something that would silently no-op or crash against a non-TL model.
- `interplab.interventions.spec.InterventionSpec`'s field shape (kind,
  feature_index, value_in_max_units, corpus_max, positions,
  checkpoint_hash, direction_seed) is reused as the JSON shape of every
  `spec` block this file writes, so a later pass through Engineer 3's
  sealing pipeline (interplab/jobs/report.py's chain assembly, which reads
  an intervention_result's `payload.spec`) sees a familiar shape --
  without this file calling `envelope.dump`/`registry.put` itself. This
  file never authors an A9 envelope or writes to the registry; "emit
  enough structured evidence for Engineer 3's sealing pipeline" is
  satisfied by shape-compatibility, not by this tool doing the sealing.

Never-do list, enforced in code, not just prose:

- `feature_idx == 250` (Gemma) / `4096` (Qwen) -- the mechanical-acceptance
  harness's own engineering-only placeholder features -- are hard-excluded
  from every shortlist/bundle/calibration output (`_MECHANICAL_ONLY_
  FEATURE_IDS`), even if activation ranking organically surfaces them.
- No suppression score is ever derived from an amplification-direction
  number's sign, or vice versa: a `--direction ablate` run records only
  quantities it directly measured for ablate; a `--direction clamp` run
  never contributes to an ablate-direction field. There is no code path
  that negates one direction's number to stand in for the other's.
- Every numerical field this file writes is non-negative by construction:
  norms, absolute activations, AUC-like scores in [0, 1], and bundle-
  composition "gain" fields (reported only when a candidate is actually
  added, i.e. exactly when the gain is >= the materiality threshold >= 0).
  Rejected bundle candidates report their own absolute metric value, never
  a signed delta.
- `--pairing`/`--model-path`/`--sae-path` reject anything but the two
  ratified final targets for free (inherited from `load_gemma_it_target`/
  `load_qwen_target`, which already fail closed via `final_pairing_
  targets.py`'s validators on any other repo/revision/subdirectory). This
  file adds nothing on top for that -- it is not re-derived, it is
  inherited.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent
# final_pairing_harness.py/final_pairing_targets.py are the frozen,
# already-accepted mechanical-acceptance artifacts (job 407008/406092) and
# deliberately remain under scripts/legacy/ -- this file lives under the
# non-legacy scripts/final_pairing/ (the current canonical discovery
# runner), so BOTH directories go on sys.path.
LEGACY_SCRIPT_DIR = SCRIPT_DIR.parent / "legacy"
sys.path.insert(0, str(LEGACY_SCRIPT_DIR))
sys.path.insert(0, str(SCRIPT_DIR))  # inserted LAST -> searched FIRST, so this file's own name never resolves to a scripts/legacy/ compatibility stub of the same name

import final_pairing_harness as harness  # noqa: E402
import final_pairing_targets as targets  # noqa: E402

SCHEMA_VERSION = 1

# The mechanical-acceptance harness's own engineering-only placeholder
# features -- never a concept, regardless of what activation ranking finds.
_MECHANICAL_ONLY_FEATURE_IDS: dict[str, int] = {
    "gemma-3-12b-it": 250,
    "qwen-3.5-27b": 4096,
}

_NOOP_JUDGE_IDENTITY = {"model": "none", "rubric_version": "none", "prompt_version": "none"}


@dataclass(frozen=True)
class MatchedConfiguration:
    """One of the two predeclared, matched Qwen/Gemma layer+family
    configurations. Values are given exactly as predeclared -- this file
    never derives or adjusts them. `PRIMARY_CONFIGURATION` and
    `BACKUP_CONFIGURATION` are the ONLY two authorized configurations;
    `MATCHED_CONFIGURATIONS` is the single source of truth every
    layer/family validator below reads from, so there is no second place a
    third configuration could be silently introduced.

    The Boolean rule for WHEN to use `backup` instead of `primary` is
    frozen separately, at `protocols/final_pairing/v1/backup_trigger.json`
    (commit 125b1d3) -- see `evaluate_backup_trigger`/
    `BACKUP_TRIGGER_SHARED_COUNT_THRESHOLD` below. `qwen_depth_fraction`
    here is that same frozen file's `configurations.<NAME>.qwen.
    depth_fraction`, used by `assert_gemma_qwen_depth_matches`; Gemma's own
    depth_fraction is deliberately NOT a stored constant (the frozen file
    itself requires it be computed from the actually-loaded model's real
    n_layers at run time, never assumed).

    `gemma_sae_release`/`gemma_sae_loader_id`/`gemma_sae_id` are recorded
    PER CONFIGURATION, never derived from one shared naming formula:
    confirmed directly against the locally-installed `sae_lens==6.44.2`
    registry (`get_pretrained_saes_directory()`) that primary's
    `resid_post_all` family and backup's `resid_post` family are TWO
    DIFFERENT releases (`gemma-scope-2-12b-it-res-all` has 192 loader ids
    including `layer_29_width_16k_l0_big` but NO `layer_24_..._l0_medium`
    variant at all; `gemma-scope-2-12b-it-res` has 52 loader ids including
    `layer_24_width_16k_l0_medium` but NO `layer_29_...` entry at all) --
    assuming one release for both, as an earlier version of this file did
    via a single f-string formula, would have failed
    `validate_sae_loader_id_registered` for the primary configuration at
    runtime, not merely been imprecise.

    This same fact is now separately, formally frozen at
    `protocols/final_pairing/v1/scientific_config_identity.json`
    (`final-pairing-config-identity/1.2.0`, commit 93450e5): BOTH releases
    are FORCED (PRIMARY because layer 29 is off the canonical resid_post
    grid; BACKUP because `resid_post_all` does not publish `l0_medium` at
    layer 24 at all -- OI-1, closed) -- the split is NECESSARY, not
    cosmetic, an earlier ("packaging, not a third family") premise that
    protocol version explicitly WITHDRAWS. Per that same protocol: a
    PRIMARY-to-BACKUP difference moves layer, sparsity tier, AND release/
    training-artifact simultaneously in Gemma (and layer/k in Qwen) --
    nothing in this file may attribute an observed PRIMARY-vs-BACKUP
    outcome to any ONE of those dimensions; backup is a fallback
    configuration, not a controlled ablation. Qwen TopK `k` and Gemma
    observed L0 remain non-commensurable throughout this file: no ratio,
    proportional-match, or "aligned/similar/matched sparsity" claim is
    ever made between them anywhere in this codebase (verified by a
    literal repo-wide search for those exact retracted phrasings during
    the 1.2.0 integration pass) -- matching between the two models is by
    transformer depth fraction ONLY (`qwen_depth_fraction`/
    `assert_gemma_qwen_depth_matches`)."""

    name: Literal["primary", "backup"]
    qwen_layer: int
    qwen_sae_family: str
    qwen_sparsity: int
    gemma_layer: int
    qwen_depth_fraction: float
    gemma_sae_release: str
    gemma_sae_id: str
    gemma_sae_loader_id: str


PRIMARY_CONFIGURATION = MatchedConfiguration(
    name="primary", qwen_layer=38, qwen_sae_family="L0_100", qwen_sparsity=100, gemma_layer=29, qwen_depth_fraction=0.59375,
    gemma_sae_release="gemma-scope-2-12b-it-res-all", gemma_sae_id="resid_post_all/layer_29_width_16k_l0_big",
    gemma_sae_loader_id="layer_29_width_16k_l0_big",
)
BACKUP_CONFIGURATION = MatchedConfiguration(
    name="backup", qwen_layer=32, qwen_sae_family="L0_50", qwen_sparsity=50, gemma_layer=24, qwen_depth_fraction=0.5,
    gemma_sae_release="gemma-scope-2-12b-it-res", gemma_sae_id="resid_post/layer_24_width_16k_l0_medium",
    gemma_sae_loader_id="layer_24_width_16k_l0_medium",
)
MATCHED_CONFIGURATIONS: dict[str, MatchedConfiguration] = {"primary": PRIMARY_CONFIGURATION, "backup": BACKUP_CONFIGURATION}

# The backup trigger's exact Boolean rule -- frozen at
# protocols/final_pairing/v1/backup_trigger.json (commit 125b1d3), found
# AFTER this module's docstring elsewhere was written to say no such rule
# existed. It does exist. `evaluate_backup_trigger` below implements
# EXACTLY its `trigger.boolean_expression`/`failure_expression`, no more.
# What is NOT implemented here: computing `primary_shared_gabc_count`
# itself requires a full 14-concept x 2-pairing x 3-gate x 3-family x
# 2-locale grid (`primary_complete`'s own definition) with per-feature
# G-A/B/C conjunction (`feature_survives_gabc`) -- this runner currently
# discovers ONE concept per invocation and has no G-C (AUROC vs near_miss)
# implementation at all yet. That aggregation is real, separate follow-up
# work; `--run-backup`/`--trigger-inputs-json` in the matched-configuration
# job remain the way that count reaches this formula until it exists.
BACKUP_TRIGGER_PROTOCOL_PATH = "protocols/final_pairing/v1/backup_trigger.json"
BACKUP_TRIGGER_PROTOCOL_SHA256 = "4a234e59799089e634f00c59d5fed71c73d0f7466e30f0c20a7d72ef4c9d23d3"
BACKUP_TRIGGER_SHARED_COUNT_THRESHOLD = 3  # frozen; "may not be changed after any activation is computed"


def validate_backup_trigger_protocol_hash(repo_root: str | Path) -> str:
    """Fails closed if `protocols/final_pairing/v1/backup_trigger.json`'s
    actual bytes don't match the pinned hash -- the same discipline
    applied to the frozen prompt artifact (`load_frozen_prompt_artifact`)
    applied to this protocol file too, since the backup-trigger formula's
    threshold is frozen precisely because it "may not be changed after
    any activation is computed"."""
    path = Path(repo_root) / BACKUP_TRIGGER_PROTOCOL_PATH
    if not path.is_file():
        raise PromptArtifactError(f"backup-trigger protocol not found at {path}")
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != BACKUP_TRIGGER_PROTOCOL_SHA256.lower():
        raise PromptArtifactError(
            f"{path} sha256={actual!r} != pinned {BACKUP_TRIGGER_PROTOCOL_SHA256!r} -- refusing to "
            f"run discovery against an altered or unpinned backup-trigger protocol."
        )
    return actual


@dataclass(frozen=True)
class BackupTriggerResult:
    run_backup: bool
    fail_run: bool
    primary_complete: bool
    primary_shared_gabc_count: int | None
    threshold: int


def evaluate_backup_trigger(*, primary_complete: bool, primary_shared_gabc_count: int | None) -> BackupTriggerResult:
    """`RUN_BACKUP = primary_complete AND (primary_shared_gabc_count < 3)`;
    `FAIL_RUN = NOT primary_complete`. An execution error never triggers
    backup -- when `primary_complete` is False, `primary_shared_gabc_count`
    is never read (it may legitimately be `None`), and the result is
    `fail_run=True`, `run_backup=False` unconditionally, matching the
    protocol's own "an incomplete primary UNDERCOUNTS" reasoning: falling
    through to backup on an infrastructure failure would let it masquerade
    as a scientific finding."""
    if not primary_complete:
        return BackupTriggerResult(
            run_backup=False, fail_run=True, primary_complete=False,
            primary_shared_gabc_count=primary_shared_gabc_count, threshold=BACKUP_TRIGGER_SHARED_COUNT_THRESHOLD,
        )
    if primary_shared_gabc_count is None:
        raise ValueError("primary_shared_gabc_count is required when primary_complete is True")
    return BackupTriggerResult(
        run_backup=primary_shared_gabc_count < BACKUP_TRIGGER_SHARED_COUNT_THRESHOLD,
        fail_run=False, primary_complete=True, primary_shared_gabc_count=primary_shared_gabc_count,
        threshold=BACKUP_TRIGGER_SHARED_COUNT_THRESHOLD,
    )


def assert_gemma_qwen_depth_matches(*, gemma_layer: int, gemma_n_layers: int, qwen_depth_fraction: float, tolerance: float = 0.02) -> float:
    """`protocols/final_pairing/v1/backup_trigger.json`'s
    `depth_matching_assertion`: `abs(gemma_depth_fraction -
    qwen_depth_fraction) <= 0.02` for whichever configuration is running,
    computed from the ACTUALLY LOADED Gemma model's own `n_layers` (never
    assumed). Raises (never warns) on violation -- "the pairing claim
    rests on matched depth; an unverified match is not a match." Returns
    the computed `gemma_depth_fraction` for provenance recording."""
    gemma_depth_fraction = gemma_layer / gemma_n_layers
    if abs(gemma_depth_fraction - qwen_depth_fraction) > tolerance:
        raise targets.TargetIdentityMismatch(
            f"depth mismatch: gemma_depth_fraction={gemma_depth_fraction!r} (layer {gemma_layer} of "
            f"{gemma_n_layers}) vs qwen_depth_fraction={qwen_depth_fraction!r}, tolerance={tolerance} -- "
            f"STOP, do not compute activations, per the frozen depth_matching_assertion."
        )
    return gemma_depth_fraction

_PROBE_MIN_EXAMPLES_PER_CLASS = 5  # matches interplab.validation.probe's own floor


# ---------------------------------------------------------------------------
# Prompt-set: one hash-pinned JSON artifact carrying every text role this
# runner needs. Researcher-authored, never generated by this file (same
# "load/validate only" discipline as interplab.corpus.battery's concept
# battery, per the earlier research pass).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PromptSet:
    concept_id: str
    probes: list[str]
    controls: list[str]
    holdout_probes: list[str]
    holdout_controls: list[str]
    background_corpus: list[str]
    source_path: str
    sha256: str


def load_prompt_set(path: str | Path, *, expected_sha256: str) -> PromptSet:
    """Fails closed if the file's actual bytes don't match
    `expected_sha256` -- the prompt-set is pinned exactly like every
    model/SAE revision elsewhere in this project, since it deterministically
    drives which features get discovered."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"prompt-set file not found: {path}")
    raw = path.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if actual != expected_sha256.lower():
        raise targets.TargetIdentityMismatch(
            f"prompt-set at {path!r} has sha256={actual!r}, expected {expected_sha256.lower()!r} "
            f"-- refusing to run discovery against an unpinned or altered prompt set."
        )
    data = json.loads(raw.decode("utf-8"))
    required_list_fields = ("probes", "controls", "holdout_probes", "holdout_controls", "background_corpus")
    missing = [f for f in required_list_fields if f not in data]
    if missing:
        raise ValueError(f"prompt-set {path!r} is missing required field(s): {missing}")
    if "concept_id" not in data or not isinstance(data["concept_id"], str) or not data["concept_id"]:
        raise ValueError(f"prompt-set {path!r} must have a non-empty string 'concept_id'")
    for f in required_list_fields:
        if not isinstance(data[f], list) or not all(isinstance(x, str) for x in data[f]):
            raise ValueError(f"prompt-set {path!r} field {f!r} must be a list of strings")
    return PromptSet(
        concept_id=data["concept_id"],
        probes=list(data["probes"]),
        controls=list(data["controls"]),
        holdout_probes=list(data["holdout_probes"]),
        holdout_controls=list(data["holdout_controls"]),
        background_corpus=list(data["background_corpus"]),
        source_path=str(path),
        sha256=actual,
    )


FROZEN_PROMPT_SET_COMMIT = "880b48a7f50b8c716e64956b915857dd1fcde350"
FROZEN_PROMPT_SET_DIR = "prompts/final_pairing/v1"
FROZEN_PROMPT_SETS_SHA256 = "b0b23cf1502dae53f88905ee7393b7e67f8b05f84f3251d26a6c506480a9531f"
FROZEN_METADATA_SHA256 = "3f8e298a18c5ba03a2aaaa4a4b99302602f381ee42b024b131fd2cf63b4b59ce"
FROZEN_PROMPT_SET_ROW_COUNT = 2800
FROZEN_PROMPT_SET_CONCEPT_COUNT = 14
FROZEN_PROMPT_SET_LOCALES = ("en", "fr")
FROZEN_PROMPT_SET_SPLITS = ("positive", "near_miss", "unrelated", "heldout_neutral", "heldout_eliciting")
FROZEN_PROMPT_SET_SHARED_SUBSTRATE_SPLITS = ("unrelated", "heldout_neutral")
PI_GATED_CONCEPT_ID = "political_framing"


class PromptArtifactError(ValueError):
    """The frozen artifact's commit/hashes don't match, the working tree
    has uncommitted changes under it, the row/concept/locale/split counts
    don't match the pinned expectation, or the committed validator itself
    failed. Always raised before either discovery lane runs."""


@dataclass(frozen=True)
class FrozenPromptArtifact:
    commit: str
    prompt_sets_sha256: str
    metadata_sha256: str
    metadata: dict
    rows: list[dict]  # PI-gated concept's rows already excluded unless allow_pi_gated
    pi_gated_excluded_row_count: int


def _git(repo_root: Path, *args: str) -> tuple[int, str]:
    import subprocess

    proc = subprocess.run(["git", *args], cwd=str(repo_root), capture_output=True, text=True)
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def load_frozen_prompt_artifact(repo_root: str | Path, *, allow_pi_gated: bool = False) -> FrozenPromptArtifact:
    """Loads and validates `prompts/final_pairing/v1/` against the pinned
    commit/hashes -- never copy-edits or regenerates anything (the two
    files are only ever read). Refuses:

    - a working tree with uncommitted changes under the artifact directory
      ("dirty or uncommitted replacements");
    - either file's actual sha256 disagreeing with the pinned value;
    - a row/concept/locale/split count that disagrees with the pinned
      metadata (2,800 rows; 14 concepts; en+fr; all five declared splits).

    The PI-gated concept (`political_framing`) is excluded from `.rows`
    unless `allow_pi_gated=True` is passed explicitly -- there is no
    default-on path to a public configuration seeing it.
    """
    repo_root = Path(repo_root)
    artifact_dir = repo_root / FROZEN_PROMPT_SET_DIR
    jsonl_path = artifact_dir / "prompt_sets.jsonl"
    metadata_path = artifact_dir / "metadata.json"
    if not jsonl_path.is_file() or not metadata_path.is_file():
        raise PromptArtifactError(f"frozen prompt artifact not found under {artifact_dir}")

    rc, out = _git(repo_root, "status", "--porcelain", "--", str(FROZEN_PROMPT_SET_DIR))
    if rc != 0:
        raise PromptArtifactError(f"git status failed while checking the frozen prompt artifact: {out}")
    if out.strip():
        raise PromptArtifactError(
            f"the frozen prompt artifact directory has uncommitted changes -- refusing to run "
            f"discovery against a dirty or uncommitted replacement:\n{out}"
        )

    actual_metadata_hash = hashlib.sha256(metadata_path.read_bytes()).hexdigest()
    actual_jsonl_hash = hashlib.sha256(jsonl_path.read_bytes()).hexdigest()
    if actual_metadata_hash != FROZEN_METADATA_SHA256.lower():
        raise PromptArtifactError(
            f"metadata.json sha256={actual_metadata_hash!r} != pinned {FROZEN_METADATA_SHA256!r}"
        )
    if actual_jsonl_hash != FROZEN_PROMPT_SETS_SHA256.lower():
        raise PromptArtifactError(
            f"prompt_sets.jsonl sha256={actual_jsonl_hash!r} != pinned {FROZEN_PROMPT_SETS_SHA256!r}"
        )

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("row_count") != FROZEN_PROMPT_SET_ROW_COUNT:
        raise PromptArtifactError(f"metadata.json row_count={metadata.get('row_count')!r} != {FROZEN_PROMPT_SET_ROW_COUNT}")
    if metadata.get("concept_count") != FROZEN_PROMPT_SET_CONCEPT_COUNT:
        raise PromptArtifactError(f"metadata.json concept_count={metadata.get('concept_count')!r} != {FROZEN_PROMPT_SET_CONCEPT_COUNT}")
    if sorted(metadata.get("locales", [])) != sorted(FROZEN_PROMPT_SET_LOCALES):
        raise PromptArtifactError(f"metadata.json locales={metadata.get('locales')!r} != {FROZEN_PROMPT_SET_LOCALES}")
    if sorted(metadata.get("splits", [])) != sorted(FROZEN_PROMPT_SET_SPLITS):
        raise PromptArtifactError(f"metadata.json splits={metadata.get('splits')!r} != {FROZEN_PROMPT_SET_SPLITS}")

    all_rows = [json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines() if line]
    if len(all_rows) != FROZEN_PROMPT_SET_ROW_COUNT:
        raise PromptArtifactError(f"prompt_sets.jsonl has {len(all_rows)} rows, expected {FROZEN_PROMPT_SET_ROW_COUNT}")

    concept_ids = {row["concept_id"] for row in all_rows}
    if len(concept_ids) != FROZEN_PROMPT_SET_CONCEPT_COUNT:
        raise PromptArtifactError(f"prompt_sets.jsonl has {len(concept_ids)} distinct concepts, expected {FROZEN_PROMPT_SET_CONCEPT_COUNT}")
    locales_present = {row["locale"] for row in all_rows}
    if not set(FROZEN_PROMPT_SET_LOCALES).issubset(locales_present):
        raise PromptArtifactError(f"prompt_sets.jsonl is missing locale(s): {set(FROZEN_PROMPT_SET_LOCALES) - locales_present}")
    splits_present = {row["split"] for row in all_rows}
    if not set(FROZEN_PROMPT_SET_SPLITS).issubset(splits_present):
        raise PromptArtifactError(f"prompt_sets.jsonl is missing split(s): {set(FROZEN_PROMPT_SET_SPLITS) - splits_present}")
    families_present = {row["family"] for row in all_rows if row["split"] == "positive"}
    if not families_present or any(f is None for f in families_present):
        raise PromptArtifactError("prompt_sets.jsonl has positive-split row(s) with no family assigned")

    pi_gated_excluded = 0
    rows = all_rows
    if not allow_pi_gated:
        rows = [row for row in all_rows if row["concept_id"] != PI_GATED_CONCEPT_ID]
        pi_gated_excluded = len(all_rows) - len(rows)

    return FrozenPromptArtifact(
        commit=FROZEN_PROMPT_SET_COMMIT, prompt_sets_sha256=actual_jsonl_hash, metadata_sha256=actual_metadata_hash,
        metadata=metadata, rows=rows, pi_gated_excluded_row_count=pi_gated_excluded,
    )


def run_prompt_set_validator(repo_root: str | Path) -> None:
    """Invokes the committed `validate_prompt_sets.py` as a real subprocess
    (never re-implemented here) and raises `PromptArtifactError` on any
    nonzero exit -- callers (the dual-GPU orchestrator, in particular) must
    call this BEFORE launching either lane, so a validation failure stops
    both, not just whichever lane happened to check first."""
    import subprocess

    repo_root = Path(repo_root)
    validator_path = repo_root / FROZEN_PROMPT_SET_DIR / "validate_prompt_sets.py"
    if not validator_path.is_file():
        raise PromptArtifactError(f"committed validator not found at {validator_path}")
    proc = subprocess.run([sys.executable, str(validator_path)], capture_output=True, text=True)
    if proc.returncode != 0:
        raise PromptArtifactError(
            f"validate_prompt_sets.py exited {proc.returncode} -- refusing to proceed:\n"
            f"{proc.stdout}\n{proc.stderr}"
        )


def rows_for_concept(
    rows: list[dict], *, concept_id: str, locale: str, split: str, family: str | None = None
) -> list[dict]:
    """Preserves shared_substrate semantics: `unrelated`/`heldout_neutral`
    rows are IDENTICAL across all 14 concepts by design (the README's own
    "must not fix" invariant) -- this function filters by concept_id
    normally, which for those two splits legitimately returns the SAME
    rows regardless of which concept_id was asked for, since every
    concept's `unrelated`/`heldout_neutral` rows in the artifact already
    carry `shared_substrate: true` and identical text. Nothing here
    deduplicates across concepts."""
    return [
        row for row in rows
        if row["concept_id"] == concept_id and row["locale"] == locale and row["split"] == split
        and (family is None or row.get("family") == family)
    ]


@dataclass(frozen=True)
class JudgeIdentity:
    model: str
    rubric_version: str
    prompt_version: str


@dataclass(frozen=True)
class GateABResult:
    concept_id: str
    locale: str
    family: str
    feature_index: int
    separation_auroc: float
    gate_a_passed: bool
    fire_rate: float
    activation_floor_fraction: float
    gate_b_passed: bool


def _auroc_from_scores(positive_scores: list[float], negative_scores: list[float]) -> float:
    from sklearn.metrics import roc_auc_score

    y = [1] * len(positive_scores) + [0] * len(negative_scores)
    scores = [*positive_scores, *negative_scores]
    return float(roc_auc_score(y, scores))


def compute_gate_a_and_b_per_family(
    backend: Backend, artifact: FrozenPromptArtifact, *, concept_id: str, locale: str, feature_index: int,
    auroc_min: float | None = None, activation_floor_fraction: float | None = None, fire_rate_min: float | None = None,
) -> list[GateABResult]:
    """G-A (separation AUROC, positive vs. unrelated) and G-B (activation
    floor / fire rate) computed INDEPENDENTLY per paraphrase family, never
    pooled -- per this artifact's own README ("pooling would hide a
    feature that fires on only one phrasing"). Thresholds default to the
    frozen artifact's own `metadata.json["thresholds"]` (never invented by
    this file) but may be overridden explicitly by a caller who has a
    reason to.

    `unrelated` is the shared_substrate split (identical across all 14
    concepts by design) -- `rows_for_concept` is called once per family
    below but always returns the SAME `unrelated` rows regardless of
    `concept_id`, which is correct, not a bug (see that function's
    docstring)."""
    thresholds = artifact.metadata["thresholds"]
    auroc_min = thresholds["G_A_separation_auroc_min"] if auroc_min is None else auroc_min
    floor_fraction = thresholds["G_B_activation_floor_fraction_of_observed_max"] if activation_floor_fraction is None else activation_floor_fraction
    fire_rate_min = thresholds["G_B_fire_rate_min"] if fire_rate_min is None else fire_rate_min

    unrelated_texts = [r["text"] for r in rows_for_concept(artifact.rows, concept_id=concept_id, locale=locale, split="unrelated")]
    if not unrelated_texts:
        raise ValueError(f"no 'unrelated' rows found for concept_id={concept_id!r} locale={locale!r}")
    _, negative_scores_arr = _pooled_residual_and_feature(backend, unrelated_texts, feature_index)
    negative_scores = negative_scores_arr.tolist()

    families = sorted({
        r["family"] for r in artifact.rows
        if r["concept_id"] == concept_id and r["locale"] == locale and r["split"] == "positive"
    })
    if not families:
        raise ValueError(f"no positive-split families found for concept_id={concept_id!r} locale={locale!r}")

    results = []
    for family in families:
        positive_texts = [
            r["text"] for r in rows_for_concept(artifact.rows, concept_id=concept_id, locale=locale, split="positive", family=family)
        ]
        _, positive_scores_arr = _pooled_residual_and_feature(backend, positive_texts, feature_index)
        positive_scores = positive_scores_arr.tolist()

        auroc = _auroc_from_scores(positive_scores, negative_scores)
        gate_a_passed = auroc >= auroc_min

        observed_max = max(positive_scores) if positive_scores else 0.0
        floor = observed_max * floor_fraction
        fire_rate = (sum(1 for s in positive_scores if s > floor) / len(positive_scores)) if positive_scores else 0.0
        gate_b_passed = fire_rate >= fire_rate_min

        results.append(
            GateABResult(
                concept_id=concept_id, locale=locale, family=family, feature_index=feature_index,
                separation_auroc=auroc, gate_a_passed=gate_a_passed,
                fire_rate=fire_rate, activation_floor_fraction=floor_fraction, gate_b_passed=gate_b_passed,
            )
        )
    return results


@dataclass(frozen=True)
class GateCResult:
    concept_id: str
    locale: str
    family: str
    feature_index: int
    near_miss_auroc: float
    gate_c_passed: bool


def compute_gate_c_per_family(
    backend: Backend, artifact: FrozenPromptArtifact, *, concept_id: str, locale: str, feature_index: int,
    auroc_min: float | None = None,
) -> list[GateCResult]:
    """G-C (specificity AUROC, positive vs. near_miss), computed
    INDEPENDENTLY per paraphrase family -- same per-family discipline as
    G-A/G-B, for the same reason: pooling would let a feature that only
    separates from its near-miss foils on one phrasing pass on the
    strength of the others. Threshold defaults to the frozen artifact's own
    `metadata.json["thresholds"]["G_C_specificity_auroc_vs_near_miss_min"]`
    (never invented here). Unlike `unrelated`/`heldout_neutral`,
    `near_miss` is concept-specific, not shared_substrate -- each concept
    has its own near-miss foils, so `rows_for_concept` returns different
    rows per concept_id here."""
    thresholds = artifact.metadata["thresholds"]
    auroc_min = thresholds["G_C_specificity_auroc_vs_near_miss_min"] if auroc_min is None else auroc_min

    near_miss_texts = [r["text"] for r in rows_for_concept(artifact.rows, concept_id=concept_id, locale=locale, split="near_miss")]
    if not near_miss_texts:
        raise ValueError(f"no 'near_miss' rows found for concept_id={concept_id!r} locale={locale!r}")
    _, near_miss_scores_arr = _pooled_residual_and_feature(backend, near_miss_texts, feature_index)
    near_miss_scores = near_miss_scores_arr.tolist()

    families = sorted({
        r["family"] for r in artifact.rows
        if r["concept_id"] == concept_id and r["locale"] == locale and r["split"] == "positive"
    })
    if not families:
        raise ValueError(f"no positive-split families found for concept_id={concept_id!r} locale={locale!r}")

    results = []
    for family in families:
        positive_texts = [
            r["text"] for r in rows_for_concept(artifact.rows, concept_id=concept_id, locale=locale, split="positive", family=family)
        ]
        _, positive_scores_arr = _pooled_residual_and_feature(backend, positive_texts, feature_index)
        positive_scores = positive_scores_arr.tolist()

        auroc = _auroc_from_scores(positive_scores, near_miss_scores)
        results.append(
            GateCResult(
                concept_id=concept_id, locale=locale, family=family, feature_index=feature_index,
                near_miss_auroc=auroc, gate_c_passed=auroc >= auroc_min,
            )
        )
    return results


def feature_survives_gabc(gate_ab_results: list[GateABResult], gate_c_results: list[GateCResult]) -> bool:
    """True iff exactly one `feature_index` is present across BOTH lists and
    that feature passed G-A and G-B in every family/locale cell it was
    evaluated on, and G-C in every family/locale cell it was evaluated on.
    Raises rather than silently comparing across features if the caller
    passed results for more than one feature_index -- 'the same feature
    must pass G-A, G-B and G-C' is a precondition of this function, not
    something it resolves on the caller's behalf: gates passed by
    different features must never be combined into one survival verdict."""
    if not gate_ab_results or not gate_c_results:
        return False
    ab_features = {r.feature_index for r in gate_ab_results}
    c_features = {r.feature_index for r in gate_c_results}
    if len(ab_features) != 1 or len(c_features) != 1 or ab_features != c_features:
        raise ValueError(
            f"feature_survives_gabc requires G-A/G-B and G-C results for exactly one shared "
            f"feature_index; got G-A/B feature(s) {sorted(ab_features)} and G-C feature(s) "
            f"{sorted(c_features)}"
        )
    return (
        all(r.gate_a_passed and r.gate_b_passed for r in gate_ab_results)
        and all(r.gate_c_passed for r in gate_c_results)
    )


def load_judge_identity(path: str | Path | None) -> JudgeIdentity:
    """No real judge is implemented or invoked by this file -- this only
    records WHICH judge identity a later stage should use, honestly
    defaulting to the same "none" identity `interplab.characterization.
    indexer.NoOpJudge` records, per this task's own "do not invent concept
    labels" instruction. A non-default config is metadata only here."""
    if path is None:
        return JudgeIdentity(**_NOOP_JUDGE_IDENTITY)
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    for key in ("model", "rubric_version", "prompt_version"):
        if key not in data or not isinstance(data[key], str):
            raise ValueError(f"judge config {path!r} must have a string field {key!r}")
    return JudgeIdentity(model=data["model"], rubric_version=data["rubric_version"], prompt_version=data["prompt_version"])


# ---------------------------------------------------------------------------
# Backend: the one seam that differs between the two pairings. Everything
# above/below this section is generic over `Backend`.
# ---------------------------------------------------------------------------


@dataclass
class Backend:
    pairing: str
    model_obj: Any  # transformer_lens.HookedTransformer (Gemma) or a raw HF Qwen3_5ForCausalLM
    sae: Any
    hook_name: str  # provenance string; also the TL hook name for Gemma
    d_sae: int
    d_model: int
    layer: int
    provenance: dict
    checkpoint_hash: str
    sae_family: str | None = None  # Qwen only: "L0_100" | "L0_50" -- distinct from sparsity/layer
    sparsity: int | None = None  # Qwen only: k, distinct from sae_family/layer
    _qwen_decoder_layer: Any = None  # Qwen only: the actual nn.Module to register_forward_hook on
    _qwen_device: str = "cuda"


_QWEN_SCIENTIFIC_SAE_FAMILIES = tuple(c.qwen_sae_family for c in MATCHED_CONFIGURATIONS.values())


def _qwen_scientific_target(*, k: int) -> targets.TargetPairing:
    """A LOCAL variant of the ratified Qwen target for scientific discovery,
    built via `dataclasses.replace` rather than editing
    `final_pairing_targets.QWEN_3_5_27B_TARGET` in place. The mechanical
    target's `expected_k=50` is fixed to the engineering-only layer-0/L0_50
    pairing job 406092 already exercised; the ratified scientific SAE
    decision's primary search (SAE family L0_100) needs k=100, a genuinely
    different, independently-verified structural property of a different
    TopK SAE -- not a free override of the mechanically-accepted identity.
    Every OTHER field (repo ids, hidden dim, hook-name convention, format)
    stays exactly the ratified value; `expected_layer` was already `None`
    ("engineering-only, supplied by the caller") on the base target, so
    layer flexibility needs no override here."""
    import dataclasses as _dc

    return _dc.replace(targets.QWEN_3_5_27B_TARGET, expected_k=k)


def load_qwen_scientific_target(
    model_path: str | Path, sae_layer_file_path: str | Path, *, layer: int, sae_family: str, k: int,
    device: str = "cuda", dtype: str = "bfloat16",
    expected_model_revision: str | None = None, expected_sae_revision: str | None = None,
):
    """Duplicates `final_pairing_harness.load_qwen_target`'s body (per this
    project's own Ground Rule 2: duplicate rather than cross-import/modify
    a frozen, already-accepted file) with one difference: `target` is a
    locally-built scientific variant (see `_qwen_scientific_target`) rather
    than the module-level mechanical `QWEN_3_5_27B_TARGET`, so a k other
    than the mechanical target's fixed 50 can be validated against without
    touching final_pairing_harness.py or final_pairing_targets.py at all.
    `sae_family` is recorded in provenance as its own field, never folded
    into `k` or `layer` -- SAE family, transformer layer, and sparsity (k)
    stay three distinct fields throughout, per the ratified scientific SAE
    decision's explicit requirement."""
    import torch
    from transformers import AutoModelForCausalLM

    if sae_family not in _QWEN_SCIENTIFIC_SAE_FAMILIES:
        raise targets.TargetIdentityMismatch(
            f"--qwen-sae-family {sae_family!r} is not one of the two ratified scientific "
            f"candidates {_QWEN_SCIENTIFIC_SAE_FAMILIES} -- refusing to stage or validate a "
            f"third family."
        )
    if layer == 0:
        raise targets.TargetIdentityMismatch(
            "layer 0 is Qwen's engineering-only mechanical-acceptance layer (job 406092) and is "
            "not a scientific candidate -- refusing to run concept discovery against it."
        )

    target = _qwen_scientific_target(k=k)
    harness._require_offline()

    model_path = Path(model_path)
    sae_layer_file_path = Path(sae_layer_file_path)
    if not model_path.exists():
        raise FileNotFoundError(f"model snapshot directory not found: {model_path}")
    if not sae_layer_file_path.exists():
        raise FileNotFoundError(f"Qwen-Scope layer file not found: {sae_layer_file_path}")
    targets.validate_qwen_layer_filename(sae_layer_file_path, layer)
    targets.validate_qwen_layer_choice(layer, target)
    model_identity = targets.validate_local_snapshot_identity(
        model_path, target, which="model", expected_revision=expected_model_revision
    )
    sae_identity = targets.validate_local_snapshot_identity(
        sae_layer_file_path.parent, target, which="sae", expected_revision=expected_sae_revision
    )

    torch_dtype = getattr(torch, dtype)
    hf_model = AutoModelForCausalLM.from_pretrained(str(model_path), dtype=torch_dtype)
    targets.validate_runtime_class(type(hf_model).__name__, target)
    targets.validate_has_callable_generate(hf_model, label="loaded Qwen model")
    hf_model.eval()
    hf_model.to(device)

    text_decoder = harness.resolve_qwen_text_decoder(hf_model)
    hidden_size = text_decoder.config.hidden_size

    sae = harness.QwenScopeSAE.from_layer_file(sae_layer_file_path, k=k, device=device, target=target)
    targets.validate_hidden_dims(hidden_size, sae.d_in, target)
    targets.validate_qwen_sae_shapes(
        w_enc_shape=(sae.d_sae, sae.d_in), b_enc_shape=(sae.d_sae,),
        w_dec_shape=(sae.d_in, sae.d_sae), b_dec_shape=(sae.d_in,), target=target,
    )

    hook_identifier = f"{target.expected_hook_name}:layer_{layer}"
    targets.validate_hook_identity(hook_identifier, target)

    provenance = {
        "target": f"{target.name}-scientific",
        "model": {
            "repository": target.model_repo_id,
            "local_path": str(model_path),
            "revision": model_identity["revision"],
            "revision_verification": model_identity["verification"],
            "actual_class": type(hf_model).__name__,
        },
        "sae": {
            "repository": target.sae_repo_id,
            "sae_family": sae_family,
            "local_path": str(sae_layer_file_path),
            "revision": sae_identity["revision"],
            "revision_verification": sae_identity["verification"],
            "resolved_files": [str(sae_layer_file_path)],
            "actual_class": type(sae).__name__,
            "format": target.sae_format,
            "d_in": sae.d_in,
            "d_sae": sae.d_sae,
            "sparsity_k": sae.k,
        },
        "layer": {"engineering_layer": layer, "engineering_only": False, "hook_name": hook_identifier},
    }
    return hf_model, text_decoder, sae, hook_identifier, provenance


def _checkpoint_hash(*, model_path: str, sae_path: str) -> str:
    """Cheap, deterministic identity hash for the `spec.checkpoint_hash`
    field (interplab.interventions.spec.InterventionSpec's shape) -- a
    content hash of the model/SAE paths and revisions is out of scope here
    (no full-weight hashing performed by this discovery tool); this is a
    path-identity fingerprint, not a substitute for the mechanical
    harness's own revision verification, which already ran during
    `load_gemma_it_target`/`load_qwen_target` above this call."""
    return hashlib.sha256(f"{model_path}\x00{sae_path}".encode()).hexdigest()[:16]


_QWEN_SCIENTIFIC_LAYERS = tuple(c.qwen_layer for c in MATCHED_CONFIGURATIONS.values())
_GEMMA_SCIENTIFIC_LAYERS = tuple(c.gemma_layer for c in MATCHED_CONFIGURATIONS.values())


def _gemma_scientific_target(*, layer: int) -> targets.TargetPairing:
    """A LOCAL variant of the ratified Gemma target for scientific
    discovery, built via `dataclasses.replace` (never editing
    `final_pairing_targets.GEMMA_3_12B_IT_TARGET` in place, exactly as
    `_qwen_scientific_target` does for Qwen). The mechanical target's
    `expected_layer=31` is fixed to the engineering-only layer job 407008
    already exercised; the two predeclared scientific configurations use
    layer 29 (primary) or 24 (backup) instead.

    `sae_release`/`sae_id`/`sae_loader_id` are looked up from
    `MATCHED_CONFIGURATIONS` (the single source of truth for these three
    identity strings, one triple per configuration -- see
    `MatchedConfiguration`'s docstring for why they are NOT derived from
    one shared naming formula: primary's `resid_post_all` family and
    backup's `resid_post` family are confirmed-different `sae_lens`
    releases, and layer 29 does not even exist under backup's release, nor
    layer 24's `_medium` variant under primary's)."""
    import dataclasses as _dc

    configuration = next((c for c in MATCHED_CONFIGURATIONS.values() if c.gemma_layer == layer), None)
    if configuration is None:
        raise targets.TargetIdentityMismatch(
            f"--layer {layer} is not one of the two predeclared Gemma scientific layers "
            f"{_GEMMA_SCIENTIFIC_LAYERS} -- refusing to run discovery against a third, "
            f"unauthorized layer."
        )
    base = targets.GEMMA_3_12B_IT_TARGET
    return _dc.replace(
        base, expected_layer=layer,
        sae_release=configuration.gemma_sae_release,
        sae_id=configuration.gemma_sae_id,
        sae_loader_id=configuration.gemma_sae_loader_id,
        expected_hook_name=f"blocks.{layer}.hook_resid_post",
    )


def resolve_gemma_num_hidden_layers(model_path: str | Path) -> int:
    """Reads `config.json` directly rather than trusting `model.cfg.n_layers`
    alone: Gemma 3's own config nests the TEXT decoder's depth under
    `text_config.num_hidden_layers` -- a multimodal `Gemma3Config` also
    carries a DIFFERENT, unrelated `vision_config.num_hidden_layers`, and
    reading the wrong one would silently compute a wrong depth fraction.
    Falls back to a top-level `num_hidden_layers` only when `text_config`
    is genuinely absent (a text-only config shape), never merely preferred
    over it."""
    config_path = Path(model_path) / "config.json"
    if not config_path.is_file():
        raise FileNotFoundError(f"Gemma config.json not found at {config_path}")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if "text_config" in config:
        text_config = config["text_config"]
        if "num_hidden_layers" not in text_config:
            raise targets.TargetIdentityMismatch(
                f"{config_path} has a text_config block with no num_hidden_layers -- refusing to "
                f"fall back to the top-level or vision value for the text decoder's depth."
            )
        return int(text_config["num_hidden_layers"])
    if "num_hidden_layers" not in config:
        raise targets.TargetIdentityMismatch(
            f"{config_path} has neither text_config.num_hidden_layers nor a top-level num_hidden_layers"
        )
    return int(config["num_hidden_layers"])


_VISION_MODULE_MARKERS = ("vision_tower", "multi_modal_projector")


def resolve_gemma_text_decoder_layer_dynamically(hf_model, *, layer: int):
    """Independent, raw-HF-side resolution of the text decoder layer at
    index `layer` -- deliberately NOT via `sae.cfg.metadata.hook_name`
    (whatever string sae_lens's registry declares, e.g. something
    "model.layers.29.output"-shaped) and NOT via a single hardcoded
    attribute-path guess (`model.layers.29` or any other), per the
    Gemma local-only-loader addendum's explicit instruction that neither
    a scientific-metadata hook string nor `blocks.N.hook_resid_post` is
    accepted as a PROVEN runtime path on its own. Walks
    `hf_model.named_modules()`, excludes any qualified name containing
    `vision_tower` or `multi_modal_projector`, and requires EXACTLY ONE
    remaining module whose qualified name ends in `.layers.<layer>` --
    ambiguity (more than one match) or absence (zero matches) both raise
    rather than falling back to a guess.

    This is a SEPARATE, independent proof from
    `run_gemma_hook_preflight` (which proves the TransformerLens hook
    STRING fires with the right shape on the TL-side graph): this
    function proves the raw HF module structure itself has exactly one
    non-vision decoder layer at the claimed index, which is the fact a
    hook-name string alone cannot establish (a conversion bug could wire
    a TL hook name to the wrong HF submodule while still firing and
    still reporting the right dimension, if the wrong submodule
    coincidentally shares that dimension)."""
    import re

    pattern = re.compile(rf"(^|\.)layers\.{layer}$")
    candidates = [
        (name, module) for name, module in hf_model.named_modules()
        if pattern.search(name) and not any(marker in name for marker in _VISION_MODULE_MARKERS)
    ]
    if len(candidates) != 1:
        raise targets.TargetIdentityMismatch(
            f"expected exactly one non-vision decoder-layer module matching layer {layer} on the "
            f"loaded HF model, found {len(candidates)}: {[n for n, _ in candidates]} -- refusing "
            f"to guess which one (if any) is the real text decoder layer."
        )
    return candidates[0]


@dataclass(frozen=True)
class GemmaRawHfHookPreflightResult:
    resolved_module_name: str
    layer_index_asserted: int
    captured_last_dim: int
    passed: bool


def run_gemma_raw_hf_hook_preflight(hf_model, tokens, *, layer: int, expected_hidden_dim: int) -> GemmaRawHfHookPreflightResult:
    """A real, tiny forward pass on the RAW HF model (never through
    TransformerLens), with a real `register_forward_hook` on the module
    `resolve_gemma_text_decoder_layer_dynamically` independently resolved
    -- proves that module's own output last dimension is
    `expected_hidden_dim` (3840 for Gemma-3-12B's text decoder),
    independent of anything TransformerLens's own hook system reports."""
    name, module = resolve_gemma_text_decoder_layer_dynamically(hf_model, layer=layer)
    captured_shapes: list[tuple[int, ...]] = []

    def _hook(_module, _inputs, output):
        hidden = output[0] if isinstance(output, tuple) else output
        captured_shapes.append(tuple(hidden.shape))
        return output

    handle = module.register_forward_hook(_hook)
    try:
        import torch

        with torch.no_grad():
            hf_model(tokens)
    finally:
        handle.remove()

    last_dim = captured_shapes[-1][-1] if captured_shapes else -1
    passed = bool(captured_shapes) and last_dim == expected_hidden_dim
    result = GemmaRawHfHookPreflightResult(
        resolved_module_name=name, layer_index_asserted=layer, captured_last_dim=last_dim, passed=passed,
    )
    if not passed:
        raise targets.TargetIdentityMismatch(
            f"Gemma raw-HF hook preflight FAILED for module {name!r} at layer {layer}: "
            f"captured_last_dim={last_dim}, expected={expected_hidden_dim} -- refusing to proceed."
        )
    return result


@dataclass(frozen=True)
class GemmaHookPreflightResult:
    configured_hook_string: str
    runtime_class: str
    hook_fired: bool
    hook_invocation_count: int
    captured_last_dim: int
    layer_index_asserted: int
    passed: bool


def run_gemma_hook_preflight(
    model, sae, hook_name: str, *, expected_hidden_dim: int, expected_layer: int,
) -> GemmaHookPreflightResult:
    """A real, tiny forward pass with a temporary probe hook -- proves the
    configured hook STRING (`sae.cfg.metadata.hook_name`) actually fires on
    the intended text-decoder layer with the expected tensor shape, rather
    than trusting the string alone. A vision-side or wrong-layer hook
    would either never fire (HookedTransformer silently registers nothing
    for a hook name that doesn't exist on this graph) or fire with a
    different last dimension (a differently-sized module) -- either is
    caught here, before any discovery stage runs. Parametric over whatever
    `hook_name` was actually resolved for whichever layer was loaded (29,
    24, or any future layer) -- nothing here is specific to a single
    layer number, per this check's own requirement not to encode a
    layer-31-only (or layer-29-only) fix.

    `expected_layer` is recorded here (`layer_index_asserted`) as an
    explicit, auditable field, but this function deliberately does NOT
    derive an expected hook-name STRING from it and compare -- the
    Gemma preflight addendum's own instruction is that a configured hook
    string ("model.layers.29.output"-shaped scientific metadata) is "not
    necessarily the literal runtime attribute path", so asserting layer
    identity by re-deriving and string-matching a hook name here would
    make exactly the mistake that addendum warns against. The actual
    layer-identity check against a STRING is `final_pairing_targets.
    validate_hook_identity(hook_name, target)`, already called by
    `load_gemma_scientific_target` immediately before this function runs,
    against `target.expected_hook_name` (itself derived from
    `MATCHED_CONFIGURATIONS`, the single source of truth for which layer
    a configuration means) -- this function's own, INDEPENDENT proof of
    layer correctness is purely dynamic: the fact that a hook fires AT
    ALL with the expected dimension on the exact `hook_name` that was
    already validated is what rules out a wrong-layer or vision-side
    hook, since TransformerLens routes hooks by exact graph-node name and
    cannot fire a `hook_name` string on a different module than the one
    that string names."""
    import torch

    captured_shapes: list[tuple[int, ...]] = []

    def _probe_hook(resid, hook):
        captured_shapes.append(tuple(resid.shape))
        return resid

    tokens = model.to_tokens("preflight probe")
    with model.hooks(fwd_hooks=[(hook_name, _probe_hook)]), torch.no_grad():
        model(tokens)

    hook_fired = len(captured_shapes) > 0
    last_dim = captured_shapes[-1][-1] if captured_shapes else -1
    passed = hook_fired and last_dim == expected_hidden_dim
    result = GemmaHookPreflightResult(
        configured_hook_string=hook_name, runtime_class=type(model).__name__,
        hook_fired=hook_fired, hook_invocation_count=len(captured_shapes),
        captured_last_dim=last_dim, layer_index_asserted=expected_layer, passed=passed,
    )
    if not passed:
        raise targets.TargetIdentityMismatch(
            f"Gemma hook preflight FAILED for hook_name={hook_name!r} (runtime_class="
            f"{result.runtime_class!r}): hook_fired={hook_fired}, hook_invocation_count="
            f"{result.hook_invocation_count}, captured_last_dim={last_dim}, expected_dim="
            f"{expected_hidden_dim}, expected_layer={expected_layer} -- refusing to proceed with "
            f"discovery on a hook that is absent, wrong-layer, vision-side, or wrong-dimension."
        )
    return result


def assert_registry_release_and_subdirectory_match(directory: dict, *, target: targets.TargetPairing) -> None:
    """Reads the installed `sae_lens` registry through its own supported
    accessor (`get_pretrained_saes_directory()`, already called by the
    caller and passed in as `directory` -- this function performs no I/O
    of its own) and asserts, as two SEPARATE, INDEPENDENT facts:

      registry[release].repo_id == target.sae_repo_id
      registry[release].saes_map[loader_sae_id] == target.sae_id (the
        scientific subdirectory)

    Never derives the scientific subdirectory by parsing
    `loader_sae_id` (e.g. prefixing it with a guessed family name) --
    the registry's own mapping is the only source of truth for which
    subdirectory a flat loader id names, per the 2026-08-13 staging-facts
    addendum's explicit instruction."""
    release_entry = directory.get(target.sae_release)
    if release_entry is None:
        raise targets.TargetIdentityMismatch(
            f"sae_lens registry has no release {target.sae_release!r} at all -- "
            f"{target.sae_release!r} is not a real, installed release."
        )
    if release_entry.repo_id != target.sae_repo_id:
        raise targets.TargetIdentityMismatch(
            f"sae_lens registry release {target.sae_release!r} has repo_id "
            f"{release_entry.repo_id!r}, expected {target.sae_repo_id!r} -- refusing to load a "
            f"release that does not belong to the ratified SAE repository."
        )
    mapped_subdirectory = release_entry.saes_map.get(target.sae_loader_id)
    if mapped_subdirectory != target.sae_id:
        raise targets.TargetIdentityMismatch(
            f"sae_lens registry release {target.sae_release!r} maps loader_sae_id "
            f"{target.sae_loader_id!r} to subdirectory {mapped_subdirectory!r}, not the expected "
            f"scientific subdirectory {target.sae_id!r} -- the registry's own mapping disagrees "
            f"with this file's recorded identity, and the registry is the source of truth."
        )


def load_gemma_scientific_target(
    model_path: str | Path, sae_path: str | Path, *, layer: int, device: str = "cuda", dtype: str = "bfloat16",
    expected_model_revision: str | None = None, expected_sae_revision: str | None = None,
):
    """Duplicates `final_pairing_harness.load_gemma_it_target`'s body (Ground
    Rule 2 -- see `load_qwen_scientific_target`'s docstring for the same
    reasoning applied to Qwen) with one difference: `target` is
    `_gemma_scientific_target(layer=...)` rather than the module-level
    mechanical `GEMMA_3_12B_IT_TARGET`, so layer 29 or 24 can be validated
    and loaded without touching final_pairing_harness.py or
    final_pairing_targets.py at all."""
    import torch
    from sae_lens import SAE
    from transformer_lens import HookedTransformer
    from transformers import AutoModel, AutoTokenizer

    target = _gemma_scientific_target(layer=layer)
    harness._require_offline()
    model_path = Path(model_path)
    sae_path = Path(sae_path)
    if not model_path.exists():
        raise FileNotFoundError(f"model snapshot directory not found: {model_path}")
    if not sae_path.exists():
        raise FileNotFoundError(f"SAE snapshot directory not found: {sae_path}")
    model_identity = targets.validate_local_snapshot_identity(
        model_path, target, which="model", expected_revision=expected_model_revision
    )
    sae_identity = targets.validate_local_snapshot_identity(
        sae_path, target, which="sae", expected_revision=expected_sae_revision
    )

    from sae_lens.loading.pretrained_saes_directory import get_pretrained_saes_directory

    directory = get_pretrained_saes_directory()
    available_loader_ids = list(directory[target.sae_release].saes_map.keys())
    targets.validate_sae_loader_id_registered(target.sae_loader_id, available_loader_ids, target)
    assert_registry_release_and_subdirectory_match(directory, target=target)

    torch_dtype = getattr(torch, dtype)
    tokenizer = AutoTokenizer.from_pretrained(str(model_path))
    hf_model = AutoModel.from_pretrained(str(model_path), dtype=torch_dtype)
    model = HookedTransformer.from_pretrained(
        target.model_repo_id, hf_model=hf_model, tokenizer=tokenizer,
        fold_ln=False, center_writing_weights=False, center_unembed=False, device=device, dtype=torch_dtype,
    )
    model.eval()

    harness._patch_gemma3_safetensors_shape_lookup()
    resolved_sae_files: list[str] = []
    requested_sae_files: list[dict[str, str]] = []
    original_hf_hub_download = harness._capture_sae_download_paths(
        resolved_sae_files, sae_path=sae_path, target=target, requested_files_out=requested_sae_files
    )
    try:
        sae = SAE.from_pretrained(release=target.sae_release, sae_id=target.sae_loader_id, device=device)
    finally:
        harness._restore_sae_download_paths(original_hf_hub_download)
    targets.validate_sae_files_match_snapshot(resolved_sae_files, sae_path, target)
    subdirectory_identity = targets.validate_sae_files_match_expected_subdirectory(resolved_sae_files, sae_path, target)
    targets.validate_sae_symlink_targets_stay_in_repository_cache(resolved_sae_files, sae_path, target)

    sae = sae.to(dtype=torch.float32)
    sae.eval()

    hook_name = sae.cfg.metadata.hook_name
    targets.validate_hook_identity(hook_name, target)
    targets.validate_hidden_dims(model.cfg.d_model, sae.cfg.d_in, target)
    hook_preflight = run_gemma_hook_preflight(
        model, sae, hook_name, expected_hidden_dim=target.expected_hidden_dim, expected_layer=layer,
    )
    raw_hf_tokens = tokenizer("preflight probe", return_tensors="pt")["input_ids"].to(device)
    raw_hf_preflight = run_gemma_raw_hf_hook_preflight(
        hf_model, raw_hf_tokens, layer=layer, expected_hidden_dim=target.expected_hidden_dim,
    )

    gemma_n_layers = resolve_gemma_num_hidden_layers(model_path)
    if gemma_n_layers != model.cfg.n_layers:
        raise targets.TargetIdentityMismatch(
            f"config.json text_config.num_hidden_layers={gemma_n_layers} disagrees with the loaded "
            f"HookedTransformer's model.cfg.n_layers={model.cfg.n_layers} -- refusing to compute a "
            f"depth fraction from a value that does not match what was actually loaded."
        )
    configuration = next((c for c in MATCHED_CONFIGURATIONS.values() if c.gemma_layer == layer), None)
    if configuration is None:
        raise AssertionError("unreachable: layer already validated against _GEMMA_SCIENTIFIC_LAYERS")
    gemma_depth_fraction = assert_gemma_qwen_depth_matches(
        gemma_layer=layer, gemma_n_layers=gemma_n_layers, qwen_depth_fraction=configuration.qwen_depth_fraction,
    )

    provenance = {
        "target": f"{target.name}-scientific",
        "model": {
            "repository": target.model_repo_id, "local_path": str(model_path),
            "revision": model_identity["revision"], "revision_verification": model_identity["verification"],
            "actual_class": type(model).__name__,
        },
        "sae": {
            "repository": target.sae_repo_id, "release": target.sae_release, "sae_id": target.sae_id,
            "scientific_sae_id": target.sae_id, "loader_sae_id": target.sae_loader_id, "local_path": str(sae_path),
            "revision": sae_identity["revision"], "revision_verification": sae_identity["verification"],
            "resolved_files": resolved_sae_files, "resolved_local_paths": resolved_sae_files,
            "requested_sae_files": requested_sae_files,
            "local_snapshot_only": True, "network_resolution_attempted": False,
            "actual_class": type(sae).__name__, "format": target.sae_format,
            "d_in": sae.cfg.d_in, "d_sae": sae.cfg.d_sae,
            "expected_sae_subdirectory": subdirectory_identity["expected_sae_subdirectory"],
            "sae_subdirectory_membership_verified": subdirectory_identity["sae_subdirectory_membership_verified"],
            "subdirectory_membership_verified": subdirectory_identity["sae_subdirectory_membership_verified"],
            "physical_cache_containment_verified": True,
            "registry_release_and_subdirectory_verified": True,
            # sae.cfg carries loader defaults (e.g. context_size, dataset_path) that describe
            # HOW the SAE was trained upstream, not a measurement this pipeline made -- never
            # copied into provenance as if they were this run's own scientific claims.
        },
        "hook_preflight": asdict(hook_preflight),
        "raw_hf_hook_preflight": asdict(raw_hf_preflight),
        "layer": {"engineering_layer": layer, "engineering_only": False, "hook_name": hook_name},
        "depth_matching": {
            "gemma_n_layers": gemma_n_layers, "gemma_depth_fraction": gemma_depth_fraction,
            "qwen_depth_fraction": configuration.qwen_depth_fraction, "configuration": configuration.name,
        },
    }
    return model, sae, hook_name, provenance


def load_backend(
    *,
    pairing: str,
    model_path: str,
    sae_path: str,
    layer: int | None,
    expected_model_revision: str | None,
    expected_sae_revision: str | None,
    device: str,
    dtype: str,
    sae_family: str | None = None,
    sparsity: int | None = None,
) -> Backend:
    if pairing not in targets.ALL_TARGETS:
        raise targets.TargetIdentityMismatch(
            f"--pairing {pairing!r} is not one of the ratified final targets {sorted(targets.ALL_TARGETS)} "
            f"-- refusing to run discovery against a legacy or unrecognized pairing."
        )

    if pairing == targets.GEMMA_3_12B_IT_TARGET.name:
        if layer is None:
            raise ValueError(
                "--layer is required for --pairing gemma-3-12b-it scientific discovery "
                f"(one of {_GEMMA_SCIENTIFIC_LAYERS} -- the mechanical layer 31 is not a "
                "scientific candidate, matching Qwen's layer-0 exclusion)."
            )
        model, sae, hook_name, provenance = load_gemma_scientific_target(
            model_path, sae_path, layer=layer, device=device, dtype=dtype,
            expected_model_revision=expected_model_revision, expected_sae_revision=expected_sae_revision,
        )
        return Backend(
            pairing=pairing, model_obj=model, sae=sae, hook_name=hook_name,
            d_sae=sae.cfg.d_sae, d_model=sae.cfg.d_in, layer=layer,
            provenance=provenance, checkpoint_hash=_checkpoint_hash(model_path=model_path, sae_path=sae_path),
        )

    if pairing == targets.QWEN_3_5_27B_TARGET.name:
        if layer is None:
            raise ValueError("--layer is required for --pairing qwen-3.5-27b (scientific search, no ratified default)")
        if sae_family is None or sparsity is None:
            raise ValueError(
                "--qwen-sae-family and --qwen-sparsity are both required for --pairing qwen-3.5-27b -- SAE "
                "family, transformer layer, and sparsity are three distinct, independently-recorded fields."
            )
        hf_model, text_decoder, sae, hook_identifier, provenance = load_qwen_scientific_target(
            model_path, sae_path, layer=layer, sae_family=sae_family, k=sparsity, device=device, dtype=dtype,
            expected_model_revision=expected_model_revision, expected_sae_revision=expected_sae_revision,
        )
        decoder_layer = harness.get_qwen_decoder_layer(text_decoder, layer)
        return Backend(
            pairing=pairing, model_obj=hf_model, sae=sae, hook_name=hook_identifier,
            d_sae=sae.d_sae, d_model=sae.d_in, layer=layer,
            provenance=provenance, checkpoint_hash=_checkpoint_hash(model_path=model_path, sae_path=sae_path),
            sae_family=sae_family, sparsity=sparsity,
            _qwen_decoder_layer=decoder_layer, _qwen_device=device,
        )

    raise AssertionError("unreachable: pairing already validated against targets.ALL_TARGETS")


def reject_mechanical_only_feature(pairing: str, feature_index: int, *, context: str) -> None:
    mechanical_id = _MECHANICAL_ONLY_FEATURE_IDS[pairing]
    if feature_index == mechanical_id:
        raise targets.TargetIdentityMismatch(
            f"feature {feature_index} is {pairing}'s mechanical-acceptance-only placeholder feature "
            f"(final_pairing_harness.py's engineering feature_idx) -- it carries no concept meaning "
            f"and must never be promoted to a discovery candidate ({context})."
        )


# ---------------------------------------------------------------------------
# Stage 1: activation census/ranking. Gemma reuses the HookedTransformer
# forward-pass idiom `FeatureIndex.search_by_activation` already uses;
# Qwen duplicates the same ranking algorithm via a raw forward hook, since
# there is no HookedTransformer to run it through.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RankedFeature:
    feature_index: int
    activation_score: float


def _gemma_max_activation_per_feature(backend: Backend, texts: list[str]) -> np.ndarray:
    import torch

    model, sae = backend.model_obj, backend.sae
    max_activation = np.zeros(backend.d_sae, dtype=np.float64)
    with torch.no_grad():
        for text in texts:
            tokens = model.to_tokens(text)
            _, cache = model.run_with_cache(tokens, names_filter=backend.hook_name)
            feats = sae.encode(cache[backend.hook_name].to(torch.float32))[0]
            per_text_max = feats.max(dim=0).values.cpu().numpy()
            max_activation = np.maximum(max_activation, per_text_max)
    return max_activation


def _qwen_max_activation_per_feature(backend: Backend, texts: list[str]) -> np.ndarray:
    import torch
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(backend.provenance["model"]["local_path"])
    max_activation = np.zeros(backend.d_sae, dtype=np.float64)
    captured: list[torch.Tensor] = []

    def _capture(_module, _args, output):
        captured.append(output.detach())

    handle = backend._qwen_decoder_layer.register_forward_hook(_capture)
    try:
        with torch.no_grad():
            for text in texts:
                captured.clear()
                inputs = tokenizer(text, return_tensors="pt").to(backend._qwen_device)
                backend.model_obj(**inputs)
                resid = captured[-1].to(torch.float32)[0]  # [seq, d_model]
                feats = backend.sae.encode(resid)  # [seq, d_sae]
                per_text_max = feats.max(dim=0).values.cpu().numpy()
                max_activation = np.maximum(max_activation, per_text_max)
    finally:
        handle.remove()
    return max_activation


def exclude_mechanical_only(pairing: str, ranked: list[RankedFeature]) -> list[RankedFeature]:
    """Drops the pairing's mechanical-acceptance-only placeholder feature
    from a ranked shortlist, if activation ranking happened to surface it
    organically. This is a filter, not an error -- unlike a manually
    supplied candidate (`reject_mechanical_only_feature`, which raises),
    naturally ranking highly is not itself a misuse."""
    mechanical_id = _MECHANICAL_ONLY_FEATURE_IDS[pairing]
    return [r for r in ranked if r.feature_index != mechanical_id]


def rank_features_by_activation(backend: Backend, texts: list[str], *, top_n: int) -> list[RankedFeature]:
    if not texts:
        raise ValueError("rank_features_by_activation requires at least one text")
    if backend.pairing == targets.GEMMA_3_12B_IT_TARGET.name:
        scores = _gemma_max_activation_per_feature(backend, texts)
    else:
        scores = _qwen_max_activation_per_feature(backend, texts)
    order = np.argsort(-scores)
    ranked = [RankedFeature(feature_index=int(i), activation_score=float(scores[i])) for i in order[:top_n]]
    return ranked


def corpus_max_per_feature(backend: Backend, background_docs: list[str]) -> dict[int, float]:
    """The general-corpus scale ('the ONLY legal source of steering units',
    per interplab.interventions.hooks' own docstring convention this file
    follows) -- deliberately a SEPARATE pass over `background_corpus`, never
    the concept probes, so the unit a dose is expressed in is never
    circularly derived from the very texts used to find the feature."""
    if not background_docs:
        raise ValueError("corpus_max_per_feature requires a non-empty background corpus")
    if backend.pairing == targets.GEMMA_3_12B_IT_TARGET.name:
        scores = _gemma_max_activation_per_feature(backend, background_docs)
    else:
        scores = _qwen_max_activation_per_feature(backend, background_docs)
    return {i: float(scores[i]) for i in range(backend.d_sae)}


# ---------------------------------------------------------------------------
# Grid assembly: the 14-concept x 2-pairing x 3-gate x 3-family x 2-locale
# grid `primary_shared_gabc_count` (the frozen backup-trigger formula's own
# input) is computed FROM. One `Backend` (one pairing, one configuration)
# evaluates all 14 concepts; a separate aggregation step (see
# `compute_primary_completeness_and_shared_count`) combines both pairings'
# grids. An ERROR cell is never silently treated as a FAIL -- completeness
# is not inferred from a clean process exit, per this task's own
# instruction.
# ---------------------------------------------------------------------------


def rank_candidates_for_concept(
    backend: Backend, artifact: FrozenPromptArtifact, *, concept_id: str, shortlist_size: int
) -> list[RankedFeature]:
    """Ranks candidates using EVERY locale's positive-split text pooled
    together (a shortlist is a starting point for per-locale G-A/B/C
    testing below, not itself a per-locale claim)."""
    texts: list[str] = []
    for locale in FROZEN_PROMPT_SET_LOCALES:
        texts += [r["text"] for r in rows_for_concept(artifact.rows, concept_id=concept_id, locale=locale, split="positive")]
    ranked = rank_features_by_activation(backend, texts, top_n=shortlist_size)
    return exclude_mechanical_only(backend.pairing, ranked)


@dataclass(frozen=True)
class CandidateGabcEvaluation:
    feature_index: int
    gate_a_b_results: list[dict]
    gate_c_results: list[dict]
    survives_gabc: bool


@dataclass(frozen=True)
class ConceptPairingVerdict:
    concept_id: str
    pairing: str
    status: Literal["pass", "fail", "error"]
    surviving_feature_index: int | None
    candidates_evaluated: list[dict]  # asdict(CandidateGabcEvaluation), in ranked order, up to and including the winner (or all, on fail)
    error: str | None


def evaluate_concept_on_pairing(
    backend: Backend, artifact: FrozenPromptArtifact, *, concept_id: str, shortlist_size: int,
    locales: tuple[str, ...] = FROZEN_PROMPT_SET_LOCALES,
) -> ConceptPairingVerdict:
    """One (concept, pairing) grid cell's full verdict: the first ranked
    candidate feature that passes G-A+G-B+G-C in EVERY family/locale it was
    tested on is the surviving feature (`status='pass'`); if none of the
    shortlisted candidates survive, `status='fail'`; if evaluation itself
    raises (missing rows, a backend failure, anything), `status='error'`
    with the exception recorded -- an error must never be read as a fail,
    since a fail is a genuine negative result and an error is the absence
    of one."""
    try:
        ranked = rank_candidates_for_concept(backend, artifact, concept_id=concept_id, shortlist_size=shortlist_size)
        evaluated: list[CandidateGabcEvaluation] = []
        surviving_feature_index: int | None = None
        for candidate in ranked:
            gate_ab: list[GateABResult] = []
            gate_c: list[GateCResult] = []
            for locale in locales:
                gate_ab += compute_gate_a_and_b_per_family(
                    backend, artifact, concept_id=concept_id, locale=locale, feature_index=candidate.feature_index
                )
                gate_c += compute_gate_c_per_family(
                    backend, artifact, concept_id=concept_id, locale=locale, feature_index=candidate.feature_index
                )
            survives = feature_survives_gabc(gate_ab, gate_c)
            evaluated.append(
                CandidateGabcEvaluation(
                    feature_index=candidate.feature_index, gate_a_b_results=[asdict(r) for r in gate_ab],
                    gate_c_results=[asdict(r) for r in gate_c], survives_gabc=survives,
                )
            )
            if survives:
                surviving_feature_index = candidate.feature_index
                break
        status: Literal["pass", "fail"] = "pass" if surviving_feature_index is not None else "fail"
        return ConceptPairingVerdict(
            concept_id=concept_id, pairing=backend.pairing, status=status,
            surviving_feature_index=surviving_feature_index,
            candidates_evaluated=[asdict(e) for e in evaluated], error=None,
        )
    except Exception as exc:  # an ERROR cell must record ANY failure, not a curated subset
        return ConceptPairingVerdict(
            concept_id=concept_id, pairing=backend.pairing, status="error",
            surviving_feature_index=None, candidates_evaluated=[], error=f"{type(exc).__name__}: {exc}",
        )


def run_concept_grid(
    backend: Backend, artifact: FrozenPromptArtifact, *, shortlist_size: int,
    concept_ids: list[str] | None = None, progress: ProgressLog | None = None,
) -> list[ConceptPairingVerdict]:
    """Evaluates every one of the frozen artifact's 14 concepts (or an
    explicit subset, for tests) on ONE already-loaded `backend`, resuming
    per-concept via `progress` exactly like every other stage in this
    file."""
    if concept_ids is None:
        concept_ids = sorted({r["concept_id"] for r in artifact.rows})
    verdicts: list[ConceptPairingVerdict] = []
    for concept_id in concept_ids:
        key = f"grid_{backend.pairing}_{concept_id}"
        if progress is not None and progress.is_done(key):
            verdicts.append(ConceptPairingVerdict(**progress.result(key)["verdict"]))
            continue
        verdict = evaluate_concept_on_pairing(backend, artifact, concept_id=concept_id, shortlist_size=shortlist_size)
        verdicts.append(verdict)
        if progress is not None:
            progress.record(key, {"verdict": asdict(verdict)})
    return verdicts


def write_grid_result(out_dir: str | Path, pairing: str, verdicts: list[ConceptPairingVerdict]) -> Path:
    """Writes `<out_dir>/grid.json` -- an EXACT, named path, never a
    location a caller has to glob for. `out_dir` is the SAME per-lane
    output directory the discovery run itself was given (never a shared
    parent directory that other, unrelated runs also write into)."""
    path = Path(out_dir) / "grid.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"schema_version": SCHEMA_VERSION, "pairing": pairing, "verdicts": [asdict(v) for v in verdicts]}, indent=2),
        encoding="utf-8",
    )
    return path


def read_grid_result(path: str | Path) -> list[ConceptPairingVerdict]:
    """Reads EXACTLY the named `grid.json` file -- never globs a parent
    directory. A caller that does not know the exact path has been given
    the wrong information, not license to search for it."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"grid result not found at the exact path {path} (this function never globs a parent directory)")
    data = json.loads(path.read_text(encoding="utf-8"))
    return [ConceptPairingVerdict(**v) for v in data["verdicts"]]


def compute_primary_completeness_and_shared_count(
    grids_by_pairing: dict[str, list[ConceptPairingVerdict]], *, concept_ids: list[str],
) -> tuple[bool, int]:
    """`primary_complete`: every cell of the concept x pairing grid carries
    an explicit pass/fail verdict (an 'error' cell is NOT complete --
    completeness is not inferred from a clean process exit).
    `primary_shared_gabc_count`: the number of concepts where BOTH ruled
    pairings independently surfaced a (possibly different) feature that
    survives G-A+G-B+G-C on that pairing -- 'shared' means both models
    passed, not that they share a feature index (features on different
    models/SAEs are never the same feature); the frozen protocol's
    `shared_gabc` is per-configuration cross-pairing agreement, not
    cross-pairing feature identity."""
    expected_pairings = {targets.GEMMA_3_12B_IT_TARGET.name, targets.QWEN_3_5_27B_TARGET.name}
    if set(grids_by_pairing) != expected_pairings:
        raise ValueError(f"grids_by_pairing must have exactly the keys {sorted(expected_pairings)}, got {sorted(grids_by_pairing)}")

    by_concept_pairing: dict[tuple[str, str], ConceptPairingVerdict] = {}
    for pairing, verdicts in grids_by_pairing.items():
        for v in verdicts:
            if v.pairing != pairing:
                raise ValueError(f"verdict for concept {v.concept_id!r} under key {pairing!r} carries pairing={v.pairing!r}")
            by_concept_pairing[(v.concept_id, pairing)] = v

    complete = True
    shared_count = 0
    for concept_id in concept_ids:
        cells = [by_concept_pairing.get((concept_id, p)) for p in expected_pairings]
        if any(cell is None or cell.status == "error" for cell in cells):
            complete = False
            continue
        if all(cell.status == "pass" for cell in cells):
            shared_count += 1
    return complete, shared_count


# ---------------------------------------------------------------------------
# Stage 2: held-out specificity validation. A genuine train/held-out split
# (fit once on train, score once on held-out) -- deliberately NOT
# interplab.validation.probe.train_probe's cross-validated design, since
# that primitive has no held-out-set concept at all (see module docstring).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SpecificityResult:
    feature_index: int
    train_auc: float
    holdout_auc: float
    holdout_feature_auc: float
    holdout_gap: float
    passed: bool


def _pooled_residual_and_feature(backend: Backend, texts: list[str], feature_index: int) -> tuple[np.ndarray, np.ndarray]:
    import torch

    if backend.pairing == targets.GEMMA_3_12B_IT_TARGET.name:
        model, sae = backend.model_obj, backend.sae
        residuals, feats_out = [], []
        with torch.no_grad():
            for text in texts:
                tokens = model.to_tokens(text)
                _, cache = model.run_with_cache(tokens, names_filter=backend.hook_name)
                x = cache[backend.hook_name].to(torch.float32)[0]
                feats = sae.encode(x)
                residuals.append(x.mean(dim=0).cpu().numpy())
                feats_out.append(float(feats[:, feature_index].mean().item()))
        return np.stack(residuals), np.array(feats_out)

    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(backend.provenance["model"]["local_path"])
    residuals, feats_out = [], []
    captured: list = []

    def _capture(_module, _args, output):
        captured.append(output.detach())

    handle = backend._qwen_decoder_layer.register_forward_hook(_capture)
    try:
        with torch.no_grad():
            for text in texts:
                captured.clear()
                inputs = tokenizer(text, return_tensors="pt").to(backend._qwen_device)
                backend.model_obj(**inputs)
                x = captured[-1].to(torch.float32)[0]
                feats = backend.sae.encode(x)
                residuals.append(x.mean(dim=0).cpu().numpy())
                feats_out.append(float(feats[:, feature_index].mean().item()))
    finally:
        handle.remove()
    return np.stack(residuals), np.array(feats_out)


def _fit_score_auc(x_train: np.ndarray, y_train: np.ndarray, x_holdout: np.ndarray, y_holdout: np.ndarray, *, seed: int) -> float:
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score

    clf = LogisticRegression(solver="lbfgs", max_iter=1000, random_state=seed)
    clf.fit(x_train, y_train)
    scores = clf.predict_proba(x_holdout)[:, 1]
    return float(roc_auc_score(y_holdout, scores))


def validate_specificity(
    backend: Backend, feature_index: int, *,
    train_probes: list[str], train_controls: list[str],
    holdout_probes: list[str], holdout_controls: list[str],
    seed: int, auc_threshold: float,
) -> SpecificityResult:
    for name, texts in (("train_probes", train_probes), ("train_controls", train_controls),
                        ("holdout_probes", holdout_probes), ("holdout_controls", holdout_controls)):
        if len(texts) < _PROBE_MIN_EXAMPLES_PER_CLASS:
            raise ValueError(
                f"{name} has {len(texts)} example(s); held-out specificity validation needs at least "
                f"{_PROBE_MIN_EXAMPLES_PER_CLASS} per class per split"
            )

    train_pos_x, train_pos_f = _pooled_residual_and_feature(backend, train_probes, feature_index)
    train_neg_x, train_neg_f = _pooled_residual_and_feature(backend, train_controls, feature_index)
    hold_pos_x, hold_pos_f = _pooled_residual_and_feature(backend, holdout_probes, feature_index)
    hold_neg_x, hold_neg_f = _pooled_residual_and_feature(backend, holdout_controls, feature_index)

    x_train = np.concatenate([train_pos_x, train_neg_x], axis=0)
    y_train = np.concatenate([np.ones(len(train_probes)), np.zeros(len(train_controls))])
    x_hold = np.concatenate([hold_pos_x, hold_neg_x], axis=0)
    y_hold = np.concatenate([np.ones(len(holdout_probes)), np.zeros(len(holdout_controls))])

    train_auc = _fit_score_auc(x_train, y_train, x_train, y_train, seed=seed)
    holdout_auc = _fit_score_auc(x_train, y_train, x_hold, y_hold, seed=seed)

    f_train = np.concatenate([train_pos_f, train_neg_f]).reshape(-1, 1)
    f_hold = np.concatenate([hold_pos_f, hold_neg_f]).reshape(-1, 1)
    holdout_feature_auc = _fit_score_auc(f_train, y_train, f_hold, y_hold, seed=seed)

    holdout_gap = max(0.0, holdout_auc - holdout_feature_auc)
    return SpecificityResult(
        feature_index=feature_index, train_auc=train_auc, holdout_auc=holdout_auc,
        holdout_feature_auc=holdout_feature_auc, holdout_gap=holdout_gap,
        # Gated on the FEATURE's own held-out AUC, not the full-residual
        # ceiling (`holdout_auc`) -- the latter is the same for every
        # feature_index by construction (it never reads the feature's
        # activation at all) and would pass every candidate whenever the
        # concept is merely present somewhere in the residual stream. Only
        # holdout_feature_auc asks whether THIS feature specifically
        # predicts the concept on held-out data.
        passed=holdout_feature_auc >= auc_threshold,
    )


# ---------------------------------------------------------------------------
# Stage 3 / 5: causal intervention + dose-response. Reuses
# interplab.interventions.hooks._make_clamp_hook and final_pairing_harness's
# diagnostic wrapper/verdict directly -- the exact mechanism jobs
# 407008/406092 already exercised, generalized to a feature SET (bundle)
# rather than always exactly one feature.
# ---------------------------------------------------------------------------

from interplab.interventions.hooks import _make_clamp_hook  # noqa: E402


@contextlib.contextmanager
def _attached(backend: Backend, hook_fn):
    if backend.pairing == targets.GEMMA_3_12B_IT_TARGET.name:
        with backend.model_obj.hooks(fwd_hooks=[(backend.hook_name, hook_fn)]):
            yield
    else:
        handle = harness.register_qwen_raw_hook(backend._qwen_decoder_layer, hook_fn)
        try:
            yield
        finally:
            handle.remove()


def _bundle_hook_fn(backend: Backend, feature_indices: list[int], clamp_value: float, positions: str, prompt_lengths, trace_out: list):
    """Chains one `_make_clamp_hook` per feature in the bundle so each
    feature's own clamp/ablate math is untouched (never re-derived for a
    multi-feature case) -- the diagnostic trace records the FIRST feature
    in the bundle (the seed) as `feature_index`, consistent with a
    single-feature result being the trace-compatible special case of a
    bundle of size 1."""
    inner_hooks = [
        _make_clamp_hook(backend.sae, i, clamp_value, positions, prompt_lengths, [])
        for i in feature_indices
    ]

    def hook_fn(resid, hook):
        out = resid
        for inner in inner_hooks:
            out = inner(out, hook)
        return out

    return hook_fn


@dataclass
class InterventionOutcome:
    feature_indices: list[int]
    direction: Literal["clamp", "ablate"]
    value_in_max_units: float
    corpus_max_used: float
    absolute_clamp_value: float
    positions: str
    generated_text: str
    verdict: dict
    spec: dict  # interplab.interventions.spec.InterventionSpec-shaped, for sealing-pipeline compatibility


def run_intervention(
    backend: Backend, feature_indices: list[int], *,
    direction: Literal["clamp", "ablate"], value_in_max_units: float, corpus_max: dict[int, float],
    positions: str, prompt: str, seed: int, max_new_tokens: int,
) -> InterventionOutcome:
    import torch

    for i in feature_indices:
        reject_mechanical_only_feature(backend.pairing, i, context="run_intervention")
        targets.validate_feature_index(i, backend.d_sae)

    seed_feature = feature_indices[0]
    absolute_clamp_value = 0.0 if direction == "ablate" else float(value_in_max_units) * float(corpus_max[seed_feature])

    trace: list = []
    if backend.pairing == targets.GEMMA_3_12B_IT_TARGET.name:
        model = backend.model_obj
        tokens = model.to_tokens(prompt)
        prompt_lengths = tokens.shape[1] if positions == "generated_only" else None
        inner = _bundle_hook_fn(backend, feature_indices, absolute_clamp_value, positions, prompt_lengths, trace)
        hook_fn = harness.wrap_hook_with_diagnostics(
            inner, sae=backend.sae, feature_index=seed_feature, mode=direction,
            dose_or_raw_label=f"value_in_max_units={value_in_max_units}", calibration_input=value_in_max_units,
            resolved_absolute_target=absolute_clamp_value, hook_name=backend.hook_name, trace_out=trace,
        )
        torch.manual_seed(seed)
        with _attached(backend, hook_fn):
            out_tokens = model.generate(tokens, max_new_tokens=max_new_tokens, do_sample=False, verbose=False)
        generated_text = model.tokenizer.decode(out_tokens[0])
    else:
        from transformers import AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(backend.provenance["model"]["local_path"])
        inputs = tokenizer(prompt, return_tensors="pt").to(backend._qwen_device)
        prompt_lengths = inputs["input_ids"].shape[1] if positions == "generated_only" else None
        inner = _bundle_hook_fn(backend, feature_indices, absolute_clamp_value, positions, prompt_lengths, trace)
        hook_fn = harness.wrap_hook_with_diagnostics(
            inner, sae=backend.sae, feature_index=seed_feature, mode=direction,
            dose_or_raw_label=f"value_in_max_units={value_in_max_units}", calibration_input=value_in_max_units,
            resolved_absolute_target=absolute_clamp_value, hook_name=backend.hook_name, trace_out=trace,
        )
        torch.manual_seed(seed)
        with _attached(backend, hook_fn), torch.no_grad():
            out_ids = backend.model_obj.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)
        generated_text = tokenizer.decode(out_ids[0], skip_special_tokens=True)

    verdict = harness.mechanical_verdict(trace, positions=positions)
    spec = {
        "kind": direction,
        "feature_index": feature_indices if len(feature_indices) > 1 else seed_feature,
        "value_in_max_units": float(value_in_max_units),
        "corpus_max": float(corpus_max[seed_feature]),
        "positions": positions,
        "checkpoint_hash": backend.checkpoint_hash,
        "direction_seed": None,
    }
    return InterventionOutcome(
        feature_indices=list(feature_indices), direction=direction, value_in_max_units=float(value_in_max_units),
        corpus_max_used=float(corpus_max[seed_feature]), absolute_clamp_value=float(absolute_clamp_value),
        positions=positions, generated_text=generated_text, verdict=verdict, spec=spec,
    )


# ---------------------------------------------------------------------------
# Stage 4: optional greedy bundle composition. Single-feature bundles are
# the first-class default (bundle_max_size=1 disables composition
# entirely); a feature is added only when the recorded metric (held-out
# AUC) improves by at least `materiality_threshold` -- both values compared
# are absolute, non-negative AUCs; only a passing "gain" is ever reported.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BundleStep:
    feature_index: int
    metric_before: float
    metric_candidate: float
    added: bool
    metric_gain: float | None  # present only when added


@dataclass(frozen=True)
class BundleResult:
    feature_indices: list[int]
    final_metric: float
    steps: list[BundleStep]


def compose_bundle_greedily(
    backend: Backend, seed_feature: int, candidate_pool: list[int], *,
    train_probes: list[str], train_controls: list[str], holdout_probes: list[str], holdout_controls: list[str],
    seed: int, materiality_threshold: float, bundle_max_size: int,
) -> BundleResult:
    """`bundle_max_size=1` is a valid, complete result: no composition is
    attempted and `steps` is empty -- this is the single-feature-bundle
    first-class case this task requires, not a degraded fallback."""
    if materiality_threshold < 0:
        raise ValueError("--bundle-materiality-threshold must be non-negative")
    bundle = [seed_feature]
    steps: list[BundleStep] = []

    y_train = np.concatenate([np.ones(len(train_probes)), np.zeros(len(train_controls))])
    y_hold = np.concatenate([np.ones(len(holdout_probes)), np.zeros(len(holdout_controls))])

    # Each candidate's own SAE-feature activation scalar (never the raw
    # residual, which is identical regardless of feature_index and would
    # make every bundle "composition" a no-op measuring the same thing
    # repeatedly) -- computed ONCE per feature per split, then reused across
    # every greedy step, rather than re-running a forward pass per step.
    all_features = sorted({seed_feature, *candidate_pool})
    scalars: dict[int, dict[str, np.ndarray]] = {}
    for f in all_features:
        scalars[f] = {
            "train_pos": _pooled_residual_and_feature(backend, train_probes, f)[1],
            "train_neg": _pooled_residual_and_feature(backend, train_controls, f)[1],
            "hold_pos": _pooled_residual_and_feature(backend, holdout_probes, f)[1],
            "hold_neg": _pooled_residual_and_feature(backend, holdout_controls, f)[1],
        }

    def _bundle_auc(features: list[int]) -> float:
        x_train = np.stack(
            [np.concatenate([scalars[f]["train_pos"], scalars[f]["train_neg"]]) for f in features], axis=1
        )
        x_hold = np.stack(
            [np.concatenate([scalars[f]["hold_pos"], scalars[f]["hold_neg"]]) for f in features], axis=1
        )
        return _fit_score_auc(x_train, y_train, x_hold, y_hold, seed=seed)

    current_metric = _bundle_auc(bundle)
    remaining = [f for f in candidate_pool if f != seed_feature]
    while len(bundle) < bundle_max_size and remaining:
        best_gain = -1.0
        best_feature = None
        best_metric = current_metric
        for candidate in remaining:
            candidate_metric = _bundle_auc([*bundle, candidate])
            gain = candidate_metric - current_metric
            if gain > best_gain:
                best_gain, best_feature, best_metric = gain, candidate, candidate_metric
        added = best_gain >= materiality_threshold
        steps.append(
            BundleStep(
                feature_index=best_feature, metric_before=current_metric, metric_candidate=best_metric,
                added=added, metric_gain=max(0.0, best_gain) if added else None,
            )
        )
        if not added:
            break
        bundle.append(best_feature)
        remaining.remove(best_feature)
        current_metric = best_metric

    return BundleResult(feature_indices=bundle, final_metric=current_metric, steps=steps)


# ---------------------------------------------------------------------------
# Dose-response CONFIRMATION: the cheap single-prompt curve above (used by
# `run()` to pick calibration candidates) is not evidence of a real,
# generalizing effect on its own. This sweep re-runs each dose in the
# grid against every one of the 20 held-out prompts, three times each
# (three distinct seeds) -- the confirmation this task's own dispatch
# calls for, kept as a SEPARATE stage rather than folded into the cheap
# curve so the two can be resumed/inspected independently.
# ---------------------------------------------------------------------------


def run_dose_response_confirmation(
    backend: Backend, feature_indices: list[int], *,
    direction: Literal["clamp", "ablate"], dose_grid: list[float], corpus_max: dict[int, float],
    positions: str, held_out_prompts: list[str], n_repeats: int, base_seed: int, max_new_tokens: int,
    progress: ProgressLog | None = None,
) -> dict[float, list[InterventionOutcome]]:
    """`len(held_out_prompts) * n_repeats` outcomes per dose -- every one
    of the 20 held-out prompts, each repeated `n_repeats` times with a
    distinct seed (`base_seed + repeat_index`), for EVERY dose in
    `dose_grid`. Resumable exactly like every other stage in this file:
    each (dose, prompt_index, repeat) cell is its own progress-log key."""
    if not held_out_prompts:
        raise ValueError("run_dose_response_confirmation requires at least one held-out prompt")
    if n_repeats < 1:
        raise ValueError("n_repeats must be at least 1")
    results: dict[float, list[InterventionOutcome]] = {}
    for dose in dose_grid:
        outcomes: list[InterventionOutcome] = []
        for prompt_index, prompt in enumerate(held_out_prompts):
            for repeat in range(n_repeats):
                key = f"confirmation_dose_{dose}_prompt_{prompt_index}_repeat_{repeat}"
                if progress is not None and progress.is_done(key):
                    outcomes.append(InterventionOutcome(**progress.result(key)["outcome"]))
                    continue
                outcome = run_intervention(
                    backend, feature_indices, direction=direction, value_in_max_units=dose,
                    corpus_max=corpus_max, positions=positions, prompt=prompt,
                    seed=base_seed + repeat, max_new_tokens=max_new_tokens,
                )
                outcomes.append(outcome)
                if progress is not None:
                    progress.record(key, {"outcome": asdict(outcome)})
        results[dose] = outcomes
    return results


# ---------------------------------------------------------------------------
# Stage 6: Low/Medium/High calibration candidates from a dose-response
# curve. The three boundaries are required CLI thresholds (Architect's
# rule) -- this file only applies them, in value_in_max_units, to whichever
# dose in --dose-grid is the smallest one at or above each boundary.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CalibrationCandidate:
    tier: Literal["low", "medium", "high"]
    value_in_max_units: float
    outcome: dict  # asdict(InterventionOutcome), minus generated_text noise kept for traceability


def select_calibration_candidates(
    dose_outcomes: list[InterventionOutcome], *,
    low_threshold: float, medium_threshold: float, high_threshold: float,
) -> dict[str, CalibrationCandidate | None]:
    if not (0 <= low_threshold <= medium_threshold <= high_threshold):
        raise ValueError(
            "calibration thresholds must satisfy 0 <= low <= medium <= high in value_in_max_units"
        )
    by_dose = sorted(dose_outcomes, key=lambda o: o.value_in_max_units)
    result: dict[str, CalibrationCandidate | None] = {}
    for tier, threshold in (("low", low_threshold), ("medium", medium_threshold), ("high", high_threshold)):
        chosen = next((o for o in by_dose if o.value_in_max_units >= threshold), None)
        result[tier] = (
            CalibrationCandidate(tier=tier, value_in_max_units=chosen.value_in_max_units, outcome=asdict(chosen))
            if chosen is not None else None
        )
    return result


# ---------------------------------------------------------------------------
# Resumability: an append-only, fsync'd JSONL progress log keyed by
# (stage, key) -- same pattern as gemma3_sweep.py's resumable cell writes,
# duplicated (not imported: that file is frozen, Engineer-2-owned) per this
# project's own Ground Rule 2.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Staggered-cold-load READY handshake: the Qwen lane loads FIRST (physical
# GPU 1, visible as cuda:0) and writes a READY record; only after that
# record is observed does the Gemma lane (physical GPU 0, visible as
# cuda:0) begin loading. Written here (not in
# final_concept_discovery_dual_gpu_job.py) so the SAME record shape is
# both written (by this file's own `run()`, after `load_backend()`
# succeeds) and read (by the orchestrator waiting on it) -- one format,
# not two independently-maintained ones.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReadyRecord:
    pairing: str
    device: str
    pid: int
    loaded_at: float


def write_ready_record(ready_path: str | Path, *, pairing: str, device: str) -> ReadyRecord:
    """Written ATOMICALLY (write to a sibling .tmp file, then os.replace)
    so a reader polling for `ready_path` never observes a partially-written
    file -- os.replace is atomic on both POSIX and NTFS when source and
    destination are on the same volume, which a sibling temp file always
    is."""
    import time as _time

    record = ReadyRecord(pairing=pairing, device=device, pid=os.getpid(), loaded_at=_time.time())
    path = Path(ready_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(asdict(record)), encoding="utf-8")
    os.replace(tmp_path, path)
    return record


class ReadyHandshakeFailed(RuntimeError):
    """The lead lane never wrote a valid READY record: it exited first,
    timed out, or wrote a record naming the wrong pairing/device. Always
    raised before the follower lane is launched -- failure before READY
    fails the allocation; it must never masquerade as scientific
    underperformance."""


def wait_for_ready_record(
    ready_path: str | Path, *, expected_pairing: str, expected_device: str,
    process_alive_fn, timeout_seconds: float, poll_interval: float = 1.0, sleep_fn=None,
) -> ReadyRecord:
    """Polls for `ready_path`. `process_alive_fn()` returning False BEFORE
    a valid READY record appears means the loader process exited without
    ever becoming ready -- fails closed immediately rather than waiting
    out the full timeout on a process that has already died. A READY
    record naming a different pairing or device than expected is refused
    rather than trusted (a misconfigured lane could otherwise silently
    satisfy the wrong handshake)."""
    import time as _time

    sleep = sleep_fn or _time.sleep
    path = Path(ready_path)
    deadline = _time.monotonic() + timeout_seconds
    while True:
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            record = ReadyRecord(**data)
            if record.pairing != expected_pairing or record.device != expected_device:
                raise ReadyHandshakeFailed(
                    f"READY record at {path} names pairing={record.pairing!r} device={record.device!r}, "
                    f"expected pairing={expected_pairing!r} device={expected_device!r}"
                )
            return record
        if not process_alive_fn():
            raise ReadyHandshakeFailed(f"the lead lane's process exited before writing a READY record at {path}")
        if _time.monotonic() >= deadline:
            raise ReadyHandshakeFailed(f"timed out after {timeout_seconds}s waiting for a READY record at {path}")
        sleep(poll_interval)


class ProgressLog:
    def __init__(self, path: Path):
        self.path = path
        self._completed: dict[str, dict] = {}
        if path.is_file():
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line:
                    continue
                record = json.loads(line)
                self._completed[record["key"]] = record

    def is_done(self, key: str) -> bool:
        return key in self._completed

    def result(self, key: str) -> dict | None:
        return self._completed.get(key)

    def record(self, key: str, payload: dict) -> None:
        entry = {"key": key, **payload}
        self._completed[key] = entry
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
            f.flush()
            os.fsync(f.fileno())


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--pairing", required=True, choices=sorted(targets.ALL_TARGETS))
    p.add_argument("--model-path", required=True)
    p.add_argument("--sae-path", required=True)
    p.add_argument("--layer", type=int, default=None, help=f"Required for both pairings. qwen-3.5-27b: any of {_QWEN_SCIENTIFIC_LAYERS} (not 0 -- engineering-only). gemma-3-12b-it: any of {_GEMMA_SCIENTIFIC_LAYERS} (not 31 -- engineering-only).")
    p.add_argument("--qwen-sae-family", choices=list(_QWEN_SCIENTIFIC_SAE_FAMILIES), default=None, help="Required for qwen-3.5-27b. Distinct from --qwen-sparsity and --layer.")
    p.add_argument("--qwen-sparsity", type=int, default=None, help="Required for qwen-3.5-27b: the SAE's TopK k, verified against the loaded file. Distinct from --qwen-sae-family and --layer.")
    p.add_argument("--expected-model-revision", default=None)
    p.add_argument("--expected-sae-revision", default=None)

    p.add_argument("--prompt-set-path", required=True)
    p.add_argument("--prompt-set-sha256", required=True)
    p.add_argument("--judge-config", default=None, help="Optional path to a {model,rubric_version,prompt_version} JSON. Defaults to the NoOp identity -- no judge is ever actually invoked by this file.")
    p.add_argument("--use-frozen-prompt-artifact", action="store_true", help=f"Additionally validate prompts/final_pairing/v1/ against the pinned commit {FROZEN_PROMPT_SET_COMMIT} and hashes, run the committed validator, and stamp prompt_set_commit/prompt_set_sha256 in the output. Refuses a dirty or hash-mismatched artifact.")
    p.add_argument("--allow-pi-gated", action="store_true", help="Only meaningful with --use-frozen-prompt-artifact. Never set for a public configuration -- political_framing stays excluded otherwise.")

    p.add_argument("--positions", choices=["all", "generated_only"], default="all")
    p.add_argument("--record-generated-only-diagnostic", action="store_true", help="Additionally run every intervention under generated_only as a separate diagnostic. positions=all remains the public calibration path regardless.")
    p.add_argument("--confirmation-repeats", type=int, default=3, help="Only used with --use-frozen-prompt-artifact: repeats per held-out prompt in the dose-response confirmation sweep (heldout_neutral for clamp, heldout_eliciting for ablate).")

    p.add_argument("--shortlist-size", type=int, required=True)
    p.add_argument("--direction", choices=["clamp", "ablate"], required=True)
    p.add_argument("--dose-grid", required=True, help="Comma-separated floats, in value_in_max_units (multiples of the background-corpus max activation).")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--prompt", default="Tell me about your day.")
    p.add_argument("--max-new-tokens", type=int, default=8)
    p.add_argument("--device", default="cuda")
    p.add_argument("--dtype", default="bfloat16")

    p.add_argument("--specificity-auc-threshold", type=float, required=True)
    p.add_argument("--bundle-materiality-threshold", type=float, required=True)
    p.add_argument("--bundle-max-size", type=int, default=1)
    p.add_argument("--calibration-low-threshold", type=float, required=True)
    p.add_argument("--calibration-medium-threshold", type=float, required=True)
    p.add_argument("--calibration-high-threshold", type=float, required=True)

    p.add_argument("--out-dir", required=True)
    p.add_argument("--state-dir", required=True, help="Separate from --out-dir: holds the resumable progress log only.")
    p.add_argument("--ready-path", default=None, help="If set, a READY record is written here immediately after the backend (model+SAE) finishes loading -- for the dual-GPU orchestrator's staggered-cold-load handshake. Omitted for a standalone/non-staggered run.")
    return p.parse_args(argv)


def _parse_dose_grid(raw: str) -> list[float]:
    doses = [float(x) for x in raw.split(",") if x.strip()]
    if not doses:
        raise ValueError("--dose-grid must contain at least one dose")
    if any(d < 0 for d in doses):
        raise ValueError("--dose-grid values must be non-negative (value_in_max_units)")
    return doses


def run(args: argparse.Namespace) -> dict:
    """The full 7-stage pipeline, resumable via `--state-dir`'s progress
    log. Returns the machine-readable result dict (also written to
    `--out-dir/result.json`)."""
    out_dir = Path(args.out_dir)
    state_dir = Path(args.state_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    state_dir.mkdir(parents=True, exist_ok=True)
    progress = ProgressLog(state_dir / "progress.jsonl")

    dose_grid = _parse_dose_grid(args.dose_grid)
    prompt_set = load_prompt_set(args.prompt_set_path, expected_sha256=args.prompt_set_sha256)
    judge = load_judge_identity(args.judge_config)

    prompt_set_commit = None
    prompt_set_sha256 = None
    if args.use_frozen_prompt_artifact:
        run_prompt_set_validator(REPO_ROOT)
        frozen_artifact = load_frozen_prompt_artifact(REPO_ROOT, allow_pi_gated=args.allow_pi_gated)
        prompt_set_commit = frozen_artifact.commit
        prompt_set_sha256 = frozen_artifact.prompt_sets_sha256

    backend = load_backend(
        pairing=args.pairing, model_path=args.model_path, sae_path=args.sae_path, layer=args.layer,
        expected_model_revision=args.expected_model_revision, expected_sae_revision=args.expected_sae_revision,
        device=args.device, dtype=args.dtype, sae_family=args.qwen_sae_family, sparsity=args.qwen_sparsity,
    )
    if args.ready_path is not None:
        write_ready_record(args.ready_path, pairing=args.pairing, device=args.device)

    ranked_key = "stage1_rank"
    if progress.is_done(ranked_key):
        ranked = [RankedFeature(**r) for r in progress.result(ranked_key)["ranked"]]
    else:
        ranked = rank_features_by_activation(backend, prompt_set.probes, top_n=args.shortlist_size)
        ranked = exclude_mechanical_only(args.pairing, ranked)
        progress.record(ranked_key, {"ranked": [asdict(r) for r in ranked]})

    corpus_max_key = "stage1_corpus_max"
    if progress.is_done(corpus_max_key):
        corpus_max = {int(k): v for k, v in progress.result(corpus_max_key)["corpus_max"].items()}
    else:
        corpus_max = corpus_max_per_feature(backend, prompt_set.background_corpus)
        progress.record(corpus_max_key, {"corpus_max": {str(k): v for k, v in corpus_max.items()}})

    specificity_results: list[SpecificityResult] = []
    for r in ranked:
        key = f"stage2_specificity_{r.feature_index}"
        if progress.is_done(key):
            specificity_results.append(SpecificityResult(**progress.result(key)["result"]))
            continue
        result = validate_specificity(
            backend, r.feature_index, train_probes=prompt_set.probes, train_controls=prompt_set.controls,
            holdout_probes=prompt_set.holdout_probes, holdout_controls=prompt_set.holdout_controls,
            seed=args.seed, auc_threshold=args.specificity_auc_threshold,
        )
        specificity_results.append(result)
        progress.record(key, {"result": asdict(result)})

    passing = [r for r in specificity_results if r.passed]
    if not passing:
        final_result = {
            "schema_version": SCHEMA_VERSION, "pairing": args.pairing, "concept_id": prompt_set.concept_id,
            "prompt_set_commit": prompt_set_commit, "prompt_set_sha256": prompt_set_sha256,
            "status": "no_candidate_passed_specificity", "ranked_candidates": [asdict(r) for r in ranked],
            "specificity_results": [asdict(r) for r in specificity_results],
        }
        (out_dir / "result.json").write_text(json.dumps(final_result, indent=2), encoding="utf-8")
        return final_result

    best = max(passing, key=lambda r: r.holdout_auc)
    seed_feature = best.feature_index

    bundle_key = "stage4_bundle"
    if progress.is_done(bundle_key):
        bundle_data = progress.result(bundle_key)["bundle"]
        bundle = BundleResult(
            feature_indices=bundle_data["feature_indices"], final_metric=bundle_data["final_metric"],
            steps=[BundleStep(**s) for s in bundle_data["steps"]],
        )
    else:
        candidate_pool = [r.feature_index for r in passing]
        bundle = compose_bundle_greedily(
            backend, seed_feature, candidate_pool, train_probes=prompt_set.probes, train_controls=prompt_set.controls,
            holdout_probes=prompt_set.holdout_probes, holdout_controls=prompt_set.holdout_controls,
            seed=args.seed, materiality_threshold=args.bundle_materiality_threshold, bundle_max_size=args.bundle_max_size,
        )
        progress.record(bundle_key, {"bundle": {"feature_indices": bundle.feature_indices, "final_metric": bundle.final_metric, "steps": [asdict(s) for s in bundle.steps]}})

    dose_outcomes: list[InterventionOutcome] = []
    diagnostic_outcomes: list[InterventionOutcome] = []
    for dose in dose_grid:
        key = f"stage5_dose_{dose}_all"
        if progress.is_done(key):
            dose_outcomes.append(InterventionOutcome(**progress.result(key)["outcome"]))
        else:
            outcome = run_intervention(
                backend, bundle.feature_indices, direction=args.direction, value_in_max_units=dose,
                corpus_max=corpus_max, positions="all", prompt=args.prompt, seed=args.seed, max_new_tokens=args.max_new_tokens,
            )
            dose_outcomes.append(outcome)
            progress.record(key, {"outcome": asdict(outcome)})

        if args.record_generated_only_diagnostic:
            diag_key = f"stage5_dose_{dose}_generated_only"
            if progress.is_done(diag_key):
                diagnostic_outcomes.append(InterventionOutcome(**progress.result(diag_key)["outcome"]))
            else:
                diag_outcome = run_intervention(
                    backend, bundle.feature_indices, direction=args.direction, value_in_max_units=dose,
                    corpus_max=corpus_max, positions="generated_only", prompt=args.prompt, seed=args.seed, max_new_tokens=args.max_new_tokens,
                )
                diagnostic_outcomes.append(diag_outcome)
                progress.record(diag_key, {"outcome": asdict(diag_outcome)})

    calibration = select_calibration_candidates(
        dose_outcomes, low_threshold=args.calibration_low_threshold,
        medium_threshold=args.calibration_medium_threshold, high_threshold=args.calibration_high_threshold,
    )

    confirmation_by_dose: dict[float, list[InterventionOutcome]] | None = None
    if args.use_frozen_prompt_artifact:
        # heldout_neutral backs an Amplify confirmation; heldout_eliciting
        # backs a Suppress (ablate) confirmation -- matching G-D/G-E's own
        # prompt-role split (see final_pairing_causal_judge.py).
        confirmation_split = "heldout_eliciting" if args.direction == "ablate" else "heldout_neutral"
        held_out_rows = rows_for_concept(
            frozen_artifact.rows, concept_id=prompt_set.concept_id, locale="en", split=confirmation_split,
        )
        held_out_prompts = [r["text"] for r in held_out_rows]
        if len(held_out_prompts) != 20:
            raise ValueError(
                f"expected exactly 20 '{confirmation_split}' prompts for concept_id="
                f"{prompt_set.concept_id!r} locale='en', found {len(held_out_prompts)}"
            )
        confirmation_by_dose = run_dose_response_confirmation(
            backend, bundle.feature_indices, direction=args.direction, dose_grid=dose_grid,
            corpus_max=corpus_max, positions="all", held_out_prompts=held_out_prompts,
            n_repeats=args.confirmation_repeats, base_seed=args.seed, max_new_tokens=args.max_new_tokens,
            progress=progress,
        )

    final_result = {
        "schema_version": SCHEMA_VERSION,
        "pairing": args.pairing,
        "concept_id": prompt_set.concept_id,
        "prompt_set": {"source_path": prompt_set.source_path, "sha256": prompt_set.sha256},
        "prompt_set_commit": prompt_set_commit,
        "prompt_set_sha256": prompt_set_sha256,
        "judge": asdict(judge),
        "status": "complete",
        "seed_feature": seed_feature,
        "ranked_candidates": [asdict(r) for r in ranked],
        "specificity_results": [asdict(r) for r in specificity_results],
        "bundle": {"feature_indices": bundle.feature_indices, "final_metric": bundle.final_metric, "steps": [asdict(s) for s in bundle.steps]},
        "direction": args.direction,
        "positions": args.positions,
        "dose_response": [asdict(o) for o in dose_outcomes],
        "generated_only_diagnostic": [asdict(o) for o in diagnostic_outcomes] if args.record_generated_only_diagnostic else None,
        "dose_response_confirmation": (
            None if confirmation_by_dose is None
            else {str(dose): [asdict(o) for o in outcomes] for dose, outcomes in confirmation_by_dose.items()}
        ),
        "calibration_candidates": {tier: (asdict(c) if c is not None else None) for tier, c in calibration.items()},
        "provenance": {
            "model": backend.provenance["model"],
            "sae": backend.provenance["sae"],
            "layer": backend.layer,
            "sae_family": backend.sae_family,
            "sparsity": backend.sparsity,
            "checkpoint_hash": backend.checkpoint_hash,
            "corpus_max": {str(k): v for k, v in corpus_max.items()},
        },
    }
    (out_dir / "result.json").write_text(json.dumps(final_result, indent=2), encoding="utf-8")
    return final_result


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = run(args)
    print(json.dumps({"status": result["status"], "concept_id": result.get("concept_id")}, indent=2))
    return 0 if result["status"] in ("complete", "no_candidate_passed_specificity") else 1


if __name__ == "__main__":
    sys.exit(main())
