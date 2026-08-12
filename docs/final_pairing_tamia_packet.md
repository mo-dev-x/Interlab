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

Orchestrator review, 2026-08-13 ("repair Step 0"): live job 406092 ran
exactly this command and got `identical_text: false` (`first_char_divergence:
1`) with `max_abs_activation_diff: 0.0` / `mean_abs_activation_diff: 0.0` --
yet the process exited `0`. Two independent defects, both fixed:

1. Both call paths used to sample (`do_sample=True, temperature=0.7,
   top_p=0.9`) under a fixed `torch.manual_seed(seed)` -- a fixed seed does
   not guarantee two different code paths consume the RNG stream
   identically, so sampling could diverge even when the underlying mechanism
   is fully correct. Both paths now decode GREEDILY (`do_sample=False`) --
   no RNG dependency at all, so a real divergence can no longer be
   dismissed as, or hidden by, sampling noise. `--max-new-tokens 64` is
   unchanged; no new flag was added -- the switch to greedy decoding is
   internal to the script.
2. `main()` used to compute a full diff report and then unconditionally
   `return 0`, never consulting any field it had just computed. The JSON
   now carries an explicit `gate_criteria` object and a top-level
   `gate_passed` boolean, and the process exit code is `0` iff
   `gate_passed` is `true`, `1` otherwise -- safe to gate a job script on
   directly (see "Expected artifacts" below for the exact schema).

Expect `identical_text: true`, `identical_token_ids: true`, and
`max_abs_activation_diff: 0.0` EXACTLY (not merely small -- a real forward
pass over already-generated tokens has no sampling inside it, so this is
not a new tolerance, it is what a correct stack should always produce). If
`gate_passed` is `false`, STOP -- do not proceed to Command 1/2, and do not
weaken any of the three criteria to force a pass; a genuine divergence
under greedy decoding is itself the finding to report.

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

Orchestrator review, 2026-08-12 ("Fail closed on the exact Gemma SAE
subdirectory", plus same-day addendum "HF snapshot symlink containment"):
the command line above is UNCHANGED -- `--sae-path` still means the SAE
snapshot ROOT directory, exactly as before. What changed is internal. The
final Gemma Scope IT snapshot ships FIVE different SAE families that all
share the identical `layer_31_width_16k_l0_medium` suffix (`attn_out`,
`mlp_out`, `resid_post`, `transcoder`, `transcoder affine`). The
pre-existing snapshot-level check only proves the loaded files fall
somewhere under the correctly-validated snapshot as a whole -- it cannot,
by itself, distinguish which of the five sibling families was actually
loaded. This run now also runs two further, complementary checks before
generation (before even the SAE dtype conversion):

1. **Logical**: fails closed if any resolved file's own (never-
   dereferenced) snapshot-relative path falls outside
   `resid_post/layer_31_width_16k_l0_medium/` specifically, even one that
   still lives inside the correct snapshot as a whole.
2. **Physical**: a real huggingface_hub cache entry is normally a SYMLINK
   whose dereferenced target legitimately lives in a sibling `blobs/`
   store outside the snapshot tree entirely -- so the logical check above
   never dereferences anything, by design, and therefore cannot catch a
   symlink whose target has been swapped to point somewhere else
   entirely. This second check dereferences ONLY symlinks that are
   actually present on disk, and fails closed if the target has left the
   repository's own cache root (`models--<org>--<repo>`, the parent both
   `snapshots/` and `blobs/` share) -- without requiring the flat,
   hash-named blob store to retain any `sae_id` directory structure.

No new flag is needed for either: both are derived directly from the
ratified `sae_id` and the `--sae-path` you already supply.

