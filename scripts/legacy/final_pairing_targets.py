"""Ratified final-pairing target identities, and the pure (no torch, no
network) validation functions that check a loaded model/SAE actually match
them. No feature meanings, bundles, weights, calibration, or behavioral
thresholds live here -- engineering identity only.

WHY A NEW MODULE RATHER THAN REUSING gemma3_sweep.load_model_and_sae:
gemma3_sweep.py's load_model_and_sae (frozen, Engineer 2 owned, not edited
here) hardcodes its own module-level MODEL_ID / SAE_RELEASE / SAE_ID
constants inside the function body -- HookedTransformer.from_pretrained(
MODEL_ID, hf_model=hf_model, ...) and SAE.from_pretrained(release=
SAE_RELEASE, sae_id=SAE_ID, ...) both ignore whatever model_path/sae_path
strings are passed in for identity-routing purposes (model_path/sae_path
are only used to load bytes from disk and to existence-check; the identity
that determines WHICH conversion recipe and WHICH registry entry gets used
is the hardcoded constant). Pointing that function's --model-path/--sae-path
at a gemma-3-12b-**it** / gemma-scope-2-12b-**it** snapshot would silently
still resolve identity against the **pt** constants -- the exact "identical
output" failure class this investigation exists to close, one level up.
This module's loaders (final_pairing_harness.py) take repo_id/release/sae_id
as explicit parameters instead, and this module's validators check what
was ACTUALLY loaded against what was ratified.

VERIFIED, not assumed (commands re-runnable against this repo's own pinned
sae_lens==6.44.2 / transformer_lens==3.2.1, both installed locally -- same
pins as the Tamia sprint venv, see project_pi_directive_2026_08.md):

    from sae_lens.loading.pretrained_saes_directory import get_pretrained_saes_directory
    get_pretrained_saes_directory()["gemma-scope-2-12b-it-res"]
        -> repo_id="google/gemma-scope-2-12b-it", model="google/gemma-3-12b-it"
        -> saes_map["layer_31_width_16k_l0_medium"] == "resid_post/layer_31_width_16k_l0_medium"
           (the exact ratified sae_id -- present, not guessed)

    import transformer_lens.loading_from_pretrained as lfp
    "google/gemma-3-12b-it" in lfp.OFFICIAL_MODEL_NAMES  -> True
    lfp.convert_hf_model_config("google/gemma-3-12b-it")
        -> d_model=3840, n_layers=48  (identical to the already-verified -pt
           figures in docs/pi_directive_plan_2026_08.md -- same architecture
           family, "google/gemma-3-12b" is a startswith() branch covering
           both variants, loading_from_pretrained.py:1199)
    any("qwen3.5" in n.lower() for n in lfp.OFFICIAL_MODEL_NAMES)  -> False
        (newest Qwen family transformer_lens==3.2.1 knows is "Qwen3",
         0.6B/1.7B/4B/8B/14B -- no 27B, and nothing named Qwen3.5 at all)

NOT verifiable from this machine without downloading weights, so recorded
as read-only public-metadata findings (HF's public /api/models endpoint,
config.json, and the release's own app.py source -- no weights fetched):

    Qwen/Qwen3.5-27B: architectures=["Qwen3_5ForConditionalGeneration"],
    model_type="qwen3_5", hidden_size=5120, num_hidden_layers=64,
    pipeline_tag="image-text-to-text" (multimodal, like Gemma3ForConditional
    Generation). Not in transformer_lens's registry (see above) -- the
    HookedTransformer path is not available for this model without either
    an unauthorized version-pin change or a raw-HF-forward-hooks fallback
    (see final_pairing_harness.py's QwenRawHookAdapter and the "unresolved
    ambiguities" list in docs/final_pairing_tamia_packet.md).

    Qwen/SAE-Res-Qwen3.5-27B-W80K-L0_50: tag "qwen-scope", model_type=
    "topk_sae", base_model=Qwen/Qwen3.5-27B, d_model=5120, d_sae=81920,
    k=50, hook_point="resid_post", one file per layer (layer0.sae.pt ..
    layer63.sae.pt, num_layers=64) -- NOT a sae_lens registry entry and NOT
    the tracked-directory layout sae_lens.SAE.load_from_pretrained expects;
    a bespoke torch.load()'d dict (keys W_enc/b_enc/W_dec per the release's
    own app.py) needing a thin duck-typed wrapper, not sae_lens.SAE itself.
    b_dec's presence is UNCONFIRMED (app.py's own steering shortcut never
    reads it) -- see QwenScopeSAE's docstring.

Per the ratified target list, the Qwen SIDE's layer is explicitly
engineering-only and NOT pre-registered here: "Qwen layer selected from the
official release or available Tamia snapshots" means whichever of the 64
per-layer files is actually staged locally, supplied by the caller -- this
module does not default or guess one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class TargetPairing:
    name: str
    model_repo_id: str
    model_architecture: str
    model_supported_by_transformer_lens: bool
    sae_repo_id: str
    sae_format: Literal["sae_lens_registry", "qwen_scope_raw_pt"]
    expected_hidden_dim: int
    # sae_lens_registry fields (Gemma-it) -- None for qwen_scope_raw_pt
    sae_release: str | None = None
    sae_id: str | None = None
    expected_layer: int | None = None
    expected_hook_name: str | None = None
    # qwen_scope_raw_pt fields (Qwen 3.5) -- None for sae_lens_registry
    expected_d_sae: int | None = None
    expected_k: int | None = None
    expected_num_layers: int | None = None
    notes: str = ""


GEMMA_3_12B_IT_TARGET = TargetPairing(
    name="gemma-3-12b-it",
    model_repo_id="google/gemma-3-12b-it",
    model_architecture="Gemma3ForConditionalGeneration",
    model_supported_by_transformer_lens=True,
    sae_repo_id="google/gemma-scope-2-12b-it",
    sae_format="sae_lens_registry",
    sae_release="gemma-scope-2-12b-it-res",
    sae_id="resid_post/layer_31_width_16k_l0_medium",
    expected_layer=31,
    expected_hook_name="blocks.31.hook_resid_post",
    expected_hidden_dim=3840,
    notes=(
        "Engineering target only (layer 31 is the same pre-existing D1 choice as the -pt "
        "pairing, carried over for architecture/hook continuity -- not re-justified here). "
        "sae_release/sae_id verified present in the locally-installed sae_lens==6.44.2 "
        "registry; not yet verified that the corresponding HF snapshot is staged on Tamia."
    ),
)

QWEN_3_5_27B_TARGET = TargetPairing(
    name="qwen-3.5-27b",
    model_repo_id="Qwen/Qwen3.5-27B",
    model_architecture="Qwen3_5ForConditionalGeneration",
    model_supported_by_transformer_lens=False,
    sae_repo_id="Qwen/SAE-Res-Qwen3.5-27B-W80K-L0_50",
    sae_format="qwen_scope_raw_pt",
    expected_hidden_dim=5120,
    expected_d_sae=81920,
    expected_k=50,
    expected_num_layers=64,
    expected_layer=None,  # engineering-only, supplied by the caller -- see module docstring
    expected_hook_name="resid_post",  # generic hook_point name from the release's own config.json, not a TL hook string
    notes=(
        "model_supported_by_transformer_lens=False is a VERIFIED negative (not an assumption): "
        "'Qwen/Qwen3.5-27B' and every 'qwen3.5'-named entry are absent from transformer_lens==3.2.1's "
        "OFFICIAL_MODEL_NAMES. Loading requires the raw-HF-forward-hooks path (see "
        "final_pairing_harness.load_qwen_target), not HookedTransformer.from_pretrained. "
        "The model is multimodal (pipeline_tag=image-text-to-text); the text decoder must be "
        "reached explicitly, mirroring the already-solved Gemma3ForConditionalGeneration pattern "
        "(docs/pi_directive_plan_2026_08.md's 'reach .language_model explicitly' note)."
    ),
)

ALL_TARGETS = {t.name: t for t in (GEMMA_3_12B_IT_TARGET, QWEN_3_5_27B_TARGET)}


# ---------------------------------------------------------------------------
# Pure validation -- no torch, no network. Fully unit-testable with plain
# strings/ints/fake objects.
# ---------------------------------------------------------------------------

_HF_CACHE_SNAPSHOT_RE = re.compile(
    r"models--(?P<org>[^\\/]+)--(?P<repo>[^\\/]+)[\\/]snapshots[\\/](?P<revision>[^\\/]+)"
)


def parse_hf_cache_snapshot_path(path: str | Path) -> dict[str, str] | None:
    """Extract {org, repo, revision} from a standard huggingface_hub cache
    layout path (.../models--<org>--<repo>/snapshots/<revision>/...). The
    on-disk cache layout embeds repo identity and revision in the path
    itself -- this is a mechanical fact about how huggingface_hub lays out
    its cache, not a guess about any specific path. Returns None (not an
    error) for a path that doesn't follow this layout at all -- e.g. an
    arbitrary local directory a caller staged by hand; callers that require
    the identity check should treat None as "cannot verify", not "verified
    absent"."""
    match = _HF_CACHE_SNAPSHOT_RE.search(str(path).replace("\\", "/"))
    if match is None:
        return None
    org_repo_underscore_fixed = match.group("org"), match.group("repo").replace("--", "/")
    return {
        "org": org_repo_underscore_fixed[0],
        "repo": org_repo_underscore_fixed[1],
        "revision": match.group("revision"),
    }


