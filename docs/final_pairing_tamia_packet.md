# Final-pairing mechanical acceptance -- Tamia command packet for Lab Assistant 2

Scope: mechanical acceptance only (does a nonzero STEER intervention reach
the residual stream, with full diagnostics). No concept discovery, no
feature meanings, no behavioral claims. Built and unit-tested on
`final-pairing-harness` (branched from `f355126`); **not run against real
weights or a GPU** -- no allocation was available during this investigation.
Everything below is the exact runnable command plus what to expect; read
"Unresolved ambiguities" before running the Qwen side.

## Prerequisites -- from Lab Assistant 1's inventory, not guessed here

This harness never guesses a local path or revision. Before running either
command, you need, from Lab Assistant 1's inventory (or your own verified
Tamia listing):

1. A local snapshot directory for the model, already downloaded, with
   `HF_HUB_OFFLINE=1` set in the environment.
2. A local snapshot directory (Gemma) or a specific `layerN.sae.pt` file
   (Qwen) for the SAE.
3. Optionally, the expected revision hash for each, if Lab Assistant 1's
   inventory records one -- pass via `--expected-revision` to get the
   revision check, not just the repo-identity check.

If your local paths follow the standard `huggingface_hub` cache layout
(`.../models--<org>--<repo>/snapshots/<revision>/...`), the harness verifies
repo identity (and revision, if given) automatically and **fails closed**
before touching any weights if they don't match the ratified target. If your
paths are hand-staged and don't follow that layout, the harness cannot
verify identity from the path alone and will say so in `notes` rather than
silently assume "verified."

## Command 1 -- Gemma-3-12b-it + Gemma-Scope-2-12b-it

```bash
HF_HUB_OFFLINE=1 python scripts/legacy/final_pairing_harness.py \
  --target gemma-3-12b-it \
  --model-path /path/from/lab-assistant-1/inventory/gemma-3-12b-it \
  --sae-path /path/from/lab-assistant-1/inventory/gemma-scope-2-12b-it \
  --feature-idx 250 \
  --mode steer \
  --raw-clamp-value 5000 \
  --positions all \
  --max-new-tokens 8 \
  --out results/final_pairing/gemma_3_12b_it_mechanical.json
```

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
  --sae-path /path/from/lab-assistant-1/inventory/qwen-scope/layer31.sae.pt \
  --qwen-layer 31 \
  --feature-idx 4096 \
  --mode steer \
  --raw-clamp-value 20 \
  --positions all \
  --max-new-tokens 8 \
  --out results/final_pairing/qwen_3_5_27b_mechanical.json