Orchestrator review, 2026-08-13 ("Separate Gemma artifact identity from
loader identity", live job 406092): the command line above is STILL
UNCHANGED. What was wrong internally: `load_gemma_it_target` was passing
`sae_id` ("resid_post/layer_31_width_16k_l0_medium", the real artifact
subdirectory) directly to `SAE.from_pretrained(sae_id=...)`, which fails --
`gemma-scope-2-12b-it-res`'s own `saes_map` is keyed by a FLAT id
(`layer_31_width_16k_l0_medium`, no `resid_post/` prefix); the artifact
path is that key's VALUE, not a key itself. There are now three distinct,
independently-recorded identities (see `provenance.sae` below): `release`
(`gemma-scope-2-12b-it-res`), `loader_sae_id` (the flat key, what
`SAE.from_pretrained` actually receives), and `sae_id` (the artifact
subdirectory, unchanged, still feeding the logical/physical subdirectory
guards above). The harness now verifies `loader_sae_id` is actually
registered for `release` -- against the real, installed `sae_lens`
registry, not a guess -- BEFORE the ~24GB model even loads.

Orchestrator review, 2026-08-14 ("Make Gemma SAE loading use the exact
pinned local snapshot", live job 406259): the command line above is STILL
UNCHANGED -- `--sae-path` remains the pinned SAE snapshot ROOT directory.
With the loader id fixed, the model loaded and the flat id validated as
registered, but `SAE.from_pretrained` still failed before any weights
loaded: none of `sae_lens`'s own `hf_hub_download` call sites for a
`gemma_3`-conversion release pass `revision=`, so `huggingface_hub`
defaults it to `"main"` and tries to resolve `refs/main -> commit hash`
from the LOCAL cache before touching any file content. Lab Assistant 1's
snapshot was staged by pinning `snapshot_download` directly to the
immutable commit sha, never to the branch name `"main"`, so no local
`refs/main` file exists to resolve that default against -- offline
resolution failed before the subdirectory/symlink guards above ever got a
chance to run, even though the exact files those guards check were
sitting on disk the whole time.

**`refs/main` and `HF_HUB_CACHE` are NOT required for Gemma SAE loading
when `--sae-path` is supplied.** `_capture_sae_download_paths` now
installs a full REPLACEMENT for `sae_lens.loading.pretrained_sae_loaders`'s
own `hf_hub_download` reference (not a pass-through wrapper around it):
every request `sae_lens` makes during SAE loading is mapped directly onto
a file inside the validated `--sae-path` snapshot
(`targets.resolve_local_gemma_sae_path`) -- no Hub ref lookup, no network,
no cache mutation, by construction, regardless of whether `refs/main`
exists or `HF_HUB_CACHE` is set to anything at all. The two
`_patch_gemma3_safetensors_shape_lookup` call sites go through the SAME
resolver now (module-qualified `psl.hf_hub_download`, not a second,
independently-imported reference), so the shape-lookup call this harness
already routes away from raw HTTP does not reopen the same offline
`refs/main` failure through a side door. Fails closed, before any file is
even read, on: a repository id other than the ratified target (defensive
-- should never actually happen from real `sae_lens` call sites); an
explicit `revision` other than the default or `"main"` (branch-dependent
resolution requests are rejected rather than silently served the pinned
snapshot's files instead); an absolute filename or a `..` path-traversal
segment; and a filename resolving outside `resid_post/layer_31_width_16k_
l0_medium/` specifically (the same sibling-family case the logical/
physical guards above catch post-hoc, now closed one request earlier).

Orchestrator review, 2026-08-15 ("Correct and fully exercise the local
safetensors shape shim", live job 406826): the local-only resolver above
reached the correct, locally-resolved `params.safetensors` file with no
Hub/network/`refs/main` involved -- proving the 2026-08-14 fix worked --
then failed deterministically one function further in, inside
`_local_get_safetensors_tensor_shapes` itself: `for k in f` (the
2026-08-14 wording of this shim) treats the real `safe_open` object as
directly iterable. It is not. `safe_open` is a Rust extension type with no
`__iter__` at all (verified directly against the installed
`safetensors==0.4.5`, not merely by reading source), so that line raised
`TypeError: 'builtins.safe_open' object is not iterable` on every real
call, every time -- a defect no test before this review could have caught,
because every existing test of this shim mocked `safe_open` itself rather
than exercising the real installed API. This project's own two
pre-existing, already-accepted copies of this same patch
(`gemma3_sweep.py`, `gemma3_necessity.py` -- Engineer 2 owned, neither
touched by this review) already used the correct `for k in f.keys()`; only
this harness's own copy had drifted from that pattern.

Fixed by using `f.keys()` (not bare iteration), and the shape API is now
exercised, in the test suite, against a REAL temporary safetensors file
via `safetensors.torch.save_file` and the real `safe_open` -- not a mock
-- covering: multiple real tensor keys with exact shapes; a genuinely
empty (zero-tensor) safetensors file, which the library can and does
create; a malformed/non-safetensors file; a missing local file; and the
full chain from the local-only resolver through to a real shape read.
Every failure mode now names the resolved local path in its message (some
real underlying exceptions, e.g. `safetensors_rust.SafetensorError` for a
malformed file, do not include the path on their own). **The complete real
`SAE.from_pretrained` load -- config parsing, weight loading, and `SAE`
construction end-to-end through this shim, not just the shim in
isolation -- still awaits the next Tamia run.**

Orchestrator review, 2026-08-16 ("Correct and comprehensively audit Gemma
path-containment guards", live job 406957): job 406957 proved deterministic
Step 0, local-only SAE resolution, loader-id validation, and the corrected
shape shim all work. It then found `validate_sae_files_match_snapshot`
(the OLDEST of the three SAE-file/path validators, written 2026-08-10 --
before the 2026-08-12 subdirectory guard and the 2026-08-16 physical-cache
guard existed to model against) still called `Path.resolve()`, which
FOLLOWS symlinks -- a real Hugging Face snapshot entry is normally a
SYMLINK into a SIBLING `blobs/` store, so resolving a legitimate resolved
file lands it OUTSIDE the snapshot directory entirely, and this check
incorrectly labeled every real symlinked file "outside the snapshot." It
also used `str.startswith()`, a SEPARATE, opposite-direction defect: a
sibling snapshot directory sharing the same string prefix (`snapshots/
<revision>-evil`) would incorrectly PASS. **Fixed identically to how
`validate_sae_files_match_expected_subdirectory` (2026-08-12) already
handled this**: `os.path.abspath` (never follows symlinks) on both sides,
`Path.is_relative_to` (full-path-segment containment) instead of a string
prefix. Physical symlink dereferencing remains EXCLUSIVELY the job of
`validate_sae_symlink_targets_stay_in_repository_cache` -- this function
now never calls `Path.resolve()`/`os.path.realpath` at all.

**Path-containment audit** (every `Path.resolve()`/`os.path.realpath()`/
`str.startswith()`/`is_relative_to`/`commonpath` occurrence in
`final_pairing_targets.py`, `final_pairing_harness.py`,
`final_pairing_gpu_job.py`, and `interplab/interventions/hooks.py` --
the only shared hook/loader code this harness imports):

| Location | Category | Verdict |
|---|---|---|
| `final_pairing_targets.validate_sae_files_match_snapshot` | LOGICAL snapshot identity | **Was defective (`.resolve()` + `startswith`) -- FIXED this review** to `os.path.abspath` + `Path.is_relative_to`, matching its two newer siblings below. |
| `final_pairing_targets.validate_sae_files_match_expected_subdirectory` | LOGICAL SAE-family-subdirectory identity | Already correct (2026-08-12): `os.path.abspath` + `Path.is_relative_to`, never dereferences. Unchanged. |
| `final_pairing_targets.resolve_local_gemma_sae_path`'s subdirectory check | LOGICAL SAE-family-subdirectory identity (request-time, pre-2026-08-14 fix) | Already correct: `PurePosixPath.is_relative_to` on the requested filename string, never touches the filesystem at all for this check. Unchanged. |
| `final_pairing_targets.validate_sae_symlink_targets_stay_in_repository_cache` | PHYSICAL symlink-target containment | Already correct (2026-08-12 addendum): `os.path.realpath` (intentional -- this IS the one check meant to dereference) + `Path.is_relative_to`. This remains the ONLY function in this module permitted to call `os.path.realpath`. Unchanged. |
| `resolve_local_gemma_sae_path`'s absolute-filename rejection (`normalized.startswith("/")`) | Input syntax validation, NOT path containment | Not a containment/identity comparison against a boundary -- a literal-string check for an absolute-path-shaped request, applied before any `Path` object is even constructed. Correct as `startswith`; `is_relative_to` doesn't apply to this check at all. Unchanged. |
| `final_pairing_harness.py`: `REPO_ROOT`/`sys.path`/`_load_gemma3_tool`'s `Path(__file__).resolve()` (3 occurrences) | N/A -- resolves this SCRIPT's own on-disk location | Not SAE/model identity or containment logic; no untrusted symlink ambiguity involved. Unchanged. |
| `final_pairing_gpu_job.py`: `SCRIPT_DIR = Path(__file__).resolve().parent` | N/A -- same as above | Unchanged. |
| `interplab/interventions/hooks.py` | N/A | Zero `Path.resolve`/`realpath`/`startswith`/`is_relative_to` occurrences -- this module operates on tensors/activations only, no filesystem paths at all. |
| `gemma3_sweep.py` / `gemma3_necessity.py`: `str(Path(args.model_path).resolve())`/`.../sae_path...` in provenance-display payloads | N/A -- display-only, no containment comparison paired with it | Frozen, Engineer-2-owned files (this harness's own docstring: "Nothing here edits gemma3_sweep.py, gemma3_necessity.py..."), out of write-scope regardless. Reviewed, not edited. |
| `gemma3_sweep.py`/`gemma3_tool.py`/etc.: `device.startswith("cuda")`, commit-message/diff-line `startswith("#")`/`"@@"`, `montreal_qwen.py`'s slash-command parser | N/A -- not path containment at all | String-content checks unrelated to filesystem paths. Not audited further; out of scope by construction. |

**GPU-job preflight** (`final_pairing_gpu_job.py`): a `symlink_
containment_preflight` step runs BEFORE Step 0 -- a REAL Hugging Face
cache fixture (`models--<repo>/blobs/<blob-id>`, `snapshots/<revision>/
resid_post/.../config.json -> ../../../blobs/<blob-id>`) exercised against
all three actual validators, inside the real allocation where real
symlinks and this cache's true on-disk shape both exist (unlike the login
node or this project's own Windows dev machine). A preflight failure stops
the job immediately -- neither Step 0 nor either Gemma scenario is
attempted -- recorded as its own `preflight` entry in `job_result.json`,
distinct from `step0`.

Orchestrator review, 2026-08-17 ("Make the Tamia symlink preflight
self-contained and pytest-free"): Lab Assistant B correctly stopped before
submission because `~/sprint-venv` (Tamia's real, shared scientific
environment) has no pytest/pluggy/iniconfig installed, and installing them
there is forbidden. **The scheduled Tamia preflight has no pytest
dependency of any kind.** `final_pairing_gpu_job.py` now invokes
`scripts/legacy/final_pairing_symlink_preflight.py` directly via
`sys.executable` -- a standalone, standard-library-only script that
imports and calls the SAME production validators
(`final_pairing_targets.py`) directly; no predicate is duplicated. It
builds its own disposable HF-cache-shaped fixture inside `$SLURM_TMPDIR`
(or an explicit `--work-dir`, never the shared HF cache), runs exactly 11
real-symlink cases, writes one deterministic JSON artifact (schema below),
and exits `0` only if all 11 executed and all 11 passed. The wrapper does
not stop at trusting that exit code alone: it independently re-reads the
JSON artifact and re-verifies `executed_count == 11`, `passed_count ==
11`, and `overall_passed == true` before proceeding to Step 0 -- defense
in depth against a hypothetical bug in the script's own exit-code logic.
**Scheduled acceptance needs only `~/sprint-venv`'s Python and the
archived repository -- nothing else.**

The pytest-based file (`tests/test_final_pairing_symlink_preflight_
nightly.py`) still exists, unchanged in purpose, as independent DEVELOPER
regression coverage (marked `@pytest.mark.nightly`, run via `pytest ... -m
nightly` on a developer or CI machine that already has pytest installed)
-- it is simply **not required on Tamia** and is no longer what the
scheduled job invokes. It now also includes one test that runs the
standalone script itself as a real subprocess, proving the actual artifact
Tamia runs, not just the validators it calls.

`final_pairing_symlink_preflight.py`'s JSON schema:

```json
{
  "preflight_name": "final_pairing_symlink_preflight",
  "schema_version": 1,
  "source_commit": "46a8643 or null",
  "platform": "... (platform.platform())",
  "case_count": 11,
  "executed_count": 11,
  "passed_count": 11,
  "overall_passed": true,
  "setup_failure": null,
  "cases": [
    {
      "name": "intended_symlink_passes_snapshot_guard",
      "expected_outcome": "validate_sae_files_match_snapshot must not raise",
      "actual_outcome": "passed",
      "passed": true
    }
  ]
}
```

`setup_failure` is non-null (and `case_count`/`executed_count`/
`passed_count`/`cases` reflect zero execution) exactly when real symlinks
cannot be created at all in the resolved scratch directory -- a dedicated
probe runs BEFORE any of the 11 named cases, so a capability gap is never
folded into a case's own result or silently treated as success. There is
no "skipped" state anywhere in this schema: every case either executed
and was judged, or the whole run reports a setup failure.

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
**Not part of the next scheduled GPU job** (2026-08-13 scope: Step 0 +
the two Gemma scenarios only, no Qwen rerun -- see "Next GPU job" below).
This section stays documented for whenever Qwen mechanical acceptance is
separately authorized; nothing about Qwen changed in this review.

## Next GPU job -- single wrapper command (replaces manual chaining)

Orchestrator review, 2026-08-13 ("aggregate job failure"): Slurm job 406092
ended `COMPLETED`/`0` even though BOTH required Gemma scenarios (Command 1
under `--positions all` and under `--positions generated_only`) exited `1`
-- whatever shell chaining ran them by hand did not aggregate exit codes at
all; a later command's exit status silently overwrote or masked an earlier
failure. `scripts/legacy/final_pairing_gpu_job.py` replaces manual chaining
for this job with a single command that:

1. Runs the symlink-containment PREFLIGHT first (2026-08-16, live job
   406957) -- see "Command 1" above for what it proves. **If the preflight
   fails, it stops immediately** -- neither Step 0 nor either Gemma
   scenario is even attempted.
2. Runs Step 0 next. **If Step 0 fails, it also stops immediately** --
   neither Gemma scenario is even attempted (no point spending GPU time on
   scenarios if the shared mechanism itself is unproven on this
   environment).
3. Once both the preflight and Step 0 pass, runs BOTH required scenarios
   and collects both exit codes for diagnostics, even if the first one
   fails -- this is not fail-fast past that gate, it is complete.
4. Computes the overall result from ALL of the preflight + Step 0 + both
   scenarios together, never by sequentially overwriting a "last exit
   code" -- a later scenario passing can never mask an earlier one's
   failure. The process's own exit code is `0` iff every required step
   passed.
5. Writes one structured `job_result.json` (and prints it) with a `status`
   of exactly `"complete_pass"`, `"failure"`, or `"partial_execution"` --
   see below for what each means.

Next job's exact scope (2026-08-13): Step 0 only, then Gemma-3-12b-it
`--positions all` and `--positions generated_only`, both at
`--max-new-tokens 8` (the wrapper's own `--scenario-max-new-tokens`
default). **No Qwen rerun.**

```bash
HF_HUB_OFFLINE=1 python scripts/legacy/final_pairing_gpu_job.py \
  --model-path /path/from/lab-assistant-1/inventory/gemma-3-12b-it \
  --sae-path /path/from/lab-assistant-1/inventory/gemma-scope-2-12b-it \
  --expected-model-revision <from inventory> \
  --expected-sae-revision <from inventory> \
  --feature-idx 250 \
  --mode steer \
  --dose-multiple 4.0 \
  --raw-clamp-value 5000 \
  --prompt "Tell me about your day." \
  --seed 0 \
  --out-dir results/final_pairing/gpu_job_<slurm-job-id>/
```

`--dose-multiple 4.0` feeds Step 0 only (it looks up `maxActApprox` from
the `-pt` pairing's own manifest, exactly as the standalone Step 0 command
above does). `--raw-clamp-value 5000` feeds both required Gemma scenarios
(same placeholder value as the standalone Command 1 above). `--step0-max-
new-tokens` defaults to `64` (unchanged); `--scenario-max-new-tokens`
defaults to `8` (this job's ratified scope) -- override either only if a
future work order changes that scope explicitly.

`job_result.json` schema:

```json
{
  "status": "complete_pass | failure | partial_execution",
  "overall_exit_code": 0,
  "preflight": {
    "name": "symlink_containment_preflight", "command": ["...", "..."],
    "attempted": true, "exit_code": 0, "json_path": ".../symlink_preflight_result.json",
    "executed_count": 11, "passed_count": 11, "overall_passed": true
  },
  "step0": {
    "name": "step0_differential_check", "command": ["...", "..."],
    "attempted": true, "exit_code": 0
  },
  "scenarios": [
    {"name": "gemma_it_all", "command": ["...", "..."], "attempted": true, "exit_code": 0},
    {"name": "gemma_it_generated_only", "command": ["...", "..."], "attempted": true, "exit_code": 0}
  ]
}
```

- `"complete_pass"`: the preflight passed AND Step 0 passed AND both
  scenarios were attempted AND both passed. `overall_exit_code` is `0`.
- `"partial_execution"`: the preflight failed (so Step 0 was never
  attempted at all -- `"step0": {"attempted": false, ...}`, `"scenarios":
  []`), OR Step 0 failed (so the scenarios were never attempted at all --
  `"scenarios": []`), OR a required scenario is present with `"attempted":
  false"` for any other reason.
- `"failure"`: everything was attempted, but at least one required
  step's `exit_code` was nonzero. Read each scenario's own `--out` JSON
  (`gemma_3_12b_it_all.json` / `gemma_3_12b_it_generated_only.json` in
  `--out-dir`) for the actual `verdict`/`gate_passed` detail behind the
  failing exit code; read the preflight's own JSON artifact (`preflight.
  json_path` in `job_result.json`, or the preflight's compact stdout
  summary the wrapper's `_run_preflight` also prints) for the per-case
  `expected_outcome`/`actual_outcome` behind which specific containment
  guard failed -- `job_result.json`'s own `preflight` block only tells you
  the aggregate counts, not the per-case detail.

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
      "loader_sae_id": "... (Gemma only, e.g. 'layer_31_width_16k_l0_medium' -- see note below)",
      "local_path": "...", "revision": "...", "revision_verification": "...",
      "resolved_files": ["... every local file the SAE loader actually read ..."],
      "requested_sae_files": [
        {"requested_filename": "... (Gemma only, e.g. 'resid_post/layer_31_width_16k_l0_medium/config.json')",
         "resolved_local_path": "..."}
      ],
      "local_snapshot_only": "... (Gemma only, always true -- see note below)",
      "network_resolution_attempted": "... (Gemma only, always false -- see note below)",
      "actual_class": "...", "format": "sae_lens_registry | qwen_scope_raw_pt",
      "d_in": <int>, "d_sae": <int>, "k": <int or null>,
      "expected_sae_subdirectory": "... (Gemma only, e.g. 'resid_post/layer_31_width_16k_l0_medium')",
      "sae_subdirectory_membership_verified": "... (Gemma only, see note below)"
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
touched by that review.

Orchestrator review, 2026-08-12 added the other direction: only the Gemma
branch gets `provenance.sae.expected_sae_subdirectory` (the ratified
`sae_id`, e.g. `resid_post/layer_31_width_16k_l0_medium`) and
`sae_subdirectory_membership_verified`. Qwen has no comparable sibling-
family directory structure to guard against (one flat `layerN.sae.pt` file
per layer, no `attn_out`/`mlp_out`/`transcoder` siblings), so this check is
Gemma-only. `sae_subdirectory_membership_verified` is always `true` when
present -- there is no `false` state: a mismatch raises
`TargetIdentityMismatch` before `main()` ever reaches the JSON write, so a
failed run produces no JSON artifact at all rather than one with this key
set to `false`. Treat "no output file" the same as "membership verified:
false" when triaging a failed Gemma run.

Orchestrator review, 2026-08-13 ("Separate Gemma artifact identity from
loader identity", live job 406092) added `provenance.sae.loader_sae_id`,
Gemma-only. The Gemma `sae` block now carries THREE independently-recorded
identities, and none of them is a rewritten copy of another:
`release` (`gemma-scope-2-12b-it-res`) names the sae_lens release;
`loader_sae_id` (e.g. `layer_31_width_16k_l0_medium`) is the FLAT key that
release's own registry actually recognizes and what `SAE.from_pretrained`
literally received; `sae_id` (e.g.
`resid_post/layer_31_width_16k_l0_medium`, unchanged from before this
review) is the real artifact subdirectory, feeding
`expected_sae_subdirectory` and the logical/physical guards above. Before this review, the harness passed `sae_id`'s value where
`loader_sae_id` was required, which fails before any weights load -- if a
future run's provenance ever shows `sae_id == loader_sae_id`, that is the
same defect recurring (the two identities collapsed back into one), not a
cosmetic detail.

Orchestrator review, 2026-08-14 ("Make Gemma SAE loading use the exact
pinned local snapshot", live job 406259) added
`provenance.sae.requested_sae_files`, `local_snapshot_only`, and
`network_resolution_attempted`, all Gemma-only. `requested_sae_files` is
the full request/response record -- one entry per `hf_hub_download`-shaped
call `sae_lens` made during SAE loading, pairing exactly what repo-relative
filename was requested with exactly which local file on disk was served
for it; `resolved_files` (existing, unchanged) is the plain list of served
paths those same entries' `resolved_local_path` values populate, kept
because the pre-existing snapshot/subdirectory/symlink validators consume
it as a plain `list[str]`. `local_snapshot_only`/`network_resolution_
attempted` are always `true`/`false` respectively whenever this block is
present at all -- there is no live/dynamic state to report, since the
resolver that produces `requested_sae_files` never calls the real
`hf_hub_download`, by construction; treat any future value other than
exactly `true`/`false` as itself a sign this guarantee has regressed.

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
| `TargetIdentityMismatch` mentioning "OUTSIDE the ratified SAE subdirectory" | **SAE_SUBDIRECTORY_MISMATCH** (new, 2026-08-12) | Gemma side only, the LOGICAL check. The resolved SAE file(s) live inside the correct snapshot/revision but under the WRONG sibling family (`attn_out`, `mlp_out`, `transcoder`, or `transcoder affine` instead of the ratified `resid_post`) -- all five share the identical `layer_31_width_16k_l0_medium` suffix, so this is not something the snapshot/revision checks above can catch. Sanity-check that `gemma-scope-2-12b-it-res` (the `-res` = resid_post release suffix) is actually the release configured, not a sibling release for one of the other four families. |
| `TargetIdentityMismatch` mentioning "dereference to a target OUTSIDE this repository's own cache root" | **SAE_SYMLINK_ESCAPED_CACHE** (new, 2026-08-12 addendum) | Gemma side only, the PHYSICAL check. A resolved SAE file is a real on-disk symlink whose dereferenced target does NOT belong to this repository's own `models--<org>--<repo>` cache root -- i.e. the symlink's logical (snapshot-relative) location looked correct, but its target physically points somewhere else (a different repo's cache, or an arbitrary path). This is a DIFFERENT failure than SAE_SUBDIRECTORY_MISMATCH above: that one catches a symlink correctly pointing to a legitimate blob but logically filed under the wrong family; this one catches a symlink logically filed correctly but pointing to the wrong (or no longer trustworthy) physical bytes. |
| `TargetIdentityMismatch` mentioning "not a registered SAE id" | **LOADER_ID_UNREGISTERED** (new, 2026-08-13) | Gemma side only, fires BEFORE the model even loads. `sae_loader_id` (the flat key) isn't in the selected release's own `saes_map` -- most likely because it got set to the artifact path (`sae_id`) by mistake, the exact live job 406092 defect. Check `provenance` was never even reached (no output file) and re-verify `sae_loader_id` against `get_pretrained_saes_directory()[release].saes_map.keys()` directly. |
| `huggingface_hub.utils.EntryNotFoundError` for a `resid_post/...` filename | **SAE_SNAPSHOT_FILE_MISSING** (new, 2026-08-14) | Gemma side only. The validated `--sae-path` snapshot is missing a file `sae_lens` actually needs -- most likely `params.safetensors` (`config.json` itself is optional: `sae_lens` infers it from `repo_id`/`folder_name` when absent, no network needed). The download to `--sae-path` was probably incomplete; re-verify the file listing against Lab Assistant 1's inventory. |
| `TargetIdentityMismatch` mentioning "safetensors file at" | **SAE_SHAPE_SHIM_FAILURE** (new, 2026-08-15) | Gemma side only, inside the corrected shape-lookup shim specifically (distinct from SAE_SNAPSHOT_FILE_MISSING above, which fires before this shim is even reached). Read the message for which of: file does not exist, cannot be opened (e.g. a truncated/corrupted download -- "could not open or read tensor shapes"), zero tensor keys, or an empty shape mapping. The message always names the resolved local path. |
| `TargetIdentityMismatch` mentioning "local-snapshot-only SAE resolution" but NOT "OUTSIDE the ratified SAE subdirectory" | **LOCAL_RESOLUTION_REJECTED** (new, 2026-08-14) | Gemma side only, defensive -- should never actually fire against `sae_lens`'s real, unmodified internal call sites. Means either an unexpected repository id or an explicit, non-default `revision` was requested during SAE loading (a branch-dependent resolution request); read the exact message for which. |
| `FileNotFoundError` for model/SAE path | **PATH_NOT_STAGED** | The inventory path doesn't exist on this machine/allocation. |
| `RuntimeError: HF_HUB_OFFLINE=1 is not set` | **ENV_NOT_OFFLINE** | Export it before invoking -- every Tamia compute-node job in this project requires it. |
| `ValueError`/`TargetIdentityMismatch` from `resolve_target_value` before any load starts | **BAD_STEER_VALUE** | `--raw-clamp-value` (or the resolved `--dose-multiple` x `--calibration-value` product) was zero, negative, NaN, or infinite. Fails before any weights load by design. |
| Gemma: `HookedTransformer.from_pretrained` raises on an unrecognized model name | **TL_REGISTRY_GAP** | Re-verify `"google/gemma-3-12b-it" in transformer_lens.loading_from_pretrained.OFFICIAL_MODEL_NAMES` on the exact installed version -- this was true for the version installed while writing this packet (3.2.1) but is a live fact, not a permanent guarantee. |
| Qwen: any exception before generation starts | **QWEN_LOAD_UNVERIFIED** | The entire Qwen load path is unverified against real weights (see below) -- capture the full traceback verbatim and stop; do not patch around it blind. |
| `final_pairing_gpu_job.py`'s `preflight` step fails (exit nonzero, or `executed_count`/`passed_count`/`overall_passed` disagree with 11/11/true even if exit code were 0) | **PREFLIGHT_CONTAINMENT_FAILURE** (new, 2026-08-16; JSON-based re-verification added 2026-08-17) | The real HF cache's actual symlink layout failed one of the three SAE-file/path guards against real files on this allocation -- read `preflight.json_path`'s own JSON artifact (`job_result.json` only records the aggregate counts) for which of the 11 named cases failed and why (`expected_outcome` vs `actual_outcome`, classified as `assertion_failure`/`unexpected_exception`/a `setup_failure` if real symlinks couldn't be created at all). Neither Step 0 nor either Gemma scenario was attempted (the wrapper enforces this). Do not weaken any containment check to force a pass; a genuine failure here means the real cache's symlink shape differs from what was audited, which is itself the finding to report. |
| Step 0 (`gemma3_tool_diff_test.py`) exits `1`, `gate_passed: false` | **STEP0_GATE_FAILURE** (exit code now meaningful, 2026-08-13) | Read `gate_criteria` to see WHICH of `identical_text`/`identical_token_ids`/`activations_effectively_identical` failed. A real divergence here under greedy decoding means the shared mechanism itself is broken on this environment -- per this task's explicit instruction, do not weaken any criterion to force a pass; report the divergence. Do not proceed to the Gemma scenarios (the wrapper below already enforces this). |
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
4. **The Gemma SAE local-snapshot-only resolver (2026-08-14) and shape
   shim (2026-08-15, live job 406826) have each been proven with REAL
   local files on disk and the REAL, unmocked `safe_open`/`hf_hub_
   download`-shaped call sites -- but the full, unmodified, real
   `SAE.from_pretrained` -> `gemma_3_sae_huggingface_loader` call chain
   (config parsing, weight loading, actual `SAE` construction) has never
   run end-to-end through both of them together.** Every test that
   exercises `load_gemma_it_target`'s integration with the resolver still
   mocks `SAE.from_pretrained` itself, simulating what its internals would
   request rather than letting them run for real; the shape shim's own
   tests exercise it directly (real `safe_open`, real temporary
   safetensors files) plus one test proving it correctly threads through
   the resolver, but not via a real `SAE.from_pretrained` call. Job 406826
   already found one real defect the mocked tests could not (`for k in f`
   is a TypeError against the real API) -- treat that as evidence this gap
   is real, not theoretical. "The mapping algorithm and the shape shim are
   each individually correct against realistic requests" and "sae_lens's
   real, unmodified internals actually make exactly those requests, in
   that order, against a real Gemma-Scope-IT snapshot's real files, start
   to finish" are different claims -- the second needs the real Tamia run
   both fixes were written for. Treat the first live Command 1 run under
   both fixes as the actual test, not a formality -- if it still fails,
   capture the full traceback and the exact `filename`/`subfolder`/
   `revision` (or safetensors error) the failing call carried rather than
   assuming either fix above is wrong; it may be a call shape or file
   condition neither review anticipated.
5. **The exact-SAE-subdirectory guards (2026-08-12, the same-day "HF
   snapshot symlink containment" addendum, and the 2026-08-16 snapshot-
   guard fix) are unrun against a real huggingface_hub cache's actual
   symlink layout on THIS machine -- real sae_lens path capture remains
   LIVE-UNVERIFIED until the Tamia run, even though a dedicated GPU-job
   preflight step now exists specifically to close this gap.** All three
   SAE-file/path checks (logical snapshot, logical SAE-family, physical
   cache) have corresponding real-filesystem regression tests, but every
   one SKIPS on this machine specifically (creating a symlink here
   requires privileges this environment doesn't have) in
   `test_final_pairing_targets.py` -- only the non-symlink and
   mocked-symlink cases ran locally there. The standalone preflight script
   (`scripts/legacy/final_pairing_symlink_preflight.py`, 2026-08-17) and
   its pytest-based developer counterpart deliberately do NOT skip on this
   same limitation -- both HARD FAIL, proven directly on this machine
   (`OSError: [WinError 1314]`, confirmed during this review, including a
   real-subprocess invocation of the standalone script itself) -- and the
   standalone script is wired as `final_pairing_gpu_job.py`'s own preflight
   gate, so the very first time it runs successfully will be inside the
   Tamia allocation itself, as part of the next scheduled job, before any
   GPU time is spent on Step 0 or the Gemma scenarios. That is by design
   (this is exactly the point of a preflight run inside the allocation
   rather than a formality check on the login node), but it also means the
   preflight mechanism itself -- not just the containment logic it
   exercises -- has never executed successfully anywhere yet. Treat its
   first real run as the actual test of the containment fix, the
   standalone script, AND the preflight wiring together, not a formality.
6. **Gemma-3-12b-it side is comparatively low-risk but still unrun**:
   `google/gemma-3-12b-it` is confirmed in `transformer_lens`'s registry
   with the identical `d_model=3840`/`n_layers=48` as the already-proven
   `-pt` pairing, and `gemma-scope-2-12b-it-res`'s own `saes_map` is
   confirmed, in the installed `sae_lens==6.44.2` registry, to have
   `layer_31_width_16k_l0_medium` (the flat `loader_sae_id`, a KEY) mapped
   to `resid_post/layer_31_width_16k_l0_medium` (the ratified `sae_id`
   artifact identity, that key's VALUE) -- worded precisely here on
   purpose, since a looser phrasing of exactly this fact ("...is confirmed
   present in the registry with the exact ratified sae_id") is what led to
   passing the VALUE where the loader wanted the KEY in the first place
   (orchestrator review, 2026-08-13, live job 406092 -- now fixed, see
   Command 1's own notes above). The remaining unknown is purely whether
   the actual HF snapshot bytes are staged on Tamia -- a Lab Assistant 1
   inventory question, not an engineering-design one.
7. **`_patch_gemma3_safetensors_shape_lookup`'s applicability to the `-it`
   SAE release is inferred, not independently re-tested**: it's a generic
   fix for any `conversion_func="gemma_3"` release in the installed
   `sae_lens`, and `gemma-scope-2-12b-it-res` uses that same
   `conversion_func` (verified via the registry) -- reasoned to apply, not
   re-run against the `-it` release specifically.
8. **No local machine used in this investigation can load either target's
   real weights** (no GPU, and neither snapshot is staged locally) -- every
   claim above is either read from public metadata/source (config.json,
   `app.py`, `modeling_qwen3_5.py`, the installed `sae_lens`/
   `transformer_lens` registries) or derived by direct code reading, or
   proven with a synthetic/monkeypatched unit test. None of it substitutes
   for a real run.
9. **`scripts/legacy/final_pairing_gpu_job.py` (the new wrapper, 2026-08-13)
   has never actually launched Step 0 or either Gemma scenario as a real
   subprocess.** Its own tests monkeypatch `_run` entirely -- they prove
   the aggregation/stop/no-overwrite LOGIC is correct, not that
   `subprocess.run([sys.executable, ...])` against the real scripts, with
   real argument quoting/paths on Tamia's actual shell, behaves as
   expected. Treat the first real invocation as the first test of the
   wrapper itself, same as every other "not yet run for real" item above.