class TargetIdentityMismatch(ValueError):
    """Raised by every validate_* function below -- fail closed, never warn-and-continue."""


def validate_local_snapshot_identity(
    path: str | Path, target: TargetPairing, *, which: Literal["model", "sae"], expected_revision: str | None = None
) -> None:
    """Fails closed if `path` follows the standard HF cache layout AND the
    org/repo it encodes disagrees with the target's ratified repo id. Does
    NOT fail if `path` doesn't follow that layout at all (e.g. a hand-staged
    directory) -- that is a "cannot verify from the path alone" case, not
    a confirmed mismatch; callers wanting a hard requirement should also
    check expected_revision is not None and reject a None parse result
    themselves (this function only ever raises on a POSITIVE mismatch)."""
    expected_repo_id = target.model_repo_id if which == "model" else target.sae_repo_id
    parsed = parse_hf_cache_snapshot_path(path)
    if parsed is None:
        return
    actual_repo_id = f"{parsed['org']}/{parsed['repo']}"
    if actual_repo_id.lower() != expected_repo_id.lower():
        raise TargetIdentityMismatch(
            f"{which} path {str(path)!r} encodes repo identity {actual_repo_id!r}, but the "
            f"ratified target is {expected_repo_id!r}. This is the exact silent-wrong-checkpoint "
            f"failure mode this validator exists to catch -- refusing to proceed."
        )
    if expected_revision is not None and parsed["revision"] != expected_revision:
        raise TargetIdentityMismatch(
            f"{which} path {str(path)!r} encodes revision {parsed['revision']!r}, but the "
            f"recorded/expected revision is {expected_revision!r}."
        )


