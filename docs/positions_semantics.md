# `positions="all"` vs `positions="generated_only"` under KV-cache decode

Both flags are consumed by the same primitive, `_make_clamp_hook` /
`_positions_mask` / `_PositionCounter` in `interplab/interventions/hooks.py`
(imported unmodified by every caller: `gemma3_sweep.run_cell`,
`gemma3_necessity.py`, and `scripts/legacy/gemma3_tool.py`'s
`generate_hooked`). All three callers also drive generation the same way --
`HookedTransformer.generate(..., use_past_kv_cache=True)` (transformer_lens's
default; none of the three callers pass `use_past_kv_cache=False`) -- so this
semantics is shared by the sweep, the necessity harness, and the tool. It is
not tool-specific, and it is not "streaming" in the sense of an incremental
per-token Gradio callback: no file in this repo calls
`HookedTransformer.generate_stream` or implements a manual token-by-token
yield loop. "KV-cache incremental decode" here means exactly what
`HookedTransformer.generate()` itself does internally, described below.

## What `HookedTransformer.generate()` actually calls, per step

(`transformer_lens/HookedTransformer.py`, `generate()`, the
`for index in range(max_new_tokens)` loop, `use_past_kv_cache=True` branch.)

- **`index == 0` (prefill):** `self.forward(residual, ...)` where `residual`
  is the embedding of the *entire* prompt, shape `[batch, prompt_len, d_model]`.
  One hook invocation, `seq_len == prompt_len`. `final_logits = logits[:, -1, :]`
  (the prompt's last position) samples the **first generated token**.
- **`index > 0` (decode step):** `self.forward(residual[:, -1:], ...,
  past_kv_cache=past_kv_cache)` -- only the *newest* token's embedding,
  shape `[batch, 1, d_model]`. One hook invocation per step, `seq_len == 1`.

So the hook fires exactly `max_new_tokens` times per generation (fewer only
if `stop_at_eos` ends it early): once over the full prompt, then once per
subsequent token, each carrying only that one new position.

`_PositionCounter` (`hooks.py`) tracks the absolute sequence position across
calls (`counter.value += seq_len` each call), so `_positions_mask` correctly
computes `abs_position >= prompt_lengths` regardless of whether a given call
carries `prompt_len` positions (the prefill) or 1 (every decode step after).
This part of the mechanism is exercised directly (not just described) by
`tests/test_interventions_identity.py::test_generated_only_steers_decode_steps_but_not_prefill`.

## `positions="all"`

`prompt_lengths=None`; `_positions_mask` is never called; every hook
invocation is unconditionally steered -- the prefill call (all prompt
positions) and every decode step. This rewrites the model's own read of the
prompt before it answers. **Every number this project has published so far
in the sweep and necessity reports was measured at `positions="all"`**
(`gemma3_tool.py`'s own docstring; `gemma3_sweep.run_cell` and
`gemma3_necessity.py` both construct their `InterventionSpec` with
`positions="all"` for every published record). The lag described below does
not apply to any published result.

## `positions="generated_only"` -- the tool's default, and its real lag

`prompt_lengths = tokens.shape[1]` (the prompt's own token count, computed
once before generation). A hook invocation is steered only where
`abs_position >= prompt_lengths`.

Consequence, precisely: the prefill call carries positions `[0, prompt_len)`
-- **all of them below `prompt_lengths`, so the entire prefill call is
masked off, a structural no-op** (`stats.append(CallStats(delta_norm=0.0,
...))`, no encode/decode round trip at all -- see `_make_clamp_hook`'s early
return). This is not merely "the prompt is left untouched" in the abstract:
the prefill call's masked-off last position is *also* the position whose
logits produce the **first generated token**. So under
`positions="generated_only"`:

- **The first generated token is always sampled with zero influence from
  the intervention.** It comes from the prompt's own (by construction,
  unsteered) final-position logits.
- **The intervention first has an effect starting with the second generated
  token.** Once token 1 is fed back in as the input to decode step `index=1`,
  its own position is now `>= prompt_lengths`, so *that* forward call's hook
  invocation *is* steered -- and the resulting (steered) logits produce
  token 2. From here the effect compounds forward through the remainder of
  the generation.

This is a real, structural property of `generate_only` combined with how
`HookedTransformer.generate()` slices its calls -- not a bug in
`_make_clamp_hook`, and not something either the sweep harness or the tool
special-cases. It has simply never been visible before, because no published
number has ever used `positions="generated_only"`; it is the tool's own
default (`DEFAULT_POSITIONS = "generated_only"`, chosen so a demo run doesn't
rewrite the model's read of the prompt -- see `gemma3_tool.py`'s module
docstring). One practical consequence: for short `max_new_tokens` or a model
that commits hard to a trajectory from its first (unsteered) token, an
observed effect under `generated_only` will be weaker, and can look closer
to the baseline, than the identical feature/dose/prompt run at
`positions="all"`. `generate_hooked()`'s new diagnostics
(`--log-level DEBUG`, see its docstring) log `CallStats` per hook
invocation; entry 0 reading `delta_norm=0.0` under `generated_only` is this
expected no-op, not evidence of a broken hook.

## Ruled out while investigating this

`gemma3_tool.py`'s `generate_hooked()` passes `bundle.sae` to
`_make_clamp_hook` directly, while `interplab.interventions.hooks.attach()`
(used by the sweep/necessity harness) wraps it in `_fp32_copy(sae)` first.
This looked like a candidate dtype divergence between the two call paths,
but both `gemma3_sweep.load_model_and_sae` and
`qwen_tool_adapter.load_model_and_sae` already unconditionally upcast the
returned SAE to `torch.float32` before handing it back
(`sae = sae.to(dtype=torch.float32...)`), independent of the `--dtype`
requested for the model itself. `bundle.sae` is fp32 in both call paths by
construction; `_fp32_copy()`'s absence in `generate_hooked()` is a
copy-safety omission (the sweep's copy also protects against mutating a
caller's live object), not a precision difference. Recorded here so this
isn't re-chased as a root-cause candidate.