```

`--qwen-layer` is REQUIRED and engineering-only -- there is no ratified
default (see final_pairing_targets.py's module docstring): pick whichever of
layers 0-63 Lab Assistant 1's inventory actually has staged locally.
`--sae-path` for this target is the single `layerN.sae.pt` file matching
`--qwen-layer`, not a directory. `--raw-clamp-value 20` is a placeholder in
this SAE's own dtype=float32 scale -- no maxActApprox-equivalent exists for
this release yet (nothing has characterized it), which is exactly why
`--raw-clamp-value` exists as an alternative to `--dose-multiple`/
`--calibration-value`.

**This command is the least-verified part of this packet** -- see
"Unresolved ambiguities" below before spending a GPU allocation on it.

## Expected artifacts

Both commands write one JSON file to `--out`:

```json
{
  "target": "...",
  "positions": "...",
  "requested_mode": "...",
  "resolved_absolute_target": <float>,
  "dose_or_raw_label": "...",
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

Each `trace` record carries every field this task's acceptance criteria
require: requested mode/dose-or-raw, calibration input, resolved absolute
target, backend-received value, hook name, hooked tensor shape, the
selected feature's activation before and after (an independent diagnostic
re-encode -- not guaranteed to exactly equal the assigned value; see
`wrap_hook_with_diagnostics`'s docstring for why), residual delta norm and
residual norm, and prefill-vs-decode classification. The process's own exit
code is `0` if `verdict.nonzero_steer_confirmed` is true, `1` otherwise --
safe to gate a job script on directly.

## Failure classification

| Symptom | Classification | Where to look |
|---|---|---|
| Process exits before any weights load, `TargetIdentityMismatch` naming a repo/revision/hook/dim | **LOADER_IDENTITY_MISMATCH** | The path given does not match the ratified target -- check which snapshot is actually staged at that path. Not a bug in the harness; the guard did its job. |
| `FileNotFoundError` for model/SAE path | **PATH_NOT_STAGED** | The inventory path doesn't exist on this machine/allocation. |
| `RuntimeError: HF_HUB_OFFLINE=1 is not set` | **ENV_NOT_OFFLINE** | Export it before invoking -- every Tamia compute-node job in this project requires it. |
| Gemma: `HookedTransformer.from_pretrained` raises on an unrecognized model name | **TL_REGISTRY_GAP** | Re-verify `"google/gemma-3-12b-it" in transformer_lens.loading_from_pretrained.OFFICIAL_MODEL_NAMES` on the exact installed version -- this was true for the version installed while writing this packet (3.2.1) but is a live fact, not a permanent guarantee. |
| Qwen: any exception before generation starts | **QWEN_LOAD_UNVERIFIED** | The entire Qwen load path is unverified against real weights (see below) -- capture the full traceback verbatim and stop; do not patch around it blind. |
| Runs to completion, `verdict.nonzero_steer_confirmed` is `false` | **MECHANICAL_FAILURE** -- the actual bug this task exists to catch | Read `verdict.first_disappearance_boundary` for the exact call index and classification (prefill/decode) where `residual_delta_norm` first hit zero outside the accepted `generated_only` exemption. This is the "first boundary where intervention disappears" the acceptance criteria ask for. |
| Runs to completion, `verdict.nonzero_steer_confirmed` is `true` | **MECHANICAL_PASS** | Proceed to the second `--positions` run, then to whatever behavioral work is separately authorized. Do not read a mechanical pass as a behavioral/concept claim. |

## Unresolved loader/environment ambiguities

Ranked by how much they can invalidate a run if wrong:

1. **Qwen3.5-27B is not in transformer_lens==3.2.1's model registry
   (verified negative, not an assumption -- checked against the exact pin
   installed locally, which matches the Tamia sprint venv's pin).** This
   harness uses a raw-HF-forward-hooks path instead (`load_qwen_target`,
   `register_qwen_raw_hook`), mirroring the already-solved
   `Gemma3ForConditionalGeneration` fallback pattern
   (`docs/pi_directive_plan_2026_08.md`'s G2 gate). The text-decoder
   resolution (`hf_model.model.language_model`) and the decoder-layer
   forward-hook signature were verified by reading
   `transformers==5.12.1`'s actual `modeling_qwen3_5.py` source (public
   package source, not weights) -- not inferred by analogy alone. Still,
   **this entire path has never run against real Qwen3.5-27B weights.**
   Treat the first live run as the actual test of this design, not a
   formality.
2. **`Qwen/SAE-Res-Qwen3.5-27B-W80K-L0_50`'s `b_dec` key is unconfirmed.**
   The release's own `app.py` (public source, read-only) never reads a
   decoder bias in its own steering shortcut, so its presence in the real
   `layerN.sae.pt` checkpoint is unverified either way.
   `QwenScopeSAE.from_state_dict` defaults to a zero bias and sets
   `used_zero_b_dec_default=True` when the key is absent -- check that flag
   in a real run's trace before trusting `decode()`'s reconstruction
   quality.
3. **The Qwen generation call (`hf_model.generate(...)`, `transformers`'
   own `GenerationMixin`) has not been run against this specific
   multimodal wrapper.** It is the standard, heavily-exercised HF decode
   path in general, but "general" is not "verified for
   `Qwen3_5ForConditionalGeneration` with a raw forward hook attached to
   one internal decoder layer."
4. **Gemma-3-12b-it side is comparatively low-risk but still unrun**:
   `google/gemma-3-12b-it` is confirmed in `transformer_lens`'s registry
   with the identical `d_model=3840`/`n_layers=48` as the already-proven
   `-pt` pairing, and `gemma-scope-2-12b-it-res` /
   `resid_post/layer_31_width_16k_l0_medium` is confirmed present in the
   installed `sae_lens==6.44.2` registry with the exact ratified `sae_id`.
   The remaining unknown is purely whether the actual HF snapshot bytes are
   staged on Tamia -- a Lab Assistant 1 inventory question, not an
   engineering-design one.
5. **`_patch_gemma3_safetensors_shape_lookup`'s applicability to the `-it`
   SAE release is inferred, not independently re-tested**: it's a generic
   fix for any `conversion_func="gemma_3"` release in the installed
   `sae_lens`, and `gemma-scope-2-12b-it-res` uses that same
   `conversion_func` (verified via the registry) -- reasoned to apply, not
   re-run against the `-it` release specifically.
6. **No local machine used in this investigation can load either target's
   real weights** (no GPU, and neither snapshot is staged locally) -- every
   claim above is either read from public metadata/source (config.json,
   `app.py`, `modeling_qwen3_5.py`, the installed `sae_lens`/
   `transformer_lens` registries) or derived by direct code reading. None of
   it substitutes for a real run.