def validate_hidden_dims(model_d_model: int, sae_d_in: int, target: TargetPairing) -> None:
    if model_d_model != sae_d_in:
        raise TargetIdentityMismatch(
            f"model hidden dim {model_d_model} != SAE d_in {sae_d_in} -- refusing to attach a "
            f"hook between mismatched dimensions."
        )
    if model_d_model != target.expected_hidden_dim:
        raise TargetIdentityMismatch(
            f"loaded hidden dim {model_d_model} != target {target.name!r}'s ratified "
            f"expected_hidden_dim {target.expected_hidden_dim}. Either the wrong model snapshot "
            f"was loaded, or the ratified expectation is stale -- both are stop conditions, not "
            f"something to silently proceed past."
        )


def validate_hook_identity(actual_hook_name: str, target: TargetPairing) -> None:
    """For sae_lens_registry targets (Gemma-it), expected_hook_name is an
    exact TL hook string ('blocks.31.hook_resid_post') and must match
    exactly. For qwen_scope_raw_pt targets, expected_hook_name is the
    release's own generic hook_point name ('resid_post') and this only
    checks that string appears in whatever hook identifier the caller
    constructed -- there is no TL hook-name convention for a raw-HF path,
    and the actual layer number is engineering-only (see module docstring),
    so an exact-match check would be checking a fact this module does not
    own."""
    if target.expected_hook_name is None:
        return
    if target.sae_format == "sae_lens_registry":
        if actual_hook_name != target.expected_hook_name:
            raise TargetIdentityMismatch(
                f"hook name {actual_hook_name!r} != target {target.name!r}'s ratified "
                f"expected_hook_name {target.expected_hook_name!r}."
            )
    else:
        if target.expected_hook_name not in actual_hook_name:
            raise TargetIdentityMismatch(
                f"hook identifier {actual_hook_name!r} does not contain the release's own "
                f"hook_point {target.expected_hook_name!r}."
            )


def validate_qwen_layer_choice(layer: int, target: TargetPairing) -> None:
    """Engineering-only gate: the layer must be a real layer the release
    covers (0..expected_num_layers-1). This is NOT a scientific check --
    it never asserts a specific layer is meaningful, only that the caller's
    choice is one the release actually shipped a file for."""
    if target.expected_num_layers is None:
        return
    if not (0 <= layer < target.expected_num_layers):
        raise TargetIdentityMismatch(
            f"layer {layer} is outside {target.name!r}'s covered range "
            f"[0, {target.expected_num_layers})."
        )
