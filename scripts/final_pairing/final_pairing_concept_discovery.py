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

SHADOW G-B, AND WHICH STATISTIC GATES (2026-08-15). Every `gate_b_passed`
this file has ever written is computed from `fire_rate_within_cell`: the
fraction of a cell's ten positive prompts scoring at or above 0.20 x the
max of those same ten scores. That reference is derived from the very
prompts it judges, so the statistic is scale-invariant and measures
within-cell dynamic range rather than firing; on run 413287 it is measured
ANTI-correlated with the search target (Spearman(separation_auroc,
fire_rate) = -0.5234 over 1080 cells, recomputed by `verify_gate_fixes.py
shadow`). Correcting it requires re-deriving `G_B_fire_rate_min` against
the new scale, which is a protocol change nobody has made, SO IT IS NOT
CORRECTED HERE. What IS done: the same arithmetic is ALSO computed against
the reference this protocol already uses for this quantity -- the feature's
max over the background `unrelated` split, the same scale the frozen dose
grid and the causal stage express Amplify in -- and recorded beside it as
`fire_rate_corpus_max`, with `corpus_max`, the explicit
`fire_rate_within_cell`, and `verdict_computed_from` on every record.
`shadow_gate_b_summary` (per verdict and grid-level) carries the resulting
distribution over every (feature, cell) pair so the 0.70 bar can be
re-derived against measured evidence rather than asserted. THE SHADOW VALUE
IS RECORDED AND NEVER CONSULTED (`SHADOW_G_B_DISCLAIMER`); no gate,
threshold or conjunction reads it.

`--mode replay` (2026-08-15) is the owed MODEL-LEVEL falsifier: given a
preserved grid `progress.jsonl` it re-scores exactly that file's (concept,
feature) population on the real backend and asserts every emitted
separation_auroc / fire_rate_within_cell / near_miss_auroc reproduces the
preserved value to 1e-9, failing loudly rather than warning. It compares
raw floats, never booleans (C1 legitimately flips `gate_b_passed` on the
degenerate cells), and asserts the C1 correction applies to EXACTLY the
expected number of dead cells and nowhere else.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import re
import sys
from collections.abc import Mapping, Sequence
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
    `protocols/final_pairing/v1/scientific_config_identity.json` --
    CURRENTLY `final-pairing-config-identity/1.3.0`, commit
    `5a5175d36eac9802b45f76aeb5b52ff6b25220a8` (see `IDENTITY_PROTOCOL_
    COMMIT` below; v1.3.0 superseded the originating v1.2.0, commit
    93450e5, by supplying PRIMARY's `params_expected_sha256`, which 1.2.0
    left null/PENDING -- no configuration, layer, release, or threshold
    changed between the two): BOTH releases are FORCED (PRIMARY because
    layer 29 is off the canonical resid_post grid; BACKUP because
    `resid_post_all` does not publish `l0_medium` at layer 24 at all --
    OI-1, closed) -- the split is NECESSARY, not cosmetic, an earlier
    ("packaging, not a third family") premise that protocol version
    explicitly WITHDRAWS. Per that same protocol: a PRIMARY-to-BACKUP
    difference moves layer, sparsity tier, AND release/training-artifact
    simultaneously in Gemma (and layer/k in Qwen) -- nothing in this file
    may attribute an observed PRIMARY-vs-BACKUP outcome to any ONE of
    those dimensions; backup is a fallback configuration, not a
    controlled ablation. Qwen TopK `k` and Gemma observed L0 remain
    non-commensurable throughout this file: no ratio, proportional-match,
    or "aligned/similar/matched sparsity" claim is ever made between them
    anywhere in this codebase (verified by a literal repo-wide search for
    those exact retracted phrasings during the 1.2.0 integration pass) --
    matching between the two models is by transformer depth fraction ONLY
    (`qwen_depth_fraction`/`assert_gemma_qwen_depth_matches`)."""

    name: Literal["primary", "backup"]
    qwen_layer: int
    qwen_sae_family: str
    qwen_sparsity: int
    gemma_layer: int
    qwen_depth_fraction: float
    gemma_sae_release: str
    gemma_sae_id: str
    gemma_sae_loader_id: str
    #: The frozen EXPECTED digest of this configuration's params.safetensors
    #: file, from protocols/final_pairing/v1/scientific_config_identity.json
    #: v1.3.0 (commit 5a5175d) `configurations.<NAME>.params_expected_sha256`.
    #: This is compared against a digest MEASURED from the actual file loaded
    #: at runtime (`assert_params_sha256_matches` below) -- it is never itself
    #: emitted as `pairing.params_sha256`: "a recorded revision is trusted
    #: only where a hash check enforces it", so the emitted value must come
    #: from hashing the file on disk, not from copying this constant.
    gemma_params_expected_sha256: str
    #: Qwen is CONFIGURATION-SPECIFIC, not merely k-specific (P0 STOP-LINE
    #: correction, 2026-08-13): unlike Gemma (one repository, two release
    #: namespaces), PRIMARY and BACKUP draw from TWO SEPARATE Qwen-Scope
    #: repositories at two separate revisions -- from
    #: protocols/final_pairing/v1/qwen_config_identity.json (commit
    #: c2927d09152118de76e7ce7f7e5c67a1801eafbd) `configurations.<NAME>`.
    #: `qwen_params_expected_sha256` is bare hex (that artifact's own
    #: `sha256:`-prefixed string with the prefix stripped), matching
    #: `gemma_params_expected_sha256`'s encoding above -- compared against a
    #: digest MEASURED from the actual `layerN.sae.pt` file loaded at
    #: runtime (`assert_qwen_params_sha256_matches` below), never emitted
    #: as-is.
    qwen_sae_repo_id: str
    qwen_sae_revision: str
    qwen_params_expected_sha256: str


PRIMARY_CONFIGURATION = MatchedConfiguration(
    name="primary", qwen_layer=38, qwen_sae_family="L0_100", qwen_sparsity=100, gemma_layer=29, qwen_depth_fraction=0.59375,
    gemma_sae_release="gemma-scope-2-12b-it-res-all", gemma_sae_id="resid_post_all/layer_29_width_16k_l0_big",
    gemma_sae_loader_id="layer_29_width_16k_l0_big",
    gemma_params_expected_sha256="6bb44c8c68797942d097604bfd8df50f4865c86282e2c4667e364382ea26120e",
    qwen_sae_repo_id="Qwen/SAE-Res-Qwen3.5-27B-W80K-L0_100",
    qwen_sae_revision="82852e98c9b33d02194e92dd514b12fafd09ed25",
    qwen_params_expected_sha256="78b94bf19d4c120e70ba2767734b6d904468d127537e5d16c2a76cbc0963aeb0",
)
BACKUP_CONFIGURATION = MatchedConfiguration(
    name="backup", qwen_layer=32, qwen_sae_family="L0_50", qwen_sparsity=50, gemma_layer=24, qwen_depth_fraction=0.5,
    gemma_sae_release="gemma-scope-2-12b-it-res", gemma_sae_id="resid_post/layer_24_width_16k_l0_medium",
    gemma_sae_loader_id="layer_24_width_16k_l0_medium",
    gemma_params_expected_sha256="2e5f3bc8edc5340ac101fe967f5b59d7a14b40c47315baf5a3446232cb2e799e",
    qwen_sae_repo_id="Qwen/SAE-Res-Qwen3.5-27B-W80K-L0_50",
    qwen_sae_revision="13d4221569f7ca5d3c1e605e3e3dc95117e4807c",
    qwen_params_expected_sha256="fbbae7cf93c1e385c68213ae871ede349ac666f3a8c4e6a75ef959db2b6612ab",
)
MATCHED_CONFIGURATIONS: dict[str, MatchedConfiguration] = {"primary": PRIMARY_CONFIGURATION, "backup": BACKUP_CONFIGURATION}
#: Configuration-specific Qwen identity is looked up by SAE family (the one
#: field a caller supplies that uniquely determines a configuration) -- the
#: single place `load_qwen_scientific_target` resolves which configuration's
#: repo/revision/layer/k/hash a given `--qwen-sae-family` means, so a caller
#: can no longer combine e.g. `sae_family="L0_100"` with BACKUP's layer/k
#: (a "crossed configuration/family path").
QWEN_CONFIGURATION_BY_SAE_FAMILY: dict[str, MatchedConfiguration] = {
    c.qwen_sae_family: c for c in MATCHED_CONFIGURATIONS.values()
}

# protocols/final_pairing/v1/scientific_config_identity.json, v1.3.0 (commit
# 5a5175d): the version this file's MATCHED_CONFIGURATIONS constants above
# are transcribed from. v1.3.0's only change from v1.2.0 (93450e5) is
# supplying PRIMARY's params_expected_sha256 (was null/PENDING); no
# configuration, layer, release, or threshold changed.
IDENTITY_PROTOCOL_PATH = "protocols/final_pairing/v1/scientific_config_identity.json"
IDENTITY_PROTOCOL_COMMIT = "5a5175d36eac9802b45f76aeb5b52ff6b25220a8"
IDENTITY_PROTOCOL_SHA256 = "ac41a858b9e8a82159d2bd85c114dfcc8cec1b4d2b6f8a250c6482c18c915023"


def validate_scientific_config_identity_hash(repo_root: str | Path) -> str:
    """Fails closed if `scientific_config_identity.json`'s actual bytes
    don't match the pinned v1.3.0 hash -- the same discipline as
    `validate_backup_trigger_protocol_hash`, applied to the identity
    artifact this file's `MATCHED_CONFIGURATIONS` constants are
    transcribed from, so a silently-edited or reverted identity file is
    caught rather than trusted because this file's own constants still
    read as v1.3.0."""
    path = Path(repo_root) / IDENTITY_PROTOCOL_PATH
    if not path.is_file():
        raise PromptArtifactError(f"scientific-config identity protocol not found at {path}")
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != IDENTITY_PROTOCOL_SHA256.lower():
        raise PromptArtifactError(
            f"{path} sha256={actual!r} != pinned {IDENTITY_PROTOCOL_SHA256!r} -- refusing to run "
            f"discovery against an altered or superseded scientific-config identity artifact."
        )
    return actual


QWEN_CONFIG_IDENTITY_PROTOCOL_PATH = "protocols/final_pairing/v1/qwen_config_identity.json"
QWEN_CONFIG_IDENTITY_PROTOCOL_VERSION = "final-pairing-qwen-config-identity/1.0.0"
QWEN_CONFIG_IDENTITY_PROTOCOL_COMMIT = "c2927d09152118de76e7ce7f7e5c67a1801eafbd"
QWEN_CONFIG_IDENTITY_PROTOCOL_SHA256 = "ad61dd463c4440ff87aecf742038adca51361f5844c2c1bd847a1213999849e4"


def validate_qwen_config_identity_protocol_hash(repo_root: str | Path) -> str:
    """Fails closed if `qwen_config_identity.json`'s actual bytes don't
    match the pinned hash -- same discipline as
    `validate_scientific_config_identity_hash`, applied to the Qwen-arm
    gating supplement `PRIMARY_CONFIGURATION`/`BACKUP_CONFIGURATION`'s
    `qwen_sae_repo_id`/`qwen_sae_revision`/`qwen_params_expected_sha256`
    fields are transcribed from -- a silently-edited or reverted identity
    file must be caught even though this file's own constants still read
    as the frozen version."""
    path = Path(repo_root) / QWEN_CONFIG_IDENTITY_PROTOCOL_PATH
    if not path.is_file():
        raise PromptArtifactError(f"qwen-config identity protocol not found at {path}")
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != QWEN_CONFIG_IDENTITY_PROTOCOL_SHA256:
        raise PromptArtifactError(
            f"{path} sha256={actual!r} != pinned {QWEN_CONFIG_IDENTITY_PROTOCOL_SHA256!r} -- refusing to "
            f"run discovery against an altered or superseded Qwen scientific-config identity artifact."
        )
    return actual


GENERATION_SETTINGS_PROTOCOL_PATH = "protocols/final_pairing/v1/generation_settings.json"
GENERATION_SETTINGS_PROTOCOL_VERSION = "final-pairing-generation-settings/1.0.0"
GENERATION_SETTINGS_PROTOCOL_SHA256 = "975e90e0271e750aea8f871f4776d2a3d0169ea4fe410e544081957907e613b1"

#: The frozen, EXPLICIT generation kwargs (`generation_settings.json`
#: section 1) -- identical across pairings, configurations, directions,
#: locales, and control/steered arms. `do_sample=True` (not the greedy
#: `do_sample=False` this file's OTHER callers still use, e.g. `run()`'s
#: single-concept pipeline) corrects a real defect: under greedy decoding
#: a seed has no effect, so "three fresh confirmation repeats" were
#: byte-identical, silently voiding the whole point of disjoint sweep/
#: confirmation seeds. `top_k=0` explicitly DISABLES top-k truncation
#: (so only top_p governs) rather than leaving it unset and inheriting
#: whichever model's own generation_config.json default. `max_new_tokens`
#: is deliberately NOT part of this dict -- the protocol freezes it at 48
#: for the one-allocation generation specifically, applied by that
#: module's own callers, not hardcoded into `run_intervention`/`run_
#: baseline_generation`, which remain shared with callers that need a
#: different token budget (e.g. `run()`'s own `--max-new-tokens`).
GENERATION_SETTINGS: dict[str, Any] = {
    "do_sample": True, "temperature": 0.7, "top_p": 0.9, "top_k": 0,
    "repetition_penalty": 1.0, "no_repeat_ngram_size": 0, "min_new_tokens": 0,
    "num_beams": 1, "num_return_sequences": 1,
}
#: The frozen max_new_tokens for one-allocation generation specifically
#: (generation_settings.json's own `settings.max_new_tokens`) -- kept
#: separate from `GENERATION_SETTINGS` per the note above.
ONE_ALLOCATION_MAX_NEW_TOKENS = 48


def validate_generation_settings_protocol_hash(repo_root: str | Path) -> str:
    """Fails closed if `generation_settings.json`'s actual bytes don't
    match the pinned hash -- same discipline as this project's other
    frozen-protocol hash guards."""
    path = Path(repo_root) / GENERATION_SETTINGS_PROTOCOL_PATH
    if not path.is_file():
        raise PromptArtifactError(f"generation-settings protocol not found at {path}")
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != GENERATION_SETTINGS_PROTOCOL_SHA256:
        raise PromptArtifactError(
            f"{path} sha256={actual!r} != pinned {GENERATION_SETTINGS_PROTOCOL_SHA256!r} -- refusing to "
            f"generate against an altered or unpinned generation-settings protocol."
        )
    return actual


def compute_file_sha256(path: str | Path, *, chunk_size: int = 1 << 20) -> str:
    """Streaming SHA-256 of a file's actual bytes on disk -- never a
    stand-in for reading the whole file into memory at once, since SAE
    params files can be large."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def assert_params_sha256_matches(resolved_sae_files: list[str], *, expected_sha256: str) -> str:
    """Finds the SAE's `params.safetensors` among the files sae_lens
    actually resolved locally, computes ITS ACTUAL SHA-256 from the bytes
    on disk, and asserts it equals `expected_sha256` (the frozen
    identity artifact's `params_expected_sha256` for this configuration).
    Returns the MEASURED digest -- the caller must persist exactly this
    return value as `pairing.params_sha256`, never the `expected_sha256`
    argument itself: 'the revision string says what was downloaded, and
    only the hash says what is on disk', so a value that was never
    actually computed from the loaded file is not a verified hash
    regardless of whether it happens to be correct."""
    candidates = [f for f in resolved_sae_files if Path(f).name == "params.safetensors"]
    if not candidates:
        raise targets.TargetIdentityMismatch(
            f"no params.safetensors found among resolved SAE files {resolved_sae_files} -- cannot "
            f"measure a params hash to verify against the frozen identity artifact"
        )
    # `resolved_sae_files` is a per-REQUEST capture log (harness._capture_sae_
    # download_paths appends once per hf_hub_download call), and one load
    # legitimately requests the SAME params.safetensors twice: once via
    # get_gemma_3_config_from_hf -> get_safetensors_tensor_shapes (routed
    # through psl.hf_hub_download by _patch_gemma3_safetensors_shape_lookup)
    # for the d_in/d_sae shapes, then again via gemma_3_sae_huggingface_loader
    # for the weights themselves. That is one file, not two, and it killed
    # job 413287's whole Gemma arm. The identity question this guard asks is
    # "did more than one DISTINCT params file get loaded", so count distinct
    # real files -- realpath, not the string as written, because a real
    # huggingface_hub cache serves symlinks and two different snapshot-
    # relative strings can name the same blob. (Dereferencing is correct HERE,
    # for identity; it must never be used for targets.validate_sae_files_match_
    # expected_subdirectory's LOGICAL containment check, which would then see
    # every legitimately symlinked file as escaping the snapshot.) Two
    # genuinely different params.safetensors still have two distinct real
    # paths and still raise.
    distinct_by_real_path: dict[str, str] = {}
    for candidate in candidates:
        distinct_by_real_path.setdefault(os.path.realpath(candidate), candidate)
    if len(distinct_by_real_path) > 1:
        raise targets.TargetIdentityMismatch(
            f"expected exactly one params.safetensors among resolved SAE files, found "
            f"{len(distinct_by_real_path)} distinct files: {sorted(distinct_by_real_path.values())} "
            f"(resolving to {sorted(distinct_by_real_path)})"
        )
    params_path = next(iter(distinct_by_real_path.values()))
    measured = compute_file_sha256(params_path)
    if measured != expected_sha256:
        raise targets.TargetIdentityMismatch(
            f"{params_path} hashes to {measured!r}, not the frozen expected "
            f"{expected_sha256!r} ({IDENTITY_PROTOCOL_COMMIT}). Mismatch is a hard stop: the "
            f"revision says what was downloaded, only the hash says what is on disk."
        )
    return measured


def assert_qwen_params_sha256_matches(layer_file_path: str | Path, *, expected_sha256: str) -> str:
    """The Qwen-side counterpart to `assert_params_sha256_matches`: computes
    the ACTUAL SHA-256 of the loaded `layerN.sae.pt` file's bytes on disk
    (a single file per layer, not a snapshot directory to search) and
    asserts it equals `expected_sha256` (`qwen_config_identity.json`'s
    `configurations.<NAME>.params_expected_sha256` for this configuration).
    Returns the MEASURED digest -- callers must persist exactly this
    return value as provenance, never the `expected_sha256` argument
    itself, per the same "the revision says what was downloaded, only the
    hash says what is on disk" discipline."""
    measured = compute_file_sha256(layer_file_path)
    if measured != expected_sha256:
        raise targets.TargetIdentityMismatch(
            f"{layer_file_path} hashes to {measured!r}, not the frozen expected {expected_sha256!r} "
            f"({QWEN_CONFIG_IDENTITY_PROTOCOL_COMMIT}). Mismatch is a hard stop: the revision says "
            f"what was downloaded, only the hash says what is on disk."
        )
    return measured

# The backup trigger's exact Boolean rule -- frozen at
# protocols/final_pairing/v1/backup_trigger.json (commit 125b1d3).
# `evaluate_backup_trigger` below implements EXACTLY its `trigger.
# boolean_expression`/`failure_expression`, no more.
#
# SUPERSEDED DISCLOSURE (this comment used to say `primary_shared_gabc_
# count` required manual computation because the full 14-concept grid and
# G-C had no implementation yet -- both now exist and are wired
# automatically): `run_grid_mode` computes the full 14-concept x 2-pairing
# x 3-gate x 3-family x 2-locale grid, `compute_gate_c_per_family`
# implements G-C, and `final_concept_discovery_matched_configuration_job.
# compute_trigger_from_grid_outputs` reads both pairings' `grid.json`
# files and derives `primary_shared_gabc_count`/`run_backup` automatically
# via `feature_survives_gabc`'s same-feature G-A+G-B+G-C conjunction --
# `run_matched_configuration_job`'s scheduled entry point calls it itself.
# `--run-backup`/`--trigger-inputs-json` remain wired into the matched-
# configuration job ONLY as a test-only override seam (there is no such
# flag on the scheduled `main()` CLI at all); they are not how the trigger
# reaches production.
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


TRANSFER_MANIFEST_FILENAME = "transfer_manifest.json"


class TransferManifestError(ValueError):
    """The archive-side transfer manifest (`transfer_manifest.json`,
    written once by `build_transfer_manifest`/`write_transfer_manifest` on
    the machine that still has `.git`, e.g. immediately before a `git
    archive` transfer to Tamia) is missing a required field, or its
    recorded file hash disagrees with what is actually on disk after
    transfer."""


def _has_git_directory(repo_root: str | Path) -> bool:
    return (Path(repo_root) / ".git").exists()


def build_transfer_manifest(repo_root: str | Path, *, extra_paths: tuple[str, ...] = ()) -> dict:
    """WINDOWS/DEV-SIDE ONLY (requires `.git`): records the exact commit
    and per-file hashes an archive (e.g. `git archive HEAD`) is about to
    ship to Tamia, which has no `.git` at all after extraction -- so Tamia
    can never run `git status`/`git rev-parse` for itself. Runs the SAME
    dirty-tree check `load_frozen_prompt_artifact` used to run on every
    single invocation, but only ONCE, HERE, at archive-build time, across
    the frozen prompt artifact directory and every one of `extra_paths`
    (e.g. `protocols/final_pairing/v1/`). Because `git archive` only ever
    exports COMMITTED content, a clean check here means the archived bytes
    are exactly HEAD's tree -- nothing on the Tamia side needs to (or can)
    re-run this check; it re-verifies the resulting BYTES instead, via
    `load_transfer_manifest`/the frozen sha256 constants."""
    repo_root = Path(repo_root)
    paths_to_check = (FROZEN_PROMPT_SET_DIR, *extra_paths)
    rc, out = _git(repo_root, "status", "--porcelain", "--", *paths_to_check)
    if rc != 0:
        raise TransferManifestError(f"git status failed while building the transfer manifest: {out}")
    if out.strip():
        raise TransferManifestError(
            f"refusing to build a transfer manifest from a dirty working tree under {paths_to_check}:\n{out}"
        )
    rc, head = _git(repo_root, "rev-parse", "HEAD")
    if rc != 0 or not head:
        raise TransferManifestError(f"git rev-parse HEAD failed while building the transfer manifest: {head!r}")

    files: dict[str, str] = {}
    for rel in (
        f"{FROZEN_PROMPT_SET_DIR}/prompt_sets.jsonl", f"{FROZEN_PROMPT_SET_DIR}/metadata.json", *extra_paths,
    ):
        path = repo_root / rel
        if not path.is_file():
            raise TransferManifestError(f"transfer manifest source file not found: {path}")
        files[rel] = compute_file_sha256(path)

    return {"schema_version": SCHEMA_VERSION, "source_commit": head, "files": files}


def write_transfer_manifest(
    repo_root: str | Path, *, extra_paths: tuple[str, ...] = (), out_path: str | Path | None = None,
) -> dict:
    """Writes the manifest `build_transfer_manifest` computes to
    `<repo_root>/transfer_manifest.json` (or `out_path`) -- the file a
    `git archive` invocation should include alongside the code (it lives
    in the working tree, not in git history, so it must be added to the
    archive command's own file list or copied in afterward)."""
    manifest = build_transfer_manifest(repo_root, extra_paths=extra_paths)
    path = Path(out_path) if out_path is not None else Path(repo_root) / TRANSFER_MANIFEST_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest


