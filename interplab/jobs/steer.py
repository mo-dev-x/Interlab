"""interplab.jobs.steer (SS7/SS8, GATE G3 consumer) -- generates across all
configured arms/scales for one (checkpoint, feature), using SS7's `attach()`
exactly as implemented; `corpus_max` and matched-feature sampling come
exclusively from the `FeatureIndex` search API (§4 A7: "the ONLY legal
source of steering units"). Claim mode (a `feature_certificate_hash` in the
config) additionally produces the two hooked control arms
(`random_direction`, `random_feature`) via `interventions.control_arms` and
the no-hook `prompt_baseline` arm, and blinds the generation order at
creation (A9 `blinding.shuffled = true`).

ED-22: `prompt_baseline` is generated from the config's
`prompt_baseline_prompts` -- researcher-authored scientific content,
index-aligned one-to-one with `prompts`, never mechanically derived from
them. Required in claim mode (checked here, not in the schema, since the
requirement is conditional on `feature_certificate_hash`); optional in
explore mode. `generations_dir` is a required config field -- there is no
default results/ path.

Reads A5 (+ its `weights`/`model` subject refs), A7 (opened via
`FeatureIndex`, search API only), A8 when claim-mode; writes A9 (+
generations dir) directly to whatever `registry_root` it's given --
`registry/` when local, or a cluster outbox dir when the launcher passes
one (§7.1, same pattern as every other cert-lane job; ED-7: this GPU stage
runs on the cluster for production checkpoints). ED-34: checkpoint weights
resolve via `local:`/`tamia:`, the base model via `local:`/`tamia:`/`hf:`
(a pinned-download acquisition step for `hf:`, never a second construction
path).

Blinding is implemented inline, not via `interplab.evaluation.blinding`:
§1's dependency edges give `jobs.steer` only `core, registry, interventions,
characterization [SEARCH API ONLY]` -- it cannot import `interplab.evaluation`
at all. This is the minimal shuffle-and-map step (Ground Rule 2: duplicate
rather than cross-import); SS8's own `blinding` module is the separate,
judge-facing step a future `jobs.judge` uses.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import torch
from sae_lens import SAE

from interplab.characterization.feature_index import FeatureIndex
from interplab.core import configs, envelope, hashing, uris
from interplab.core import environment as environment_mod
from interplab.core.errors import ContractViolationError, EnvironmentBaselineError
from interplab.interventions.control import control_arms
from interplab.interventions.hooks import attach
from interplab.interventions.spec import InterventionSpec, to_dict
from interplab.registry.registry import REGISTRY_ROOT, REPO_ROOT
from interplab.registry.registry import get as registry_get
from interplab.registry.registry import put as registry_put
from interplab.registry.run_card import new_run_card

_ARM_ORDER = ["steered", "baseline", "random_direction", "random_feature", "prompt_baseline"]


def _load_local_hooked_transformer(model_dir: str, *, device: str = "cpu", dtype: torch.dtype = torch.float32):
    """Duplicated from `interplab.certification.model_loading` (§1 Ground
    Rule 2: `jobs.steer` may only import `core`, `registry`,
    `interventions`, and `characterization` [search API only] -- not
    `certification`). Fourth duplicate of this loader in the codebase
    (`characterization.model_loading`, `validation.model_loading`,
    `certification.model_loading` are the other three); no package
    `jobs.steer` is allowed to import exposes it."""
    from transformer_lens import HookedTransformer
    from transformer_lens.loading_from_pretrained import get_pretrained_model_config
    from transformer_lens.pretrained.weight_conversions import convert_qwen2_weights
    from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer

    hf_config = AutoConfig.from_pretrained(model_dir)
    architecture = hf_config.architectures[0]
    converters = {"Qwen2ForCausalLM": convert_qwen2_weights}
    if architecture not in converters:
        raise NotImplementedError(
            f"no transformer_lens weight-conversion mapping for architecture {architecture!r}; "
            f"known: {sorted(converters)}"
        )
    hf_model = AutoModelForCausalLM.from_pretrained(model_dir)
    tokenizer = AutoTokenizer.from_pretrained(model_dir)
    cfg = get_pretrained_model_config(model_dir, fold_ln=False, device=device, dtype=dtype)
    state_dict = converters[architecture](hf_model, cfg)
    model = HookedTransformer(cfg, tokenizer=tokenizer)
    model.load_and_process_state_dict(
        state_dict, fold_ln=False, center_writing_weights=False, center_unembed=False
    )
    model.eval()
    return model


def _resolve_hf_model_snapshot(location: str) -> Path:
    """ED-34: `hf:` is an acquisition scheme, never a second construction
    path -- `HookedTransformer.from_pretrained`'s processing defaults
    (`fold_ln=True`, ...) diverge from `_load_local_hooked_transformer`'s
    deliberate `fold_ln=False`/`center_writing_weights=False`/
    `center_unembed=False`, which would silently change `hook_resid_post`.
    So this only downloads the pinned revision to a local directory, fed
    unchanged to the one loader above. Duplicated per the same Ground Rule
    2 boundary as `_load_local_hooked_transformer` itself."""
    from huggingface_hub import snapshot_download

    parsed = uris.parse(location)
    if parsed.scheme != "hf":
        raise uris.URIError(f"_resolve_hf_model_snapshot only accepts 'hf:' URIs, got {location!r}")
    repo, _, revision = parsed.value.partition("@")

    scratch = os.environ.get("SCRATCH")
    if not scratch:
        raise uris.URIError(
            f"cannot resolve {location!r}: $SCRATCH is not set -- hf: model acquisition downloads "
            "into $SCRATCH/hf_cache, only meaningful on a machine with the cluster scratch mounted"
        )
    cache_dir = Path(scratch) / "hf_cache"
    snapshot_dir = snapshot_download(
        repo_id=repo, revision=revision, cache_dir=str(cache_dir), local_files_only=True
    )
    return Path(snapshot_dir)


def _resolve_model_location(location: str) -> Path:
    parsed = uris.parse(location)
    if parsed.scheme == "local":
        return uris.resolve_local(location)
    if parsed.scheme == "tamia":
        return uris.resolve_tamia(location)
    if parsed.scheme == "hf":
        return _resolve_hf_model_snapshot(location)
    raise NotImplementedError(f"cannot resolve model location scheme {parsed.scheme!r}: {location!r}")


def _get_or_raise(content_hash: str, *, registry_root: Path, role: str) -> dict:
    try:
        return registry_get(content_hash, registry_root=registry_root)
    except Exception as e:
        raise ContractViolationError(f"could not resolve {role} {content_hash!r}: {e}") from e


def _find_subject_ref(artifact: dict, role: str) -> dict:
    for ref in artifact["subject"]:
        if ref["role"] == role:
            return ref
    raise ContractViolationError(
        f"{artifact['artifact_type']} {artifact['self_hash']!r} has no subject entry with role {role!r}"
    )


def _load_local(location: str, *, what: str) -> Path:
    parsed = uris.parse(location)
    if parsed.scheme == "tamia":
        return uris.resolve_tamia(location)
    if parsed.scheme != "local":
        raise NotImplementedError(
            f"steer can only load {what} from local:/tamia: URIs; got {location!r}"
        )
    return uris.resolve_local(location)


def _generate(model, sae, spec: InterventionSpec, prompt: str, sampling: dict) -> str:
    tokens = model.to_tokens(prompt)
    prompt_lengths = tokens.shape[1] if spec.positions == "generated_only" else None
    torch.manual_seed(sampling["seed"])
    with attach(model, sae, spec, prompt_lengths=prompt_lengths):
        output = model.generate(
            tokens,
            max_new_tokens=sampling["max_new_tokens"],
            temperature=sampling["temperature"],
            top_p=sampling["top_p"],
            do_sample=sampling["temperature"] > 0,
            verbose=False,
        )
    return model.to_string(output[0, tokens.shape[1] :])


def run(
    config_path: str | Path,
    *,
    registry_root: Path = REGISTRY_ROOT,
    repo_root: Path = REPO_ROOT,
) -> int:
    config = configs.load_and_validate(config_path, "steer")
    checkpoint_hash = config["checkpoint_hash"]
    manifest_hash = config["characterization_manifest_hash"]
    feature_cert_hash = config.get("feature_certificate_hash")
    claim_mode = feature_cert_hash is not None

    checkpoint_ref = {
        "content_hash": checkpoint_hash,
        "location": f"local:registry/sae_checkpoint/{hashing.short_hash(checkpoint_hash)}.json",
        "role": "sae_checkpoint",
    }
    manifest_ref = {
        "content_hash": manifest_hash,
        "location": f"local:registry/characterization_manifest/{hashing.short_hash(manifest_hash)}.json",
        "role": "characterization_manifest",
    }
    inputs = [checkpoint_ref, manifest_ref]
    feature_cert_ref = None
    if claim_mode:
        feature_cert_ref = {
            "content_hash": feature_cert_hash,
            "location": f"local:registry/feature_certificate/{hashing.short_hash(feature_cert_hash)}.json",
            "role": "feature_certificate",
        }
        inputs.append(feature_cert_ref)

    handle = new_run_card("steer", config_path, registry_root=registry_root, repo_root=repo_root, inputs=inputs)

    status, exit_code, outcome_line = "failed", 4, "unhandled error"
    outputs: list[dict] = []
    environment: dict | None = None

    try:
        # ED-32: asserted at startup, before any registry/model access.
        environment = environment_mod.build_certification_environment()
        environment_mod.check_sae_stack_baseline(environment)

        checkpoint = _get_or_raise(checkpoint_hash, registry_root=registry_root, role="sae_checkpoint")
        weights_ref = _find_subject_ref(checkpoint, "weights")
        model_ref = _find_subject_ref(checkpoint, "model")
        sae = SAE.load_from_pretrained(str(_load_local(weights_ref["location"], what="SAE weights")), device="cpu")
        model = _load_local_hooked_transformer(str(_resolve_model_location(model_ref["location"])))

        _get_or_raise(manifest_hash, registry_root=registry_root, role="characterization_manifest")
        feature_index_obj = FeatureIndex.open(manifest_hash, registry_root=registry_root)
        target_feature = config["feature_index"]
        if target_feature >= feature_index_obj.n_features:
            raise ContractViolationError(
                f"feature_index {target_feature} is out of range for an index with "
                f"{feature_index_obj.n_features} features"
            )
        corpus_max = feature_index_obj.corpus_max(target_feature)

        matched_feature_index = matched_feature_corpus_max = None
        if claim_mode:
            _get_or_raise(feature_cert_hash, registry_root=registry_root, role="feature_certificate")
            matched_feature_index = feature_index_obj.sample_matched_frequency(
                target_feature,
                rng_seed=config.get("matched_frequency_rng_seed", 0),
                band=config.get("matched_frequency_band", 3.0),
                exclude=frozenset({target_feature}),
            )
            matched_feature_corpus_max = feature_index_obj.corpus_max(matched_feature_index)

        prompts = config["prompts"]
        scales = config["scales_in_max_units"]
        sampling = config["sampling"]
        positions = config.get("positions", "all")
        direction_seed = config.get("direction_seed", 0)
        prompt_baseline_prompts = config.get("prompt_baseline_prompts")

        if claim_mode and not prompt_baseline_prompts:
            raise ContractViolationError(
                "claim mode requires prompt_baseline_prompts (ED-22): researcher-authored "
                "scientific content, index-aligned one-to-one with prompts, generated with "
                "no intervention hook -- never mechanically derived from prompts"
            )
        if prompt_baseline_prompts is not None and len(prompt_baseline_prompts) != len(prompts):
            raise ContractViolationError(
                f"prompt_baseline_prompts must be index-aligned one-to-one with prompts: "
                f"got {len(prompt_baseline_prompts)} prompt_baseline_prompts for {len(prompts)} prompts"
            )

        noop_spec = InterventionSpec(
            kind="noop", feature_index=None, value_in_max_units=None, corpus_max=None,
            positions="all", checkpoint_hash=checkpoint_hash, direction_seed=None,
        )

        records: list[dict] = []
        for i, prompt in enumerate(prompts):
            text = _generate(model, sae, noop_spec, prompt, sampling)
            records.append({"arm": "baseline", "scale": None, "prompt_id": f"p{i}", "prompt": prompt, "text": text})
        if prompt_baseline_prompts:
            for i, pb_prompt in enumerate(prompt_baseline_prompts):
                text = _generate(model, sae, noop_spec, pb_prompt, sampling)
                records.append(
                    {"arm": "prompt_baseline", "scale": None, "prompt_id": f"p{i}", "prompt": pb_prompt, "text": text}
                )

        for scale in scales:
            steered_spec = InterventionSpec(
                kind="clamp", feature_index=target_feature, value_in_max_units=scale, corpus_max=corpus_max,
                positions=positions, checkpoint_hash=checkpoint_hash, direction_seed=None,
            )
            for i, prompt in enumerate(prompts):
                text = _generate(model, sae, steered_spec, prompt, sampling)
                records.append({"arm": "steered", "scale": scale, "prompt_id": f"p{i}", "prompt": prompt, "text": text})

            if claim_mode:
                add_direction_spec, matched_feature_spec = control_arms(
                    steered_spec,
                    matched_feature_index=matched_feature_index,
                    matched_feature_corpus_max=matched_feature_corpus_max,
                    direction_seed=direction_seed,
                )
                for i, prompt in enumerate(prompts):
                    text = _generate(model, sae, add_direction_spec, prompt, sampling)
                    records.append(
                        {"arm": "random_direction", "scale": scale, "prompt_id": f"p{i}", "prompt": prompt, "text": text}
                    )
                for i, prompt in enumerate(prompts):
                    text = _generate(model, sae, matched_feature_spec, prompt, sampling)
                    records.append(
                        {"arm": "random_feature", "scale": scale, "prompt_id": f"p{i}", "prompt": prompt, "text": text}
                    )

        # Inline blinding (§1: jobs.steer cannot import interplab.evaluation):
        # shuffle write order + a separate map file, satisfying A9's
        # blinding.shuffled = true at creation.
        blinding_seed = config.get("blinding_rng_seed", 0)
        order = np.random.default_rng(blinding_seed).permutation(len(records))
        shuffled = [records[int(i)] for i in order]

        gen_dir = Path(config["generations_dir"])
        if not gen_dir.is_relative_to(uris.REPO_ROOT):
            raise ContractViolationError(
                f"generations_dir {gen_dir} must resolve inside the repo root {uris.REPO_ROOT} -- it becomes a "
                "registered local: subject entry, which is only valid for repo-relative paths"
            )
        gen_dir.mkdir(parents=True, exist_ok=True)
        (gen_dir / "generations.json").write_text(
            json.dumps({"records": shuffled}, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (gen_dir / "blinding_map.json").write_text(
            json.dumps(
                {
                    f"blind-{rank:06d}": {"arm": r["arm"], "scale": r["scale"], "prompt_id": r["prompt_id"]}
                    for rank, r in enumerate(shuffled)
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        gen_hash = hashing.hash_directory(gen_dir)
        gen_location = f"local:{gen_dir.relative_to(uris.REPO_ROOT).as_posix()}"

        arms_payload = []
        for arm_name in _ARM_ORDER:
            arm_records = [r for r in records if r["arm"] == arm_name]
            if not arm_records:
                continue
            scales_present = sorted({r["scale"] for r in arm_records if r["scale"] is not None})
            arms_payload.append(
                {
                    "arm": arm_name,
                    "scales_in_max_units": [float(s) for s in scales_present],
                    "generations_ref": {"content_hash": gen_hash, "location": gen_location},
                }
            )

        payload = {
            "spec": to_dict(
                InterventionSpec(
                    kind="clamp", feature_index=target_feature, value_in_max_units=None, corpus_max=corpus_max,
                    positions=positions, checkpoint_hash=checkpoint_hash, direction_seed=None,
                )
            ),
            "arms": arms_payload,
            "blinding": {"shuffled": True, "map_ref": f"local:{gen_dir.relative_to(uris.REPO_ROOT).as_posix()}/blinding_map.json"},
            "sampling": sampling,
            "lodestar": None,
            "capability_delta": None,
        }

        subject = [checkpoint_ref]
        if feature_cert_ref is not None:
            subject.append(feature_cert_ref)

        artifact = envelope.dump(
            artifact_type="intervention_result",
            schema_version=1,
            created_by=handle.created_by,
            subject=subject,
            payload=payload,
        )
        result_hash = registry_put(artifact, registry_root=registry_root)

        outputs = [
            {"content_hash": gen_hash, "location": gen_location, "role": "generations"},
            {
                "content_hash": result_hash,
                "location": f"local:registry/intervention_result/{hashing.short_hash(result_hash)}.json",
                "role": "intervention_result",
            },
        ]
        status, exit_code = "completed", 0
        outcome_line = (
            f"intervention_result {hashing.short_hash(result_hash)}; "
            f"{len(records)} generations across {len(arms_payload)} arms (claim_mode={claim_mode})"
        )

    except ContractViolationError as e:
        status, exit_code = "failed", 3
        outcome_line = str(e)
    except EnvironmentBaselineError as e:  # ED-32: a designed refusal, not an unexpected failure
        status, exit_code = "failed", 4
        outcome_line = f"environment baseline violated: {e}"
    except Exception as e:  # deliberate catch-all mapping to exit 4 (§6.2)
        status, exit_code = "failed", 4
        outcome_line = f"unexpected error: {e}"
    finally:
        handle.finalize(status, outputs, exit_code, outcome_line=outcome_line, environment=environment)

    return exit_code
