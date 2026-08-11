# Final-pairing mechanical acceptance -- Tamia command packet for Lab Assistant 2

Scope: mechanical acceptance only (does a nonzero STEER intervention reach
the residual stream, with full diagnostics). No concept discovery, no
feature meanings, no behavioral claims. Built and unit-tested on
`final-pairing-harness` (successor to `b4481ec`, itself branched from
`f355126`); **not run against real weights or a GPU** -- no allocation was
available during this investigation. Everything below is the exact runnable
command plus what to expect; read "Unresolved ambiguities" before running
the Qwen side.

## Step 0 -- known-good differential check FIRST (required before either new pairing)

Before spending any Tamia allocation on the brand-new loaders below, confirm
the underlying mechanism and environment are healthy against the pairing
that's already fully proven: the existing `-pt` Gemma pairing, via
`scripts/legacy/gemma3_tool_diff_test.py` (accepted, f355126's own work
order). This diffs the sweep harness's call path against the tool's call
path for the SAME feature/dose/prompt/seed -- if this doesn't come back
identical, nothing below is trustworthy either, since both pairings share
the same `_make_clamp_hook` mechanism.

```bash
HF_HUB_OFFLINE=1 python scripts/legacy/gemma3_tool_diff_test.py \
  --model-path <inventory path to gemma-3-12b-pt> \
  --sae-path <inventory path to gemma-scope-2-12b-pt> \
  --feature-idx 250 --mode steer --dose-multiple 4.0 --positions all \
  --prompt "Tell me about your day." --seed 0 --max-new-tokens 64
```

Expect `identical_text: true` and `max_abs_activation_diff` near zero. If
this fails, stop -- do not proceed to Command 1/2 until it's understood,
since a failure here means the shared mechanism itself is broken on this
environment, not something specific to the new pairings.

## Prerequisites -- from Lab Assistant 1's inventory, not guessed here

This harness never guesses a local path or revision. Before running either
command, you need, from Lab Assistant 1's inventory (or your own verified
Tamia listing):

1. A local snapshot directory for the model, already downloaded, with
   `HF_HUB_OFFLINE=1` set in the environment.
2. A local snapshot directory (Gemma) or a specific `layerN.sae.pt` file
   (Qwen) for the SAE.
3. The expected revision for each, independently -- `--expected-model-revision`
   and `--expected-sae-revision` are separate flags; model and SAE
   provenance are never conflated into one shared value.

If your local paths follow the standard `huggingface_hub` cache layout
(`.../models--<org>--<repo>/snapshots/<revision>/...`), the harness verifies
repo identity and revision (if given) automatically from the path itself.
**If your paths do NOT follow that layout** (hand-staged directories), you
**must** supply the corresponding `--expected-*-revision` flag, or the
harness raises `IdentityUnverified` and refuses to proceed -- there is no
silent "cannot verify, continue anyway" path anymore. Passing the expected
revision in that case is recorded in the output as
`"verification": "explicit_revision_declared_not_path_derived"` (trusted
because Lab Assistant 1 attested to it, not because the path proves it) --
distinguishable from `"verification": "hf_cache_layout"` (mechanically
derived from the path) in the JSON's `provenance` block.

## Command 1 -- Gemma-3-12b-it + Gemma-Scope-2-12b-it

```bash
HF_HUB_OFFLINE=1 python scripts/legacy/final_pairing_harness.py \
  --target gemma-3-12b-it \
  --model-path /path/from/lab-assistant-1/inventory/gemma-3-12b-it \
  --sae-path /path/from/lab-assistant-1/inventory/gemma-scope-2-12b-it \
  --expected-model-revision <from inventory> \
  --expected-sae-revision <from inventory> \
  --feature-idx 250 \
  --mode steer \
  --raw-clamp-value 5000 \
  --positions all \
  --max-new-tokens 8 \
  --out results/final_pairing/gemma_3_12b_it_mechanical.json
```

`--expected-model-revision`/`--expected-sae-revision` are optional ONLY if
your paths already follow the HF cache layout (see above) -- include them
whenever Lab Assistant 1's inventory records a revision, since that also
activates the revision cross-check, not just the repo-identity one.
`--feature-idx 250` and `--raw-clamp-value 5000` are placeholder engineering
values (250 is in-range for a 16k-width SAE; 5000 is in the same order of
magnitude as this SAE family's previously-observed maxActApprox range,
docs/pi_directive_plan_2026_08.md) -- swap for whatever Lab Assistant 1's
inventory or your own engineering judgment prefers; neither is a concept
claim. `--positions all` is the default and the recommended choice for a
*mechanical* proof: it removes the accepted `generated_only` first-token
no-op (docs/positions_semantics.md) from the picture entirely, so a failure
here cannot be explained away by that already-understood behavior. Add
`--positions generated_only` as a second run once `all` passes, specifically
to confirm the documented first-call no-op reproduces on the real stack --
that is confirming the retained policy, not questioning it.