def load_transfer_manifest(repo_root: str | Path) -> dict | None:
    """Returns `None` (never raises) when no transfer manifest is present
    -- the normal case on a Windows/dev checkout that still has `.git` and
    has never been archived. Tamia-side code should treat a present
    manifest as authoritative and a `None` manifest as "fall back to a
    live git check, if `.git` exists here at all"."""
    path = Path(repo_root) / TRANSFER_MANIFEST_FILENAME
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _verify_against_transfer_manifest(transfer_manifest: dict, *, jsonl_path: Path, metadata_path: Path) -> None:
    required = ("source_commit", "files")
    missing = [k for k in required if k not in transfer_manifest]
    if missing:
        raise TransferManifestError(f"{TRANSFER_MANIFEST_FILENAME} is missing required field(s): {missing}")
    files = transfer_manifest["files"]
    for path, suffix in ((jsonl_path, "prompt_sets.jsonl"), (metadata_path, "metadata.json")):
        rel = f"{FROZEN_PROMPT_SET_DIR}/{suffix}"
        if rel not in files:
            raise TransferManifestError(f"{TRANSFER_MANIFEST_FILENAME} does not record a hash for {rel}")
        actual = compute_file_sha256(path)
        if actual != files[rel]:
            raise TransferManifestError(
                f"{path} sha256={actual!r} != {TRANSFER_MANIFEST_FILENAME}'s recorded {files[rel]!r} -- "
                f"the file was altered after the transfer archive was built"
            )


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

    ARCHIVE EXECUTION MUST NOT REQUIRE `.git`: a Tamia allocation receives
    this repository via a `git archive`-based transfer (see
    `build_transfer_manifest`/`write_transfer_manifest`), which by
    construction never includes a `.git` directory. A live
    `git status`/`git rev-parse` call would therefore always fail there --
    not merely be redundant. Precedence: (1) if `transfer_manifest.json`
    is present (the Tamia-side case), the dirty-tree check is NOT re-run
    here at all -- it already ran once, on Windows, before the archive was
    built (`build_transfer_manifest`'s own dirty-tree check); this
    function instead re-verifies the manifest's recorded per-file hashes
    against what is actually on disk after transfer. (2) Otherwise, if
    `.git` exists (the Windows/dev-side case, no archive has been built
    yet), the original live dirty-tree check runs exactly as before.
    (3) Neither present is a hard stop -- there is no way to prove the
    artifact was not tampered with after being committed.
    """
    repo_root = Path(repo_root)
    artifact_dir = repo_root / FROZEN_PROMPT_SET_DIR
    jsonl_path = artifact_dir / "prompt_sets.jsonl"
    metadata_path = artifact_dir / "metadata.json"
    if not jsonl_path.is_file() or not metadata_path.is_file():
        raise PromptArtifactError(f"frozen prompt artifact not found under {artifact_dir}")

    transfer_manifest = load_transfer_manifest(repo_root)
    if transfer_manifest is not None:
        _verify_against_transfer_manifest(transfer_manifest, jsonl_path=jsonl_path, metadata_path=metadata_path)
    elif _has_git_directory(repo_root):
        rc, out = _git(repo_root, "status", "--porcelain", "--", str(FROZEN_PROMPT_SET_DIR))
        if rc != 0:
            raise PromptArtifactError(f"git status failed while checking the frozen prompt artifact: {out}")
        if out.strip():
            raise PromptArtifactError(
                f"the frozen prompt artifact directory has uncommitted changes -- refusing to run "
                f"discovery against a dirty or uncommitted replacement:\n{out}"
            )
    else:
        raise PromptArtifactError(
            f"{repo_root} has neither {TRANSFER_MANIFEST_FILENAME} nor a .git directory -- cannot verify "
            f"the frozen prompt artifact was not tampered with after being committed. Build a transfer "
            f"manifest (write_transfer_manifest) before archiving this repository for Tamia."
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


#: The split the SHADOW G-B reference scale is measured over. NOT a new
#: choice: `final_pairing_one_allocation_generation.py` already computes the
#: causal stage's `corpus_max` from exactly this split ("`unrelated`
#: (shared_substrate, identical text across all 14 concepts by design) is
#: the same concept-agnostic negative/background role G-A already reads; the
#: frozen artifact carries no field explicitly named 'background_corpus' of
#: its own, so this is a disclosed re-use, not an invented split"), and the
#: frozen dose grid states Amplify in multiples of it. The shadow metric
#: expresses G-B in the units this protocol ALREADY uses for the same
#: quantity, instead of in the within-cell units G-B invented.
SHADOW_G_B_REFERENCE_SPLIT = "unrelated"

#: Carried on every record that has a shadow value, so no later reader can
#: mistake which statistic produced a verdict.
SHADOW_G_B_DISCLAIMER = (
    "fire_rate_corpus_max is a SHADOW MEASUREMENT ONLY. Every gate_b_passed in this file is "
    "computed from fire_rate_within_cell (the frozen within-cell statistic) and from nothing else; "
    "the shadow value is recorded and never consulted by any verdict, conjunction or threshold. "
    "Re-deriving G_B_fire_rate_min against the corpus-max scale is a protocol change nobody has "
    "made, and this field does not make it."
)

#: The single string every emitted G-A/G-B record carries in
#: `verdict_computed_from`. A literal, not a formatted value: if a future
#: edit ever routes a verdict through the shadow statistic, this constant is
#: the thing that has to change with it, and the tests assert on it.
GATE_B_VERDICT_SOURCE = "fire_rate_within_cell"

ANTI_SPECIFICITY_NOTE = (
    "ANTI-SPECIFIC: separation_auroc < 0.5, i.e. this feature ranks the CONTROL texts above the "
    "concept's own positives -- it fires HARDER on text the concept is defined against than on the "
    "concept. RECORDED AS A DISQUALIFIER AND READ BY NO VERDICT. G-B cannot see this by "
    "construction: dividing by the cell's own observed max is scale-invariant, so a feature that "
    "fires on everything and a feature that fires only on the concept produce the SAME fire_rate, "
    "and 105 anti-specific cells passed within-cell G-B in the 415590 grid. This field makes the "
    "property expressible in the record; acting on it would move a gate, which no ruling has "
    "authorized. Nothing here changes a threshold, a conjunction or a verdict."
)


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
    # C4 (2026-08-15): the ABSOLUTE quantities G-B's verdict is actually a
    # function of, recorded rather than discarded. `activation_floor_fraction`
    # alone (0.20) is a constant -- it says nothing about whether the feature
    # fired at all. `activation_floor` is the absolute threshold a positive
    # prompt had to clear (`observed_max * activation_floor_fraction`, or 0.0
    # in the degenerate case guarded below), `observed_max` is the largest
    # per-prompt score in this cell's positive set, and `n_positives` is how
    # many prompts the fire_rate denominator counted. Without these three, a
    # `fire_rate` of 1.0 is indistinguishable between "fired on all ten
    # prompts" and "never fired at all, and the floor collapsed to zero" --
    # the exact ambiguity that hid 295 dead cells in run 413287. This field
    # is what ENDED that ambiguity: the GPU replay in Tamia job 414676
    # (2026-08-15) read `observed_max == 0.0` directly and measured 295,
    # where the record-only signature could see only 182 (it also requires
    # the CONTROLS to be silent, so it misses the 113 cells that are dead
    # on the concept and active on the controls). Purely additive: no
    # existing field changes meaning or value.
    activation_floor: float = 0.0
    observed_max: float = 0.0
    n_positives: int = 0
    # SHADOW G-B (2026-08-15). MEASUREMENT ONLY -- see
    # `SHADOW_G_B_DISCLAIMER`, which every populated record carries in
    # `shadow_disclaimer`. `fire_rate_within_cell` is the SAME NUMBER as
    # `fire_rate` above, named explicitly so the two statistics can never
    # be confused in a downstream reader; it is the one the verdict is
    # computed from, and `verdict_computed_from` says so on every record.
    # `fire_rate_corpus_max` is the same arithmetic against the protocol's
    # own background reference scale (`shadow_corpus_max_per_feature`), and
    # `corpus_max`/`shadow_reference_source` record the reference value and
    # where it came from. All defaulted and purely additive: no existing
    # field changes meaning or value, and a record written before this
    # change still round-trips.
    fire_rate_within_cell: float = 0.0
    fire_rate_corpus_max: float | None = None
    corpus_max: float | None = None
    shadow_activation_floor: float | None = None
    shadow_reference_source: str = "not_computed"
    shadow_reference_degenerate: bool = False
    verdict_computed_from: str = GATE_B_VERDICT_SOURCE
    shadow_disclaimer: str = ""
    #: ANTI-SPECIFICITY, recorded as a DISQUALIFIER (architect RULING_8,
    #: 2026-08-15). True when `separation_auroc < 0.5` -- the feature ranks
    #: the control texts ABOVE the concept's own positives. 343 such cells
    #: exist in the 415590 grid and 105 of them PASS within-cell G-B; all 18
    #: of the shadow's PASS->FAIL flips are anti-specific.
    #:
    #: WHY G-B CANNOT DO THIS ITSELF, and it is not a tuning problem: the
    #: within-cell reference divides by the cell's own observed max, which
    #: makes the statistic SCALE-INVARIANT, so "fires on everything" and
    #: "fires only on the concept" are the same number. The property is
    #: invisible to that denominator BY CONSTRUCTION, at any threshold.
    #:
    #: READ BY NO VERDICT. Additive record only -- acting on it would be a
    #: gate change, which no ruling has authorized. Defaulted, so a record
    #: written before this field still round-trips.
    anti_specific: bool = False
    anti_specific_note: str = ""


def _auroc_from_scores(positive_scores: list[float], negative_scores: list[float]) -> float:
    from sklearn.metrics import roc_auc_score

    y = [1] * len(positive_scores) + [0] * len(negative_scores)
    scores = [*positive_scores, *negative_scores]
    return float(roc_auc_score(y, scores))


def compute_gate_b_fire_rate(positive_scores: Sequence[float], *, floor_fraction: float) -> tuple[float, float]:
    """G-B's firing arithmetic, pure and independently testable: the floor
    is `floor_fraction` (0.20 by default) times the observed max of
    `positive_scores`, and a prompt fires iff its score is `>= floor` --
    P0 STOP-LINE correction: NOT a strict `>` (a prompt landing exactly
    at the floor must count as firing). Returns `(fire_rate, floor)`.

    C1 DEGENERATE-CASE GUARD (2026-08-15). SAE scores are post-ReLU, so
    they are non-negative and a feature that never fires on ANY positive
    prompt yields `observed_max == 0.0`. The floor is then `0.0 * 0.20 ==
    0.0`, every score satisfies the (correct, non-strict) `0.0 >= 0.0`,
    and `fire_rate` comes out 1.0 -- G-B PASSING a feature that is
    completely silent on the concept prompts. MEASURED on production run
    413287 by the GPU replay in Tamia job 414676 (2026-08-15): 295 of that
    run's 660 recorded G-B passes were this degenerate case (44.7%) --
    ARTIFACTS, not passes; a G-B pass rate computed with them included is
    not a fact about that run and must not be quoted as one. Grid-wide,
    660 recorded G-B passes are 365 real ones.

    READ THE SCOPE OF "DEAD" HERE, IT IS NARROWER THAN IT LOOKS. This
    function's `observed_max` is taken over the POSITIVE scores ALONE, so
    the degenerate case means SILENT ON THE CONCEPT PROMPTS and says
    NOTHING about the controls -- a feature firing hard on the near-miss
    and unrelated sets lands here too, and 113 of the 295 did exactly that
    (`separation_auroc` as low as 0.12, i.e. firing MORE on the controls
    than on the concept, and every one of them passed G-B with `fire_rate`
    1.0). The earlier figure of 182 came from a RECORD-ONLY signature that
    additionally demanded AUROC 0.5 against both control sets; it is
    preserved as `REPLAY_SIGNATURE_VISIBLE_DEAD_CELLS`, a correct LOWER
    BOUND, and it is all the preserved record can see without
    `observed_max`. The guard below is
    strictly STRICTER (it can only turn a pass into a fail, never the
    reverse) and it is the SAME intent as the pre-existing
    empty-`positive_scores` early return directly above it: no evidence
    of firing is not evidence of firing. Thresholds are untouched -- this
    is not a threshold change, it is a division-by-a-degenerate-scale
    guard.

    OBSERVATION, DELIBERATELY NOT IMPLEMENTED (2026-08-15). `observed_max`
    is a WITHIN-CELL reference scale: it is derived from the very positive
    prompts whose firing it then judges, so it is circular. The guard
    below removes only the case where that circularity degenerates
    completely (a scale of exactly zero); it does NOT make the scale
    non-circular. This protocol already contains the non-circular
    reference this quantity should be expressed against -- the frozen dose
    grid states Amplify in units of the feature's own CORPUS max
    (`corpus_max_per_feature` below: "the ONLY legal source of steering
    units ... never the concept probes"), and the causal stage already
    uses it. G-B's within-cell max is inconsistent with this protocol's
    own convention for the same quantity. Changing it would require
    re-deriving `G_B_fire_rate_min` against the new scale -- a protocol
    change nobody has made -- so it is RECORDED HERE AND NOT DONE. Every
    G-B number this file emits is computed through the within-cell
    (circular) denominator and must be read as such."""
    if len(positive_scores) == 0:
        return 0.0, 0.0
    observed_max = max(positive_scores)
    if observed_max <= 0:
        return 0.0, 0.0
    floor = observed_max * floor_fraction
    fire_rate = sum(1 for s in positive_scores if s >= floor) / len(positive_scores)
    return fire_rate, floor


def rank_auroc_matrix(positive_scores: np.ndarray, negative_scores: np.ndarray) -> np.ndarray:
    """AUROC of every COLUMN at once: `positive_scores` is `[n_pos, n_feat]`,
    `negative_scores` is `[n_neg, n_feat]`, the result is `[n_feat]`.

    The Mann-Whitney U identity that `sklearn.metrics.roc_auc_score`
    already computes: `AUROC == (sum of the positives' ranks - n_pos *
    (n_pos + 1) / 2) / (n_pos * n_neg)`, with AVERAGE ranks for ties.
    Ties are the normal case here, not an edge case -- SAE scores are
    post-ReLU and mostly exact zeros -- so `method="average"` is
    load-bearing, and `verify_gate_fixes.py c3` falsifies this against
    `_auroc_from_scores` on deliberately tie-heavy inputs.

    This exists so that G-A/G-C can be evaluated for ALL d_sae features
    in one pass instead of one feature at a time. It is a SCREEN: every
    verdict this file records is re-computed through the frozen
    `_auroc_from_scores` (see `evaluate_concept_on_pairing`), so the
    recorded numbers never depend on this function agreeing with sklearn
    in the last ulp."""
    pos = np.asarray(positive_scores, dtype=np.float64)
    neg = np.asarray(negative_scores, dtype=np.float64)
    if pos.ndim == 1:
        pos = pos[:, None]
    if neg.ndim == 1:
        neg = neg[:, None]
    n_pos, n_neg = pos.shape[0], neg.shape[0]
    if n_pos == 0 or n_neg == 0:
        raise ValueError("rank_auroc_matrix needs at least one positive and one negative row")

    from scipy.stats import rankdata

    ranks = rankdata(np.concatenate([pos, neg], axis=0), method="average", axis=0)
    positive_rank_sum = ranks[:n_pos].sum(axis=0)
    return (positive_rank_sum - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)


def fire_rate_matrix(positive_scores: np.ndarray, *, floor_fraction: float) -> tuple[np.ndarray, np.ndarray]:
    """`compute_gate_b_fire_rate` for every COLUMN at once. Returns
    `(fire_rates, floors)`, both `[n_feat]`.

    Bit-identical to the scalar function, C1 degenerate guard included
    (`observed_max <= 0 -> (0.0, 0.0)`), and falsified against it on
    randomised inputs that deliberately include fully dead columns.

    Same caveat as the scalar function and for the same reason: the floor
    is a WITHIN-CELL fraction of the positives' own max, which is
    circular. Vectorising it computes the same circular quantity faster;
    it does not make it sound. See `compute_gate_b_fire_rate`'s docstring
    for the non-circular reference this protocol already defines and for
    why changing it is not authorised here."""
    pos = np.asarray(positive_scores, dtype=np.float64)
    if pos.ndim == 1:
        pos = pos[:, None]
    n_pos = pos.shape[0]
    if n_pos == 0:
        zeros = np.zeros(pos.shape[1], dtype=np.float64)
        return zeros, zeros.copy()
    observed_max = pos.max(axis=0)
    floors = observed_max * floor_fraction
    rates = (pos >= floors).sum(axis=0) / n_pos
    dead = observed_max <= 0
    return np.where(dead, 0.0, rates), np.where(dead, 0.0, floors)


def shadow_corpus_max_per_feature(
    backend: Backend, artifact: FrozenPromptArtifact, *,
    locales: tuple[str, ...] = FROZEN_PROMPT_SET_LOCALES, cache: FeatureMatrixCache | None = None,
) -> np.ndarray:
    """The SHADOW G-B reference scale: each feature's max activation over the
    frozen artifact's `unrelated` split, both locales, as a `[d_sae]` array.

    This is the non-circular reference the protocol already defines for
    this quantity (see `SHADOW_G_B_REFERENCE_SPLIT`), computed the same way
    `corpus_max_per_feature` computes the causal stage's: a max over
    background text that is NEVER the concept probes under judgement. Two
    deliberate consequences follow, and they are the whole point:

    1. It is the SAME number in every (concept, locale, family) cell of the
       run, so a fire rate expressed against it is not scale-invariant --
       unlike the within-cell statistic, which divides by the max of the
       ten scores it is judging and therefore measures dynamic range
       rather than firing.
    2. It is measured on text the feature was not selected on, so a
       concept-selective feature can legitimately score a corpus max well
       BELOW its within-cell max. The within-cell reference can never
       produce that ordering.

    Costs ZERO additional forward passes in a grid run: `pin_shared_substrate`
    already encodes and pins exactly these texts for the whole run, so this
    is a cache read plus a column-wise max. Both locales are pooled (the
    causal stage's own corpus max reads the `en` subset only, because it
    generates in `en`); pooling is the conservative direction -- it can only
    RAISE the reference and therefore only LOWER a shadow fire rate.

    DISCLOSED CHOICE -- why the BACKGROUND split and not "every text the
    run touched". A reference taken over ALL of the run's text would
    include each cell's own positives, so `corpus_max >= observed_max`
    would hold by construction in every cell. The shadow fire rate is
    non-increasing in the reference and equals the frozen statistic exactly
    at `corpus_max == observed_max` (both falsified by
    `verify_gate_fixes.py shadow`, SHADOW-A), so such a reference could
    only ever produce a rate at or BELOW the within-cell one: a uniformly
    stricter gate whose direction is known in advance and which therefore
    measures nothing new. The background split is the only reference that
    can move a cell in either direction, and it is the one the protocol
    already uses. Neither choice is a threshold change; both are recorded
    quantities.

    Never raises for a missing split on one concept: the `unrelated` rows
    are shared_substrate and identical across all 14 concepts, so the first
    concept that has them supplies them, exactly as `pin_shared_substrate`
    does."""
    cache = FeatureMatrixCache() if cache is None else cache
    reference = np.zeros(backend.d_sae, dtype=np.float64)
    texts_seen = 0
    for locale in locales:
        for concept_id in sorted({r["concept_id"] for r in artifact.rows}):
            texts = [
                r["text"] for r in rows_for_concept(
                    artifact.rows, concept_id=concept_id, locale=locale, split=SHADOW_G_B_REFERENCE_SPLIT
                )
            ]
            if texts:
                reference = np.maximum(reference, cache.features(backend, texts).astype(np.float64).max(axis=0))
                texts_seen += len(texts)
                break
    if texts_seen == 0:
        raise ValueError(
            f"shadow_corpus_max_per_feature found no {SHADOW_G_B_REFERENCE_SPLIT!r} rows in the "
            f"artifact for locales {locales} -- refusing to invent a reference scale"
        )
    return reference


def compute_shadow_fire_rate_corpus_max(
    positive_scores: Sequence[float], *, floor_fraction: float, corpus_max: float
) -> tuple[float, float, bool]:
    """The SHADOW G-B statistic: the same fire-rate arithmetic as
    `compute_gate_b_fire_rate`, with the floor taken at `floor_fraction *
    corpus_max` (`shadow_corpus_max_per_feature`, the protocol's own
    background scale) instead of at `floor_fraction * max(positive_scores)`
    (the same ten scores under test). Returns `(fire_rate, floor,
    reference_degenerate)`.

    READ `SHADOW_G_B_DISCLAIMER`. Nothing computed here decides anything.
    No verdict, gate, threshold or conjunction reads this function's return
    value; `gate_b_passed` is and remains `fire_rate_within_cell >=
    G_B_fire_rate_min`. This exists so that whoever re-derives that 0.70
    bar against the corrected scale has a measured distribution instead of
    an assertion.

    Firing rule, stated exactly: a positive prompt fires iff `score >=
    floor AND score > 0`. When `floor > 0` the second clause is a no-op
    (it is implied), so on every non-degenerate cell this is bit-for-bit
    the frozen `>=` rule with a different floor -- the only difference
    under test is the DENOMINATOR. The second clause exists for the
    degenerate reference case `corpus_max == 0` (a feature completely
    silent on the background corpus), where the floor collapses to 0.0 and
    the frozen non-strict `>=` would count a score of exactly 0.0 as firing
    -- the identical artifact C1 removed from the within-cell statistic,
    which produced 295 phantom passes in run 413287 (measured on GPU by
    job 414676; 182 of them visible to the record-only signature).
    `reference_degenerate`
    is returned so those cells can be counted and excluded rather than
    silently folded into a distribution. Note a degenerate reference is
    NOT the same thing as a dead cell: `corpus_max == 0` with a live
    positive set is maximal selectivity (the feature fires on the concept
    and nowhere in the background), and it scores 1.0 here on purpose."""
    if len(positive_scores) == 0:
        return 0.0, 0.0, corpus_max <= 0
    floor = max(float(corpus_max), 0.0) * floor_fraction
    fired = sum(1 for s in positive_scores if s >= floor and s > 0)
    return fired / len(positive_scores), floor, corpus_max <= 0


def shadow_fire_rate_matrix(
    positive_scores: np.ndarray, *, floor_fraction: float, corpus_max: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """`compute_shadow_fire_rate_corpus_max` for every COLUMN at once, given
    a `[n_feat]` vector of per-feature corpus maxima. Returns `(fire_rates,
    floors)`, both `[n_feat]`. Falsified against the scalar function on
    randomised inputs (including dead columns and zero references) by
    `verify_gate_fixes.py shadow`.

    Feeds the run-level shadow DISTRIBUTION only. Like the scalar function
    it decides nothing -- see `SHADOW_G_B_DISCLAIMER`."""
    pos = np.asarray(positive_scores, dtype=np.float64)
    if pos.ndim == 1:
        pos = pos[:, None]
    reference = np.maximum(np.asarray(corpus_max, dtype=np.float64), 0.0)
    n_pos = pos.shape[0]
    if n_pos == 0:
        zeros = np.zeros(pos.shape[1], dtype=np.float64)
        return zeros, zeros.copy()
    floors = reference * floor_fraction
    fired = (pos >= floors) & (pos > 0)
    return fired.sum(axis=0) / n_pos, floors


#: Bin width of the shadow-distribution histogram: 0.05 over [0, 1], 21
#: bins, lower edge inclusive. Deliberately a width the frozen threshold
#: (0.70) and every rate a 10-prompt positive split can take (k/10) land
#: exactly ON an edge of, so "bins 14 and above" and "at or above 0.70" are
#: the same set of pairs -- see `shadow_histogram_bins` for the binary
#: floating-point care that requires, and the test that falsifies it.
SHADOW_HISTOGRAM_BIN_WIDTH = 0.05
SHADOW_HISTOGRAM_BINS = 21


def shadow_histogram_bins(rates: np.ndarray) -> np.ndarray:
    """Counts per fixed 0.05-wide bin, as a `[21]` integer array. Fixed bins,
    never data-derived ones: two runs' histograms have to be comparable
    without re-binning.

    THE EPSILON IS LOAD-BEARING, not defensive padding. 0.05 and 0.7 are
    both inexact in binary: `0.7 / 0.05 == 13.999999999999998`, so a plain
    truncation files a fire rate of exactly 0.70 -- the frozen threshold
    itself -- into the 0.65 bin, and the histogram then disagrees with the
    `>= fire_rate_min` count computed beside it. Every rate a 10-prompt
    split can take (k/10) sits exactly on a 0.05 edge, so this is the
    common case here, not an edge case. Nudging by 1e-9 before the floor
    restores lower-edge-inclusive semantics; it can only move a value that
    is within 1e-9 of an edge, and only up to the bin that edge opens."""
    idx = np.clip(
        np.floor(np.asarray(rates, dtype=np.float64) / SHADOW_HISTOGRAM_BIN_WIDTH + 1e-9).astype(np.int64),
        0, SHADOW_HISTOGRAM_BINS - 1,
    )
    return np.bincount(idx, minlength=SHADOW_HISTOGRAM_BINS)


def concept_locale_texts(
    artifact: FrozenPromptArtifact, *, concept_id: str, locale: str
) -> tuple[list[str], list[str], dict[str, list[str]]]:
    """The three text blocks one (concept, locale) cell is made of, read
    ONCE: `(unrelated_texts, near_miss_texts, positive_texts_by_family)`.

    Single source of the split/family selection for both the per-feature
    gate path and the full-space selector, so the two can never drift into
    scoring different text sets. Raises for a missing split rather than
    returning an empty list -- an empty control set is an artifact
    integrity failure, not a zero-information cell."""
    unrelated_texts = [r["text"] for r in rows_for_concept(artifact.rows, concept_id=concept_id, locale=locale, split="unrelated")]
    if not unrelated_texts:
        raise ValueError(f"no 'unrelated' rows found for concept_id={concept_id!r} locale={locale!r}")
    near_miss_texts = [r["text"] for r in rows_for_concept(artifact.rows, concept_id=concept_id, locale=locale, split="near_miss")]
    if not near_miss_texts:
        raise ValueError(f"no 'near_miss' rows found for concept_id={concept_id!r} locale={locale!r}")
    families = sorted({
        r["family"] for r in artifact.rows
        if r["concept_id"] == concept_id and r["locale"] == locale and r["split"] == "positive"
    })
    if not families:
        raise ValueError(f"no positive-split families found for concept_id={concept_id!r} locale={locale!r}")
    positives_by_family = {
        family: [
            r["text"] for r in rows_for_concept(artifact.rows, concept_id=concept_id, locale=locale, split="positive", family=family)
        ]
        for family in families
    }
    return unrelated_texts, near_miss_texts, positives_by_family


def compute_gate_a_and_b_from_scores(
    *, concept_id: str, locale: str, feature_index: int,
    positive_scores_by_family: dict[str, Sequence[float]], negative_scores: Sequence[float],
    auroc_min: float, floor_fraction: float, fire_rate_min: float,
    corpus_max_by_feature: Sequence[float] | Mapping[int, float] | None = None,
) -> list[GateABResult]:
    """G-A and G-B, per family, from ALREADY-EXTRACTED per-prompt score
    vectors -- no backend, no feature index lookup, no forward pass.

    C2 (2026-08-15): this is where the gate arithmetic actually lives now.
    `compute_gate_a_and_b_per_family` below is a thin wrapper that turns
    (backend, feature_index) into these vectors. The arithmetic is
    UNCHANGED and deliberately so: the same `_auroc_from_scores`, the same
    pooled negative set, the same `compute_gate_b_fire_rate`, in the same
    family order. Any difference in an emitted number between this and the
    pre-C2 path is a refactor defect, not an improvement.

    SHADOW G-B (2026-08-15): `corpus_max_by_feature`, when supplied, adds
    the shadow fields (`fire_rate_corpus_max` and friends) to every emitted
    record. IT CHANGES NO VERDICT AND NO EXISTING FIELD: `gate_b_passed`
    below is `fire_rate >= fire_rate_min` on the frozen within-cell
    statistic whether the shadow reference is supplied or not, and the
    tests assert that the two call shapes emit identical
    `gate_a_passed`/`gate_b_passed`/`separation_auroc`/`fire_rate`. Omit it
    and the shadow fields stay at their `not_computed` defaults."""
    reference: float | None = None
    results = []
    for family in sorted(positive_scores_by_family):
        positive_scores = list(positive_scores_by_family[family])

        auroc = _auroc_from_scores(positive_scores, list(negative_scores))
        gate_a_passed = auroc >= auroc_min

        fire_rate, floor = compute_gate_b_fire_rate(positive_scores, floor_fraction=floor_fraction)
        # THE VERDICT, AND THE ONLY PLACE IT IS DECIDED: the frozen
        # within-cell statistic, compared against the frozen threshold. The
        # shadow value computed below is not in this expression and must
        # never be put into it without re-deriving `G_B_fire_rate_min`.
        gate_b_passed = fire_rate >= fire_rate_min

        shadow_rate = shadow_floor = None
        shadow_degenerate = False
        shadow_source = "not_computed"
        if corpus_max_by_feature is not None:
            reference = float(corpus_max_by_feature[feature_index])
            shadow_rate, shadow_floor, shadow_degenerate = compute_shadow_fire_rate_corpus_max(
                positive_scores, floor_fraction=floor_fraction, corpus_max=reference
            )
            shadow_source = f"frozen_artifact:{SHADOW_G_B_REFERENCE_SPLIT}:max_over_all_locales"

        results.append(
            GateABResult(
                concept_id=concept_id, locale=locale, family=family, feature_index=feature_index,
                separation_auroc=auroc, gate_a_passed=gate_a_passed,
                fire_rate=fire_rate, activation_floor_fraction=floor_fraction, gate_b_passed=gate_b_passed,
                # C4: the floor is no longer discarded into a `_floor` throwaway.
                activation_floor=floor,
                observed_max=(max(positive_scores) if positive_scores else 0.0),
                n_positives=len(positive_scores),
                # Shadow block. `fire_rate_within_cell` is deliberately the
                # SAME value as `fire_rate` -- an explicit name for the
                # statistic that gated, not a second measurement.
                fire_rate_within_cell=fire_rate,
                fire_rate_corpus_max=shadow_rate,
                corpus_max=reference,
                shadow_activation_floor=shadow_floor,
                shadow_reference_source=shadow_source,
                shadow_reference_degenerate=shadow_degenerate,
                verdict_computed_from=GATE_B_VERDICT_SOURCE,
                shadow_disclaimer=("" if corpus_max_by_feature is None else SHADOW_G_B_DISCLAIMER),
                anti_specific=bool(auroc < 0.5),
                anti_specific_note=(ANTI_SPECIFICITY_NOTE if auroc < 0.5 else ""),
            )
        )
    return results


def compute_gate_a_and_b_per_family(
    backend: Backend, artifact: FrozenPromptArtifact, *, concept_id: str, locale: str, feature_index: int,
    auroc_min: float | None = None, activation_floor_fraction: float | None = None, fire_rate_min: float | None = None,
    cache: FeatureMatrixCache | None = None,
    corpus_max_by_feature: Sequence[float] | Mapping[int, float] | None = None,
) -> list[GateABResult]:
    """G-A (separation AUROC, positive vs. POOLED controls: near_miss +
    unrelated, within the same locale/family) and G-B (activation floor /
    fire rate) computed INDEPENDENTLY per paraphrase family, never pooled
    ACROSS families -- per this artifact's own README ("pooling [families]
    would hide a feature that fires on only one phrasing"). Thresholds
    default to the frozen artifact's own `metadata.json["thresholds"]`
    (never invented by this file) but may be overridden explicitly by a
    caller who has a reason to.

    P0 FINAL DELTA correction (PROVENANCE, RETAINED): G-A's negative/
    control set is the POOL of `near_miss` + `unrelated`; it was
    `unrelated` alone before that correction. G-C
    (`compute_gate_c_per_family` below) remains the SEPARATE, near_miss-
    ONLY specificity test. The reason recorded at the time was that G-A
    asks "does this feature separate the concept from background text in
    general, including its closest foils" while G-C asks "does it
    separate from just its closest foils" -- "different denominators,
    different questions, BOTH REQUIRED".

    C5 CORRECTION (2026-08-15) -- THE "BOTH REQUIRED" HALF OF THAT CLAIM
    IS FALSE, AS AN ACCEPTANCE CLAIM. The two questions do differ, but
    G-C cannot reject anything G-A accepted, so it adds no acceptance
    power. AUROC against a pooled control set built from two EQUAL-SIZED
    subsets is identically the arithmetic mean of the two component
    AUROCs, and the frozen artifact has exactly 15 `near_miss` and 15
    `unrelated` rows per (concept, locale). Therefore

        separation_auroc == (near_miss_auroc + unrelated_auroc) / 2

    identically -- not approximately, and not as a property of any
    particular sample. Since `unrelated_auroc <= 1`, G-A's frozen
    threshold of 0.90 forces `near_miss_auroc >= 2 * 0.90 - 1 == 0.80`,
    which already clears G-C's frozen 0.75. VERIFIED: 0 of run 413287's
    1080 recorded cells had G-A pass while G-C failed, and the identity
    itself is falsified over random inputs by `verify_gate_fixes.py c5`.

    G-C IS STILL COMPUTED AND STILL RECORDED, deliberately: under C2 it
    costs nothing (the scores are already in the cache), the record must
    stay complete, and the subsumption is a consequence of the CURRENT
    equal-sized splits and the CURRENT thresholds -- change either and it
    stops holding. `gate_c_subsumption_note` re-derives it from the
    artifact actually loaded, per concept and locale, rather than
    asserting it from here; it is emitted machine-readably on every
    verdict so a downstream reader is never left to infer it.

    This corrects the DOCSTRING only. G-A's negative set is separately
    referred for ratification and is NOT changed here.

    `unrelated` is the shared_substrate split (identical across all 14
    concepts by design) -- `rows_for_concept` is called once per family
    below but always returns the SAME `unrelated` rows regardless of
    `concept_id`, which is correct, not a bug (see that function's
    docstring). `near_miss` is concept-specific (each concept has its own
    near-miss foils), same as `compute_gate_c_per_family` reads it.

    C2 (2026-08-15): the per-text encode is now done once and reused. Pass
    a shared `FeatureMatrixCache` to get that reuse across candidate
    features (and, for the shared_substrate `unrelated` split, across
    concepts); omitting it keeps the old behaviour of encoding this call's
    own texts, which is correct but pays the forward passes again. The
    gate arithmetic itself moved verbatim into
    `compute_gate_a_and_b_from_scores` -- nothing about WHAT is measured
    changed here."""
    thresholds = artifact.metadata["thresholds"]
    auroc_min = thresholds["G_A_separation_auroc_min"] if auroc_min is None else auroc_min
    floor_fraction = thresholds["G_B_activation_floor_fraction_of_observed_max"] if activation_floor_fraction is None else activation_floor_fraction
    fire_rate_min = thresholds["G_B_fire_rate_min"] if fire_rate_min is None else fire_rate_min

    cache = FeatureMatrixCache() if cache is None else cache
    unrelated_texts, near_miss_texts, positives_by_family = concept_locale_texts(
        artifact, concept_id=concept_id, locale=locale
    )

    unrelated_scores = cache.feature_scores(backend, unrelated_texts, feature_index)
    near_miss_scores = cache.feature_scores(backend, near_miss_texts, feature_index)

    # POOLED control set for G-A only -- G-C (compute_gate_c_per_family)
    # separately computes its own positive-vs-near_miss-ONLY AUROC. Order
    # is unrelated-then-near_miss, unchanged from the pre-C2 path.
    negative_scores = [*unrelated_scores, *near_miss_scores]

    return compute_gate_a_and_b_from_scores(
        concept_id=concept_id, locale=locale, feature_index=feature_index,
        positive_scores_by_family={
            family: cache.feature_scores(backend, texts, feature_index)
            for family, texts in positives_by_family.items()
        },
        negative_scores=negative_scores,
        auroc_min=auroc_min, floor_fraction=floor_fraction, fire_rate_min=fire_rate_min,
        # Shadow reference, recorded on the emitted records and consulted by
        # nothing (see `SHADOW_G_B_DISCLAIMER`). Passing None simply omits
        # the shadow fields; it cannot change a verdict either way.
        corpus_max_by_feature=corpus_max_by_feature,
    )


@dataclass(frozen=True)
class GateCResult:
    concept_id: str
    locale: str
    family: str
    feature_index: int
    near_miss_auroc: float
    gate_c_passed: bool


def gate_c_subsumption_note(
    artifact: FrozenPromptArtifact, *, concept_id: str,
    locales: tuple[str, ...] = FROZEN_PROMPT_SET_LOCALES,
) -> dict:
    """C5 (2026-08-15): the machine-readable record that, under THIS
    artifact's split sizes and THESE frozen thresholds, G-C cannot reject
    anything G-A accepted.

    AUROC against a pooled control set of two EQUAL-SIZED subsets is
    identically the mean of the two component AUROCs. With 15 `near_miss`
    and 15 `unrelated` rows per (concept, locale), `separation_auroc ==
    (near_miss_auroc + unrelated_auroc) / 2`, so `separation_auroc >=
    G_A_min` forces `near_miss_auroc >= 2 * G_A_min - 1` (because
    `unrelated_auroc <= 1`). At the frozen values that floor is 0.80,
    above G-C's frozen 0.75.

    Re-derived from the artifact actually loaded, per locale, rather than
    asserted: if a future artifact carries unequal control splits, or a
    future threshold moves, `holds` comes back False and G-C regains
    independent acceptance power. This is a REPORT, never a control flow
    input -- G-C is computed and recorded either way, and nothing in this
    file skips it."""
    thresholds = artifact.metadata["thresholds"]
    g_a_min = thresholds["G_A_separation_auroc_min"]
    g_c_min = thresholds["G_C_specificity_auroc_vs_near_miss_min"]

    per_locale: dict[str, dict] = {}
    for locale in locales:
        unrelated_texts, near_miss_texts, _positives = concept_locale_texts(
            artifact, concept_id=concept_id, locale=locale
        )
        equal_sized = len(unrelated_texts) == len(near_miss_texts)
        implied_floor = 2.0 * g_a_min - 1.0 if equal_sized else None
        per_locale[locale] = {
            "n_unrelated": len(unrelated_texts),
            "n_near_miss": len(near_miss_texts),
            "control_sets_equal_sized": equal_sized,
            "implied_near_miss_auroc_floor_given_gate_a_pass": implied_floor,
            "gate_c_subsumed_by_gate_a": bool(equal_sized and implied_floor >= g_c_min),
        }

    return {
        "corrected_claim": (
            "G-A and G-C ask different questions, but G-C cannot REJECT anything G-A accepted under "
            "this artifact's equal-sized control splits and these frozen thresholds; the docstring's "
            "'both required' was false as an acceptance claim."
        ),
        "identity": "separation_auroc == (near_miss_auroc + unrelated_auroc) / 2 when |near_miss| == |unrelated|",
        "g_a_separation_auroc_min": g_a_min,
        "g_c_specificity_auroc_vs_near_miss_min": g_c_min,
        "holds": all(v["gate_c_subsumed_by_gate_a"] for v in per_locale.values()),
        "per_locale": per_locale,
        "measured_evidence": (
            "0 of run 413287's 1080 recorded cells had G-A pass while G-C failed; the identity is "
            "falsified over random inputs by scripts/final_pairing/verify_gate_fixes.py c5."
        ),
        "gate_c_still_computed_and_recorded": True,
        "gate_a_negative_set_change": "NOT made here -- referred for ratification",
    }


def compute_gate_c_from_scores(
    *, concept_id: str, locale: str, feature_index: int,
    positive_scores_by_family: dict[str, Sequence[float]], near_miss_scores: Sequence[float],
    auroc_min: float,
) -> list[GateCResult]:
    """G-C, per family, from already-extracted score vectors. Same C2 split
    as G-A/G-B above: the arithmetic lives here, the wrapper below only
    turns (backend, feature_index) into vectors."""
    return [
        GateCResult(
            concept_id=concept_id, locale=locale, family=family, feature_index=feature_index,
            near_miss_auroc=(auroc := _auroc_from_scores(list(positive_scores_by_family[family]), list(near_miss_scores))),
            gate_c_passed=auroc >= auroc_min,
        )
        for family in sorted(positive_scores_by_family)
    ]


def compute_gate_c_per_family(
    backend: Backend, artifact: FrozenPromptArtifact, *, concept_id: str, locale: str, feature_index: int,
    auroc_min: float | None = None, cache: FeatureMatrixCache | None = None,
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
    rows per concept_id here.

    C2 (2026-08-15): shares `cache` with G-A/G-B, so the near_miss and
    positive texts this gate needs are encoded once per (concept, locale)
    for the whole run rather than once per gate per candidate feature."""
    thresholds = artifact.metadata["thresholds"]
    auroc_min = thresholds["G_C_specificity_auroc_vs_near_miss_min"] if auroc_min is None else auroc_min

    cache = FeatureMatrixCache() if cache is None else cache
    _unrelated_texts, near_miss_texts, positives_by_family = concept_locale_texts(
        artifact, concept_id=concept_id, locale=locale
    )

    return compute_gate_c_from_scores(
        concept_id=concept_id, locale=locale, feature_index=feature_index,
        positive_scores_by_family={
            family: cache.feature_scores(backend, texts, feature_index)
            for family, texts in positives_by_family.items()
        },
        near_miss_scores=cache.feature_scores(backend, near_miss_texts, feature_index),
        auroc_min=auroc_min,
    )


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


_QWEN_REPO_L0_SUFFIX_RE = re.compile(r"L0_(\d+)$")


def assert_qwen_configuration_self_consistent(configuration: MatchedConfiguration) -> None:
    """Two runtime cross-checks of `qwen_config_identity.json`'s own
    recorded constants -- run at every real Qwen load, never merely
    trusted because the constants were transcribed carefully:

    1. k must equal the `L0_<N>` suffix of the configuration's OWN SAE
       repository id (`qwen_config_identity.json`'s own validation rule:
       "k must equal the L0_N value in the repository identifier;
       disagreement is a hard stop").
    2. `qwen_depth_fraction` must equal `qwen_layer / expected_num_layers`
       (64), recomputed here rather than merely read off the stored
       constant ("depth_fraction is recomputed as layer / 64 at load and
       asserted equal to the recorded value")."""
    match = _QWEN_REPO_L0_SUFFIX_RE.search(configuration.qwen_sae_repo_id)
    if match is None:
        raise targets.TargetIdentityMismatch(
            f"configuration {configuration.name!r}'s SAE repository id "
            f"{configuration.qwen_sae_repo_id!r} does not end in an L0_<N> suffix -- cannot "
            f"cross-check k against it."
        )
    repo_k = int(match.group(1))
    if repo_k != configuration.qwen_sparsity:
        raise targets.TargetIdentityMismatch(
            f"configuration {configuration.name!r}: k={configuration.qwen_sparsity} disagrees with "
            f"the L0_{repo_k} suffix of its own SAE repository id {configuration.qwen_sae_repo_id!r}."
        )
    computed_depth_fraction = configuration.qwen_layer / targets.QWEN_3_5_27B_TARGET.expected_num_layers
    if abs(computed_depth_fraction - configuration.qwen_depth_fraction) > 1e-9:
        raise targets.TargetIdentityMismatch(
            f"configuration {configuration.name!r}: recomputed depth_fraction "
            f"{configuration.qwen_layer}/{targets.QWEN_3_5_27B_TARGET.expected_num_layers}="
            f"{computed_depth_fraction} disagrees with the recorded qwen_depth_fraction="
            f"{configuration.qwen_depth_fraction}."
        )


def _qwen_scientific_target(*, configuration: MatchedConfiguration) -> targets.TargetPairing:
    """A LOCAL variant of the ratified Qwen target for scientific discovery,
    built via `dataclasses.replace` rather than editing
    `final_pairing_targets.QWEN_3_5_27B_TARGET` in place -- CONFIGURATION-
    SPECIFIC (P0 STOP-LINE correction, 2026-08-13), not merely k-specific:
    `sae_repo_id`, `expected_k`, and `expected_layer` are ALL drawn from
    `configuration` (`qwen_config_identity.json`'s per-configuration
    repository/layer/k, never a caller-supplied override combined freely
    with a mismatched family). Every OTHER field (hidden dim, hook-name
    convention, format) stays exactly the ratified base value."""
    import dataclasses as _dc

    return _dc.replace(
        targets.QWEN_3_5_27B_TARGET,
        sae_repo_id=configuration.qwen_sae_repo_id,
        expected_k=configuration.qwen_sparsity,
        expected_layer=configuration.qwen_layer,
    )


def qwen_manifest_identity(
    configuration: MatchedConfiguration, *, layer_file_name: str,
) -> dict[str, str]:
    """Return the Qwen identity vocabulary accepted by the bundle consumer.

    Qwen Scope is loaded directly from a ``layerN.sae.pt`` file rather than
    through an sae_lens release map.  The bundle still requires the same three
    namespace fields on every model.  For Qwen, the repository itself is the
    release namespace, the frozen ``params_file`` is the loader key, and the
    scientific id uses the already-established consumer convention
    ``resid_post/layer_N_width_80k_l0_K``.  Every component is derived from the
    configuration-specific frozen identity; caller text is never accepted.
    """
    expected_file = f"layer{configuration.qwen_layer}.sae.pt"
    if layer_file_name != expected_file:
        raise targets.TargetIdentityMismatch(
            f"Qwen manifest loader identity requires {expected_file!r} for "
            f"configuration {configuration.name!r}, got {layer_file_name!r}"
        )
    scientific_sae_id = (
        f"resid_post/layer_{configuration.qwen_layer}_width_80k_"
        f"l0_{configuration.qwen_sparsity}"
    )
    return {
        "release": configuration.qwen_sae_repo_id,
        "loader_sae_id": expected_file,
        "sae_id": scientific_sae_id,
        "scientific_sae_id": scientific_sae_id,
    }


def load_qwen_scientific_target(
    model_path: str | Path, sae_layer_file_path: str | Path, *, layer: int, sae_family: str, k: int,
    device: str = "cuda", dtype: str = "bfloat16",
    expected_model_revision: str | None = None, expected_sae_revision: str | None = None,
):
    """Duplicates `final_pairing_harness.load_qwen_target`'s body (per this
    project's own Ground Rule 2: duplicate rather than cross-import/modify
    a frozen, already-accepted file) with one difference: `target` is a
    locally-built scientific variant (see `_qwen_scientific_target`) rather
    than the module-level mechanical `QWEN_3_5_27B_TARGET`.
    `sae_family` is recorded in provenance as its own field, never folded
    into `k` or `layer` -- SAE family, transformer layer, and sparsity (k)
    stay three distinct fields throughout.

    P0 STOP-LINE correction (2026-08-13), "reject crossed family/
    configuration paths": `sae_family` resolves to EXACTLY ONE of
    `PRIMARY_CONFIGURATION`/`BACKUP_CONFIGURATION`
    (`QWEN_CONFIGURATION_BY_SAE_FAMILY`) and the caller's OWN `layer`/`k`
    are asserted to agree with that configuration's ratified values before
    anything loads -- a caller can no longer combine e.g.
    `sae_family="L0_100"` (PRIMARY) with `layer=32`/`k=50` (BACKUP's own
    values). `expected_sae_revision`, if supplied, must likewise agree
    with the configuration's frozen, pinned `qwen_sae_revision`; if
    omitted, that pinned value is used directly (Qwen's identity is
    PINNED_LOCAL_ONLY per `qwen_config_identity.json`, unlike Gemma's
    shared-revision, caller-supplied convention). The loaded `layerN.sae.pt`
    file's ACTUAL SHA-256 is measured and asserted against the
    configuration's frozen `qwen_params_expected_sha256`
    (`assert_qwen_params_sha256_matches`) before generation is possible."""
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

    configuration = QWEN_CONFIGURATION_BY_SAE_FAMILY[sae_family]
    assert_qwen_configuration_self_consistent(configuration)
    if layer != configuration.qwen_layer:
        raise targets.TargetIdentityMismatch(
            f"--qwen-layer {layer} does not match configuration {configuration.name!r}'s ratified "
            f"layer {configuration.qwen_layer} for --qwen-sae-family {sae_family!r} -- refusing to "
            f"load a crossed configuration/family combination."
        )
    if k != configuration.qwen_sparsity:
        raise targets.TargetIdentityMismatch(
            f"--qwen-sparsity {k} does not match configuration {configuration.name!r}'s ratified "
            f"k={configuration.qwen_sparsity} for --qwen-sae-family {sae_family!r} -- refusing to "
            f"load a crossed configuration/family combination."
        )
    if expected_sae_revision is not None and expected_sae_revision != configuration.qwen_sae_revision:
        raise targets.TargetIdentityMismatch(
            f"--expected-sae-revision {expected_sae_revision!r} disagrees with configuration "
            f"{configuration.name!r}'s frozen, pinned revision {configuration.qwen_sae_revision!r} "
            f"(qwen_config_identity.json) -- refusing to proceed with an unpinned or altered revision."
        )
    resolved_expected_sae_revision = expected_sae_revision or configuration.qwen_sae_revision

    target = _qwen_scientific_target(configuration=configuration)
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
        sae_layer_file_path.parent, target, which="sae", expected_revision=resolved_expected_sae_revision
    )
    measured_params_sha256 = assert_qwen_params_sha256_matches(
        sae_layer_file_path, expected_sha256=configuration.qwen_params_expected_sha256,
    )
    manifest_identity = qwen_manifest_identity(
        configuration, layer_file_name=sae_layer_file_path.name,
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

    # Symmetric with the Gemma lane. This arm already moved its model to the
    # device and job 415590 proved it works, so this asserts a property that
    # currently holds rather than fixing a defect -- which is the point: the
    # two lanes are now checked by the SAME gate, so a future divergence
    # between them is caught on whichever arm regresses, not only on Gemma.
    device_placement = assert_load_devices_agree(device=device, model=hf_model, sae=sae)

    provenance = {
        "target": f"{target.name}-scientific",
        "device_placement": {"requested": device, **device_placement},
        "model": {
            "repository": target.model_repo_id,
            "local_path": str(model_path),
            "revision": model_identity["revision"],
            "revision_verification": model_identity["verification"],
            "actual_class": type(hf_model).__name__,
        },
        "sae": {
            "repository": target.sae_repo_id,
            **manifest_identity,
            "sae_family": sae_family,
            "configuration": configuration.name,
            "local_path": str(sae_layer_file_path),
            "revision": sae_identity["revision"],
            "revision_verification": sae_identity["verification"],
            "resolved_files": [str(sae_layer_file_path)],
            "actual_class": type(sae).__name__,
            "format": target.sae_format,
            "d_in": sae.d_in,
            "d_sae": sae.d_sae,
            "sparsity_k": sae.k,
            # MEASURED from the actual layerN.sae.pt bytes on disk
            # (assert_qwen_params_sha256_matches), already asserted equal to
            # the frozen qwen_config_identity.json expectation above --
            # never the expected constant copied in without hashing the file.
            "params_sha256": measured_params_sha256,
            # QwenScopeSAE.from_state_dict (final_pairing_harness.py, frozen)
            # explicitly casts every tensor (.to(dtype=torch.float32, ...))
            # at load -- SAE parameters are float32 while the model runs in
            # its own dtype; recorded here, not merely performed silently.
            "dtype_cast": "float32 (explicit, at load, via QwenScopeSAE.from_state_dict)",
            # weights_only=True is on this load path (final_pairing_harness.
            # QwenScopeSAE.from_layer_file -> torch.load(..., weights_only=
            # True)) -- the .sae.pt files are PyTorch pickles, not
            # safetensors; the hash check above proves which file this is,
            # weights_only=True is the separate, independent control that
            # loading it cannot execute arbitrary code.
            "torch_load_weights_only": True,
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


def resolve_module_device(module):
    """The device an object's own weights actually live on, or `None` if it
    holds no tensors at all.

    The SINGLE SOURCE OF TRUTH for "where does a forward through this
    object run". Reading it off the object removes the need for any caller
    to hold a second, independently-maintained opinion -- which is exactly
    what failed in job 415590.

    Handles BOTH shapes this codebase loads, deliberately: `nn.Module`
    (HookedTransformer, the raw Gemma `AutoModel`, sae_lens `SAE`) via
    `parameters()`/`buffers()`, and PLAIN OBJECTS holding tensor attributes
    (`final_pairing_harness.QwenScopeSAE` is not an `nn.Module` -- it is a
    plain class with `W_enc`/`b_enc`/`W_dec`/`b_dec`) via an attribute
    scan. A resolver that only understood `nn.Module` would return `None`
    for the Qwen SAE and silently assert nothing about it, which is the
    failure mode this whole change exists to remove."""
    import torch

    tensors = []
    if hasattr(module, "parameters") and callable(getattr(module, "parameters", None)):
        try:
            tensors = list(module.parameters()) + list(module.buffers())
        except (TypeError, AttributeError):
            tensors = []
    if not tensors:
        tensors = [v for v in vars(module).values() if isinstance(v, torch.Tensor)]
    for tensor in tensors:
        # The tensor's device VERBATIM. Do not synthesise an index: `cpu` has
        # none, and `torch.device("cpu", 0)` stringifies as "cpu:0", which
        # compares unequal to "cpu" and would make this gate refuse a
        # correctly-placed CPU run. Index normalisation belongs to
        # `_normalise_device`, which applies it only where it is meaningful.
        return tensor.device
    return None


def _normalise_device(device) -> object:
    """`cuda` and `cuda:0` name the same device; `torch.device` does not
    treat them as equal. Normalises an index-less CUDA device to the
    process's current one so a comparison cannot fail on spelling."""
    import torch

    resolved = torch.device(device)
    if resolved.type == "cuda" and resolved.index is None:
        index = torch.cuda.current_device() if torch.cuda.is_available() else 0
        resolved = torch.device("cuda", index)
    return resolved


class BackendDeviceMismatch(RuntimeError):
    """Raised when a loaded object is not on the device the run was told to
    use. Deliberately its own type: this is neither an identity mismatch
    nor a science failure, and conflating it with `TargetIdentityMismatch`
    would file a placement bug under a heading that gates on scientific
    identity."""


def assert_load_devices_agree(*, device: str, **objects) -> dict[str, str]:
    """FAIL-FAST DEVICE GATE, run after load and BEFORE the first forward.

    JOB 415590 (2026-08-15) is what this exists for. Gemma's raw
    `AutoModel` was never moved to the run's device while the preflight's
    input_ids were, so `torch.embedding` got an index on `cuda:0` and a
    weight on `cpu`, one minute into a six-hour allocation, with the whole
    two-lane job exiting 1. The forward that crashed was the FIRST forward
    in the process: there was nothing to catch it earlier, and nothing
    reported the placement that caused it.

    Every named object must have its parameters on `device`. Returns the
    measured placement per object so it can be recorded in provenance --
    a device that is asserted but never reported is a device nobody can
    audit after the fact. Objects with no parameters are reported as
    `"no-parameters"` and are not asserted, because there is nothing to
    misplace.

    NOT the primary defence. Placement is made structurally impossible
    first (`resolve_module_device`, used to put a forward's inputs on the
    module's own device); this gate is the backstop that turns a
    late-and-obscure crash into an immediate, named refusal."""
    expected = _normalise_device(device)
    measured: dict[str, str] = {}
    wrong: list[str] = []
    for name, obj in objects.items():
        actual = resolve_module_device(obj)
        if actual is None:
            measured[name] = "no-parameters"
            continue
        measured[name] = str(actual)
        if _normalise_device(actual) != expected:
            wrong.append(f"{name} on {actual}")
    if wrong:
        raise BackendDeviceMismatch(
            f"loaded object(s) are not on the requested device {expected}: {', '.join(sorted(wrong))} "
            f"-- refusing to run a forward pass that would fail on a device mismatch partway into the "
            f"allocation. Measured placement: {measured}"
        )
    return measured


@dataclass(frozen=True)
class GemmaRawHfHookPreflightResult:
    resolved_module_name: str
    layer_index_asserted: int
    captured_last_dim: int
    passed: bool
    ran_on_device: str = "unrecorded"


def run_gemma_raw_hf_hook_preflight(hf_model, tokens, *, layer: int, expected_hidden_dim: int) -> GemmaRawHfHookPreflightResult:
    """A real, tiny forward pass on the RAW HF model (never through
    TransformerLens), with a real `register_forward_hook` on the module
    `resolve_gemma_text_decoder_layer_dynamically` independently resolved
    -- proves that module's own output last dimension is
    `expected_hidden_dim` (3840 for Gemma-3-12B's text decoder),
    independent of anything TransformerLens's own hook system reports.

    THE INPUT DEVICE IS DERIVED FROM `hf_model`, NEVER PASSED IN (fix for
    job 415590, 2026-08-15). This function previously consumed whatever
    device the caller had already put `tokens` on, so correctness required
    the caller to hold a SECOND opinion about where the model lived and
    for the two opinions to agree. They did not: the tokens were moved to
    the run's device and the model never was, and `torch.embedding` raised
    with an index on `cuda:0` and a weight on `cpu`. Taking the device off
    the model's own parameters makes that disagreement UNREPRESENTABLE --
    there is only one opinion now, and it belongs to the object doing the
    forward. This mirrors the HookedTransformer arm, which never had the
    bug because `model.to_tokens` derives the device the same way."""
    name, module = resolve_gemma_text_decoder_layer_dynamically(hf_model, layer=layer)
    captured_shapes: list[tuple[int, ...]] = []

    def _hook(_module, _inputs, output):
        hidden = output[0] if isinstance(output, tuple) else output
        captured_shapes.append(tuple(hidden.shape))
        return output

    model_device = resolve_module_device(hf_model)
    if model_device is not None:
        tokens = tokens.to(model_device)

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
        ran_on_device=str(model_device) if model_device is not None else "no-parameters",
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
    # JOB 415590 (2026-08-15): the raw `AutoModel` above is a SECOND model
    # object, and `HookedTransformer.from_pretrained(device=...)` moves only
    # the HookedTransformer it builds -- it copies weights out of `hf_model`
    # and leaves that object exactly where `from_pretrained` put it, on CPU.
    # `hf_model` is then forwarded directly by the raw-HF hook preflight
    # below, which is how a `cuda:0` index met a `cpu` weight. Moved here,
    # mirroring the Qwen path's `hf_model.to(device)`, which is why that lane
    # never had this defect.
    #
    # AFTER the HookedTransformer is built, deliberately: moving it before
    # would put two full copies of a 12B model on the GPU simultaneously
    # during conversion, changing a peak-memory profile that job 415590
    # proved fits. This ordering leaves that profile untouched. `hf_model` is
    # not returned, so its memory becomes reusable when this function
    # returns.
    hf_model.to(device)

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

    configuration = next((c for c in MATCHED_CONFIGURATIONS.values() if c.gemma_layer == layer), None)
    if configuration is None:
        raise AssertionError("unreachable: layer already validated against _GEMMA_SCIENTIFIC_LAYERS")
    measured_params_sha256 = assert_params_sha256_matches(
        resolved_sae_files, expected_sha256=configuration.gemma_params_expected_sha256,
    )

    sae = sae.to(dtype=torch.float32)
    sae.eval()

    hook_name = sae.cfg.metadata.hook_name
    targets.validate_hook_identity(hook_name, target)
    targets.validate_hidden_dims(model.cfg.d_model, sae.cfg.d_in, target)
    # BEFORE THE FIRST FORWARD. Every forward in this function is below this
    # line; job 415590 died on the first one it reached.
    device_placement = assert_load_devices_agree(
        device=device, hooked_transformer=model, raw_hf_model=hf_model, sae=sae,
    )
    hook_preflight = run_gemma_hook_preflight(
        model, sae, hook_name, expected_hidden_dim=target.expected_hidden_dim, expected_layer=layer,
    )
    # No `.to(device)` here on purpose: the preflight derives the device from
    # `hf_model` itself, so the caller cannot put these on the wrong one.
    raw_hf_tokens = tokenizer("preflight probe", return_tensors="pt")["input_ids"]
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
            # MEASURED from the actual params.safetensors bytes on disk (assert_params_sha256_matches),
            # already asserted equal to the frozen identity artifact's expected value above -- never the
            # expected constant copied in without hashing the file.
            "params_sha256": measured_params_sha256,
            # sae.cfg carries loader defaults (e.g. context_size, dataset_path) that describe
            # HOW the SAE was trained upstream, not a measurement this pipeline made -- never
            # copied into provenance as if they were this run's own scientific claims.
        },
        "hook_preflight": asdict(hook_preflight),
        "raw_hf_hook_preflight": asdict(raw_hf_preflight),
        # MEASURED off each loaded object's own parameters, not the value
        # requested. A device that is asserted but never reported is one
        # nobody can audit after the run.
        "device_placement": {"requested": device, **device_placement},
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


def encode_texts(backend: Backend, texts: list[str]) -> tuple[np.ndarray, np.ndarray]:
    """ONE forward pass + ONE SAE encode per text, returning BOTH per-text
    summaries this file ever needs from a text:

    - `residuals`  `[n_texts, d_model]`, MEAN-pooled over positions (the
      specificity probe's logistic-regression input, and only that);
    - `features`   `[n_texts, d_sae]`, MAX over positions (the per-prompt
      SAE-feature score every gate reads).

    This is exactly `_pooled_residual_and_feature`'s body with the
    single-feature column selection (`feats[:, feature_index].max()`)
    replaced by the whole-row max (`feats.max(dim=0).values`) -- the same
    inner loop `_qwen_max_activation_per_feature` runs, WITHOUT its
    `np.maximum` fold across texts, so the per-text rows survive instead
    of being collapsed. The arithmetic per (text, feature) is unchanged:
    `feats.max(dim=0).values[j]` and `feats[:, j].max()` are the same
    reduction over the same tensor, so a score read out of this matrix is
    bit-identical to the score the per-feature path computed.

    Why this exists (C2, 2026-08-15): every G-A/G-B/G-C cell previously
    re-ran the model over the SAME texts for EVERY candidate feature. One
    concept cost 20 candidates x 2 locales x (15 unrelated + 15 near_miss
    + 3 x 10 positive, twice over because G-A and G-C each re-encoded
    near_miss and positives) forward passes to extract 20 columns of a
    matrix that one pass over 60 texts produces in full. The encode is the
    expensive step and it does not depend on the feature index.

    Dtype note: `features` is float32 because the SAE's own encode output
    is float32; widening a float32 to float64 is exact, so
    `features[:, j].astype(np.float64)` reproduces the Python floats the
    old `float(feats[:, j].max().item())` path produced, exactly."""
    import torch

    if not texts:
        return (
            np.zeros((0, backend.d_model), dtype=np.float32),
            np.zeros((0, backend.d_sae), dtype=np.float32),
        )

    residuals: list[np.ndarray] = []
    feature_rows: list[np.ndarray] = []

    if backend.pairing == targets.GEMMA_3_12B_IT_TARGET.name:
        model, sae = backend.model_obj, backend.sae
        with torch.no_grad():
            for text in texts:
                tokens = model.to_tokens(text)
                _, activation_cache = model.run_with_cache(tokens, names_filter=backend.hook_name)
                x = activation_cache[backend.hook_name].to(torch.float32)[0]  # [seq, d_model]
                feats = sae.encode(x)  # [seq, d_sae]
                residuals.append(x.mean(dim=0).cpu().numpy())
                feature_rows.append(feats.max(dim=0).values.cpu().numpy())
        return np.stack(residuals), np.stack(feature_rows)

    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(backend.provenance["model"]["local_path"])
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
                x = captured[-1].to(torch.float32)[0]  # [seq, d_model]
                feats = backend.sae.encode(x)  # [seq, d_sae]
                residuals.append(x.mean(dim=0).cpu().numpy())
                feature_rows.append(feats.max(dim=0).values.cpu().numpy())
    finally:
        handle.remove()
    return np.stack(residuals), np.stack(feature_rows)


def feature_matrix_for_texts(backend: Backend, texts: list[str]) -> np.ndarray:
    """`[n_texts, d_sae]` max-over-positions SAE activations -- the feature
    half of `encode_texts`. One row per text, one column per SAE feature."""
    return encode_texts(backend, texts)[1]


class FeatureMatrixCache:
    """Encode-once-per-text cache, keyed by the EXACT text tuple.

    Scope discipline: an instance is created per grid run and passed
    explicitly. There is deliberately NO module-level default instance --
    a cache that outlives the backend that filled it would silently serve
    one model's activations for another model's question, which is the
    one failure mode a cache in this position can cause. The backend's
    identity is part of the key for the same reason.

    `pin()` marks an entry as never-evicted. `unrelated` is the
    shared_substrate split: the SAME 15 texts per locale for all 14
    concepts (see `rows_for_concept`), so it is encoded once for the whole
    run and pinned, while per-concept entries are dropped between concepts
    by `evict_unpinned()`.

    Memory: one (concept, locale) entry is 60 texts x d_sae x 4B == 19.2
    MB at d_sae 80,000, plus a negligible 60 x d_model residual block."""

    def __init__(self) -> None:
        self._entries: dict[tuple, tuple[np.ndarray, np.ndarray]] = {}
        self._pinned: set[tuple] = set()
        self.encode_calls = 0
        self.texts_encoded = 0
        self.hits = 0

    @staticmethod
    def _key(backend: Backend, texts: Sequence[str]) -> tuple:
        return (id(backend), backend.pairing, backend.checkpoint_hash, tuple(texts))

    def encode(self, backend: Backend, texts: Sequence[str]) -> tuple[np.ndarray, np.ndarray]:
        """Returns `(residuals, features)` for `texts`, encoding only on a
        miss. The returned arrays are the cache's own -- callers must not
        mutate them (no caller in this file does; every read is a column
        selection or a row slice)."""
        key = self._key(backend, texts)
        entry = self._entries.get(key)
        if entry is None:
            self.encode_calls += 1
            self.texts_encoded += len(texts)
            entry = encode_texts(backend, list(texts))
            self._entries[key] = entry
        else:
            self.hits += 1
        return entry

    def features(self, backend: Backend, texts: Sequence[str]) -> np.ndarray:
        return self.encode(backend, texts)[1]

    def feature_scores(self, backend: Backend, texts: Sequence[str], feature_index: int) -> list[float]:
        """One feature's per-text score vector, as the list of Python floats
        `_auroc_from_scores`/`compute_gate_b_fire_rate` have always been
        given. float32 -> float64 is exact, so these are the same values
        the per-feature forward-pass path produced."""
        return self.features(backend, texts)[:, feature_index].astype(np.float64).tolist()

    def pin(self, backend: Backend, texts: Sequence[str]) -> None:
        self.encode(backend, texts)
        self._pinned.add(self._key(backend, texts))

    def evict_unpinned(self) -> None:
        for key in [k for k in self._entries if k not in self._pinned]:
            del self._entries[key]

    def __len__(self) -> int:
        return len(self._entries)


def exclude_mechanical_only(pairing: str, ranked: list[RankedFeature]) -> list[RankedFeature]:
    """Drops the pairing's mechanical-acceptance-only placeholder feature
    from a ranked shortlist, if activation ranking happened to surface it
    organically. This is a filter, not an error -- unlike a manually
    supplied candidate (`reject_mechanical_only_feature`, which raises),
    naturally ranking highly is not itself a misuse."""
    mechanical_id = _MECHANICAL_ONLY_FEATURE_IDS[pairing]
    return [r for r in ranked if r.feature_index != mechanical_id]


def rank_features_by_activation(backend: Backend, texts: list[str], *, top_n: int) -> list[RankedFeature]:
    """Pure max-activation ranking over `texts`. NO control text is ever
    shown to this function, so it is a MAGNITUDE LEADERBOARD, not a
    concept filter, and it must not be read as one -- see
    `rank_candidates_for_concept` for what that cost run 413287. Since
    C3 the 14-concept grid does not use it; the single-prompt-set
    (`--mode full`) stage still does."""
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
    """SUPERSEDED BY C3 (2026-08-15) AND NO LONGER USED BY THE GRID. Kept
    only so the shortlist run 413287 actually used can be reproduced for
    audit; `evaluate_concept_on_pairing` now scores the whole feature
    space (`score_full_feature_space`) and never calls this.

    Ranks candidates using EVERY locale's positive-split text pooled
    together, by pure max activation, with NO control text ever shown to
    the ranker -- which is why it was superseded. MEASURED on run 413287's
    9 completed concepts:

    - the 180 shortlist slots held only 74 DISTINCT features;
    - feature 37587 was rank 0 for 8 of the 9 concepts, and 6 features
      appeared in all 9 shortlists (30% of the entire candidate budget);
    - mean pairwise Jaccard overlap between concepts' shortlists 0.391
      against a chance value of 0.005 -- roughly 2200x chance;
    - Spearman(rank index, min separation_auroc) = +0.4501: quality ROSE
      with rank index, and 6 of the run's 8 G-A passes sat in the last
      quarter of the shortlist.

    A magnitude leaderboard is not a concept filter: it is anti-correlated
    with the acceptance criterion it was feeding."""
    texts: list[str] = []
    for locale in FROZEN_PROMPT_SET_LOCALES:
        texts += [r["text"] for r in rows_for_concept(artifact.rows, concept_id=concept_id, locale=locale, split="positive")]
    ranked = rank_features_by_activation(backend, texts, top_n=shortlist_size)
    return exclude_mechanical_only(backend.pairing, ranked)


#: Carried on EVERY verdict this file emits, and on grid.json. Both of the
#: gates' denominators are under referral and neither has been corrected:
#: G-B scores firing against a WITHIN-CELL reference scale derived from the
#: very prompts it judges (see `compute_gate_b_fire_rate`), and G-A's
#: negative set is separately referred for ratification. Correcting either
#: requires re-deriving its frozen threshold, which is a protocol change
#: nobody has made. C1 removes one fully degenerate case from G-B; it does
#: not make the denominator sound. Scoring the whole feature space (C3)
#: therefore produces MORE results through the same defective denominator,
#: not better ones -- a "k of d_sae" count from this grid is an engineering
#: measurement of the pipeline, NOT a discovery result, and must not be
#: reported as one until both denominators are ratified.
GATE_DENOMINATOR_CAVEAT = (
    "engineering-preview-only: every G-B figure in this grid is computed against a within-cell "
    "reference scale derived from the same prompts it judges, and G-A's negative set is under "
    "referral. Neither denominator has been corrected (doing so requires re-deriving its frozen "
    "threshold, a protocol change not made). No count of surviving features from this grid is a "
    "discovery result."
)

#: How many features the whole-space scan records in full detail beyond the
#: ones that pass G-A. Bounds the size of a per-concept record; it is a
#: REPORTING budget only and has no effect on which features are scored or
#: on any verdict (contrast the pre-C3 `shortlist_size`, which decided
#: which features were ever measured at all).
DEFAULT_REPORT_TOP_N = 25


@dataclass(frozen=True)
class CandidateGabcEvaluation:
    feature_index: int
    gate_a_b_results: list[dict]
    gate_c_results: list[dict]
    survives_gabc: bool


class SurvivorRecordingMismatch(RuntimeError):
    """Raised when the recorded survivor list disagrees with the per-candidate
    `survives_gabc` flags it is supposed to summarise. Its own type: this is
    a REPORTING defect, not a gate result, and filing it under a
    science-identity error would misattribute it."""


def assert_recorded_survivors_match_the_flag(evaluated, recorded_indices) -> None:
    """FALSIFIER: the recorded survivor set must equal the set of candidates
    whose `survives_gabc` is true, in the same order.

    THE EQUALITY THAT FAILED SILENTLY (2026-08-15). On the grid at
    49f8a73, `survives_gabc` was `Counter({False: 347, True: 3})` while only
    two concepts reported a survivor: `formal_register` had both 38600 and
    51952 clearing all three gates in all six cells and the scalar field
    could hold one of them. Nothing in the record contradicted anything
    else, because the only statement of the survivor set WAS the scalar.
    This function makes that disagreement expressible, and therefore
    catchable.

    Compares ORDER as well as membership: `surviving_feature_index` is
    documented as `surviving_feature_indices[0]`, which is only true if the
    list preserves the candidates' best-first order.

    Verdicts are never consulted here beyond the flag already computed --
    this checks the REPORT against the flags, and changes no gate, no
    threshold and no verdict."""
    expected = [c.feature_index for c in evaluated if c.survives_gabc]
    actual = list(recorded_indices)
    if expected != actual:
        raise SurvivorRecordingMismatch(
            f"recorded survivors {actual} do not match the candidates whose survives_gabc is true "
            f"{expected} -- {len(expected)} candidate(s) survived and {len(actual)} were recorded. "
            f"A survivor set that disagrees with the per-candidate flags is a lossy report, and a "
            f"lossy report is indistinguishable from a complete one to every downstream reader."
        )


@dataclass(frozen=True)
class ConceptPairingVerdict:
    concept_id: str
    pairing: str
    status: Literal["pass", "fail", "error"]
    #: THE FIRST SURVIVOR ONLY, in the recorded best-first candidate order.
    #: PRESERVED WITH ITS ORIGINAL SEMANTICS, NOT REPURPOSED (2026-08-15):
    #: every existing consumer reads it expecting exactly this, and silently
    #: widening a scalar into "some survivor" would change what stored
    #: records mean without changing their bytes. Read
    #: `surviving_feature_indices` for the DELIVERABLE; this stays as the
    #: deterministic single entry point the one-allocation CLI is driven
    #: off, and it is always `surviving_feature_indices[0]` when a survivor
    #: exists.
    surviving_feature_index: int | None
    candidates_evaluated: list[dict]  # asdict(CandidateGabcEvaluation), best-first by min-across-cells separation_auroc
    error: str | None
    # C3/C5 additions (2026-08-15). All defaulted, so a verdict written by
    # an earlier revision still round-trips through
    # `ConceptPairingVerdict(**...)` in `run_concept_grid`/
    # `read_grid_result` -- a stale record is corrected, never dropped.
    features_scored: int = 0
    selection_mode: str = "activation_shortlist"
    gate_a_passing_feature_count: int = 0
    gate_denominator_caveat: str = ""
    gate_c_subsumption: dict | None = None
    #: SHADOW G-B evidence for this concept: the distribution of the
    #: corpus-max-referenced fire rate over every (feature, cell) pair
    #: scored, beside the frozen within-cell one on the same bins.
    #: Recorded; never read by this file's control flow.
    shadow_gate_b_summary: dict | None = None
    #: EVERY feature clearing G-A, G-B and G-C in all six cells, in the same
    #: best-first order as `candidates_evaluated`. THE DELIVERABLE IS A
    #: GROUP, NOT A FEATURE: amplification and group ablation both act on a
    #: SET, and a scalar field is structurally incapable of expressing that.
    #:
    #: MEASURED CONSEQUENCE (grid at 49f8a73, job 415590's Qwen lane):
    #: `survives_gabc` was true for THREE candidates while only two concepts
    #: reported a survivor -- `formal_register` had BOTH 38600 and 51952
    #: clearing all three gates in all six cells, and the scalar recorded
    #: 38600 and silently dropped 51952. The verdicts were never wrong; the
    #: REPORTING was lossy, and a lossy report looks exactly like a complete
    #: one.
    #:
    #: Defaulted to `None` rather than `[]` so a verdict written before this
    #: field existed is DISTINGUISHABLE from one that genuinely found no
    #: survivors. An empty list asserts "none survived"; `None` asserts
    #: "this record predates the field and does not say", and conflating
    #: them is how a stale record acquires a false claim.
    surviving_feature_indices: list[int] | None = None
    #: PER-CELL full-space separation AUROC (architect RULING_8 T1). The
    #: candidate list this verdict carries is ranked by the MINIMUM across
    #: six cells, which cannot represent a feature that is excellent in one
    #: cell and weak in another -- so a statement like "no feature passed
    #: this cell" was only ever true of the recorded candidates, never of
    #: the space. This field is what makes the difference checkable: per
    #: cell, the full-space ceiling and how many of all `features_scored`
    #: clear G-A. Recorded; read by no verdict and no selection.
    per_cell_full_space_auroc: dict | None = None


@dataclass(frozen=True)
class FullSpaceScan:
    """Per-feature G-A/G-B/G-C SCREEN values for a whole (concept, pairing),
    minimised across all 6 (locale, family) cells -- the exact aggregation
    the frozen survival conjunction applies (ALL families, BOTH locales),
    so `min_separation_auroc >= 0.90` is the same statement as "G-A passed
    in every cell". Arrays are `[d_sae]`, indexed by feature index."""

    concept_id: str
    locales: tuple[str, ...]
    families_by_locale: dict[str, list[str]]
    min_separation_auroc: np.ndarray
    min_fire_rate: np.ndarray
    min_near_miss_auroc: np.ndarray
    cells_scored: int
    #: SHADOW G-B distribution over EVERY (feature, cell) pair this scan
    #: touched -- `d_sae x cells_scored` values, not a per-feature minimum
    #: and not a survivor count. None when no shadow reference was supplied.
    #: Consulted by nothing; `select_candidates_from_scan` does not read it.
    shadow_fire_rate_summary: dict | None = None
    #: PER-CELL full-space separation AUROC summary (architect RULING_8 T1,
    #: 2026-08-15). The `min_*` arrays above collapse six cells into one
    #: number per feature, and a MINIMUM cannot represent a feature that is
    #: excellent in one cell and weak in another -- so the grid was
    #: STRUCTURALLY BLIND to single-cell champions, and every candidate list
    #: it produced was ranked by a statistic anti-correlated with
    #: complementarity. This retains what the minimum destroys. None when
    #: not computed. Recorded; read by no verdict and by no selection.
    per_cell_separation_auroc: dict | None = None


#: How many per-cell full-space leaders `summarise_per_cell_auroc` keeps.
#: See its docstring for why this is a TRUNCATION and what it costs.
PER_CELL_FULL_SPACE_TOP_K = 25


def summarise_per_cell_auroc(
    per_cell: dict[str, np.ndarray], *, auroc_min: float, top_k: int = PER_CELL_FULL_SPACE_TOP_K,
) -> dict:
    """The per-cell full-space separation AUROC, retained instead of thrown
    away (architect RULING_8 T1, 2026-08-15).

    WHAT WAS BROKEN. `score_full_feature_space` computes
    `rank_auroc_matrix` for all `d_sae` features in every cell and then
    folds each vector straight into a running MINIMUM. The per-cell matrix
    was discarded and never written, so a feature scoring 1.00 in `en/f1`
    and 0.40 in `fr/f2` recorded a min of 0.40, fell below the candidate
    cut, and was never seen. The grid was structurally incapable of seeing
    a SINGLE-CELL CHAMPION, and `select_candidates_from_scan` ranks by that
    same minimum -- a criterion anti-correlated with complementarity by
    construction.

    WHAT THIS DECIDES. Per cell: the ceiling (`max_separation_auroc`) and
    how many features clear G-A (`features_at_or_above_gate_a`). If a
    concept's failing cell contains a full-space feature at or above the
    G-A bar, that cell's failure is a SELECTION artifact. If the cell's
    ceiling sits below the bar, the failure is a property of the encoding
    at this layer under this SAE. Those are opposite conclusions and
    nothing in the previous record could tell them apart.

    THIS IS A TRUNCATION AND HERE IS EXACTLY WHAT IT COSTS. The full matrix
    is `d_sae x cells` -- 81920 x 6 = 491520 float64, 3.9 MB in memory per
    concept and roughly 10 MB as JSON, so ~140 MB of grid.json across 14
    concepts. That is refused. RETAINED per cell: the max, the G-A-clearing
    count, and the `top_k` leading features with their AUROCs (~1.5 KB per
    cell, ~130 KB per grid). DISCARDED: the AUROC of every feature outside
    each cell's top `top_k`. Stated rather than done silently, because a
    silent truncation here would recreate the exact defect being fixed --
    the previous code also "summarised", to one number, and said nothing.

    Peak memory is UNCHANGED: the per-cell vector was already materialised
    to compute the minimum; this summarises it before it goes out of scope
    rather than allocating anything new. Zero new prompts, zero new forward
    passes -- purely a recording change, and no threshold, gate or verdict
    reads any of it.

    `auroc_min` is READ from the frozen thresholds by the caller and used
    only to COUNT. Nothing here moves it."""
    summary: dict = {
        "gate_a_auroc_min_used_for_the_count": float(auroc_min),
        "top_k_retained_per_cell": int(top_k),
        "truncation": (
            "per cell: max, the count at or above the G-A bar, and the top_k leading features. The "
            "AUROC of every feature outside a cell's top_k is NOT retained -- the full d_sae x cells "
            "matrix is ~3.9 MB per concept in memory and ~10 MB as JSON, which is refused. This is a "
            "stated truncation, not a silent one."
        ),
        "cells": {},
    }
    for cell, values in per_cell.items():
        values = np.asarray(values, dtype=np.float64)
        order = np.argsort(-values, kind="stable")[:top_k]
        summary["cells"][cell] = {
            "max_separation_auroc": float(values.max()) if values.size else None,
            "features_at_or_above_gate_a": int((values >= auroc_min).sum()),
            "features_scored": int(values.size),
            "top_features": [
                {"feature_index": int(i), "separation_auroc": float(values[i])} for i in order
            ],
        }
    return summary


def summarise_shadow_distribution(
    within_cell_counts: np.ndarray, corpus_max_counts: np.ndarray, *,
    within_cell_values: np.ndarray, corpus_max_values: np.ndarray,
    degenerate_reference_features: int, dead_cell_pairs: int, cells: int, d_sae: int,
    fire_rate_min: float, floor_fraction: float,
) -> dict:
    """The run-level shadow evidence, in the shape someone re-deriving the
    0.70 bar actually needs: two histograms on the SAME fixed bins (the
    frozen within-cell statistic and the shadow corpus-max one), quantiles
    of each, and how many (feature, cell) pairs each statistic puts at or
    above the CURRENT bar.

    THAT LAST NUMBER IS NOT A SURVIVOR COUNT AND MUST NOT BE READ AS ONE.
    It counts (feature, cell) pairs of ONE gate's statistic. It is not
    conjoined with G-A or G-C, not minimised across cells, and not filtered
    to any candidate set; a feature contributes up to `cells` separate
    counts. It exists to describe where the mass of each distribution sits
    relative to 0.70, which is exactly the question a re-derivation asks."""
    def _q(values: np.ndarray) -> dict:
        if values.size == 0:
            return {}
        qs = np.quantile(values, [0.0, 0.05, 0.25, 0.5, 0.75, 0.95, 1.0])
        return {
            "min": float(qs[0]), "p05": float(qs[1]), "p25": float(qs[2]), "median": float(qs[3]),
            "p75": float(qs[4]), "p95": float(qs[5]), "max": float(qs[6]), "mean": float(values.mean()),
        }

    total_pairs = int(d_sae * cells)
    return {
        "disclaimer": SHADOW_G_B_DISCLAIMER,
        "not_a_survivor_count": (
            "Every count below is over (feature, cell) PAIRS of a single gate's statistic -- never "
            "conjoined with G-A/G-C, never minimised across cells, never filtered to a candidate "
            "set. It is a distribution, not a discovery result."
        ),
        "reference_split": SHADOW_G_B_REFERENCE_SPLIT,
        "floor_fraction": float(floor_fraction),
        "current_fire_rate_min": float(fire_rate_min),
        "cells": int(cells),
        "d_sae": int(d_sae),
        "feature_cell_pairs": total_pairs,
        "histogram_bin_width": SHADOW_HISTOGRAM_BIN_WIDTH,
        "histogram_bin_lower_edges": [round(i * SHADOW_HISTOGRAM_BIN_WIDTH, 4) for i in range(SHADOW_HISTOGRAM_BINS)],
        "fire_rate_within_cell": {
            "histogram": [int(x) for x in within_cell_counts],
            "quantiles": _q(within_cell_values),
            "pairs_at_or_above_current_min": int((within_cell_values >= fire_rate_min).sum()),
        },
        "fire_rate_corpus_max": {
            "histogram": [int(x) for x in corpus_max_counts],
            "quantiles": _q(corpus_max_values),
            "pairs_at_or_above_current_min": int((corpus_max_values >= fire_rate_min).sum()),
        },
        "degenerate_reference_features": int(degenerate_reference_features),
        "degenerate_reference_note": (
            "features whose corpus_max is 0.0 -- completely silent on the background split, so the "
            "shadow floor collapses to 0.0 and the shadow rate degenerates to 'fraction of positives "
            "with any activation at all'. Counted here so they can be excluded from a re-derivation."
        ),
        "dead_cell_pairs": int(dead_cell_pairs),
        "dead_cell_note": (
            "(feature, cell) pairs whose positive scores are all exactly 0.0 -- silent on the CONCEPT "
            "prompts, which says nothing about the controls. Both statistics score these 0.0 (the C1 "
            "guard); before C1 the within-cell statistic scored them 1.0, which is what produced run "
            "413287's 295 phantom G-B passes (measured on GPU by job 414676, 2026-08-15; the "
            "record-only 0.5/0.5/1.0 signature saw 182 of them and was blind to the other 113, which "
            "were active on a control set)."
        ),
    }


def score_full_feature_space(
    backend: Backend, artifact: FrozenPromptArtifact, *, concept_id: str,
    locales: tuple[str, ...] = FROZEN_PROMPT_SET_LOCALES, cache: FeatureMatrixCache | None = None,
    floor_fraction: float | None = None,
    corpus_max_by_feature: np.ndarray | None = None, fire_rate_min: float | None = None,
    auroc_min: float | None = None,
) -> FullSpaceScan:
    """Computes G-A, G-B and G-C for EVERY one of `backend.d_sae` features,
    in every (locale, family) cell, from the cached activation matrices --
    zero additional forward passes beyond C2's one-encode-per-text.

    Cost: 6 cells x one `scipy.stats.rankdata` over a `[40, d_sae]` array
    (10 positives + 15 near_miss + 15 unrelated), i.e. seconds of CPU per
    concept. The pre-C3 alternative was to measure 20 magnitude-ranked
    features and never look at the other d_sae - 20.

    This is a SCREEN, deliberately: the values it returns are used to
    choose which features to verify, and every recorded verdict is then
    re-computed through the frozen scalar primitives
    (`_auroc_from_scores`, `compute_gate_b_fire_rate`). Nothing this
    function returns is ever written out as a gate result.

    IT DOES NOT MAKE THE GATES SOUND. G-B here is `fire_rate_matrix`,
    which is the same within-cell circular denominator as everywhere else
    (see `GATE_DENOMINATOR_CAVEAT`). Scoring d_sae features through a
    defective denominator produces d_sae defective results faster.

    SHADOW G-B (2026-08-15): when `corpus_max_by_feature` is supplied, the
    same cells are ALSO scored against the protocol's background reference
    and the full `d_sae x cells` distribution of both statistics is
    summarised into `shadow_fire_rate_summary`. That summary feeds the
    record and nothing else -- `select_candidates_from_scan` reads
    `min_separation_auroc` only, and no verdict reads any of it."""
    thresholds = artifact.metadata["thresholds"]
    floor_fraction = thresholds["G_B_activation_floor_fraction_of_observed_max"] if floor_fraction is None else floor_fraction
    fire_rate_min = thresholds["G_B_fire_rate_min"] if fire_rate_min is None else fire_rate_min
    # READ, never chosen: used only to COUNT how many features clear the
    # frozen G-A bar per cell. No threshold moves.
    auroc_min = thresholds["G_A_separation_auroc_min"] if auroc_min is None else auroc_min
    cache = FeatureMatrixCache() if cache is None else cache

    per_cell_sep: dict[str, np.ndarray] = {}
    min_sep = np.full(backend.d_sae, np.inf, dtype=np.float64)
    min_fire = np.full(backend.d_sae, np.inf, dtype=np.float64)
    min_near = np.full(backend.d_sae, np.inf, dtype=np.float64)
    families_by_locale: dict[str, list[str]] = {}
    cells = 0
    # Shadow accumulators: fixed-bin histograms plus the raw values, which
    # at d_sae x 6 stay small enough to quantile exactly rather than
    # estimate off the histogram.
    within_counts = np.zeros(SHADOW_HISTOGRAM_BINS, dtype=np.int64)
    shadow_counts = np.zeros(SHADOW_HISTOGRAM_BINS, dtype=np.int64)
    within_values: list[np.ndarray] = []
    shadow_values: list[np.ndarray] = []
    dead_cell_pairs = 0

    for locale in locales:
        unrelated_texts, near_miss_texts, positives_by_family = concept_locale_texts(
            artifact, concept_id=concept_id, locale=locale
        )
        families_by_locale[locale] = sorted(positives_by_family)
        unrelated = cache.features(backend, unrelated_texts).astype(np.float64)
        near_miss = cache.features(backend, near_miss_texts).astype(np.float64)
        # POOLED control set for G-A only, unrelated-then-near_miss --
        # identical construction to the per-feature path.
        negatives = np.concatenate([unrelated, near_miss], axis=0)

        for family in families_by_locale[locale]:
            positives = cache.features(backend, positives_by_family[family]).astype(np.float64)
            # RULING_8 T1: keep the per-cell vector long enough to summarise
            # it. It was previously consumed directly by `np.minimum` and
            # lost on the same line -- which is what made a single-cell
            # champion unrepresentable. Same array, same arithmetic, no
            # extra allocation: only its lifetime changes.
            cell_sep = rank_auroc_matrix(positives, negatives)
            per_cell_sep[f"{locale}/{family}"] = cell_sep
            min_sep = np.minimum(min_sep, cell_sep)
            cell_fire = fire_rate_matrix(positives, floor_fraction=floor_fraction)[0]
            min_fire = np.minimum(min_fire, cell_fire)
            min_near = np.minimum(min_near, rank_auroc_matrix(positives, near_miss))
            cells += 1

            if corpus_max_by_feature is not None:
                cell_shadow = shadow_fire_rate_matrix(
                    positives, floor_fraction=floor_fraction, corpus_max=corpus_max_by_feature
                )[0]
                within_counts += shadow_histogram_bins(cell_fire)
                shadow_counts += shadow_histogram_bins(cell_shadow)
                within_values.append(cell_fire)
                shadow_values.append(cell_shadow)
                dead_cell_pairs += int((positives.max(axis=0) <= 0).sum())

    shadow_summary = None
    if corpus_max_by_feature is not None:
        shadow_summary = summarise_shadow_distribution(
            within_counts, shadow_counts,
            within_cell_values=np.concatenate(within_values) if within_values else np.empty(0),
            corpus_max_values=np.concatenate(shadow_values) if shadow_values else np.empty(0),
            degenerate_reference_features=int((np.asarray(corpus_max_by_feature) <= 0).sum()),
            dead_cell_pairs=dead_cell_pairs, cells=cells, d_sae=int(backend.d_sae),
            fire_rate_min=fire_rate_min, floor_fraction=floor_fraction,
        )

    return FullSpaceScan(
        concept_id=concept_id, locales=tuple(locales), families_by_locale=families_by_locale,
        min_separation_auroc=min_sep, min_fire_rate=min_fire, min_near_miss_auroc=min_near,
        cells_scored=cells, shadow_fire_rate_summary=shadow_summary,
        per_cell_separation_auroc=summarise_per_cell_auroc(per_cell_sep, auroc_min=auroc_min),
    )


#: Slack applied to the SCREEN only, never to a recorded verdict. The
#: vectorised rank-based AUROC and sklearn's trapezoidal one agree to
#: floating-point noise, not necessarily bit-for-bit; screening at
#: `threshold - _SCREEN_EPSILON` and then DECIDING with the frozen scalar
#: primitive at the exact frozen threshold means a feature can never be
#: dropped by last-ulp disagreement, and can never be admitted by it
#: either. This widens what gets verified; it does not weaken any gate.
_SCREEN_EPSILON = 1e-9


def select_candidates_from_scan(
    scan: FullSpaceScan, *, pairing: str, auroc_min: float, report_top_n: int = DEFAULT_REPORT_TOP_N,
) -> list[RankedFeature]:
    """Which features the whole-space screen hands to exact verification,
    best-first by min-across-cells separation AUROC (ties broken by
    ascending feature index, so the order is deterministic).

    Two groups, unioned: EVERY feature whose screened G-A clears the
    frozen threshold in all six cells (this set is the answer to "which
    features pass G-A", and must never be truncated by a reporting
    budget), plus the next best `report_top_n` for context. The mechanical
    -acceptance placeholder is filtered out by `exclude_mechanical_only`,
    exactly as it was from the pre-C3 shortlist."""
    min_sep = scan.min_separation_auroc
    gate_a_screened = np.flatnonzero(min_sep >= auroc_min - _SCREEN_EPSILON)
    order = np.lexsort((np.arange(min_sep.size), -min_sep))
    selected: list[int] = list(dict.fromkeys([*gate_a_screened.tolist(), *order[:report_top_n].tolist()]))
    selected.sort(key=lambda i: (-min_sep[i], i))
    # `RankedFeature.activation_score` carries the SCREENED min-across-cells
    # separation AUROC here, not a raw activation magnitude -- the container
    # is reused so that `exclude_mechanical_only` (the frozen placeholder
    # filter) applies unchanged. Only `.feature_index` is ever recorded.
    ranked = [RankedFeature(feature_index=int(i), activation_score=float(min_sep[i])) for i in selected]
    return exclude_mechanical_only(pairing, ranked)


def pin_shared_substrate(
    cache: FeatureMatrixCache, backend: Backend, artifact: FrozenPromptArtifact, *,
    locales: tuple[str, ...] = FROZEN_PROMPT_SET_LOCALES,
) -> None:
    """Encodes the `unrelated` split ONCE for the whole run and pins it.

    `unrelated` is shared_substrate: the same 15 texts per locale for all
    14 concepts (`rows_for_concept`'s own docstring records this as a
    deliberate artifact invariant). Encoding it per concept would repeat
    the identical forward passes 14 times. Any concept_id selects the same
    rows, so the first one that HAS them is used and the result is keyed
    by the texts themselves, not by concept.

    Reads the `unrelated` split ONLY, and never raises. This is a warm-up,
    not a validation step: if some concept is missing a split, that must
    surface as an ERROR verdict for THAT concept (inside
    `evaluate_concept_on_pairing`'s own try/except, where an error is
    recorded rather than confused with a fail) and must never take the
    whole grid down from out here. `concept_locale_texts` is deliberately
    not used for that reason -- it validates all three splits, which is
    right for a gate and wrong for a cache warm-up."""
    for locale in locales:
        for concept_id in sorted({r["concept_id"] for r in artifact.rows}):
            unrelated_texts = [
                r["text"] for r in rows_for_concept(artifact.rows, concept_id=concept_id, locale=locale, split="unrelated")
            ]
            if unrelated_texts:
                cache.pin(backend, unrelated_texts)
                break


def evaluate_concept_on_pairing(
    backend: Backend, artifact: FrozenPromptArtifact, *, concept_id: str,
    report_top_n: int = DEFAULT_REPORT_TOP_N,
    locales: tuple[str, ...] = FROZEN_PROMPT_SET_LOCALES, cache: FeatureMatrixCache | None = None,
    shortlist_size: int | None = None,
    corpus_max_by_feature: np.ndarray | None = None,
) -> ConceptPairingVerdict:
    """One (concept, pairing) grid cell's full verdict.

    C3 (2026-08-15) -- WHAT CHANGED. The candidate set is no longer a
    20-feature magnitude shortlist chosen without ever showing the ranker
    a control text (see `rank_candidates_for_concept` for the measured
    reasons that was untenable). Every one of `backend.d_sae` features is
    screened in every cell (`score_full_feature_space`, zero extra forward
    passes on top of C2's cache), and the features that clear the screen
    -- plus `report_top_n` more for context -- are then measured through
    the UNCHANGED frozen primitives and recorded. The question the grid
    answers becomes "which features pass" instead of "did one of these 20
    happen to".

    WHAT DID NOT CHANGE, deliberately: the thresholds, the per-family
    scope, and the survival conjunction. `feature_survives_gabc` still
    requires ONE feature to pass G-A, G-B and G-C in ALL 3 families in
    BOTH locales. Nothing is pooled across families, no per-locale winner
    is accepted, and 5-of-6 is not a pass.

    `status='pass'` iff at least one feature survives that conjunction;
    `status='fail'` iff none of `backend.d_sae` did; `status='error'` iff
    evaluation itself raised -- an error must never be read as a fail,
    since a fail is a genuine negative result and an error is the absence
    of one. Candidates are recorded best-first by min-across-cells
    separation AUROC (ties by ascending feature index), so "the surviving
    feature" is deterministic rather than an artifact of iteration order.

    READ `GATE_DENOMINATOR_CAVEAT`, which every verdict carries. Scoring
    the whole feature space does not repair either gate's denominator; it
    produces more results through the same one. A count of survivors from
    this grid is an engineering measurement, not a discovery result.

    `shortlist_size` is accepted and ignored, for callers pinned to the
    pre-C3 keyword; it is recorded nowhere and selects nothing.

    `corpus_max_by_feature` is the SHADOW G-B reference scale
    (`shadow_corpus_max_per_feature`). Supplying it adds the shadow fields
    to every emitted G-B record and a run-level distribution to
    `shadow_gate_b_summary`; omitting it omits both. It cannot move a
    verdict in either direction -- `gate_b_passed`, `feature_survives_gabc`
    and `status` are computed from the frozen within-cell statistic in both
    cases, and the tests assert the two runs are verdict-identical."""
    del shortlist_size  # pre-C3 keyword; the shortlist no longer decides what is measured
    try:
        cache = FeatureMatrixCache() if cache is None else cache
        thresholds = artifact.metadata["thresholds"]
        scan = score_full_feature_space(
            backend, artifact, concept_id=concept_id, locales=locales, cache=cache,
            corpus_max_by_feature=corpus_max_by_feature,
        )
        candidates = select_candidates_from_scan(
            scan, pairing=backend.pairing,
            auroc_min=thresholds["G_A_separation_auroc_min"], report_top_n=report_top_n,
        )

        evaluated: list[CandidateGabcEvaluation] = []
        surviving_feature_index: int | None = None
        surviving_feature_indices: list[int] = []
        gate_a_passing = 0
        for candidate in candidates:
            gate_ab: list[GateABResult] = []
            gate_c: list[GateCResult] = []
            for locale in locales:
                gate_ab += compute_gate_a_and_b_per_family(
                    backend, artifact, concept_id=concept_id, locale=locale, feature_index=candidate.feature_index,
                    cache=cache, corpus_max_by_feature=corpus_max_by_feature,
                )
                gate_c += compute_gate_c_per_family(
                    backend, artifact, concept_id=concept_id, locale=locale, feature_index=candidate.feature_index,
                    cache=cache,
                )
            survives = feature_survives_gabc(gate_ab, gate_c)
            gate_a_passing += int(all(r.gate_a_passed for r in gate_ab))
            evaluated.append(
                CandidateGabcEvaluation(
                    feature_index=candidate.feature_index, gate_a_b_results=[asdict(r) for r in gate_ab],
                    gate_c_results=[asdict(r) for r in gate_c], survives_gabc=survives,
                )
            )
            # NOT short-circuited (the pre-C3 loop broke on the first
            # survivor): the full G-A-passing set is the auditable output,
            # and the recorded order already makes the winner deterministic.
            if survives:
                surviving_feature_indices.append(candidate.feature_index)
                if surviving_feature_index is None:
                    surviving_feature_index = candidate.feature_index
        # THE FALSIFIER FOR THE DEFECT ITSELF. Every candidate whose
        # `survives_gabc` is true must appear in the recorded survivor list.
        # This is precisely the equality that failed silently before the list
        # existed: three candidates survived and one concept's second
        # survivor was dropped, with nothing in the record disagreeing with
        # anything else. Raised, never warned -- a lossy record that reports
        # itself as complete is the failure mode.
        assert_recorded_survivors_match_the_flag(evaluated, surviving_feature_indices)
        status: Literal["pass", "fail"] = "pass" if surviving_feature_index is not None else "fail"
        return ConceptPairingVerdict(
            concept_id=concept_id, pairing=backend.pairing, status=status,
            surviving_feature_index=surviving_feature_index,
            surviving_feature_indices=surviving_feature_indices,
            candidates_evaluated=[asdict(e) for e in evaluated], error=None,
            features_scored=int(backend.d_sae),
            selection_mode="full_space_exhaustive",
            gate_a_passing_feature_count=gate_a_passing,
            gate_denominator_caveat=GATE_DENOMINATOR_CAVEAT,
            gate_c_subsumption=gate_c_subsumption_note(artifact, concept_id=concept_id, locales=locales),
            shadow_gate_b_summary=scan.shadow_fire_rate_summary,
            per_cell_full_space_auroc=scan.per_cell_separation_auroc,
        )
    except Exception as exc:  # an ERROR cell must record ANY failure, not a curated subset
        return ConceptPairingVerdict(
            concept_id=concept_id, pairing=backend.pairing, status="error",
            surviving_feature_index=None, surviving_feature_indices=[],
            candidates_evaluated=[], error=f"{type(exc).__name__}: {exc}",
            selection_mode="full_space_exhaustive", gate_denominator_caveat=GATE_DENOMINATOR_CAVEAT,
        )


def run_concept_grid(
    backend: Backend, artifact: FrozenPromptArtifact, *, report_top_n: int = DEFAULT_REPORT_TOP_N,
    concept_ids: list[str] | None = None, progress: ProgressLog | None = None,
    shortlist_size: int | None = None, record_shadow: bool = True,
) -> list[ConceptPairingVerdict]:
    """Evaluates every one of the frozen artifact's 14 concepts (or an
    explicit subset, for tests) on ONE already-loaded `backend`, resuming
    per-concept via `progress` exactly like every other stage in this
    file.

    C2 (2026-08-15): owns ONE `FeatureMatrixCache` for the whole grid. The
    shared_substrate `unrelated` split is encoded once and pinned; each
    concept's own texts are evicted when that concept is finished, so peak
    memory is one concept's two locales (2 x 60 x d_sae x 4B == 38 MB at
    d_sae 80,000) plus the pinned substrate, not the whole grid's.

    C3 (2026-08-15): `shortlist_size` no longer exists as a concept -- the
    whole feature space is scored. It is still accepted and ignored so a
    pinned caller does not break; `report_top_n` bounds how many extra
    features are RECORDED, never which are measured.

    SHADOW G-B (2026-08-15): the background reference scale is measured
    ONCE for the whole grid, immediately after the shared_substrate split
    is pinned -- it reads exactly those pinned texts, so it costs zero
    additional forward passes -- and is handed to every concept. It is
    recorded on every G-B record and summarised per concept; no verdict
    reads it (`SHADOW_G_B_DISCLAIMER`). `record_shadow` exists to turn it
    off for a caller that wants the pre-shadow record shape; the verdicts
    are identical either way."""
    del shortlist_size  # pre-C3 keyword; retained so an existing caller does not raise
    if concept_ids is None:
        concept_ids = sorted({r["concept_id"] for r in artifact.rows})
    cache = FeatureMatrixCache()
    substrate_pinned = False
    corpus_max_by_feature: np.ndarray | None = None
    verdicts: list[ConceptPairingVerdict] = []
    for concept_id in concept_ids:
        key = f"grid_{backend.pairing}_{concept_id}"
        if progress is not None and progress.is_done(key):
            verdicts.append(ConceptPairingVerdict(**progress.result(key)["verdict"]))
            continue
        if not substrate_pinned:
            # Deferred to the first concept actually evaluated: a fully
            # resumed run must not pay a forward pass it will not use.
            pin_shared_substrate(cache, backend, artifact)
            substrate_pinned = True
            if record_shadow:
                corpus_max_by_feature = shadow_corpus_max_per_feature(backend, artifact, cache=cache)
        verdict = evaluate_concept_on_pairing(
            backend, artifact, concept_id=concept_id, report_top_n=report_top_n, cache=cache,
            corpus_max_by_feature=corpus_max_by_feature,
        )
        verdicts.append(verdict)
        cache.evict_unpinned()
        if progress is not None:
            progress.record(key, {"verdict": asdict(verdict)})
    return verdicts


def aggregate_shadow_summaries(verdicts: list[ConceptPairingVerdict]) -> dict | None:
    """Sums the per-concept shadow histograms into ONE grid-level
    distribution -- the artefact a re-derivation of `G_B_fire_rate_min`
    reads. Returns None when no verdict carries a shadow summary.

    Histograms sum exactly (fixed bins, disjoint (feature, cell) pairs).
    Quantiles do NOT sum, so the grid-level ones are recomputed FROM the
    summed histogram and are therefore bin-resolution (0.05) accurate --
    labelled as such rather than presented as exact. The per-concept
    summaries keep their exact quantiles and are not replaced."""
    summaries = [v.shadow_gate_b_summary for v in verdicts if v.shadow_gate_b_summary is not None]
    if not summaries:
        return None

    def _sum(statistic: str, field: str) -> list[int]:
        return [int(sum(s[statistic][field][i] for s in summaries)) for i in range(SHADOW_HISTOGRAM_BINS)]

    def _quantiles_from_histogram(counts: list[int]) -> dict:
        total = sum(counts)
        if total == 0:
            return {}
        cumulative = np.cumsum(counts)
        edges = np.array([i * SHADOW_HISTOGRAM_BIN_WIDTH for i in range(SHADOW_HISTOGRAM_BINS)])
        out = {}
        for name, q in (("p05", 0.05), ("p25", 0.25), ("median", 0.5), ("p75", 0.75), ("p95", 0.95)):
            out[name] = float(edges[int(np.searchsorted(cumulative, q * total, side="left"))])
        return out

    within_hist = _sum("fire_rate_within_cell", "histogram")
    shadow_hist = _sum("fire_rate_corpus_max", "histogram")
    return {
        "disclaimer": SHADOW_G_B_DISCLAIMER,
        "not_a_survivor_count": summaries[0]["not_a_survivor_count"],
        "concepts_summarised": len(summaries),
        "reference_split": summaries[0]["reference_split"],
        "floor_fraction": summaries[0]["floor_fraction"],
        "current_fire_rate_min": summaries[0]["current_fire_rate_min"],
        "feature_cell_pairs": int(sum(s["feature_cell_pairs"] for s in summaries)),
        "histogram_bin_width": SHADOW_HISTOGRAM_BIN_WIDTH,
        "histogram_bin_lower_edges": summaries[0]["histogram_bin_lower_edges"],
        "fire_rate_within_cell": {
            "histogram": within_hist,
            "quantiles_from_histogram_bin_resolution": _quantiles_from_histogram(within_hist),
            "pairs_at_or_above_current_min": int(
                sum(s["fire_rate_within_cell"]["pairs_at_or_above_current_min"] for s in summaries)
            ),
        },
        "fire_rate_corpus_max": {
            "histogram": shadow_hist,
            "quantiles_from_histogram_bin_resolution": _quantiles_from_histogram(shadow_hist),
            "pairs_at_or_above_current_min": int(
                sum(s["fire_rate_corpus_max"]["pairs_at_or_above_current_min"] for s in summaries)
            ),
        },
        "dead_cell_pairs": int(sum(s["dead_cell_pairs"] for s in summaries)),
        "quantile_note": (
            "grid-level quantiles are read off the summed fixed-bin histogram, so they are accurate "
            "to the 0.05 bin width; the per-concept summaries carry exact quantiles."
        ),
    }


def write_grid_result(out_dir: str | Path, pairing: str, verdicts: list[ConceptPairingVerdict]) -> Path:
    """Writes `<out_dir>/grid.json` -- an EXACT, named path, never a
    location a caller has to glob for. `out_dir` is the SAME per-lane
    output directory the discovery run itself was given (never a shared
    parent directory that other, unrelated runs also write into)."""
    path = Path(out_dir) / "grid.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "pairing": pairing,
                # Grid-level, so a reader never has to open a verdict to
                # find them. Both are also carried per verdict.
                "gate_denominator_caveat": GATE_DENOMINATOR_CAVEAT,
                "gate_c_subsumption": next(
                    (v.gate_c_subsumption for v in verdicts if v.gate_c_subsumption is not None), None
                ),
                # Grid-level SHADOW G-B distribution. Measurement only; no
                # verdict in this file, or in any consumer of this file,
                # may be computed from it (`SHADOW_G_B_DISCLAIMER`).
                "shadow_gate_b_summary": aggregate_shadow_summaries(verdicts),
                "verdicts": [asdict(v) for v in verdicts],
            },
            indent=2,
        ),
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
# THE OWED MODEL-LEVEL REPLAY (2026-08-15).
#
# The C2 falsifier could not run its literal form: run 413287 preserved
# VERDICTS, not activations, and the dev box is CPU-only, so equivalence was
# proven against a deterministic surrogate with pre/post arms. That is sound
# structurally and is NOT a model-level replay. What follows makes the real
# replay executable on GPU: re-score exactly the preserved (concept,
# feature) population on the real backend and assert every preserved float
# comes back.
#
# It asserts on RAW FLOATS, never on booleans: C1 legitimately changes
# `gate_b_passed` on the degenerate cells, so a boolean comparison would
# fail for a reason that is a correction rather than a regression. The one
# float that is EXPECTED to differ -- `fire_rate` on a cell whose positives
# are all identically zero, 1.0 before the C1 guard and 0.0 after -- is
# asserted to differ on EXACTLY the expected number of cells and nowhere
# else. Anything outside that carve-out is a hard failure.
# ---------------------------------------------------------------------------


class ReplayMismatch(RuntimeError):
    """Raised when a model-level replay does not reproduce the preserved
    record. Deliberately an exception and not a returned flag: a replay that
    quietly warns is a replay nobody acts on."""


#: The number of (feature, cell) records in run 413287 whose positive scores
#: were all identically zero -- the degenerate cells C1 corrects from
#: `fire_rate 1.0` to `fire_rate 0.0`. MEASURED ON GPU by Tamia job 414676
#: (2026-08-15), `--mode replay` on real Qwen3.5-27B weights against run
#: 413287's preserved record, from `observed_max == 0.0` on the replayed
#: cell -- the direct quantity, not an inference. Asserted, never assumed:
#: if the real model returns a different number, either the guard or the
#: identification is wrong and the replay must fail rather than absorb it.
#:
#: CORRECTED 182 -> 295 (2026-08-15). This is an EXPECTATION MOVED TO MATCH
#: AN OBSERVATION, which is legitimate here only because the justification
#: is independent of the observation that failed. Two independent legs:
#:   (1) A PROOF FROM THE CODE. `compute_gate_b_fire_rate` takes
#:       `observed_max` over the POSITIVE scores ALONE, so "dead" means
#:       silent on the concept prompts and says NOTHING about the controls.
#:       `_preserved_dead_cell_signature` additionally demands AUROC 0.5
#:       against BOTH control sets, which holds only when the controls are
#:       silent too. The signature therefore sees only the DOUBLY-dead
#:       subset and is STRUCTURALLY BLIND to a cell that is silent on the
#:       concept and ACTIVE on the controls. 182 was never the degenerate
#:       population; it was the part of it the record could see.
#:   (2) A PREDICTION FIXED BEFORE THE COUNT WAS TAKEN. Post-ReLU scores
#:       are non-negative, so dead-on-positives FORCES `separation_auroc <=
#:       0.5 AND near_miss_auroc <= 0.5 AND fire_rate == 1.0`. That
#:       candidate set is a strict UPPER BOUND on the degenerate population
#:       and had to contain at least 295 cells or the explanation was
#:       refuted. Measured on the preserved record: 527, every one of which
#:       passed G-B. 182 <= 295 <= 527 holds; `verify_gate_fixes.py c1`
#:       re-derives both bounds from the record and fails if 295 leaves
#:       them.
#: No threshold, gate semantics or falsifier strictness changed with it.
REPLAY_EXPECTED_DEAD_CELLS = 295

#: The subset of `REPLAY_EXPECTED_DEAD_CELLS` that the preserved record can
#: identify ON ITS OWN, via `_preserved_dead_cell_signature`. PRESERVED, NOT
#: DELETED: 182 is the number every pre-414676 count, comment and report in
#: this codebase was computed from, it is still the exact figure
#: `verify_gate_fixes.py c1` measures (that check has no `observed_max` to
#: read), and it remains a correct LOWER BOUND on the degenerate population.
#: The replay asserts it exactly, alongside the 295, so that a change in
#: either number is visible instead of being absorbed by the other.
REPLAY_SIGNATURE_VISIBLE_DEAD_CELLS = 182

#: `REPLAY_EXPECTED_DEAD_CELLS - REPLAY_SIGNATURE_VISIBLE_DEAD_CELLS`: cells
#: silent on the concept prompts and ACTIVE on at least one control set, so
#: their AUROCs are not 0.5 and the record-only signature cannot see them.
#: Every one of them passed G-B with `fire_rate` 1.0 on a floor of zero.
#: Named rather than left implicit because this population is the entire
#: content of the correction.
REPLAY_SIGNATURE_BLIND_DEAD_CELLS = REPLAY_EXPECTED_DEAD_CELLS - REPLAY_SIGNATURE_VISIBLE_DEAD_CELLS

#: Every emitted float the replay compares. `fire_rate_within_cell` is
#: compared against the preserved record's `fire_rate` (the same statistic
#: under its explicit name); the shadow fields are RECORDED by the replay
#: and compared against nothing, because the preserved run has no shadow
#: value to compare to.
REPLAY_COMPARED_FIELDS = ("separation_auroc", "fire_rate_within_cell", "near_miss_auroc")

REPLAY_TOLERANCE = 1e-9


def load_preserved_grid_cells(progress_path: str | Path) -> tuple[dict, dict, dict[str, list[int]]]:
    """Flattens a preserved grid `progress.jsonl` into
    `(ab_by_key, c_by_key, feature_indices_by_concept)`, keyed by
    `(concept_id, locale, family, feature_index)`.

    Reads the EXACT named path (never globs), and preserves the file's own
    concept order and per-concept candidate order -- the replay must
    re-score exactly the population that was recorded, not a re-derived
    one."""
    path = Path(progress_path)
    if not path.is_file():
        raise FileNotFoundError(f"preserved progress log not found at the exact path {path}")
    ab: dict[tuple, dict] = {}
    c: dict[tuple, dict] = {}
    features_by_concept: dict[str, list[int]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        verdict = json.loads(line)["verdict"]
        concept_id = verdict["concept_id"]
        features_by_concept.setdefault(concept_id, [])
        for candidate in verdict["candidates_evaluated"]:
            features_by_concept[concept_id].append(candidate["feature_index"])
            for r in candidate["gate_a_b_results"]:
                ab[(r["concept_id"], r["locale"], r["family"], r["feature_index"])] = r
            for r in candidate["gate_c_results"]:
                c[(r["concept_id"], r["locale"], r["family"], r["feature_index"])] = r
    return ab, c, features_by_concept


def replay_preserved_cells(
    backend: Backend, artifact: FrozenPromptArtifact, *, features_by_concept: dict[str, list[int]],
    locales: tuple[str, ...] = FROZEN_PROMPT_SET_LOCALES, cache: FeatureMatrixCache | None = None,
    record_shadow: bool = True,
) -> tuple[dict, dict]:
    """Re-scores exactly `features_by_concept` on the REAL backend, through
    the same frozen primitives the grid uses, and returns
    `(ab_by_key, c_by_key)` in the same key shape as
    `load_preserved_grid_cells`.

    Nothing here selects features: the population comes from the preserved
    record. The full-space scan is deliberately NOT run -- C3 changed WHICH
    features are measured, and mixing that in would compare different
    populations and prove nothing about the measurement."""
    cache = FeatureMatrixCache() if cache is None else cache
    pin_shared_substrate(cache, backend, artifact)
    corpus_max_by_feature = (
        shadow_corpus_max_per_feature(backend, artifact, locales=locales, cache=cache) if record_shadow else None
    )

    ab: dict[tuple, dict] = {}
    c: dict[tuple, dict] = {}
    for concept_id, feature_indices in features_by_concept.items():
        for feature_index in feature_indices:
            for locale in locales:
                for r in compute_gate_a_and_b_per_family(
                    backend, artifact, concept_id=concept_id, locale=locale, feature_index=feature_index,
                    cache=cache, corpus_max_by_feature=corpus_max_by_feature,
                ):
                    ab[(r.concept_id, r.locale, r.family, r.feature_index)] = asdict(r)
                for r in compute_gate_c_per_family(
                    backend, artifact, concept_id=concept_id, locale=locale, feature_index=feature_index,
                    cache=cache,
                ):
                    c[(r.concept_id, r.locale, r.family, r.feature_index)] = asdict(r)
        cache.evict_unpinned()
    return ab, c


def _preserved_dead_cell_signature(ab_cell: dict, c_cell: dict) -> bool:
    """The record-only identification of a degenerate cell, reproduced from
    `verify_gate_fixes.check_c1` verbatim: AUROC is exactly 0.5 against BOTH
    control sets and `fire_rate` is exactly 1.0.

    SOUND BUT INCOMPLETE, AND THE INCOMPLETENESS IS STRUCTURAL (established
    2026-08-15, job 414676). A cell is degenerate when
    `compute_gate_b_fire_rate` sees `observed_max == 0.0`, and that max is
    taken over the POSITIVE scores ALONE -- being dead says nothing
    whatever about the controls. This signature additionally requires both
    AUROCs to be exactly 0.5, which post-ReLU happens only when the CONTROL
    scores are all zero too. It therefore selects the DOUBLY-dead subset
    and CANNOT see a feature that is silent on the concept prompts and
    active on the controls, of which the replay measured 113. Read it as a
    LOWER BOUND (`REPLAY_SIGNATURE_VISIBLE_DEAD_CELLS`), never as the
    population.

    The replay does not trust it in the direction it can be wrong: a cell
    carrying this signature whose replayed `observed_max` is NOT 0.0 is a
    hard failure, because that would falsify the 182 itself. The reverse --
    measured dead, signature absent -- is the expected blind spot above and
    is counted, not treated as a disagreement."""
    return ab_cell["separation_auroc"] == 0.5 and c_cell["near_miss_auroc"] == 0.5 and ab_cell["fire_rate"] == 1.0


def compare_replay_to_preserved(
    *, preserved_ab: dict, preserved_c: dict, replayed_ab: dict, replayed_c: dict,
    tolerance: float = REPLAY_TOLERANCE, expected_dead_cells: int = REPLAY_EXPECTED_DEAD_CELLS,
    expected_signature_visible_dead_cells: int | None = REPLAY_SIGNATURE_VISIBLE_DEAD_CELLS,
) -> dict:
    """Asserts the replay reproduces the preserved record. Returns a report
    dict on success; RAISES `ReplayMismatch` on any failure -- it never
    warns and never returns a soft verdict.

    What must match, to `tolerance` (1e-9), on every one of the preserved
    cells: `separation_auroc`, `near_miss_auroc`, and
    `fire_rate_within_cell` against the preserved `fire_rate`.

    The ONE licensed difference: on a cell whose replayed positives are all
    identically 0.0 (`observed_max == 0.0`), the preserved `fire_rate` is
    exactly 1.0 and the replayed `fire_rate_within_cell` is exactly 0.0 --
    the C1 correction. That is asserted, not tolerated: the preserved value
    must be exactly 1.0, the replayed exactly 0.0, and the count of such
    cells must equal `expected_dead_cells` EXACTLY. More or fewer is a
    failure.

    THE TWO DEAD-CELL POPULATIONS, WHICH ARE NOT THE SAME SET (corrected
    2026-08-15 from job 414676). `expected_dead_cells` is MEASURED, from
    `observed_max == 0.0` on the replayed cell. The record-only signature
    (`_preserved_dead_cell_signature`) is a strict SUBSET of it, because
    `observed_max` is taken over the positives alone while the signature
    also demands both control AUROCs be 0.5. The relation between them is
    asserted DIRECTIONALLY:

      * signature present but the cell measures LIVE  -> HARD FAILURE. It
        would falsify the signature-derived figure itself, which every
        pre-replay count in this codebase rests on.
      * cell measures DEAD but carries no signature   -> EXPECTED. This is
        the structural blind spot: silent on the concept, ACTIVE on the
        controls. Counted, reported, and asserted to be exactly
        `expected_dead_cells - expected_signature_visible_dead_cells`.

    Both counts are pinned, so neither can drift into the other:
    `expected_signature_visible_dead_cells` (None to skip) is asserted
    exactly against the preserved record alone, `expected_dead_cells`
    exactly against the measurement.

    AUROCs are NOT exempted on any of these cells: a DOUBLY-dead cell ties
    against both control sets and must still return exactly 0.5, and a
    signature-blind dead cell must return whatever the preserved record
    holds. Both are compared like any other float.

    Booleans are never compared. `gate_b_passed` legitimately flips on the
    degenerate cells and comparing it would report a correction as a
    regression."""
    problems: list[str] = []
    if set(preserved_ab) != set(replayed_ab):
        missing = sorted(set(preserved_ab) - set(replayed_ab))[:5]
        extra = sorted(set(replayed_ab) - set(preserved_ab))[:5]
        problems.append(f"G-A/G-B cell key sets differ: {len(set(preserved_ab) - set(replayed_ab))} missing "
                        f"(e.g. {missing}), {len(set(replayed_ab) - set(preserved_ab))} extra (e.g. {extra})")
    if set(preserved_c) != set(replayed_c):
        problems.append(f"G-C cell key sets differ: {len(set(preserved_c) ^ set(replayed_c))} symmetric-difference cells")
    if set(preserved_ab) != set(preserved_c):
        # Every G-A/G-B cell must have a G-C cell to be read beside it.
        # Raising here rather than letting the loop below KeyError keeps the
        # failure mode a stated one.
        problems.append(
            f"the preserved record's G-A/G-B and G-C cells do not cover the same "
            f"{len(set(preserved_ab) ^ set(preserved_c))} (concept, locale, family, feature) keys"
        )
    if problems:
        raise ReplayMismatch("; ".join(problems))

    worst = {field: 0.0 for field in REPLAY_COMPARED_FIELDS}
    worst_key = {field: None for field in REPLAY_COMPARED_FIELDS}
    dead_cells: list[tuple] = []
    signature_cells: list[tuple] = []
    signature_disagreements: list[tuple] = []
    signature_blind_dead: list[tuple] = []
    mismatches: list[str] = []

    for key in sorted(preserved_ab):
        old_ab, new_ab = preserved_ab[key], replayed_ab[key]
        old_c, new_c = preserved_c[key], replayed_c[key]

        measured_dead = float(new_ab["observed_max"]) == 0.0 and int(new_ab["n_positives"]) > 0
        recorded_dead = _preserved_dead_cell_signature(old_ab, old_c)
        if recorded_dead:
            signature_cells.append(key)
            # The ONLY direction that can falsify the signature-derived
            # figure. The reverse is the signature's known structural blind
            # spot and is collected below, not flagged here.
            if not measured_dead:
                signature_disagreements.append(key)
        elif measured_dead:
            signature_blind_dead.append(key)

        for field, old_value in (
            ("separation_auroc", old_ab["separation_auroc"]),
            ("near_miss_auroc", old_c["near_miss_auroc"]),
        ):
            new_value = new_ab["separation_auroc"] if field == "separation_auroc" else new_c["near_miss_auroc"]
            delta = abs(float(new_value) - float(old_value))
            if delta > worst[field]:
                worst[field], worst_key[field] = delta, key
            if delta > tolerance:
                mismatches.append(f"{key} {field}: preserved {old_value!r} vs replayed {new_value!r} (|delta|={delta:.3e})")

        old_fire = float(old_ab["fire_rate"])
        new_fire = float(new_ab["fire_rate_within_cell"])
        if measured_dead:
            dead_cells.append(key)
            if old_fire != 1.0 or new_fire != 0.0:
                mismatches.append(
                    f"{key} fire_rate_within_cell: measured-dead cell must be preserved 1.0 -> replayed 0.0, "
                    f"got preserved {old_fire!r} -> replayed {new_fire!r}"
                )
        else:
            delta = abs(new_fire - old_fire)
            if delta > worst["fire_rate_within_cell"]:
                worst["fire_rate_within_cell"], worst_key["fire_rate_within_cell"] = delta, key
            if delta > tolerance:
                mismatches.append(
                    f"{key} fire_rate_within_cell: preserved {old_fire!r} vs replayed {new_fire!r} (|delta|={delta:.3e})"
                )

    if signature_disagreements:
        mismatches.append(
            f"{len(signature_disagreements)} cell(s) CARRY the record-only dead-cell signature "
            f"(auroc 0.5/0.5 and fire_rate 1.0) but measure observed_max != 0.0, "
            f"e.g. {signature_disagreements[:5]} -- the signature-derived lower bound "
            f"({REPLAY_SIGNATURE_VISIBLE_DEAD_CELLS} on run 413287) was derived from that signature, "
            f"so a cell it names that is not in fact dead invalidates it"
        )
    if (
        expected_signature_visible_dead_cells is not None
        and len(signature_cells) != expected_signature_visible_dead_cells
    ):
        mismatches.append(
            f"record-only dead-cell signature matches {len(signature_cells)} preserved cell(s), "
            f"expected exactly {expected_signature_visible_dead_cells} -- this is a property of the "
            f"PRESERVED RECORD alone, so a change here means a different record, not a different model"
        )
    if len(dead_cells) != expected_dead_cells:
        mismatches.append(
            f"dead-cell count is {len(dead_cells)}, expected exactly {expected_dead_cells} -- the C1 "
            f"correction must apply to exactly the population it was measured on"
        )
    if expected_signature_visible_dead_cells is not None:
        expected_blind = expected_dead_cells - expected_signature_visible_dead_cells
        if len(signature_blind_dead) != expected_blind:
            mismatches.append(
                f"{len(signature_blind_dead)} measured-dead cell(s) are invisible to the record-only "
                f"signature (silent on the concept, ACTIVE on a control set), expected exactly "
                f"{expected_blind} = {expected_dead_cells} - {expected_signature_visible_dead_cells}"
            )
    # Internal consistency: the two named populations must partition the
    # measured-dead set. A violation is a defect in this comparator, not in
    # the replay, and it must not be reported as either kind of drift.
    if len(signature_cells) - len(signature_disagreements) + len(signature_blind_dead) != len(dead_cells):
        mismatches.append(
            f"comparator inconsistency: {len(signature_cells)} signature cell(s) minus "
            f"{len(signature_disagreements)} disagreement(s) plus {len(signature_blind_dead)} "
            f"signature-blind dead cell(s) does not equal the {len(dead_cells)} measured-dead cells"
        )

    report = {
        "schema_version": SCHEMA_VERSION,
        "cells_compared": len(preserved_ab),
        "tolerance": tolerance,
        "compared_fields": list(REPLAY_COMPARED_FIELDS),
        "booleans_compared": [],
        "worst_abs_delta": {field: worst[field] for field in REPLAY_COMPARED_FIELDS},
        "worst_abs_delta_cell": {
            field: (list(worst_key[field]) if worst_key[field] is not None else None)
            for field in REPLAY_COMPARED_FIELDS
        },
        "dead_cells_measured": len(dead_cells),
        "dead_cells_expected": expected_dead_cells,
        "signature_visible_dead_cells_measured": len(signature_cells),
        "signature_visible_dead_cells_expected": expected_signature_visible_dead_cells,
        "signature_blind_dead_cells_measured": len(signature_blind_dead),
        "signature_blind_dead_cells_expected": (
            None if expected_signature_visible_dead_cells is None
            else expected_dead_cells - expected_signature_visible_dead_cells
        ),
        "dead_cell_signature_disagreements": len(signature_disagreements),
        "mismatches": mismatches,
        "passed": not mismatches,
        "note": (
            "fire_rate on a measured-dead cell is EXPECTED to read preserved 1.0 -> replayed 0.0 (the C1 "
            "correction) and is asserted to do so; gate_b_passed and every other boolean is deliberately "
            "not compared, because C1 legitimately flips it."
        ),
        "dead_cell_population_note": (
            "dead_cells_measured counts observed_max == 0.0 and is the population. "
            "signature_visible_dead_cells counts the preserved record's auroc-0.5/0.5 + fire_rate-1.0 "
            "signature and is a strict SUBSET of it -- that signature also requires the CONTROLS to be "
            "silent, so it cannot see a feature that is dead on the concept and active on the controls. "
            "signature_blind_dead_cells is exactly that difference. dead_cell_signature_disagreements "
            "counts only the falsifying direction (signature present, cell measures live) and any "
            "non-zero value is a hard failure."
        ),
    }
    if mismatches:
        raise ReplayMismatch(
            f"model-level replay did not reproduce the preserved record: {len(mismatches)} problem(s). "
            + " | ".join(mismatches[:10])
            + (f" | ... and {len(mismatches) - 10} more" if len(mismatches) > 10 else "")
        )
    return report


def run_replay_mode(args: argparse.Namespace) -> dict:
    """`--mode replay`: the owed model-level C2 falsifier, on GPU.

    Loads the real backend, re-scores exactly the (concept, feature)
    population preserved in `--replay-progress`, and asserts every emitted
    `separation_auroc`, `fire_rate_within_cell` and `near_miss_auroc`
    matches the preserved value to 1e-9. Writes `<out_dir>/
    replay_report.json` whether it passes or fails, then RAISES on failure
    -- a mismatch is not a warning.

    Writes no `grid.json` and no verdicts: this mode measures the
    measurement, it does not produce a discovery result."""
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "replay_report.json"

    run_prompt_set_validator(REPO_ROOT)
    artifact = load_frozen_prompt_artifact(REPO_ROOT, allow_pi_gated=True)
    preserved_ab, preserved_c, features_by_concept = load_preserved_grid_cells(args.replay_progress)

    backend = load_backend(
        pairing=args.pairing, model_path=args.model_path, sae_path=args.sae_path, layer=args.layer,
        expected_model_revision=args.expected_model_revision, expected_sae_revision=args.expected_sae_revision,
        device=args.device, dtype=args.dtype, sae_family=args.qwen_sae_family, sparsity=args.qwen_sparsity,
    )
    if args.ready_path is not None:
        write_ready_record(args.ready_path, pairing=args.pairing, device=args.device)

    replayed_ab, replayed_c = replay_preserved_cells(
        backend, artifact, features_by_concept=features_by_concept
    )

    header = {
        "mode": "replay",
        "pairing": args.pairing,
        "replay_progress": str(args.replay_progress),
        "concepts_replayed": len(features_by_concept),
        "features_per_concept": {k: len(v) for k, v in features_by_concept.items()},
        "prompt_set_commit": artifact.commit,
        "prompt_set_sha256": artifact.prompt_sets_sha256,
        "checkpoint_hash": backend.checkpoint_hash,
        "shadow_disclaimer": SHADOW_G_B_DISCLAIMER,
    }
    try:
        report = compare_replay_to_preserved(
            preserved_ab=preserved_ab, preserved_c=preserved_c,
            replayed_ab=replayed_ab, replayed_c=replayed_c,
            tolerance=args.replay_tolerance, expected_dead_cells=args.replay_expected_dead_cells,
            expected_signature_visible_dead_cells=args.replay_expected_signature_visible_dead_cells,
        )
    except ReplayMismatch as exc:
        report_path.write_text(
            json.dumps({**header, "passed": False, "error": str(exc)}, indent=2), encoding="utf-8"
        )
        raise
    report = {**header, **report}
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    report["report_path"] = str(report_path)
    report["status"] = "complete"
    return report


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


def _pooled_residual_and_feature(
    backend: Backend, texts: list[str], feature_index: int, *, cache: FeatureMatrixCache | None = None
) -> tuple[np.ndarray, np.ndarray]:
    """Returns (per-text mean-pooled residual, per-text feature score).

    C2 (2026-08-15): when a `FeatureMatrixCache` is supplied this is a
    CACHE INDEX, not a forward pass -- both return values are slices of
    the one `encode_texts` result for these texts, and the model is never
    re-run for a second feature index over the same texts. With
    `cache=None` it runs the forward pass itself, which is the original
    behaviour and is what the standalone (non-grid) callers still do. The
    two paths are numerically identical: `encode_texts` computes
    `feats.max(dim=0).values` where this computes `feats[:, j].max()` --
    the same reduction over the same tensor -- and float32 -> float64 is
    exact.

    P0 STOP-LINE correction, 2026-08-13: the per-prompt FEATURE score is
    MAX over positions, never mean -- matching this file's own established
    convention everywhere else a per-text SAE-feature scalar is computed
    (`rank_features_by_activation`'s `_gemma_max_activation_per_feature`/
    `_qwen_max_activation_per_feature`, `feats.max(dim=0).values`). This
    function was the one place that deviated (`.mean()`), silently
    diluting a feature that fires sharply on only a few tokens of a
    prompt -- exactly the failure mode "max over positions" exists to
    avoid. Every caller of this function (G-A/B/C, held-out specificity
    validation, greedy bundle composition) reads its second return value
    as that per-prompt feature score. The residual pooling (first return
    value, used only for the specificity probe's own logistic-regression
    input, never for a gate score) is UNCHANGED mean-pooling -- this
    correction is scoped to the feature score only, per the frozen
    metric's own definition."""
    if cache is not None:
        residuals, features = cache.encode(backend, texts)
        return residuals, features[:, feature_index].astype(np.float64)

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
                feats_out.append(float(feats[:, feature_index].max().item()))
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
                feats_out.append(float(feats[:, feature_index].max().item()))
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


class _DtypeRecordingSAE:
    """A minimal `.encode`/`.decode` object used ONLY to observe what
    dtype `_make_clamp_hook` (frozen, `interplab/interventions/hooks.py`)
    actually passes it -- deliberately does NOT auto-cast its own inputs
    (unlike `final_pairing_fakes.FakeSAE`, whose `encode`/`decode` call
    `.to(torch.float32)` internally and would therefore mask a real
    caller-side regression). If `_make_clamp_hook` ever stopped casting
    the residual to float32 before calling `encode`/`decode`, this object
    would receive and record the WRONG dtype, catching it."""

    def __init__(self, d_in: int, d_sae: int) -> None:
        import torch

        self.encode_input_dtypes: list[torch.dtype] = []
        self.decode_input_dtypes: list[torch.dtype] = []
        w = torch.zeros(d_sae, d_in, dtype=torch.float32)
        w[0, 0] = 1.0
        self._w = w

    def encode(self, x):
        import torch

        self.encode_input_dtypes.append(x.dtype)
        return torch.relu(x) @ self._w.T

    def decode(self, feats):
        self.decode_input_dtypes.append(feats.dtype)
        return feats @ self._w


@dataclass(frozen=True)
class DtypeBoundaryDiagnostics:
    residual_input_dtype: str
    residual_output_dtype: str
    sae_encode_input_dtypes: list[str]
    sae_decode_input_dtypes: list[str]
    explicit_cast_confirmed: bool


def verify_dtype_boundary_policy(
    *, residual_dtype=None, d_in: int = 8, d_sae: int = 16, feature_index: int = 0, clamp_value: float = 1.0,
    seq_len: int = 3, batch: int = 1,
) -> DtypeBoundaryDiagnostics:
    """A REAL, direct numerical proof of the dtype boundary policy the
    frozen `_make_clamp_hook` already implements: the INPUT residual
    retains the model's own dtype (bfloat16 here by default -- this
    project's real Gemma/Qwen inference dtype); the SAE's encode/decode
    math runs in float32 (`_DtypeRecordingSAE` observes and records the
    exact dtype it receives, never assuming it); and the reconstructed
    intervention delta is cast EXPLICITLY back to the residual's own
    dtype before `hook_fn` returns -- never an implicit promotion of the
    whole residual stream to float32. Calls `_make_clamp_hook` DIRECTLY
    against a synthetic tensor (no model, no GPU, no real weights) so
    this is a genuine test of the frozen hook's actual dtype arithmetic,
    not a description of intended behavior."""
    import torch

    residual_dtype = residual_dtype or torch.bfloat16
    recording_sae = _DtypeRecordingSAE(d_in, d_sae)
    resid = torch.randn(batch, seq_len, d_in, dtype=residual_dtype)
    hook_fn = _make_clamp_hook(recording_sae, feature_index, clamp_value, "all", None, [])
    result = hook_fn(resid, hook=None)

    if any(dt != torch.float32 for dt in recording_sae.encode_input_dtypes):
        raise AssertionError(
            f"SAE encode() received a non-float32 tensor: {recording_sae.encode_input_dtypes} -- the residual "
            f"must be cast to float32 BEFORE the SAE encode/decode round trip, never passed through at model dtype."
        )
    if any(dt != torch.float32 for dt in recording_sae.decode_input_dtypes):
        raise AssertionError(
            f"SAE decode() received a non-float32 tensor: {recording_sae.decode_input_dtypes}"
        )
    if result.dtype != residual_dtype:
        raise AssertionError(
            f"dtype boundary violated: input residual dtype {residual_dtype} became {result.dtype} on return -- "
            f"the model residual stream must never be implicitly promoted away from its own dtype."
        )
    return DtypeBoundaryDiagnostics(
        residual_input_dtype=str(residual_dtype), residual_output_dtype=str(result.dtype),
        sae_encode_input_dtypes=[str(dt) for dt in recording_sae.encode_input_dtypes],
        sae_decode_input_dtypes=[str(dt) for dt in recording_sae.decode_input_dtypes],
        explicit_cast_confirmed=(result.dtype == residual_dtype),
    )


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
    direction: Literal["clamp", "ablate", "baseline"]
    value_in_max_units: float
    corpus_max_used: float
    absolute_clamp_value: float
    positions: str
    generated_text: str
    verdict: dict
    spec: dict  # interplab.interventions.spec.InterventionSpec-shaped, for sealing-pipeline compatibility
    #: True iff generation stopped at max_new_tokens rather than at a stop
    #: token (EOS/end-of-turn) -- `generation_settings.json`'s own
    #: `truncation_flag` requirement: "48 tokens ... is thin for Suppress
    #: ... this flag makes the adequacy of 48 an empirical question."
    truncated: bool = False


def _resolved_generation_kwargs(max_new_tokens: int, generation_kwargs: dict[str, Any] | None) -> dict[str, Any]:
    """`do_sample=False` (greedy) unless the caller supplies its own
    `generation_kwargs` (e.g. `final_pairing_concept_discovery.
    GENERATION_SETTINGS`, the frozen, EXPLICIT one-allocation settings) --
    `max_new_tokens` always comes from the function's own parameter, never
    from inside `generation_kwargs`, so there is exactly one place a
    caller sets it."""
    resolved = {"do_sample": False, **(generation_kwargs or {})}
    resolved["max_new_tokens"] = max_new_tokens
    return resolved


def resolve_tokenizer_for_backend(backend: Backend):
    """The one real tokenizer object backing this backend's chat template
    and stop-token resolution -- Gemma's `HookedTransformer` already
    carries one (`model.tokenizer`, the same `AutoTokenizer` it was built
    with); Qwen has no comparable stored tokenizer on `Backend` (every
    other Qwen code path in this file reloads it from the validated local
    model path), so this does the same, never inventing a separate
    lookup."""
    if backend.pairing == targets.GEMMA_3_12B_IT_TARGET.name:
        return backend.model_obj.tokenizer
    from transformers import AutoTokenizer

    return AutoTokenizer.from_pretrained(backend.provenance["model"]["local_path"])


def resolve_chat_template_identity(tokenizer) -> str:
    """P0 STOP-LINE correction ("derive/record template identity rather
    than accepting an arbitrary label"): a stable fingerprint of the
    tokenizer's OWN real `chat_template` Jinja string, actually in effect
    at generation time -- never a free-text CLI/caller label. Raises if
    the tokenizer carries no chat_template at all: an instruction-tuned
    model with no template is itself a stop condition, not license to
    silently fall back to raw (non-chat) tokenization."""
    name = getattr(tokenizer, "name_or_path", None) or "unknown"
    template = getattr(tokenizer, "chat_template", None)
    if not template:
        raise ValueError(
            f"tokenizer {name!r} has no chat_template -- refusing to invent one or silently fall "
            f"back to raw (non-chat) tokenization for an instruction-tuned model."
        )
    template_sha256 = hashlib.sha256(template.encode("utf-8")).hexdigest()
    return f"{name}:{template_sha256[:16]}"


#: Well-known chat end-of-turn marker spellings this file checks for IN
#: ADDITION to the tokenizer's own primary `eos_token_id` -- a chat model's
#: real stop condition is often MORE than one token id (e.g. Gemma's own
#: generation_config.json ships `eos_token_id: [<eos>, <end_of_turn>]`).
#: Never a newline or any other content-shaped stopping criterion.
_CHAT_END_OF_TURN_MARKERS: tuple[str, ...] = ("<end_of_turn>", "<|im_end|>")


def resolve_stop_token_ids(tokenizer) -> dict[str, Any]:
    """P0 STOP-LINE correction ("resolve and record EOS/EOT/PAD
    explicitly; never stop on newline"): explicitly resolves the real
    stop-token id(s) and pad-token id from the tokenizer, rather than
    relying on whatever implicit default `generate()` would otherwise
    apply -- and never introduces any newline-based stopping criterion.
    `eos_token_id` is a LIST when a known end-of-turn marker is present in
    the tokenizer's vocabulary in addition to its primary EOS (matching
    `transformers.GenerationConfig`'s own accepted shape), a plain int
    otherwise."""
    if tokenizer.eos_token_id is None:
        raise ValueError(
            f"tokenizer {getattr(tokenizer, 'name_or_path', tokenizer)!r} has no eos_token_id -- "
            f"cannot resolve an explicit stop token."
        )
    eos_ids = [tokenizer.eos_token_id]
    unk_id = getattr(tokenizer, "unk_token_id", None)
    for marker in _CHAT_END_OF_TURN_MARKERS:
        marker_id = tokenizer.convert_tokens_to_ids(marker)
        if marker_id is not None and marker_id != unk_id and marker_id not in eos_ids:
            eos_ids.append(marker_id)
    pad_token_id = tokenizer.pad_token_id if tokenizer.pad_token_id is not None else eos_ids[0]
    return {"eos_token_id": eos_ids if len(eos_ids) > 1 else eos_ids[0], "pad_token_id": pad_token_id}


def render_chat_prompt_tokens(tokenizer, prompt: str, *, return_tensors: str = "pt", return_dict: bool = False):
    """P0 STOP-LINE correction ("apply each model's real chat template:
    one user turn, no system prompt"): applies the tokenizer's REAL chat
    template via `apply_chat_template`, never a hand-built prompt string
    -- exactly one user-role message, no system message."""
    messages = [{"role": "user", "content": prompt}]
    return tokenizer.apply_chat_template(
        messages, tokenize=True, add_generation_prompt=True, return_tensors=return_tensors, return_dict=return_dict,
    )


def run_intervention(
    backend: Backend, feature_indices: list[int], *,
    direction: Literal["clamp", "ablate"], value_in_max_units: float, corpus_max: dict[int, float],
    positions: str, prompt: str, seed: int, max_new_tokens: int, generation_kwargs: dict[str, Any] | None = None,
) -> InterventionOutcome:
    import torch

    for i in feature_indices:
        reject_mechanical_only_feature(backend.pairing, i, context="run_intervention")
        targets.validate_feature_index(i, backend.d_sae)

    seed_feature = feature_indices[0]
    absolute_clamp_value = 0.0 if direction == "ablate" else float(value_in_max_units) * float(corpus_max[seed_feature])
    gen_kwargs = _resolved_generation_kwargs(max_new_tokens, generation_kwargs)

    trace: list = []
    if backend.pairing == targets.GEMMA_3_12B_IT_TARGET.name:
        model = backend.model_obj
        tokens = render_chat_prompt_tokens(model.tokenizer, prompt, return_tensors="pt", return_dict=False)
        stop_ids = resolve_stop_token_ids(model.tokenizer)
        prompt_length = tokens.shape[1]
        prompt_lengths = prompt_length if positions == "generated_only" else None
        inner = _bundle_hook_fn(backend, feature_indices, absolute_clamp_value, positions, prompt_lengths, trace)
        hook_fn = harness.wrap_hook_with_diagnostics(
            inner, sae=backend.sae, feature_index=seed_feature, mode=direction,
            dose_or_raw_label=f"value_in_max_units={value_in_max_units}", calibration_input=value_in_max_units,
            resolved_absolute_target=absolute_clamp_value, hook_name=backend.hook_name, trace_out=trace,
        )
        torch.manual_seed(seed)
        with _attached(backend, hook_fn):
            out_tokens = model.generate(tokens, verbose=False, **{**gen_kwargs, **stop_ids})
        generated_text = model.tokenizer.decode(out_tokens[0][prompt_length:], skip_special_tokens=True)
        new_token_count = out_tokens.shape[1] - prompt_length
    else:
        tokenizer = resolve_tokenizer_for_backend(backend)
        inputs = render_chat_prompt_tokens(tokenizer, prompt, return_tensors="pt", return_dict=True).to(backend._qwen_device)
        stop_ids = resolve_stop_token_ids(tokenizer)
        prompt_length = inputs["input_ids"].shape[1]
        prompt_lengths = prompt_length if positions == "generated_only" else None
        inner = _bundle_hook_fn(backend, feature_indices, absolute_clamp_value, positions, prompt_lengths, trace)
        hook_fn = harness.wrap_hook_with_diagnostics(
            inner, sae=backend.sae, feature_index=seed_feature, mode=direction,
            dose_or_raw_label=f"value_in_max_units={value_in_max_units}", calibration_input=value_in_max_units,
            resolved_absolute_target=absolute_clamp_value, hook_name=backend.hook_name, trace_out=trace,
        )
        torch.manual_seed(seed)
        with _attached(backend, hook_fn), torch.no_grad():
            out_ids = backend.model_obj.generate(**inputs, **{**gen_kwargs, **stop_ids})
        generated_text = tokenizer.decode(out_ids[0][prompt_length:], skip_special_tokens=True)
        new_token_count = out_ids.shape[1] - prompt_length

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
        truncated=bool(new_token_count >= gen_kwargs["max_new_tokens"]),
    )


def run_baseline_generation(
    backend: Backend, *, prompt: str, seed: int, max_new_tokens: int, positions: str,
    generation_kwargs: dict[str, Any] | None = None,
) -> InterventionOutcome:
    """The unsteered (CONTROL) counterpart to `run_intervention`: generates
    from the SAME prompt/seed/max_new_tokens with NO hook attached at all
    -- not a clamp/ablate at value 0, an actual absence of intervention.
    G-D/G-E's own `evaluate_gate_d`/`evaluate_gate_e` (`final_pairing_
    causal_judge.py`) already require a `control_relevance_by_prompt` map
    computed from generations paired with the steered ones at the SAME
    prompt_id -- this is the only place in the codebase that can produce
    those generations, since Tamia is the only place doing model
    inference. `generation_settings.json`'s own `3_control_arm.SAME_SEED_
    IS_MANDATORY` rule means the CALLER must pass the exact same `seed`
    (and, for an attested run, the exact same `generation_kwargs`) it used
    for the steered generation this control pairs with -- this function
    does not re-derive or default either.

    Returns an `InterventionOutcome` with `direction='baseline'`,
    `feature_indices=[]`, `value_in_max_units=0.0`. `verdict={}` and
    `spec['kind']='baseline'` -- there is no hook diagnostic trace to
    report a mechanical verdict from (mechanical acceptance is a property
    of the CLAMP/ABLATE hook, which a baseline run never attaches), so an
    empty verdict is the honest result, not a fabricated pass/fail."""
    import torch

    gen_kwargs = _resolved_generation_kwargs(max_new_tokens, generation_kwargs)

    if backend.pairing == targets.GEMMA_3_12B_IT_TARGET.name:
        model = backend.model_obj
        tokens = render_chat_prompt_tokens(model.tokenizer, prompt, return_tensors="pt", return_dict=False)
        stop_ids = resolve_stop_token_ids(model.tokenizer)
        prompt_length = tokens.shape[1]
        torch.manual_seed(seed)
        out_tokens = model.generate(tokens, verbose=False, **{**gen_kwargs, **stop_ids})
        generated_text = model.tokenizer.decode(out_tokens[0][prompt_length:], skip_special_tokens=True)
        new_token_count = out_tokens.shape[1] - prompt_length
    else:
        tokenizer = resolve_tokenizer_for_backend(backend)
        inputs = render_chat_prompt_tokens(tokenizer, prompt, return_tensors="pt", return_dict=True).to(backend._qwen_device)
        stop_ids = resolve_stop_token_ids(tokenizer)
        prompt_length = inputs["input_ids"].shape[1]
        torch.manual_seed(seed)
        with torch.no_grad():
            out_ids = backend.model_obj.generate(**inputs, **{**gen_kwargs, **stop_ids})
        generated_text = tokenizer.decode(out_ids[0][prompt_length:], skip_special_tokens=True)
        new_token_count = out_ids.shape[1] - prompt_length

    spec = {
        "kind": "baseline", "feature_index": None, "value_in_max_units": 0.0, "corpus_max": None,
        "positions": positions, "checkpoint_hash": backend.checkpoint_hash, "direction_seed": None,
    }
    return InterventionOutcome(
        feature_indices=[], direction="baseline", value_in_max_units=0.0, corpus_max_used=0.0,
        absolute_clamp_value=0.0, positions=positions, generated_text=generated_text, verdict={}, spec=spec,
        truncated=bool(new_token_count >= gen_kwargs["max_new_tokens"]),
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


def write_ready_record(ready_path: str | Path, *, pairing: str, device: str, pid: int | None = None) -> ReadyRecord:
    """Written ATOMICALLY (write to a sibling .tmp file, then os.replace)
    so a reader polling for `ready_path` never observes a partially-written
    file -- os.replace is atomic on both POSIX and NTFS when source and
    destination are on the same volume, which a sibling temp file always
    is. `pid` defaults to `os.getpid()` (the real, production case: this
    function runs INSIDE the child process it is reporting readiness
    for) -- overridable so a test can fake a launch WITHOUT a real
    subprocess while still recording the fake process handle's own pid,
    which `wait_for_ready_record`'s `expected_pid` check requires to
    agree."""
    import time as _time

    record = ReadyRecord(pairing=pairing, device=device, pid=pid if pid is not None else os.getpid(), loaded_at=_time.time())
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


def delete_stale_ready_record(ready_path: str | Path) -> None:
    """P0 STOP-LINE correction ('delete an old READY file before
    launch'): removes any pre-existing READY record at `ready_path`
    BEFORE this lane's child process is even launched -- a state_dir
    reused across runs (a resumed job, a re-submitted allocation) must
    never let a PREVIOUS run's READY record be misread as THIS run's
    signal. A no-op (never raises) if no file is present."""
    Path(ready_path).unlink(missing_ok=True)


def wait_for_ready_record(
    ready_path: str | Path, *, expected_pairing: str, expected_device: str,
    process_alive_fn, timeout_seconds: float, poll_interval: float = 1.0, sleep_fn=None,
    expected_pid: int | None = None, min_loaded_at: float | None = None,
) -> ReadyRecord:
    """Polls for `ready_path`. `process_alive_fn()` returning False BEFORE
    a valid READY record appears means the loader process exited without
    ever becoming ready -- fails closed immediately rather than waiting
    out the full timeout on a process that has already died. A READY
    record naming a different pairing or device than expected is refused
    rather than trusted (a misconfigured lane could otherwise silently
    satisfy the wrong handshake).

    P0 STOP-LINE correction ('require READY pid/start time to match this
    child'): when `expected_pid`/`min_loaded_at` are supplied (the real
    orchestrator always supplies both -- see `DualGpuOrchestrator.
    launch_staggered`), the record's own `pid` must equal `expected_pid`
    (THIS child's actual spawned pid, never merely "a" pid) and its
    `loaded_at` must be `>= min_loaded_at` (no earlier than when THIS
    child was launched) -- a defense-in-depth check independent of
    `delete_stale_ready_record`, in case that deletion ever raced with a
    straggler process from a previous run still writing to the same path."""
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
            if expected_pid is not None and record.pid != expected_pid:
                raise ReadyHandshakeFailed(
                    f"READY record at {path} names pid={record.pid!r}, expected THIS child's own "
                    f"pid={expected_pid!r} -- refusing to trust a READY record that may belong to a "
                    f"different (e.g. stale, previous-run) process."
                )
            if min_loaded_at is not None and record.loaded_at < min_loaded_at:
                raise ReadyHandshakeFailed(
                    f"READY record at {path} has loaded_at={record.loaded_at!r}, earlier than "
                    f"min_loaded_at={min_loaded_at!r} (when THIS child was launched) -- refusing to "
                    f"trust a READY record written before this launch even started."
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
    p.add_argument(
        "--mode", choices=["full", "grid", "replay"], default="full",
        help=(
            "'full' (default): the single-concept 7-stage pipeline (rank -> specificity -> bundle -> "
            "dose-response -> confirmation), unchanged. 'grid': the production discovery-lane mode -- "
            "evaluates G-A/B/C for EVERY concept in the frozen prompt artifact (all 14, both locales; "
            "there is deliberately no subset/--concept-id flag) on this one already-loaded backend and "
            "writes grid.json (run_concept_grid + write_grid_result), then exits. Does not run "
            "specificity/bundle/dose-response/confirmation at all -- that is a separate, later stage "
            "(final_pairing_one_allocation_generation.py) driven off this grid's surviving features. "
            "'replay': the owed model-level falsifier -- re-scores exactly the (concept, feature) "
            "population preserved in --replay-progress on the real backend and asserts every emitted "
            "separation_auroc / fire_rate_within_cell / near_miss_auroc matches the preserved value "
            "to --replay-tolerance, failing loudly on any mismatch. Writes replay_report.json and no "
            "grid.json; it produces no verdict and no discovery result."
        ),
    )
    p.add_argument("--pairing", required=True, choices=sorted(targets.ALL_TARGETS))
    p.add_argument("--model-path", required=True)
    p.add_argument("--sae-path", required=True)
    p.add_argument("--layer", type=int, default=None, help=f"Required for both pairings. qwen-3.5-27b: any of {_QWEN_SCIENTIFIC_LAYERS} (not 0 -- engineering-only). gemma-3-12b-it: any of {_GEMMA_SCIENTIFIC_LAYERS} (not 31 -- engineering-only).")
    p.add_argument("--qwen-sae-family", choices=list(_QWEN_SCIENTIFIC_SAE_FAMILIES), default=None, help="Required for qwen-3.5-27b. Distinct from --qwen-sparsity and --layer.")
    p.add_argument("--qwen-sparsity", type=int, default=None, help="Required for qwen-3.5-27b: the SAE's TopK k, verified against the loaded file. Distinct from --qwen-sae-family and --layer.")
    p.add_argument("--expected-model-revision", default=None)
    p.add_argument("--expected-sae-revision", default=None)

    p.add_argument("--prompt-set-path", default=None, help="Required in --mode full.")
    p.add_argument("--prompt-set-sha256", default=None, help="Required in --mode full.")
    p.add_argument("--judge-config", default=None, help="Optional path to a {model,rubric_version,prompt_version} JSON. Defaults to the NoOp identity -- no judge is ever actually invoked by this file.")
    p.add_argument("--use-frozen-prompt-artifact", action="store_true", help=f"Additionally validate prompts/final_pairing/v1/ against the pinned commit {FROZEN_PROMPT_SET_COMMIT} and hashes, run the committed validator, and stamp prompt_set_commit/prompt_set_sha256 in the output. Refuses a dirty or hash-mismatched artifact.")
    p.add_argument("--allow-pi-gated", action="store_true", help="Only meaningful with --use-frozen-prompt-artifact (mode=full) or --mode grid. Never set for a public configuration -- political_framing stays excluded otherwise.")

    p.add_argument("--positions", choices=["all", "generated_only"], default="all")
    p.add_argument("--record-generated-only-diagnostic", action="store_true", help="Additionally run every intervention under generated_only as a separate diagnostic. positions=all remains the public calibration path regardless.")
    p.add_argument("--confirmation-repeats", type=int, default=3, help="Only used with --use-frozen-prompt-artifact: repeats per held-out prompt in the dose-response confirmation sweep (heldout_neutral for clamp, heldout_eliciting for ablate).")

    p.add_argument(
        "--shortlist-size", type=int, required=True,
        help=(
            "Required in both modes. --mode full still ranks candidates with it (that stage is a "
            "single prompt set, not the 14-concept grid). --mode grid IGNORES it since C3: the grid "
            "scores every SAE feature, so nothing is shortlisted; use --report-top-n to bound how "
            "many extra features the grid RECORDS."
        ),
    )
    p.add_argument(
        "--report-top-n", type=int, default=DEFAULT_REPORT_TOP_N,
        help=(
            "--mode grid only: how many features beyond the G-A-passing set to record per concept. "
            "A reporting budget; it never affects which features are scored or any verdict."
        ),
    )
    p.add_argument("--direction", choices=["clamp", "ablate"], default=None, help="Required in --mode full.")
    p.add_argument("--dose-grid", default=None, help="Required in --mode full. Comma-separated floats, in value_in_max_units (multiples of the background-corpus max activation).")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--prompt", default="Tell me about your day.")
    p.add_argument("--max-new-tokens", type=int, default=8)
    p.add_argument("--device", default="cuda")
    p.add_argument("--dtype", default="bfloat16")

    p.add_argument("--specificity-auc-threshold", type=float, default=None, help="Required in --mode full.")
    p.add_argument("--bundle-materiality-threshold", type=float, default=None, help="Required in --mode full.")
    p.add_argument("--bundle-max-size", type=int, default=1)
    p.add_argument("--calibration-low-threshold", type=float, default=None, help="Required in --mode full.")
    p.add_argument("--calibration-medium-threshold", type=float, default=None, help="Required in --mode full.")
    p.add_argument("--calibration-high-threshold", type=float, default=None, help="Required in --mode full.")

    p.add_argument(
        "--replay-progress", default=None,
        help=(
            "--mode replay only (required there): the EXACT path to the preserved grid progress.jsonl "
            "to replay, e.g. D:/devcache/tmp/fp413287/primary/qwen/grid/state/progress.jsonl. Never "
            "globbed for."
        ),
    )
    p.add_argument(
        "--replay-tolerance", type=float, default=REPLAY_TOLERANCE,
        help="--mode replay only: max permitted |replayed - preserved| on every compared float (default 1e-9).",
    )
    p.add_argument(
        "--replay-expected-dead-cells", type=int, default=REPLAY_EXPECTED_DEAD_CELLS,
        help=(
            "--mode replay only: the EXACT number of cells whose positives are all zero, where the C1 "
            "correction turns the preserved fire_rate 1.0 into 0.0. Asserted exactly; more or fewer "
            f"fails the replay. Default {REPLAY_EXPECTED_DEAD_CELLS}, MEASURED on run 413287's record "
            "by the GPU replay in Tamia job 414676 (2026-08-15) from observed_max == 0.0."
        ),
    )
    p.add_argument(
        "--replay-expected-signature-visible-dead-cells", type=int,
        default=REPLAY_SIGNATURE_VISIBLE_DEAD_CELLS,
        help=(
            "--mode replay only: the EXACT number of preserved cells carrying the RECORD-ONLY dead-cell "
            "signature (auroc 0.5 against both control sets and fire_rate 1.0). A strict SUBSET of "
            "--replay-expected-dead-cells: the signature also requires the CONTROLS to be silent, so it "
            f"cannot see a dead-on-concept/active-on-controls cell. Default "
            f"{REPLAY_SIGNATURE_VISIBLE_DEAD_CELLS} against run 413287, of which "
            f"{REPLAY_SIGNATURE_BLIND_DEAD_CELLS} of the {REPLAY_EXPECTED_DEAD_CELLS} dead cells are "
            "invisible to it. Asserted exactly, as is that difference."
        ),
    )
    p.add_argument("--out-dir", required=True)
    p.add_argument("--state-dir", required=True, help="Separate from --out-dir: holds the resumable progress log only.")
    p.add_argument("--ready-path", default=None, help="If set, a READY record is written here immediately after the backend (model+SAE) finishes loading -- for the dual-GPU orchestrator's staggered-cold-load handshake. Omitted for a standalone/non-staggered run.")
    args = p.parse_args(argv)
    _validate_args_for_mode(p, args)
    return args


_FULL_MODE_REQUIRED_FIELDS = (
    "prompt_set_path", "prompt_set_sha256", "direction", "dose_grid", "specificity_auc_threshold",
    "bundle_materiality_threshold", "calibration_low_threshold", "calibration_medium_threshold",
    "calibration_high_threshold",
)


def _validate_args_for_mode(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    """`--mode full`'s own fields stay `required=True` in spirit, but are
    declared `default=None` at the argparse level so `--mode grid` (which
    needs none of them) does not have to supply placeholder values for
    flags it never uses. Enforced here instead, with the same fail-closed
    `parser.error` (exit code 2, matching argparse's own convention for a
    genuinely missing required argument) `--mode grid` never touches this
    path at all -- there is no field required there beyond `--shortlist-
    size`, which stays `required=True` at the parser level since both
    modes need it."""
    if args.mode == "full":
        missing = [f for f in _FULL_MODE_REQUIRED_FIELDS if getattr(args, f) is None]
        if missing:
            parser.error(f"--mode full requires: {', '.join('--' + f.replace('_', '-') for f in missing)}")
    if args.mode == "replay" and args.replay_progress is None:
        parser.error("--mode replay requires --replay-progress (the exact path to the preserved progress.jsonl)")


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


def run_grid_mode(args: argparse.Namespace) -> dict:
    """`--mode grid`: the real production discovery-lane entry point.
    Loads ONE already-configured backend (one pairing, one configuration),
    validates the frozen prompt artifact (git-independent -- see
    `load_frozen_prompt_artifact`), then evaluates G-A/B/C for EVERY
    concept the frozen artifact carries (`run_concept_grid`'s own default
    `concept_ids=None` -- there is no CLI flag anywhere in this function
    that could narrow that set; a production run always covers all 14)
    and writes `grid.json` via `write_grid_result`. Returns the same
    aggregate dict `write_grid_result`'s caller already gets, plus the
    written path, so `main()` can report status without re-reading the
    file it just wrote.

    Does not rank/compose a bundle/run any dose-response or confirmation
    intervention -- those stages belong to `final_pairing_one_allocation_
    generation.py`'s CLI, driven off THIS grid's `surviving_feature_index`
    per concept, once the grid (and the automatic backup-trigger decision
    it feeds) has been written."""
    out_dir = Path(args.out_dir)
    state_dir = Path(args.state_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    state_dir.mkdir(parents=True, exist_ok=True)
    progress = ProgressLog(state_dir / "progress.jsonl")

    run_prompt_set_validator(REPO_ROOT)
    # The frozen backup-trigger protocol's own grid is fixed at "14 concepts x 2
    # pairings x 3 gates x 3 paraphrase families x 2 locales" (protocols/final_
    # pairing/v1/backup_trigger.json) -- primary_shared_gabc_count's range is
    # explicitly 0-14. allow_pi_gated is therefore NOT wired to --allow-pi-gated
    # here (that flag governs --mode full's single-concept, public-facing
    # exclusion); grid mode always evaluates all 14, including political_framing,
    # since a 13-concept grid would silently break the trigger's own arithmetic.
    artifact = load_frozen_prompt_artifact(REPO_ROOT, allow_pi_gated=True)

    backend = load_backend(
        pairing=args.pairing, model_path=args.model_path, sae_path=args.sae_path, layer=args.layer,
        expected_model_revision=args.expected_model_revision, expected_sae_revision=args.expected_sae_revision,
        device=args.device, dtype=args.dtype, sae_family=args.qwen_sae_family, sparsity=args.qwen_sparsity,
    )
    if args.ready_path is not None:
        write_ready_record(args.ready_path, pairing=args.pairing, device=args.device)

    verdicts = run_concept_grid(backend, artifact, report_top_n=args.report_top_n, progress=progress)
    # P0 STOP-LINE correction: "exactly the frozen 14 concepts; no
    # operator-selected subset" is enforced here as a RUNTIME invariant,
    # not merely the absence of a CLI flag -- a caller that ever manages
    # to narrow concept_ids (a future refactor, a bug) fails loudly rather
    # than silently writing an incomplete grid.
    if len(verdicts) != FROZEN_PROMPT_SET_CONCEPT_COUNT:
        raise PromptArtifactError(
            f"grid mode produced {len(verdicts)} concept verdict(s), expected exactly "
            f"{FROZEN_PROMPT_SET_CONCEPT_COUNT} -- refusing to write a partial grid.json; "
            f"the backup-trigger formula's own primary_shared_gabc_count arithmetic assumes "
            f"the full 14-concept grid."
        )
    grid_path = write_grid_result(out_dir, args.pairing, verdicts)

    concept_count = len(verdicts)
    error_count = sum(1 for v in verdicts if v.status == "error")
    pass_count = sum(1 for v in verdicts if v.status == "pass")
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": "grid",
        "pairing": args.pairing,
        "prompt_set_commit": artifact.commit,
        "prompt_set_sha256": artifact.prompt_sets_sha256,
        "concept_count": concept_count,
        "pass_count": pass_count,
        "fail_count": concept_count - pass_count - error_count,
        "error_count": error_count,
        "grid_path": str(grid_path),
        "status": "complete" if error_count == 0 else "complete_with_errors",
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.mode == "replay":
        # No try/except: `run_replay_mode` writes its report and then
        # re-raises `ReplayMismatch`, so a mismatch surfaces as a non-zero
        # exit AND a traceback naming the offending cells. Swallowing it
        # into a status string would make the falsifier advisory.
        replay_result = run_replay_mode(args)
        print(json.dumps({
            "status": replay_result["status"], "pairing": replay_result["pairing"],
            "cells_compared": replay_result["cells_compared"],
            "worst_abs_delta": replay_result["worst_abs_delta"],
            "dead_cells_measured": replay_result["dead_cells_measured"],
            "report_path": replay_result["report_path"],
        }, indent=2))
        return 0
    if args.mode == "grid":
        grid_result = run_grid_mode(args)
        print(json.dumps({"status": grid_result["status"], "pairing": grid_result["pairing"], "grid_path": grid_result["grid_path"]}, indent=2))
        return 0 if grid_result["error_count"] == 0 else 1
    result = run(args)
    print(json.dumps({"status": result["status"], "concept_id": result.get("concept_id")}, indent=2))
    return 0 if result["status"] in ("complete", "no_candidate_passed_specificity") else 1


if __name__ == "__main__":
    sys.exit(main())