## Command 2 -- Qwen3.5-27B + Qwen-Scope (SAE-Res-Qwen3.5-27B-W80K-L0_50)

```bash
HF_HUB_OFFLINE=1 python scripts/legacy/final_pairing_harness.py \
  --target qwen-3.5-27b \
  --model-path /path/from/lab-assistant-1/inventory/qwen3.5-27b \
  --sae-path /path/from/lab-assistant-1/inventory/qwen-scope/layer0.sae.pt \
  --qwen-layer 0 \
  --expected-model-revision <from inventory> \
  --expected-sae-revision <from inventory> \
  --feature-idx 4096 \
  --mode steer \
  --raw-clamp-value 20 \
  --positions all \
  --max-new-tokens 8 \
  --out results/final_pairing/qwen_3_5_27b_mechanical.json
```

`--qwen-layer 0` here is the command packet's own default selection, NOT a
harness-level default -- `--qwen-layer` remains REQUIRED with no code
default (see final_pairing_targets.py's module docstring: there is no
ratified layer). Layer 0 is chosen because it's the official Qwen-Scope
release's own documented example; the harness still fully supports any
other layer 0-63 Lab Assistant 1's inventory has staged locally for later
mechanical testing. The harness cross-checks the chosen layer against the
SAE file's own name (must literally be `layer<N>.sae.pt` for the same `N`)
-- a mismatch fails closed before any weights load. `--sae-path` for this
target is the single `layerN.sae.pt` file matching `--qwen-layer`, not a
directory. `--raw-clamp-value 20` is a placeholder in this SAE's own
dtype=float32 scale -- no maxActApprox-equivalent exists for this release
yet (nothing has characterized it), which is exactly why `--raw-clamp-value`
exists as an alternative to `--dose-multiple`/`--calibration-value`.

Orchestrator review, 2026-08-11 ("Align Qwen harness with official release
and Tamia runtime"): this command now loads via `AutoModelForCausalLM` (not
`AutoModelForImageTextToText`), matching both Tamia's actual installed
transformers==5.14.1 and the official Qwen-Scope release's own application,
which hooks `model.model.layers[layer]` the same way. The harness fails
closed before generation if the loaded class isn't exactly
`Qwen3_5ForCausalLM` or lacks a callable `.generate()`
(`targets.validate_runtime_class` / `validate_has_callable_generate`), and
`QwenScopeSAE` now REQUIRES `b_dec` in the layer file and fails closed if
it's absent -- the release's own checkpoint contract lists it as present,
so there is no more silent zero-bias fallback.

**This command is still the least-verified part of this packet** -- see
"Unresolved ambiguities" below before spending a GPU allocation on it.

## Expected artifacts

Both commands write one JSON file to `--out`:

```json
{
  "target": "...",
  "positions": "...",
  "requested_mode": "...",
  "requested_dose_multiple": <float or null>,
  "requested_calibration_value": <float or null>,
  "requested_raw_clamp_value": <float or null>,
  "resolved_absolute_target": <float>,
  "dose_or_raw_label": "...",
  "provenance": {
    "target": "...",
    "model": {
      "repository": "...", "local_path": "...", "revision": "...",
      "revision_verification": "hf_cache_layout | explicit_revision_declared_not_path_derived",
      "actual_class": "HookedTransformer | Qwen3_5ForCausalLM",
      "transformers_version": "... (Qwen only, e.g. 5.14.1)",
      "selected_auto_class": "... (Qwen only, always 'AutoModelForCausalLM')",
      "decoder_attribute_path": "... (Qwen only, always 'model.layers')"
    },
    "sae": {
      "repository": "...", "release": "... or null", "sae_id": "... or null",
      "local_path": "...", "revision": "...", "revision_verification": "...",
      "resolved_files": ["... every local file the SAE loader actually read ..."],
      "actual_class": "...", "format": "sae_lens_registry | qwen_scope_raw_pt",
      "d_in": <int>, "d_sae": <int>, "k": <int or null>
    },
    "layer": {
      "engineering_layer": <int or null>, "engineering_only": "... (Qwen only, always true)",
      "hook_name": "...", "hooked_module_class": "..."
    },
    "feature_idx": <int>
  },
  "trace": [ { <one InterventionTrace per hook invocation> }, ... ],
  "verdict": {
    "hook_invocation_count": <int>,
    "prefill_call_count": <int>,
    "decode_call_count": <int>,
    "nonzero_steer_confirmed": <bool>,
    "first_disappearance_boundary": <trace record or null>
  }
}
```

`provenance` is the complete requested-to-hook chain: which repository/local
path/revision were actually used for the model and the SAE, how that
identity was verified, the actual runtime classes involved, the resolved
engineering layer and hook identity, the SAE's own structural facts
(dimensions, k), and the feature index that was steered.
`provenance.sae.resolved_files` for the Gemma target is the mechanical
proof that the sae_lens registry loader actually read from the validated
snapshot (see "Unresolved ambiguities" -- this is a real check, not a
restated assumption).

Schema note: the Gemma and Qwen branches are not perfectly symmetric.
Gemma still emits `provenance.sae.used_zero_b_dec_default: null` (a
vestigial placeholder -- the sae_lens-loaded Gemma SAE never had this
concept at all, since that field's presence/absence was always specific to
the Qwen-Scope raw-`.pt` format). Qwen no longer emits that key: the
release's own checkpoint contract lists `b_dec` as present, so
`QwenScopeSAE` now requires it and fails closed if it's missing, rather
than defaulting to zero and flagging that it did so. Only the Qwen branch
gets `transformers_version`/`selected_auto_class`/`decoder_attribute_path`/
`layer.engineering_only` -- these describe facts specific to the raw-HF
loading route this harness uses for Qwen; Gemma loads through
`HookedTransformer`/`sae_lens` instead and its provenance path was not
touched by this review.

Each `trace` record carries every per-call field this task's acceptance
criteria require: requested mode/dose-or-raw, calibration input, resolved
absolute target, backend-received value, hook name, hooked tensor shape, the
selected feature's activation before and after (an independent diagnostic
re-encode -- not guaranteed to exactly equal the assigned value; see
`wrap_hook_with_diagnostics`'s docstring for why), residual delta norm and
residual norm, and prefill-vs-decode classification. The process's own exit
code is `0` if `verdict.nonzero_steer_confirmed` is true, `1` otherwise --
safe to gate a job script on directly.

## Failure classification

| Symptom | Classification | Where to look |
|---|---|---|
| `IdentityUnverified` before any weights load | **PROVENANCE_UNVERIFIED** | The path given doesn't follow the HF cache layout and no `--expected-*-revision` was supplied. Supply the revision from Lab Assistant 1's inventory, or re-stage under the standard cache layout. This is new, stricter behavior versus the first version of this harness -- it used to silently continue here, which was itself the defect. |
| `TargetIdentityMismatch` naming a repo/revision/hook/dim/shape/k/layer-filename | **LOADER_IDENTITY_MISMATCH** | The path/file/checkpoint given does not match the ratified target. Not a bug in the harness; the guard did its job. |
| `TargetIdentityMismatch` mentioning "resolved file(s) OUTSIDE the validated snapshot" | **SAE_PROVENANCE_MISMATCH** | The SAE registry loader (Gemma side) resolved a DIFFERENT cached revision than the one validated at `--sae-path` -- likely more than one revision of this SAE is cached locally. Check `provenance.sae.resolved_files` against `--sae-path`. |
| `FileNotFoundError` for model/SAE path | **PATH_NOT_STAGED** | The inventory path doesn't exist on this machine/allocation. |
| `RuntimeError: HF_HUB_OFFLINE=1 is not set` | **ENV_NOT_OFFLINE** | Export it before invoking -- every Tamia compute-node job in this project requires it. |
| `ValueError`/`TargetIdentityMismatch` from `resolve_target_value` before any load starts | **BAD_STEER_VALUE** | `--raw-clamp-value` (or the resolved `--dose-multiple` x `--calibration-value` product) was zero, negative, NaN, or infinite. Fails before any weights load by design. |
| Gemma: `HookedTransformer.from_pretrained` raises on an unrecognized model name | **TL_REGISTRY_GAP** | Re-verify `"google/gemma-3-12b-it" in transformer_lens.loading_from_pretrained.OFFICIAL_MODEL_NAMES` on the exact installed version -- this was true for the version installed while writing this packet (3.2.1) but is a live fact, not a permanent guarantee. |
| Qwen: any exception before generation starts | **QWEN_LOAD_UNVERIFIED** | The entire Qwen load path is unverified against real weights (see below) -- capture the full traceback verbatim and stop; do not patch around it blind. |
| Runs to completion, `verdict.nonzero_steer_confirmed` is `false` | **MECHANICAL_FAILURE** -- the actual bug this task exists to catch | Read `verdict.first_disappearance_boundary` for the exact call index and classification (prefill/decode) where `residual_delta_norm` first hit zero outside the accepted `generated_only` exemption. This is the "first boundary where intervention disappears" the acceptance criteria ask for. |
| Runs to completion, `verdict.nonzero_steer_confirmed` is `true` | **MECHANICAL_PASS** | Proceed to the second `--positions` run, then to whatever behavioral work is separately authorized. Do not read a mechanical pass as a behavioral/concept claim. |

## Unresolved loader/environment ambiguities

Ranked by how much they can invalidate a run if wrong:

1. **The entire Qwen raw-HF path has never run against real Qwen3.5-27B
   weights.** transformer_lens==3.2.1 has no registry entry for this model
   (verified negative, same pin as the Tamia sprint venv), so this harness
   uses `transformers.AutoModelForCausalLM` + a raw PyTorch
   `register_forward_hook` instead of `HookedTransformer`. Orchestrator
   review, 2026-08-11: this replaced the earlier
   `AutoModelForImageTextToText` route after Tamia reported its actual
   installed transformers (5.14.1) dispatches `model_type="qwen3_5"`
   through `AutoModelForCausalLM` to `Qwen3_5ForCausalLM` instead, matching
   the official Qwen-Scope release's own application. This was verified
   two ways, not merely taken on the orchestrator's word: (a) read directly
   from the public transformers GitHub source at tag v5.14.1 (the exact
   version Tamia reports), and (b) independently re-confirmed against this
   machine's own installed transformers==5.12.1 -- which already has the
   identical `MODEL_FOR_CAUSAL_LM_MAPPING_NAMES["qwen3_5"] ==
   "Qwen3_5ForCausalLM"` mapping, and whose `Qwen3_5ForCausalLM.model` is
   already a `Qwen3_5TextModel` with `.layers` as its own `nn.ModuleList`
   (no `.language_model` indirection -- that nesting is specific to the
   multimodal `Qwen3_5ForConditionalGeneration` class this harness no
   longer loads). `Qwen3_5DecoderLayer.forward()` still returns a plain
   tensor in both versions (`register_qwen_raw_hook` now also verifies this
   at runtime and fails clearly if it ever isn't). Still, none of this has
   touched real weights. Treat the first live run as the actual test of
   this design, not a formality.
2. **`Qwen/SAE-Res-Qwen3.5-27B-W80K-L0_50`'s `b_dec` presence, the
   ReLU-then-TopK(50) activation order, and layer 0 as the release's own
   documented example are taken directly from the work order's stated
   findings, not independently re-derived this round.** A guessed URL for
   the official Qwen-Scope application's own source 404'd, and no further
   URL was guessed (per this project's policy against fabricating URLs) --
   these facts are trusted as Lab Assistant 1's inventory / orchestrator
   findings, the same trust model already used for the ratified target
   identities themselves. `QwenScopeSAE.from_state_dict` now REQUIRES
   `b_dec` and fails closed (`TargetIdentityMismatch`) if a real layer file
   turns out not to have it -- if that happens, it means this specific
   claim was wrong, not that the harness is broken.
3. **The Qwen generation call (`hf_model.generate(...)`, `transformers`'
   own `GenerationMixin`) has not been run against this specific
   causal-LM wrapper.** It is the standard, heavily-exercised HF decode
   path in general, but "general" is not "verified for
   `Qwen3_5ForCausalLM` with a raw forward hook attached to one internal
   decoder layer."
4. **The Gemma SAE-provenance proof (`resolved_files` matching
   `--sae-path`) has only been exercised with a monkeypatched fake
   `hf_hub_download` in tests, never against sae_lens's real download
   path for a `gemma_3`-conversion release.** The mechanism (patching
   `sae_lens.loading.pretrained_sae_loaders`'s own `hf_hub_download`
   reference) is verified correct by direct source reading of that module,
   but "the right function is patched" and "it behaves as expected against
   real registry internals" are different claims -- the second needs a
   real run.
5. **Gemma-3-12b-it side is comparatively low-risk but still unrun**:
   `google/gemma-3-12b-it` is confirmed in `transformer_lens`'s registry
   with the identical `d_model=3840`/`n_layers=48` as the already-proven
   `-pt` pairing, and `gemma-scope-2-12b-it-res` /
   `resid_post/layer_31_width_16k_l0_medium` is confirmed present in the
   installed `sae_lens==6.44.2` registry with the exact ratified `sae_id`.
   The remaining unknown is purely whether the actual HF snapshot bytes are
   staged on Tamia -- a Lab Assistant 1 inventory question, not an
   engineering-design one.
6. **`_patch_gemma3_safetensors_shape_lookup`'s applicability to the `-it`
   SAE release is inferred, not independently re-tested**: it's a generic
   fix for any `conversion_func="gemma_3"` release in the installed
   `sae_lens`, and `gemma-scope-2-12b-it-res` uses that same
   `conversion_func` (verified via the registry) -- reasoned to apply, not
   re-run against the `-it` release specifically.
7. **No local machine used in this investigation can load either target's
   real weights** (no GPU, and neither snapshot is staged locally) -- every
   claim above is either read from public metadata/source (config.json,
   `app.py`, `modeling_qwen3_5.py`, the installed `sae_lens`/
   `transformer_lens` registries) or derived by direct code reading, or
   proven with a synthetic/monkeypatched unit test. None of it substitutes
   for a real run.
