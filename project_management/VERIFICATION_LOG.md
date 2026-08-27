# Verification Log

## 2026-08-08 — D2.1 sweep job 399312: COMPLETED, hash-bound

`results/` is gitignored at `.gitignore:19`, but this file is committed at `339a35d`
(`results/gemma3_sweep/records.jsonl` + `module_identity_report.json`), so it carries both
a git blob identity and this log entry.

**sacct, State/ExitCode/Elapsed/MaxRSS (a clean record count is not the same as a clean
exit — checked separately):**

| Field | Value |
|---|---|
| State | `COMPLETED` |
| ExitCode | `0:0` |
| Elapsed | `11:14:48` |
| MaxRSS (batch step) | `134857620K` |

Record count matches the full expected grid (108 cells × 8 prompts × 2 arms). Not a
partial sweep. Log tail at job end: clean NVML report, "No running processes found", no
error text in stderr beyond benign module-unload notices.

| SHA-256 | File |
|---|---|
| `1a888a573e8c19dead2fd856caa536cf23db5112b67448b1457499b9a68976b0` | `results/gemma3_sweep/records.jsonl` |

Pulled from Tamia and re-hashed on both sides (not trusting rsync's exit code); matched.
Secret-scanned (HF token pattern, `Bearer` headers, key/secret/password assignments) —
0 hits.

## 2026-08-08 — D2.1-necessity jobs 400287 → 400297 → 400342 → 400377: five
successive control designs, hash-bound — LAST COMPUTE JOB OF THE SPRINT

Committed at `b9888f2` (400287), `b974ec3` (400297), `d6ea3e9` (400342), `00af203`
(400377). All real runs' evidence held deliberately, per instruction — successive
`active_nontarget_control` designs, each degenerate for a different reason until the
last, is a more useful record than one clean run alone.

| Job | sacct: State/ExitCode/Elapsed/MaxRSS | `active_nontarget_control_idx` distribution (144 own-text records) |
|---|---|---|
| 399619 | COMPLETED / 0:0 / 00:03:17 / — | pre-fix; cross/within-feature controls guaranteed 0.0 by construction (not a scientific control) |
| 400287 | COMPLETED / 0:0 / 00:03:47 / `135191928K` | `{180: 144}` — argmax over the full sequence selected the position-0 (`<bos>`) attention-sink feature bit-identically on every record; caught by inspection, not by any gate (none existed yet) |
| 400297 | COMPLETED / 0:0 / 00:03:52 / `135392988K` | `{221: 142, 107: 2}` — position 0 excluded (`be9cade`); pre-flight diversity gate PASSED (2 unique indices / 9 unique activations on the probe); full-run distribution is real but thin, one feature still dominant in ~98.6% of records |
| 400342 | COMPLETED / 0:0 / 00:04:07 / `135570080K` | argmax replaced entirely with matched-strength uniform random sampling (`a1f736d`); max-share diversity gate PASSED over the full 144-record population (137 unique indices, dominant index at 2.1% share, 0 empty-eligible-set skips). `strength_match_ratio` spread: min 0.504, p25 0.594, median 0.757, p75 0.996, max 5.315 — the eligibility criterion has a declared lower bound (≥0.5×) but no upper bound, so some matched picks are markedly stronger than the target on that snippet |
| 400377 | COMPLETED / 0:0 / 00:04:00 / `135366864K` | two-sided `strength_band=(0.8, 1.25)` (`4a9adfb`), converting the post-hoc 400342 restriction into the pre-registered eligibility criterion itself. Mode line verified in a dry-run before firing (`two_sided_band (0.8, 1.25)`), matching the real run's own log line. Gate PASSED (136 unique indices, 1.4% max share, 0 empty-eligible-set skips). All nine features MEASURABLE at 16/16 eligible each — 500 and 4500 did **not** fall out despite the pre-declared structural-thinness warning. Per-feature ratio medians: 0.893 (2500) to 1.011 (2048); overall in-band spread min 0.801, median 0.943, max 1.248 |

**MaxRSS is a headroom fact, not a budget constraint.** All completions land at
`~135GK` MaxRSS on a whole-node H100×4 allocation, all finishing in under four-and-a-half
minutes. This job can be re-fired freely on the next control-design iteration rather than
rationed — the cost of another `--restart` is minutes, not an allocation concern.

## 2026-08-07 — Pre-registration documents: hash-bound before any result exists

`reports/` is gitignored (`.gitignore:45`, zero tracked files), so these digests are the **only**
durable identity these documents have. Both were authored **before** the measurements they govern.

| SHA-256 | Bytes | File | Governs |
|---|---|---|---|
| `6ebaac18942eec521037a021b98df91616b8449bc60ea00ffb2cdace9fec8fd0` | 23,537 | `reports/adjudication_prereg_v1.md` **v1.5** — *current* | Four-bucket class scheme, 16/16 matched evidence depth, snippets-adjudicate rule, hard-case ruling. **Supersedes `40e40b98…` and `b64a74a1…`.** The v1.2 edit changed §7.1 only, leaving the banner, version row, both reporting templates and the what-to-return line at 20/20 — **an above-the-fold instruction contradicting the binding ruling 200 lines below**, which would have sent the adjudicator to collect at the wrong depth. v1.3 reconciles all of them, marks §7.1 as governing, discharges the now-answered top-k verification item, and carries the tie/no-re-sort rule into the banner. |
**Digest chain for `adjudication_prereg_v1.md`, all superseded by `6ebaac18…`:** `40e40b98…`
(v1.1) → `b64a74a1…` (§7.1 to 16/16) → `108c576d…` (v1.3: banner/templates reconciled, top-k
discharged, checksum protocol) → `77f629c0…` (7623-reads-19 example withdrawn) → `6ebaac18…`
(**v1.5: class 11 `topical domain` added mid-adjudication**). Every revision is recorded in-document
with its evidence; none was made after a count, tally or fraction existed.

| `3bdbdb05eba868febf6a277548b665dc38e7af6b1ca29e670563fa404555a5b1` | 44,535 | `reports/methods_and_limitations_v1.md` — **authoritative consolidation**: the claim and its six unmatched axes, both instruments, sampling and all pre-registrations, the four-bucket scheme, all six characterised instrument failure modes, the adjudication protocol and drift check, both causal experiments and the ablation instrument substitution, the concept-string named result, twelve declared divergences, what voids the comparison, claim limits, reporting structure, provenance |
| `dbf1029e804655f032a6f831f3d4b766fefc14b75aa1f26ee89dad790e1ebbf2` | 6,282 | `reports/necessity_substitution_prereg_v1.md` | Ablation instrument substitution: behavioural → ΔNLL on top-activating text, two required controls, upper-bound framing, declared construct mismatch. |

**Depth revision history, recorded because a reader seeing only the endpoint cannot verify it was
not outcome-driven:** `5 → 16 → 20 → 16`, **no counts existed at any point.** The final move back
to 16 rests on an argument that makes it defensible rather than merely cautious — the fetcher
truncates large documents at a varying point (15/16/19/20 for the same cached JSON), proven by two
internal contradictions (idx 2848 reporting "16 entries" while citing a 20-object hex ID span; idx
13848 returning the same terminal element at positions 19 and 16). **Truncation can only
undercount**, so one reading of ≥16 proves the pool is ≥16 — **16 is measured, 20 is aspirational**,
and idx 7623 reads 19.

## 2026-08-07 — D3.2 Qwen taxonomy evidence: **ACCEPTED, hash-bound** (R6-V5B precedent)

Job 398527, COMPLETED 00:14:39, node tg11304, exit 0. `results/` is gitignored at
`.gitignore:19`, so these artifacts **cannot be committed** — hash-binding is not the preferred
route, it is the only one, and these digests are the sole durable identity the files have.
Pulled to the workstation and **re-hashed on both sides** (not trusting rsync's exit code);
all six match cluster↔local, 70 files / 2,535,080 bytes both sides.

| SHA-256 | Bytes | File |
|---|---|---|
| `e1f56c60c03fc449070b22687d93be5de02b72d9512cba3d587130f237c8bee7` | 436,542 | `characterize_lite.json` |
| `c78aa3cec30e3a3d77883be9951728f4b0b121a7708925e8587259dba6558fe6` | 544,279 | `taxonomy_arms.json` |
| `939954d8bf21629f89594f87356167bba392f638be3b68bc77d6263a6c88419c` | 14,558 | `taxonomy_set.json` |
| `b06bce1a7f2b84accb6a8bac09813b2ebfce23655077f3f1f23e6226cf69d0cf` | 1,849 | `feature_selection.json` |
| `b859ae024f49fb7eb1cdba3a5c166e668cb0b1f58bab6d2f2cf231bb364b212b` | 1,690 | `select_features.py` |
| `93ea4d2eeeefc0a29b3e1c1c48328b937cbb2a744647ed04b365a7ea5dfe1711` | 5,157 | `build_arms.py` |

**Widened-context artifacts (job 399311), hash-bound:**

| SHA-256 | Bytes | File |
|---|---|---|
| `3e46036b42222ed13392da181355bd86addef18b56d1e8cd9bb63d400c2d525a` | 11,070,155 | `example_context_full.json` — **canonical**; `full_chunk.role = PRIMARY`, both centred widths marked SENSITIVITY ARM ONLY |
| `287df4add929b9ab3101d3bdccbac427ad8b8084bbd37108c1a9ed7ede30eaf5` | — | `widen_windows.py` (generator) |
| `f6279502b48b07b58f58ddc744013a7a2f3df52c92e9467de8521d2feb70103c` | 1,695,147 | `example_windows_centred.json` — earlier, untouched, still valid |

**Job 399311 shows FAILED and the artifact is nonetheless sound — the exit status reports on the
launcher's epilogue, not the computation.** The payload ran to completion (`widen` exit 0, file
written, both hash-bound digests printed unchanged afterwards); the script then died on a stale
`ls` of a filename deleted two turns earlier, under `set -e`. Verified independently rather than
inferred from exit code: SHA-256 matches the digest the job itself printed, in-job / cluster /
local; JSON parses with 12 top-level keys and 40 primary + 24 reserve entries; 11,070,155 bytes
identical both sides. A truncated write could not reproduce the digest. Alignment: offset=0 100 %,
offset=1 0 % — the exact-span discriminator, not the containment test it replaced.

**Open comparability residual, pre-registered before counts exist.** Qwen `ARM_PRIMARY` chunk
lengths: min 250 · p25 1373 · **median 2038** · p75 2322 · max 2999. Against Gemma's measured
1269–2847: **78.09 % within, 21.30 % below, 0.62 % above.** Medians align and the upper tail is
negligible, but the left tail is material — roughly one Qwen row in five carries less context than
Gemma's shortest record, and short context plausibly drives `indeterminate`. **This does not
undermine full-vs-full**, whose load-bearing property is that neither column requires a windowing
decision, so no width can be chosen after counts are seen. It is a disclosed residual, now
measurable: `full_chunk.char_len` is on every row.

> **PROVISIONALITY NOTICE — the artifact cannot carry this, so the log must.**
> `example_context_full.json` holds a field named **`vs_gemma_record_range_1269_2847`** carrying the
> 78.09 / 21.30 / 0.62 split. The field name documents *which* interval was used, but nothing inside
> the file records that **1269–2847 was measured on three features / ~15 records**, standing in for
> forty. An auditor reading hard percentages against a named interval has no way to see it was
> provisional. The file is **not** being edited — `3e46036b…` is bound, and breaking a binding to fix
> a documentation gap is the wrong trade. **Recomputation needs no job and no regeneration:**
> `full_chunk.char_len` is on all 1,538 rows, so it is a pure read of the bound artifact. The
> recomputed split is recorded **here**, superseding the provisional one, leaving both on the record
> with their provenance.

**Gemma side of that comparison is an estimate from three features, not a distribution** — see the pre-registered diagnostic in
`COMPLETION_LEDGER.md`.

64 activation-distribution PNGs bound by manifest digest
`9213a5e529d54494ee9760b9a065897c34c1a385e088081d0b3c49531c4a5ab7` (SHA-256 over the sorted
`sha256␣filename` lines, reproduced identically both sides).

**Secret scan: NO — nothing found.** Two independent passes. (A) Structural, against the argv
risk: every key of all four JSONs (89/123/65/11 distinct) matched against
`argv|cmd|command|cmdline|invocation|env|environ|shell|launch|sbatch|exec` — **0 matches**, and
structurally so: `characterize_lite.py` never reads `sys.argv` as data, it serialises named
scalars only, so no code path exists by which a command line could reach the output. (B)
Credential patterns over all 70 files with PNGs read as **raw bytes** (matplotlib writes
metadata, correctly not exempted): HF tokens, `api_org_`, `sk-`, `AKIA`, GitHub PAT, `xox*`,
PEM blocks, JWTs, Bearer headers, assigned `password|secret|api_key|auth_token|HF_TOKEN`, wandb
key — **0 hits**. The `unset HF_TOKEN` payload line and the no-`set -x` rule did their job.

**Disclosed, ruled not to act on:** `/home/y/yazid` and `/scratch/y/yazid` are embedded.
Username and cluster layout, not a credential, and **already throughout the repo** — relativizing
these six files alone buys nothing while the rest carries it. Recorded as a **pre-publication
item for the report**, which is what ships publicly, not the repo. `top_examples.text` holds
verbatim FineWeb excerpts ≤9 tokens: public crawl, standard practice in this literature
(Neuronpedia publishes the same), no action.

**Durability:** two physical copies (cluster + workstation). The local copy is invisible to git
and will not travel with a clone. Judged adequate against a 5-day horizon given `/scratch`'s
demonstrated ≥53-day survival on both mtime and atime; a third location is not worth sprint time.

## 2026-08-05 — R9-V11: **ACCEPTED for exact `664eda9`**; publication is the only remaining step

Record: `d:\lodstar\R9_V11_INTEGRATION_CANDIDATE_AUDIT.md`. All seven blob hashes recomputed
at `664eda9` and **MATCH** the R9-V10 values.

**Stronger than equality:** each of the seven is the **same git blob object** at `a9a174f`
and `664eda9` — the replay reuses blobs rather than re-creating them, so byte identity is
*structural*, not coincidental. Working-tree bytes equal blob bytes: no CRLF drift.

- **Ancestry.** Merge-base `4bf0fd8`; nine commits, every one single-parent, exact order,
  **zero merges**. One-to-one with the original nine proved by identical
  `git patch-id --stable` **and** identical subject for all nine pairs. No squash, no
  reordering.
- **Scope, checked two ways.** Endpoint diff is exactly seven paths — *and* the union of
  paths touched by each of the nine commits **individually** is also exactly seven. So no
  eighth path was touched even transiently and later reverted, which an endpoint diff alone
  would hide.
- **R10 overlay survived.** `slurm/launch_census.sh` (`f689698cc842…`) and
  `docs/ablation_9056_spec.md` (`8288fa62cc85…`) byte-identical to base; only 7 of 293
  tracked files differ.
- **Suite** 795 passed / 1 skipped / 3 deselected, exit 0, 252s — the Docker branch
  (Docker 28.5.1, `desktop-linux`, local `python:3.11-slim-bookworm` `sha256:d29f48a31a8b…`),
  with the isolation test confirmed **running and passing** (1.48s) rather than skipping. The
  single skip is the Linux-`/proc`-gated test, which always skips on win32 **regardless of
  Docker**. Line re-derived independently: `skipif` decorator at **1657**, `def` at 1658 —
  confirming `:1381` was stale.
- Static gates: CI Ruff, `uv lock --check` (196 packages), `bash -n` ×7, `git diff --check`,
  clean status. Worktrees 15 → 15; `r9-ed36-bundle-builder` = `a9a174f`, `r9-integration` =
  `664eda935757d1d2cf2cb332454532632d7da133`, `main` = `c6ef2df` — all unmoved.

**Two Orchestrator brief errors, corrected.** (1) The Engineer's worktree is
`D:\qwen-sae-interp-r9-integration`; my R9-V11 brief wrote
`D:\qwen-sae-integration-r9-integration`. (2) "All seven launchers" is imprecise — it is
**six** `slurm/launch_*.sh` (census, certify, characterize, steer, train, validate) **plus
`setup_env.sh`** = seven shell scripts. All seven were syntax-checked.

## 2026-08-05 — R11-V1: **ACCEPTED (hash-bound)** — R11-C00 + R11-C00-A

Record: `d:\lodstar\R11_V1_PROSE_CORRECTION_AUDIT.md`. **Second untracked-candidate
acceptance under the R6-V5B precedent.** `reports/` is gitignored, so there is no commit to
cite and **these hashes are the only durable identity these files have**:

| File | Final SHA-256 |
|---|---|
| `reports/internship_report.md` | `d9dc88b1f9b2cfeb261a2b583815f7163a81e52f5aa57dd58f380789bbc76db7` |
| `reports/presentation/internship_report.md` | `e17ce6f6ec85443835546e781a43d5a6d46670be0999073e488578ce3e879591` |
| `…/script_oral_detaille_interlab_lodestar.md` | `e526e8c845a23954e3d54b0135fcaa5dff174816cf07ce354510ff5e6c2b3c6c` |
| `…/fiche_revision_composantes_scientifiques.md` | `7f16f089f57958265018083642337e60b3007b6a75c3f27840ba851423fe48c2` |

Independence was real: every hash recomputed from bytes and every diff re-derived against
`pre/`. The Auditor deliberately did **not** read `r11_c00_a.diff`, `r11_c00.diff`, the
cumulative diff, the occurrence table, or the recorded divergence list — both criteria
corrections were confirmed from first principles.

- Nine sites re-derived independently: 92, 398, 470, 529 (both report copies), 171, 457,
  685, 690, 698. Nothing else touched.
- **Encoding criterion, now precise on two axes.** The prior "all four UTF-8 no-BOM"
  criterion is **VOID and must not be reintroduced**. Three files are LF with no BOM; the
  fiche has a genuine pre-existing BOM (`ef bb bf`) **and is CRLF throughout** (CR counts
  1346 → 1346). Any future criterion must be per-file **"encoding unchanged from
  pre-state."** All valid UTF-8; fiche still 1346 lines.
- The 14 divergences re-derived twice (37, 71, 145, 148, 160, 194, 206, 209, 229, 292, 358,
  385, 394, 409) — all 28 divergent lines carry markdown image syntax, zero non-image.
- Lines 470 and 529 are **pure insertions** — the pre text is a subsequence of the post text,
  which proves the hedges and mock-judge exclusion survived verbatim rather than being
  rewritten. 529's HIGH/ABSENT labels unchanged. Numeric α/ICC/κ and the 0.983–0.998 token
  multisets identical. `reliability.csv` pointers intact. French contains **zero U+03B1** and
  spells "Krippendorff alpha" in words throughout.
- §45 supporting lines (604, 674–681, 739–740) confirmed unchanged **and already correct** —
  not missed edits.
- No affirmative prohibited claim survives. Every remaining keyword hit is an explicit
  negation, a preserved hedge, the quoted log phrase under rebuttal, an evidence pointer, or
  not about the judge at all — `stable` at 364 is ED-27 checkpoint identity and at 494 a
  generation regime; French *vérifiable*/*falsifiable*/*planifiables* are substring artifacts.
- Stop condition not triggered: `git status --porcelain` identical, 0 staged, 0 files tracked
  or staged under `reports/`.

**Standing note for any future edit of these files:** `reports/` is gitignored, so the
working tree is the **only** copy and `D:\interlab_evidence\r11_c00_20260804\` is the **only**
rollback point. Snapshot pre-state the same way before touching bytes.

## 2026-08-05 — R9-A7 ruling: convert "someone must notice" into "CI fails"

Verified on `a9a174f` (5148 lines). Confirms all four findings:
`_validate_tooling_entries` (`:3299` at this revision; `:3263` at the `1aca37d` anchor) binds
only to `manifest["generator"]`, has **zero** references to `tooling_lock_artifacts`, and
checks only pip/hatchling/virtualenv/build — **setuptools and wheel have no version check at
all**. `source_hashes_for_root` (`:215`) returns exactly three keys; the tooling lock is
absent.

**Scope finding that decides half the questions:**
`schemas/environment_install_manifest/v1.schema.json` has `additionalProperties: false` at
top level and `source_hashes.required: [pyproject, uv_lock, cluster_requirements]` with
`additionalProperties: false`. **That schema is not among the authorized seven.** Q4, Q5b, and
Q6 all require editing it → **eighth path, escalated, not assumed**.

**The completeness rule.** *Every claim the consumer reads must have a named enforcing
mechanism, a declared class, and a machine-proved path from a consumer entry point. The set
of claims is derived from the manifests' own exact-key sets, never from a maintained list.
Both properties are repository tests, not disciplines.*

**Why A5 was insufficient — the key diagnosis.** A5 required an Engineer to (a) notice a
control exists, (b) classify it, (c) choose a surface. **Step (a) is the failure point.**
Nothing forced the question at the moment of writing, so four independent engineers each
skipped it. "A rule that depends on remembering to invoke it will fail exactly as a
hand-maintained checklist fails — which is the same diagnosis A4 made about the schema. The
fix is identical in shape: convert *someone must notice* into *CI fails*."

1. **Enumerable set, derived not remembered.** Claims live in exactly two places: manifest
   fields — already exhaustively enumerated by the `_require_exact_keys` sets that A4's drift
   test pins against the schema — and committed authority files (`pyproject.toml`, `uv.lock`,
   `requirements.cluster.txt`, the tooling lock). The obligation is a **total function** over
   that derived set: field → named mechanism → class → consumer reachability. A field with no
   named mechanism is a hole *by construction*, and the enumeration cannot drift because it is
   computed from the same exact-key sets the validators enforce.
2. **Mechanical reachability — mandatory repository test.** AST-parse the module, build the
   call graph, assert every mapped mechanism is reachable from at least one of the six
   consumer entry points. V8 and V9B did this by hand; that is precisely the expensive manual
   audit to automate once. **The mapping and the reachability test are one artifact used
   twice: totality proves nothing is unlisted, reachability proves nothing listed is
   stranded.**
3. **Tooling cross-binding confirmed and extended.** Authority must be the committed lock,
   not `manifest["generator"]` — A6's principle exactly, since generator and
   `tooling.installers` are both producer-authored and their agreement proves only internal
   consistency. Cross-check on distribution + version + sha256 against
   `tooling_lock_artifacts()`. Add the missing setuptools and wheel checks per R9-D2.
   **Asymmetry the Engineer must confirm:** `setuptools==83.0.0` is in the export so
   `_validate_runtime_tooling_overlap` already binds it partially by field-identity; **if
   `wheel` is not in the export, the committed lock is its only possible root.**
4. **Tooling lock into `source_hashes` — yes.** It is an authority file and every other
   authority file is bound that way. It is not currently *unrooted* — `repo_revision` binds
   the whole clean tree — but the roots differ in **reach**: `repo_revision` exists only in
   the install manifest, so at preflight (pre-activation, no install manifest yet) a bundle
   built against repo state A and consumed in checkout B would have the mismatch detected for
   the three bound files and **not** for the tooling lock. A genuine, if narrow, hole.
   **A6 stands unchanged.** Note the convergence: if the eighth path is authorized, the
   marginal cost of also committing torch identity as a `source_hashes`-registered file drops
   sharply, unifying all artifact-identity rooting under one mechanism — **a Human election,
   not a self-authorized migration.**
5. **pip check splits.** Recomputable → consumer-mandatory. (a) Re-run at
   `certification_environment_inputs`, one subprocess in an already-active venv — this **is**
   the control, needs no schema change, **authorized now**. (b) `pip_check` attestation field
   — corroboration only, blocked on the eighth path. **"If only one can land, take the re-run:
   it does not depend on the attestation being truthful."**
6. **`require_files=False` — same rule, not separate.** At cert-lane time the bundle may
   legitimately be absent, so "the bytes were verified" is an event that surface cannot
   re-observe — **attestable-only**. Needs a `files_verified` attestation with the limitation
   explicit in the design. Rows 5 and 6 unify: both are install-manifest attestation fields.

**No ED amendment** — ED-36 §3 already sites verification at consumption, §2 already requires
the torch artifact be hashed, §5 already requires pip check. Every finding is a **compliance
gap, not a policy gap**.

**Gating — still does not gate publication, but adds a new standing condition.** None of the
four is a regression introduced by publishing producer-side code. However, four measured
occurrences change one thing: **the mapping and reachability test must land before any
further ED-36 control is written** — not merely before first construction. "Publication is
safe; continuing to grow the control surface without the test is what is demonstrably
unsafe."

## 2026-08-05 — R9-V9B: rows 4 and 9 **NOT COVERED**; the asymmetry is now a class

Record: `d:\lodstar\R9_V9B_TOOLING_AND_PIP_AUDIT.md`. Anchor `1aca37d` (5112 lines), fresh
detached worktree, removed and pruned; in-source `uris.REPO_ROOT` assertion carried through
both probes. The branch advanced `92a12f6` → `a9a174f` during the audit, which does not
affect the frozen anchor.

### Row 4 — tooling cross-binding: NOT COVERED

Two mechanisms exist and are **never joined**:

- `_validated_tooling_lock_files` (`:775`) binds lock → bundle file bytes by real
  recomputation, but is reachable **only** from `validate_bundle` (the `preflight`
  subcommand) — not from `certification_environment_inputs`, not from
  `_validate_acquisition_manifest_semantics`.
- `_validate_tooling_entries` (`:3263`) is the cert-lane gate and binds manifest entries to
  `manifest["generator"]`. **It contains no reference to the lock at all.**
- In `validate_bundle` both results are returned as separate keys (`"tooling"`,
  `"tooling_closure"`) and never compared.

**V9B-F1 (MAJOR), two distinct failures.**
(a) *The manifest binds to itself.* `entry 9.9.9` vs `generator 25.0` (inconsistent) →
rejected; `entry 9.9.9` **and** `generator 9.9.9` (self-consistent) → **ADMITTED**.
(b) *`setuptools` and `wheel` have no version check at all* — present in the required name
set, absent from the generator cross-check. These are precisely the two pins **R9-D2
ratified with exact artifact identity** (`wheel==0.45.0`, `setuptools 83.0.0`). Hand-crafted
drift to `70.0.0` and `0.1.0` — both **ADMITTED**.

Name-set closure is sound (omission, extras, substitution all rejected). Separately,
`require_files=False` is the default and the cert lane does not override it, so **manifest
tooling bytes are never verified there**.

### Row 9 — pip check: NOT COVERED

**The mechanism is good.** `pip check` at `:2648` is unconditional (AST-confirmed, inside no
`if`), uses `check=True`, and both failure modes raise. The manifest write happens strictly
after, so a failure yields no manifest. Mandatory and fail-closed — that part of **R9-A1
holds**.

**V9B-F2 (MAJOR).** `grep "pip_check"` across the module and the install schema returns
**none**. The install manifest's exact-key set has **no field recording that the check
ran**, so the consumer can neither verify it happened nor re-run it. Live-introspection
reach at the cert lane is **torch alone**; `installed_distributions` and `loaded_modules` are
compared document-to-document. Under A5, pip check is **recomputable → consumer mandatory**,
and it is not there. In fairness to the design: the consumer does pin every required
distribution to an exact version and reject extras, which makes a broken set hard to reach
*if the manifests are honest* — a control-surface defect, not a live exploit, but exactly
the "assume the producer ran" reasoning A5 forbids.

**V9B-F3 (MAJOR, coverage).** R9-V2's "unexercised private pip" referred to
`_assert_bootstrapped_pip_only` (`:1529`) — a **different control**, with four `raise`
branches, called at two R9-D2 stop conditions. All five test references are
`monkeypatch.setattr(..., lambda: None)`. **Zero tests exercise it.** R9-V2's finding stands
unchanged.

### The producer/consumer asymmetry is occurrence three and four

TL (R9-V8), torch (V9-F1), tooling cross-binding (V9B-F1), pip check (V9B-F2) — **four
independently-written controls, same shape**. R9-A5 predicted the class. Per the Auditor's
recommendation, individual routing stops here: **R9-A7** asks the Architect for a
consumer-surface completeness rule the Engineer applies **once**, rather than four point
fixes.

**Two concrete design inputs recorded for that ruling:**
1. Row 4's fix shape — cross-check `manifest["tooling"]["installers"]` against
   `tooling_lock_artifacts()` on distribution + version + sha256 inside
   `_validate_tooling_entries`, so authority is the **committed lock** rather than the
   manifest's own generator block.
2. **The tooling lock is not in `source_hashes_for_root` (`:215`)** alongside
   `pyproject.toml`, `uv.lock`, and `requirements.cluster.txt` — which is what roots every
   other artifact authority. Whether it should be is a ruling, not an edit.

Row 9 splits: the mechanism needs no repair, but needs an **attestation field** in the
install manifest plus a **re-run at `certification_environment_inputs`** (one subprocess in
an already-active venv). V9B-F3 is separable **test-only** work needing no architecture
ruling.

**Matrix bookkeeping.** The Auditor counts 6 of 13 covered (1, 3, 5, 8, 11, 12). The
Orchestrator ledger also counts row 2, covered by transcription of the Auditor's own
read-only ancestry proof rather than by a dedicated audit — real evidence, stricter
bookkeeping. Either way no further work is required on row 2. Remaining by priority:
**row 7** (atomic finalization/rollback), then 13, 10.

## 2026-08-05 — R11-C00-A complete: fiche line 685 corrected, 9 sites total

`reports/presentation/fiche_revision_composantes_scientifiques.md`, edited in place; no
branch, no commit, no other file touched.

Line 685: `- Haut alpha : le juge est stable avec lui-même.` →
`- Haut alpha : accord quasi déterministe entre répétitions, à réglages fixes (le juge
tourne à température 0) — un contrôle de déterminisme, pas une preuve que le juge est
stable ou fiable.` Single bullet, inside the "Interprétation" block, same pattern as 698,
no bare α symbol.

| State | SHA-256 | Bytes |
|---|---|---|
| `pre/` (rollback, untouched) | `92684f6d…56acefad5` | 44525 |
| `post/` (8 sites) | `71971fe2…5627d9684008` | 44831 |
| `post_a/` (9 sites) | `7f16f089…840ba851423fe48c2` | 44982 |

BOM `ef bb bf` preserved. Line count unchanged at 1346. The `post → post_a` diff is a single
isolated hunk touching only 685; the cumulative `pre → post_a` diff shows exactly the three
intended fiche edits (685, 690, 698) and nothing else. The fiche's supporting §45 lines
(604, 674–681, 739–740) were correctly left unedited — they already read correctly.
`git status --porcelain` identical to baseline; nothing entered the index. Evidence at
`D:\interlab_evidence\r11_c00_20260804\post_a\` plus isolated and cumulative diffs.

## 2026-08-05 — R9-X3 result: `packaging` IS satisfied on Tamia (benign, not guaranteed)

Raw probe output, login node, exit 0:

```
executable        /cvmfs/soft.computecanada.ca/easybuild/software/2023/x86-64-v4/
                  Compiler/gcccore/python/3.11.5/bin/python
version           3.11.5
tomllib           ok
packaging_file    …/python3.11/lib/python3.11/site-packages/packaging/__init__.py
packaging_version 23.1
tags              ok
Requirement       ok
canonicalize_name ok
parse_wheel_filename ok
sys_tags_count    39
```

**R9-A4 interpretation (Orchestrator).** The pre-activation dependency is **satisfied**.
`packaging` resolves to a real top-level install in the module's `site-packages` — **not**
`pip/_vendor`, so the shadowing failure mode is absent. Version 23.1 is well above the
≥ 20.9 floor that `parse_wheel_filename` requires; all four imported symbols load; and
`sys_tags()` returns a real ordered list of 39. `tomllib` confirms a genuine ≥ 3.11
interpreter. **This is not a cluster bootstrap break.** R9-C1 did not break the cluster.

**But it is benign-by-circumstance, not by guarantee**, exactly as the Researcher
predicted. `packaging` is present because the EasyBuild `python/3.11.5` module happens to
ship it. Nothing in this repository pins, requires, or checks it, and an Alliance module
refresh could remove or downgrade it without notice.

**R9-A4 criterion reworded, binding.** The prior phrasing "module-level imports remain
stdlib plus `interplab.core.hashing`" is **false as a description** of
`environment_bundle.py` and is withdrawn. The accurate statement:

> `environment_bundle.py` imports four symbols from three `packaging` submodules at
> `:33-36` — `packaging.tags`, `packaging.requirements.Requirement`,
> `packaging.utils.canonicalize_name`, `packaging.utils.parse_wheel_filename`. The
> pre-activation bootstrap therefore **depends on `packaging` (≥ 20.9) being present in the
> system environment**. This is a **documented external assumption, not a guarantee**.
> Everything else at module level is stdlib plus `interplab`. `jsonschema` must never
> appear pre-activation, directly or transitively.

Deferred, not now: a fail-fast preflight diagnostic naming the missing dependency instead
of an opaque `ImportError` at `:33`, plus an explicit version floor. Both would touch the
seven paths and would invalidate the accepted integration candidate. Sequence after
publication.

### New construction-readiness risk — `sys_tags()` is environment-sensitive

R9-V3 confirmed that `compatible_tags` is derived from `packaging_tags.sys_tags()` and
compared with list `!=`, so **ordering is enforced**, and bound to the manifest target by
exact field equality. Tamia reports **39** tags under CPython 3.11.5 / packaging 23.1.
An Orchestrator control on this host returned **42** under CPython 3.12.11 / packaging 26.2.

That comparison is **not** the relevant pair — different interpreter *and* different
packaging version — so it proves only that the value is environment-sensitive, **not** that
a build-host/Tamia mismatch exists. It makes the question concrete and cheap to settle:
when a real build host is stood up, run the same probe inside
`python:3.11-slim-bookworm` and compare against Tamia's **39**. If the ordered lists differ,
exact-equality target-capture comparison fails closed at first real construction. Tracked as
a construction-readiness item, not an integration blocker.

## 2026-08-05 — R9-I1 integration candidate `664eda9`

Base confirmed `origin/main` = `9d90ef6`; merge-base with `a9a174f` is exactly `4bf0fd8`.
The two intervening R10 commits are `2e8efb0` (`docs/ablation_9056_spec.md`) and `9d90ef6`
(`slurm/launch_census.sh`) — **disjoint from the seven R9 paths**, confirming the
disjointness analysis.

Ordered cherry-pick of the nine accepted commits applied cleanly with **zero conflicts**.
Resulting chain, one-to-one with the original, each commit's sole parent the previous:
`9d90ef6 → 1e381c4 → 2912f0a → 44235eb → f696254 → ac02fcc → b6ef67d → b1629b6 → 066c2bb →
664eda9`. All seven blob hashes match the R9-V10 values; diff from `9d90ef6` is exactly the
seven paths; R10 blobs byte-identical. Suite 795 passed / 1 skipped / 3 deselected; exact
CI Ruff, `uv lock --check`, `bash -n` on all **7** launchers (now including
`launch_census.sh`), `git diff --check` clean. `r9-repair` untouched at `a9a174f`;
`r9-ed36-bundle-builder` still at `a9a174f`. Nothing pushed.

**Line-number correction (second Orchestrator instance of this class).** The surviving skip
is `tests/test_environment_bundle_builder.py:1657`, **not `:1381`** — same test, same
reason, shifted by R9-C10's ~276 lines of Part-A insertions earlier in that file. `:1381`
was stale from before R9-C10 and was carried into acceptance text. Together with the
5131/5148 line-count error, the rule is now explicit: **line numbers and line counts must be
re-derived per commit, never reused across one.**

**Two process notes, both benign, both recorded rather than buried.** (1) A first
`worktree add` used a backslash path that git-bash mis-resolved as relative, nesting the
checkout inside `D:\qwen-sae-interp`; the Engineer caught it via `git worktree list`,
removed it untouched, and force-deleted the zero-commit branch pointer. (2) The failed `cd`
in that command left a stray `git config core.autocrlf false` in the **repo-local** config.
Orchestrator-verified: `core.autocrlf` is now local `false`, global **unset**. This is the
value every worktree has been created with since the R8-I2 CRLF incident, so the effect is
to make LF-faithful checkout the repository default. **Unintended but beneficial —
retained deliberately**, and now recorded so it is not mistaken for drift. (3) The Engineer
pulled `python:3.11-slim-bookworm` to run the Docker-isolation test after a first run showed
794 passed / 2 skipped. Local developer tooling on the user's own machine, not evidence
acquisition or cluster action; noted for completeness.

## 2026-08-05 — R9-V10 combined integration audit: **ACCEPTED for exact `a9a174f`**

Record: `d:\lodstar\R9_V10_COMBINED_INTEGRATION_AUDIT.md`. Audited by a **fresh** Auditor
(Auditor 1) for independence — Auditor 2 had audited this branch's predecessors including
its own. Delta audited: `1aca37d..a9a174f` (`70c6d25` → `92a12f6` → `a9a174f`).

**Seven blob hashes, Orchestrator-re-verified at log time** (the Auditor's required
freshness check — all seven reproduce exactly; the branch has not moved):

| Path | sha256 |
|---|---|
| `interplab/core/environment_bundle.py` | `37881566694791a9cb71661538e50c78a72e7036da0876ebf19eb44d80f9f3f6` |
| `schemas/environment_acquisition_manifest/v1.schema.json` | `f60fff8d031215ef544f43de9eb2a4b4a44568f663562781f124debeaf0c644b` |
| `slurm/environment_bundle.tooling.lock.json` | `4df4f6e701a7562b903ed21e70b2439e152b7cf99b2119b2c2cb981cf4507b0e` |
| `slurm/setup_env.sh` | `cb0aecf3d9fd6684258fbbe691ec0accb4c0f1b1244ab44f33dbaf297799386a` |
| `tests/test_environment_bundle.py` | `7dddb2ed6efce57afb5228787e861b8403a426b784aa06bbe47cb76ecdeab28f` |
| `tests/test_environment_bundle_builder.py` | `543491f58fbb9e798caee89f74198ac97a91d43f89ca8738139bc6507801e049` |
| `tests/test_slurm_setup_env.py` | `a81d12f31344bce0d0bf2cf87db440060e56cbccd19aac444c3f4fb5f7e4c35c` |

Scope exactly seven paths, no eighth. All four certified units unchanged at their shifted
coordinates: `_current_target_capture_fields` now **L233–247**; the two builder blocks now
**L3554–3565** and **L4289–4299**.

- **Pre-activation isolation proved by execution, with a negative control.** Both paths
  completed under a live `sys.meta_path` block while `record_installed_environment` **hit**
  it — the negative control is what makes the completions meaningful rather than proof of a
  no-op blocker. The Auditor's first attempt tripped on the test module's own
  `_schema_registry` import (a harness artifact) and was rebuilt to purge the cached
  registry so the lazy import genuinely re-executes.
- **The drift corpus can actually fail** — it catches schema loosening two ways and
  over-tightening once, and passes clean. Class 3 is correctly directional with no
  equivalence assertion.
- **Tightening went to the schema, not away from a validator** — confirmed by the
  schema-only diff, zero `required=`/`optional=` changes in Python, and `git log -S` showing
  R9-C6 (the accepted baseline) added the stricter Python checks that C9 then matched.
- **The fourth rollback claim holds, independently verified.**
  `_build_derived_runtime_wheel` has three narrow `CalledProcessError` handlers that raise
  with no cleanup, no `finally` anywhere, and its only rollback is success-path at
  **L1966**; `unpack_root` sits under the caller's `staging_path`, so failure cleanup is
  `build_runtime_bundle`'s. Nothing to mask, nothing leaked. Against pre-fix code the four
  masking regressions fail with `PermissionError: locked cleanup path escaping` while both
  characterization tests pass — which **also independently confirms R9-C8's negative
  reproduction**. A first pre-fix harness producing `FileNotFoundError: pyproject.toml` was
  discarded as environmental rather than counted as regression failure.
- **TL consumer negative is generic, as expected.** The message comes from a parameterized
  template at **L3401**; `_validate_runtime_manifest` contains no `transformer` literal and
  never calls the gate. *Minor reconcilable discrepancy: R9-V8 enumerated eight enforcement
  sites, one of which it described as an inline export check; R9-V10 counts seven
  producer-side call sites. Both agree on the conclusion — none is consumer-reachable.*
- Regressions: **795 passed, 1 skipped, 3 deselected, exit 0**; CI Ruff clean;
  `uv lock --check` pass; `bash -n` ×6; `git diff --check` clean.
- **State fully accounted:** 15 worktree records at start, 14 at end. The audit worktree was
  created, used read-only, removed. `r9-v9b2-1aca37d`'s directory had already been deleted
  before the audit began; only a stale admin record remained, cleared by the instructed
  prune — **no live tree was removed**. Engineer 2's `r9-repair` untouched; branch tip
  unmoved at `a9a174f3bb8dc6dc343fef6158323dececb2c0a7`.

**New advisory — tracked, non-blocking, pre-existing.** The private-pip identity assertions
at `environment_bundle.py:1749-1750` are uncovered: neutralising both yields 147 passed, 0
failed. Confirmed to predate the candidate (the same mutation on pre-fix shapes adds no
failures). Relatedly, R9-C10 narrowed them from both paths to success-only, which is
**correct and necessary** — you cannot preserve a primary error while running a check that
may itself raise — and it fails closed. Worth a positive test so a refactor cannot silently
drop them. Tracked as **R9-C14**.

**Orchestrator correction.** Briefs issued for R9-V10 and R9-A6 stated
`environment_bundle.py` is 5131 lines. Actual at `a9a174f` is **5148**. The 5131 figure was
correct at `92a12f6` and was carried across a commit without re-derivation. Not a defect —
the anti-stale property (≠ 2279) held decisively and the Auditor asserted it in-source on
every probe — but line counts must be re-derived per commit, not reused.

## 2026-08-05 — R9-A6 ruling: commit the sanctioned torch identity; enforce by recomputation

Verified by the Architect on `92a12f6` (5131 lines — correct revision this time). All three
causes independently confirmed: constants at `:70-73` carry version, public version, CUDA,
and origin prefix but **no SHA**; `import_alliance_torch_artifact` defined at `:2234`,
referenced exactly once at `:5101` inside `main`; `grep -cE "^torch"` on the export returns
0, and `uv.lock` carries only `2.13.0` (macOS) and `2.13.0+cpu` (pytorch.org) — **never
`+computecanada`**. The strong check at `:2284-2296` does compare a measured sha256, but
against an operator-supplied `expected_identity` that never persists past the CLI.

**Ruling: (b), with (c) as its capture step.** The sanctioned Alliance torch identity must
be **committed at a pinned repository revision** and enforced by the consumer through
**hash recomputation**. `import_alliance_torch_artifact` is retained as the capture
instrument that produces the attested value — **it is not itself the anchor**.

- **(a) rejected on principle.** Hash-binding the receipt into the acquisition manifest
  makes the manifest self-certifying: a substitute bundle arrives with a substitute
  manifest that self-consistently declares the substitute's hash, and the hash chain
  faithfully protects the wrong value. **Self-reference is not a root** — the A5 failure
  mode reproduced one layer deeper.
- **(c) alone insufficient.** An operator-supplied expected identity is unbounded at
  capture time and evaporates before consumption. The right way to measure, no way to root.

**1. External root.** None exists cryptographically — the Alliance wheelhouse publishes no
hash the lab controls. The root must therefore be a **named human attestation**: attester,
timestamp, source host, source path within the wheelhouse, and capture method, recorded
alongside the measured sha256, size_bytes, and filename. This is existing doctrine, not
new: **ED-8** already rules that when a recipe is unrecoverable the checksum becomes the
operative identity, recorded honestly; **ED-30** already rules that a value travels with
its source and confidence and is never blended. Committing the attested identity converts
an unrepeatable observation into durable, revision-bound truth — the same standing that
makes `requirements.cluster.txt` authoritative. **The researcher attests, once,
explicitly. This is a Human authorization point, not an engineering step.**

**2. A5 classification refinement — generalizes beyond torch.** Torch artifact
authenticity is today *declarative with no closure*, which is why it fails; it must become
*recomputable*. The refinement this case forces: **an attestable-only fact becomes
recomputable by being committed at a pinned revision.** Two stages, two classes. Added to
the A5 rule so a future Engineer does not conclude that "attestable-only" means "the
consumer cannot enforce it."

**3. What the origin check must state about itself.** `_ALLIANCE_TORCH_ORIGIN_PREFIX`
matching proves exactly one thing: that the manifest author typed a string beginning
`alliance:wheelhouse`. It proves **nothing about the bytes**. It is a
**labelling-consistency check, not an authenticity check**, and must say so in its own
documentation. It may never be cited as authenticity evidence in any manifest, report, run
card, or audit finding. Authenticity comes solely from comparison against the committed
sanctioned hash.

**4. R9-C12 matrix — reusable but not sufficient.** V9-F1's 15 manifest/artifact and 9
live-runtime cases stay valid as-is but do not cover the new control. Required additions,
each constructed **without invoking the builder**: substitute wheel (correct METADATA,
version, and origin prefix, different bytes) ⇒ rejected — this is exactly the case that
passes today; sanctioned bytes with a tampered origin string ⇒ rejected; manifest
declaring the sanctioned sha256 while the bundle file's bytes differ ⇒ rejected by
recomputation, never by declaration; sanctioned sha256 with mismatched size_bytes or
filename ⇒ rejected.

**5. Gating.** **Does not gate R9-I1** — V9-F1 is a pre-existing missing consumer control,
not a regression the builder introduces; publishing producer-side code neither creates nor
worsens it. **Gates first real construction harder than the A5 matrix did**, because torch
is the largest artifact, the one carrying CUDA execution, and the one whose substitution is
most consequential. Ordered: (i) Human obtains the artifact from the wheelhouse and attests
its identity, capturing via `import_alliance_torch_artifact`; (ii) the attested identity is
committed at a pinned revision; (iii) the consumer enforces it, reachable from all six
consumer functions; (iv) the extended adversarial matrix passes.

**No ED amendment** — ED-36 §2 already requires this: "CUDA torch remains the ED-1 profile
exception, but its public version must equal the locked version and its exact Alliance
artifact must be hashed." The obligation exists; what is missing is a committed root and
consumer reachability. Compliance, not amendment.

**No path expansion in the minimal form** — committing the identity as module-level
constants beside `_ALLIANCE_TORCH_VERSION` in `environment_bundle.py` (path 1) is bound by
`repo_revision`, the same root that already makes every validator in that module
trustworthy, with tests in the authorized test paths. **Stop condition:** if the Human
prefers the identity as a separate committed data file registered in `source_hashes`, that
requires a new committed path (eighth) plus `source_hashes` key-set changes in paths 1 and
7 — escalate for authorization, do not self-expand.

*Orchestrator note: the Architect labelled the follow-on `R9-C5`, which is taken by the
pre-recorded `R9-C5-REAL-DERIVED-WHEEL-RUNTIME-EXPORT` gate. Reassigned as **R9-C13**.
This is the third Architect ID collision (`R9-C3`, `R9-C4`, `R9-C5`); future Architect
briefs must carry a pre-assigned work-item ID.*

## 2026-08-05 — R9-C10 complete (`a9a174f`); branch tip stable for the integration audit

Commit `a9a174f3bb8dc6dc343fef6158323dececb2c0a7`. Orchestrator-verified: clean
three-commit chain from accepted `1aca37d` (`70c6d25` → `92a12f6` → `a9a174f`),
cumulative delta 4 files (+827/−17), cumulative from `4bf0fd8` still **exactly the seven
authorized paths**, repair worktree clean. 795 passed (787 + 8 new), 1 skipped
(`:1381`, Windows-expected), 3 deselected; CI Ruff, `uv lock --check`, `bash -n` ×6,
`git diff --check` clean.

**Part A — per-function, with a self-correction that matters.**

| Function | Verdict | Detail |
|---|---|---|
| `_extract_sdist_to_directory` | unsafe, fixed | **two** independent sites — the `except Exception:` block and the `roots != 1` check |
| `_bootstrap_private_pip` | unsafe, fixed | a **different shape** — nested `finally: … finally: _rollback_partial_path(…)`, not a bare except/raise; both the subprocess failure and the identity-verification failure now route through the helper |
| `build_runtime_bundle` | unsafe, fixed | the textbook `except Exception: _rollback_partial_path(staging_path); raise` |
| `_build_derived_runtime_wheel` | **already safe — no change** | its three `subprocess.CalledProcessError` handlers never call cleanup, and the tail `shutil.rmtree`/`_rollback_partial_path` calls run unguarded after success with no primary error in flight |

**The R9-C8 report's claim that all four carried the unsafe pattern was imprecise, and the
Engineer corrected it here rather than letting it stand.** The durable record is the
table above, not the C8 note. All four received a regression proven empirically against
pre-fix code: the three unsafe ones fail pre-fix (cleanup's `PermissionError` replaces
the real error) and pass post-fix; the safe one passed unmodified, driving a full
successful build and forcing the first cleanup call to raise while asserting that exact
exception — not a replacement — propagates. `_extract_sdist_to_directory` received two
tests for its two sites.

**Part B — V8-F1 closed, with an empirical corroboration of R9-V8's call-graph finding.**
Branch 2 (`4.0.0` → "unexpected transformer-lens version"), branch 3 (duplicate `3.2.1`
under `require_exact_runtime=True`), and the consumer-path negative all land. The
consumer negative is the informative one: `3.4.0` is rejected by
`_validate_runtime_manifest`'s **generic version check, with no TL-specific wording** —
independently confirming that the TL gate does not reach the consumer and that the
generic check is what actually protects that surface. R9-V8 established this by static
call-graph analysis; this reaches the same conclusion empirically.

The branch tip is now stable and is the candidate for the R9-V10 integration audit.

## 2026-08-05 — R9-V9: packaging break confirmed; matrix row 6 **NOT COVERED** (V9-F1 MAJOR)

Record: `d:\lodstar\R9_V9_PACKAGING_AND_TORCH_AUDIT.md`. Two separate detached
`core.autocrlf=false` worktrees (Part A at `92a12f6`, Part B at `1aca37d`), both removed
and pruned; every probe asserted `uris.REPO_ROOT` against its own worktree in-source, so
a stale-main read would have aborted rather than produced numbers. 14 worktrees at start
and end.

### Part A — the `packaging` dependency is real, breaking, and R9-introduced

R9-C9's guard writes the exemption in **by name** (`allowed = stdlib | {"packaging",
"interplab"}`) while the hook blocks only the `jsonschema` closure.

| Blocked set | `preflight` rc | plan written |
|---|---|---|
| jsonschema closure (C9's own criterion) | 0 | True |
| jsonschema **+ packaging** | **1** | **False** |

It dies at `environment_bundle.py:33`, before any subcommand logic; `create-venv` fails
identically — the module cannot load at all.

**A lazy import would not fix it.** With `packaging` importable but each bound symbol
poisoned, the probe reports `PACKAGING USED pre-activation: packaging_tags.sys_tags` —
`:246` in `_current_target_capture_fields`, reached from `preflight` via
`enforce_current_target=True`. The dependency is genuine, not an import-ordering
artifact, so the fix is a **scope ruling, not a mechanical edit**.

**It does not predate R9.** AST across the chain: `4bf0fd8` (2279 lines) → `['interplab']`;
`c847e07` (R9-C1, the first builder commit) → `['interplab', 'packaging']`, unchanged
since. **R9-C1 introduced it.**

**Unresolved and decisive:** whether `import packaging` resolves after
`module load python/3.11 arrow` on Tamia. No cluster access. Proxy only —
`python:3.11-slim` ships `packaging` top-level, but pip and setuptools vendor it
privately as `pip._vendor.packaging`, which would not satisfy the import. One login-node
line settles it:
`module load python/3.11 arrow && python -c "import packaging; print(packaging.__file__)"`.

### Part B — matrix row 6 **NOT COVERED**; V9-F1 is a real hole

Torch code confirmed byte-identical `1aca37d` → `92a12f6` across all five functions, so
this holds at the current tip.

Every **recomputable** control fails closed and none could be broken: 15 hand-crafted
manifest/artifact attacks all rejected (`+cu121`, missing file, arbitrary hash, stale
manifest after tampering, wrong size/filename/METADATA/origin, `../escape.whl`, lock
mismatch) and all 9 live-runtime attacks rejected (CPU runtime, false availability,
CUDA 12.4, version drift). Both matrices ran from an accepted clean baseline.

**V9-F1 — MAJOR.** Two wheels with **completely different bytes**, both labelled
`torch 2.13.0+computecanada` with correct METADATA and an `alliance:wheelhouse` origin,
are **both ADMITTED**. The consumer cannot distinguish the sanctioned build from a
substitute. Orchestrator-verified independently:

- **No SHA constant exists.** Only `_ALLIANCE_TORCH_VERSION`, `_PUBLIC_VERSION`,
  `_CUDA_VERSION`, `_ORIGIN_PREFIX` (`:70-73`). Origin is a `startswith` on a
  self-declared string (`:2288`).
- **torch is excluded from the source-hash-bound export** — `grep -cE "^torch"
  slurm/requirements.cluster.txt` returns **0**, while the other 113 distributions are
  each rooted by `sha256 not in requirement.hashes` (`:3382`). `uv.lock` carries only
  public `2.13.0`/`+cpu` from pytorch.org, not the Alliance build.
- **The real root exists but never crosses the boundary.**
  `import_alliance_torch_artifact` (`:2251`) is strong — operator-supplied
  `expected_identity` matched against measured sha256/size/filename/version/origin plus a
  no-index/no-deps/only-binary transcript — but it is referenced exactly once, at
  `:5118` inside `main`. **CLI-only; unreachable from every consumer function.**

Under R9-A5: recomputable ✓, live-introspection ✓, but **artifact authenticity is
declarative with no closure**. This is **worse than the TL case**: TL was ruled a
layering asymmetry because the consumer enforced the same fact by a stronger hash
binding rooted in a source-hash-bound file. Here **the hash binds the manifest to
itself.**

Closing it means carrying the **authority** across, not the check: either hash-bind the
torch receipt into the acquisition manifest, or commit the sanctioned torch identity
into the repository so it becomes source-hash-bound like the export. The latter matches
how everything else is rooted. Routed to the Architect as **R9-A6**, A5 follow-through
rather than a point fix.

Neither Part A nor Part B gates R9-I1. Both gate first real construction, and the torch
cases from this audit are reusable as-is in the R9-C12 consumer-only adversarial matrix.

## 2026-08-05 — R9-C9 complete (`92a12f6`), plus an unvalidated pre-activation import

Commit `92a12f6`, paths 1/4/7 only, +385/−3 (`environment_bundle.py` +19, schema +4/−3,
`test_environment_bundle.py` +365). 787 passed (773 + 14 new), 1 skipped (`:1381`,
Windows-expected), 3 deselected. CI Ruff, `uv lock --check`, `bash -n` ×6,
`git diff --check` clean. No stop condition hit.

- **Real mismatch found and fixed in the required-key audit.** Every
  `_require_exact_keys` site was walked against the schema field-for-field. All matched
  except the two connection attempts: the R9-C6 validators require all fields
  (`{succeeded, error}` / `{argv, returncode, stdout, stderr}`) while the schema
  required only `["succeeded"]` / `["returncode"]`. The schema's `required` arrays were
  tightened to match Python. **Direction is correct** — the validators were already
  *stricter*, so A4's directional invariant was never violated; tightening the schema
  satisfies the Architect's field-for-field acceptance criterion without touching a
  validator. Pre-first-write, so no manifest migration arises.
- Four certified hashes reproduce exactly. Two shifted line position; the Engineer
  diffed them byte-identical against pre-edit content *before* re-hashing at the new
  coordinates — the correct method.
- Blocking-import-hook evidence is by **execution**: a real `sys.meta_path` finder
  raising `ImportError` for `jsonschema`, `referencing`, `rpds`, `attrs`, and
  `jsonschema_specifications` in a fresh subprocess, running each subcommand to
  completion.
- Anti-drift corpus, 9 cases + baseline: class 1 valid (1), class 2 shape (5
  parametrized, rejected by both), class 3 semantic-only (3 — hash mismatch,
  unauthorized export hash, lock-binding mismatch: Python rejects, schema acceptance
  asserted as expected, with an explicit comment against ever "fixing" it by tightening
  the schema). Wiring proof at both post-activation sites forces only the schema call
  to fail on an already-passing fixture, proving the check is genuinely consulted and
  additive.

### Finding — `packaging` is a module-level non-stdlib import, and nothing blocks it

Orchestrator AST check of the real top-level `Import`/`ImportFrom` nodes at `92a12f6`:
non-stdlib roots are **`interplab` and `packaging`**. The Engineer's mechanical
assertion allows stdlib ∪ {`packaging`, `interplab`}, which matches reality but is
**broader than R9-A4's stated criterion** ("stdlib plus `interplab.core.hashing`").

The consequence is not cosmetic. The blocking-import-hook tests block the `jsonschema`
closure but **not `packaging`**, so the pre-activation import surface still carries an
unvalidated third-party dependency. `preflight` and `create-venv` run on bare system
python after `module load python/3.11` and before `source …/activate`. Whether
`packaging` is importable there on Tamia has **never been exercised** — the cluster
preflight has never run to completion, since R9-X1 found no bundle and no usable venv.
If it is absent, this is a latent bootstrap break that predates all R9 work. Routed to
Auditor 2 as a bounded probe. Not a defect in `92a12f6`; the Engineer's allowlist
described the tree accurately.

## 2026-08-05 — R9-A5 ruling: producer-only enforcement is an accident of growth

**Provenance caveat.** The Architect reported confirming consumer-chain mechanisms in
"the current working tree… 2279 lines". Orchestrator-verified line counts:
`c6ef2df` = 2279, `1aca37d` = 5112, `92a12f6` = 5131. The Architect therefore read
`D:\qwen-sae-interp` at **stale main `c6ef2df`**, a revision predating the entire
builder. The ruling is architectural doctrine and stands on its own reasoning, and the
export citation (`requirements.cluster.txt:2175`) is exact — but its *independent
mechanism confirmation was against the wrong revision*. **Third occurrence of the
stale-main-worktree hazard**; every future role brief must name the exact revision and
worktree to read.

**Doctrine.** The bundle crosses a trust boundary — built off-cluster, transferred by
hand, consumed on-cluster. ED-36 §3 places the obligation at the consumer in its own
verb. A control existing only on the producer is, from the consumer's standpoint, not a
control: it is an assumption that one particular producer ran, which the consumer
cannot observe. **Producer-side checks are fail-fast ergonomics; consumer-side checks
are the security boundary.**

**TL is not an exposure.** The fact is enforced consumer-side by a *stronger* mechanism
than the missing gate — exact version plus hash binding rooted in a source-hash-bound
committed file, closed against the live environment by introspection. A hash binding
beats a declarative gate. **Layering asymmetry, not a hole.** For producer-only
duplication to stay safe, this must hold *and be stated per control*: the consumer
independently enforces the same fact by recomputation or introspection, without relying
on the producer having run.

**R9-A4 does not settle this.** A4 ruled which *implementation* is normative; its "on
every path" claimed the validators' universality wherever manifests are read, not that
every fact is checked at every surface. A4 settles mechanism, A5 settles surface —
orthogonal halves. A4 is not retrofitted to pretend otherwise.

**The general rule — classify by the kind of fact, not by convenience:**

| Class | Fact type | Enforcing surface | Examples |
|---|---|---|---|
| Recomputable | property of bytes present at consumption | **Consumer mandatory**, producer optional | hashes, sizes, versions, filenames, closure completeness |
| Attestable-only | property of a past event the consumer cannot re-observe | **Producer mandatory**, recorded and hash-bound; consumer verifies record integrity, never the event | network isolation, build argv, backend origin, build-input closure |
| Declarative | a claim the manifest makes about the world | **Never sufficient alone**; closed at the consumer by live introspection | "TL is 3.2.1", "torch is CUDA x" |

The test a future Engineer applies: *"If a hand-crafted bundle that never saw the
builder were handed to the consumer, would this control still hold?"* If no, it belongs
on — or must extend to — the consumer. Where the fact is attestable-only, the honest
answer is "the consumer verifies the record, not the event," and that limitation must be
**explicit in the control's design, not implicit in its absence**.

**Corollary preventing recurrence:** no ED-36 control may be discharged solely by a
producer-side check. Adding one to the builder is permitted only together with a
statement naming the consumer-side mechanism enforcing the same fact.

**Gating.** Does **not** gate R9-I1 — integration publishes producer-side code that adds
a layer and removes nothing; no control regresses. **Does** gate first real construction
and consumption: a **consumer-only** adversarial matrix must pass first, because
co-testing producer and consumer cannot distinguish "the consumer enforces this" from
"the producer never emitted a violation." Minimum cases, each hand-crafted and fed to
the consumer path alone: TL declared 3.4.0; TL 3.2.1 with a hash outside the export's
authorized set; manifest declaring 3.2.1 while the live environment has 3.4.0; TL absent
from the closure; and the same shape for torch identity and for one recomputable control
(recorded hash not matching bytes).

No ED amendment, no path expansion. *Orchestrator note: the Architect labelled the
follow-on `R9-C4`, which is taken by commit `1ed3ad9`. Reassigned as **R9-C12**,
sequenced after R9-I1 and before first real construction.*

## 2026-08-05 — R9-A4 ruling; two standing records corrected

### Correction 1 — the `rpds-py` watch item was WRONG. Do not re-cite it.

The R9-V6 finding that `rpds-py` has no offline Linux wheel is incorrect, and the
"forward-looking watch item" transcribed from it on 2026-08-04 is withdrawn. The lock
records `rpds_py-2026.6.3-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl`,
and `jsonschema`, `referencing`, `attrs`, and `jsonschema-specifications` are each
pure-Python `py3-none-any`. Orchestrator-verified in the frozen export:
`rpds-py==2026.6.3` at `:1721`, `attrs` `:132`, `jsonschema` `:609`,
`jsonschema-specifications` `:613`, `referencing` `:1598`. **The entire jsonschema
closure installs offline on the cluster target with no compilation and no derived
wheel.** This also confirms R9-A3's count: `rpds-py` is not a third source-only
package. What R9-V6 actually measured was its own unpinned `slim-bookworm` audit
container, not the cluster target.

### Correction 2 — R9-V2's "all TransformerLens surfaces untested" is OUTDATED.

Superseded by R9-V8: TL tests exist and 11 pass. Must not be re-cited.

### R9-A4 ruling: (d) as doctrine, (b) as mechanism, closed by a mandatory anti-drift test

The real constraint is structural and permanent: `jsonschema` is unavailable
pre-activation because `preflight` runs on bare system python before any venv exists,
and it is the gate that decides what gets installed.

1. **The hand-written Python validators are the normative enforcement contract** — on
   every path, pre- and post-activation, stdlib-only. They are not a fallback. They
   are strictly stronger than the schema: they enforce cross-artifact semantics JSON
   Schema cannot express — export hash authorization, lock-sdist binding, target
   equality, runtime/tooling overlap identity, build-input closure completeness.
   Nothing may weaken them.
2. **The schema is the declarative shape contract**, enforced as defence-in-depth only
   where `jsonschema` is legitimately present — the two post-activation sites
   (`record-installed`, `certification_environment_inputs`) — via **function-level lazy
   import inside post-activation code paths only**. Module-level imports stay stdlib.
   Pre-activation paths never touch it, directly or transitively.
3. **The pre-first-write condition is closed by drift-proofing, not runtime
   enforcement.** A deterministic offline CI test asserts the two validators agree on
   shape over a corpus: valid fixture ⇒ both accept; every shape mutation ⇒ both
   reject; every semantic mutation (hash mismatch, unauthorized export hash,
   lock-sdist mismatch) ⇒ Python rejects, and schema acceptance is **recorded as
   expected and documented**, because the schema cannot express these. **The invariant
   is directional: the Python validators must be at least as strict as the schema,
   never the reverse.** Demanding bidirectional equivalence would be wrong and would
   pressure someone to weaken the validators to match a shape-only document.

Rationale: the genuine risk in an unenforced schema is not unchecked shape — the
Python validators check it more strictly — but that the schema **drifts and becomes a
false description of the trust chain**. A CI equivalence test converts "unenforced,
may drift" into "cannot drift undetected," which is the guarantee R9-D4 wanted.

Rejected: (a) deferring preflight validation leaves the install-deciding gate
unenforced at gate time and inverts the trust order. (c) vendoring a JSON Schema
validator into the bootstrap adds a second, itself-unvalidated implementation to the
most safety-critical stdlib-only surface, to re-check a shape already checked more
strictly — disproportionate and net-negative.

For the D4 chain to stay honest: the schema is provably a subset of what the
validators enforce; drift is CI-detectable; the schema is **never described in any
artifact, manifest, or document as the enforcement mechanism**; and any manifest
written passes both wherever both are available.

**No ED amendment** — ED-36 §3 mandates verification, not a validator technology; the
Python validators satisfy it today. **No path expansion** — paths 1, 4, and 7 only.
**Stop condition:** if wiring post-activation enforcement requires modifying
`_schema_registry.py` or `config_lifecycle.py`, halt and escalate.

*Orchestrator note: the Architect labelled the follow-on work item `R9-C3`, which is
already taken by commit `490ae73`. Reassigned as **R9-C9**.*

## 2026-08-05 — R9-C8: row 7 defect does NOT reproduce; coverage gap closed

Commit `70c6d25`, test-only (40 insertions), no push. **Reproduction negative.**

Two rollback mechanisms coexist. The unsafe one —
`except Exception: _rollback_partial_path(x); raise` — would indeed drop the primary
error if cleanup throws, because the bare `raise` never executes. But
`finalize_bundle`'s atomic-promotion path does **not** use it: it routes through
`_rethrow_primary_with_cleanup` (`:384-393`), which collects cleanup failures into a
list and always re-raises the original primary exception, appending a "cleanup failed
after primary error" note rather than replacing it.

Verified empirically, not by reading: the regression was written against the
**unmodified** file first — tamper a copied artifact so `finalize_bundle`'s internal
`validate_bundle` raises `EnvironmentBundleError: bundle artifact … mismatch`, then
monkeypatch `_rollback_partial_path` to raise `PermissionError` only for the
`.bundle-staging-*` path. It passed at `1aca37d` unmodified; the original error
survives with the cleanup note. `create_virtualenv` already had the equivalent
regression; `finalize_bundle` never did. **Row 7 was a coverage gap, not a live bug.**

**New finding, unscoped:** the genuinely unsafe pattern does exist in four functions —
`_extract_sdist_to_directory`, `_bootstrap_private_pip`, `_build_derived_runtime_wheel`,
`build_runtime_bundle`. Outside atomic finalization and outside R9-C8's scope; the
Engineer correctly left them. These sit on the **real bundle-construction path**,
where a masked primary error would be most costly. Tracked as **R9-C11**.

## 2026-08-05 — R9-V8: matrix row 11 **COVERED**, with one MAJOR coverage defect

Record: `d:\lodstar\R9_V8_TL_SEPARATION_AUDIT.md`. Host-local over committed bytes;
no container, so the V6 networked-staging caveat does not arise.

- **Contract** (`:67-68`): `transformer-lens==3.2.1` admitted, `3.4.0` forbidden
  everywhere except `comparison.candidate_transformer_lens` in the equivalence report
  (`:3189-3192`) — exactly where it belongs. 3.4.0 may be reported on, never installed.
- **Eight enforcement sites, not two**, mapped by AST: `:1795`, `:2073`, `:2089`,
  `:2154`, `:2221`, `:2225`, `:2400`, `:2401`. Second independent source of truth:
  `requirements.cluster.txt:2175` pins `transformer-lens==3.2.1` and
  `source_hashes_for_root` (`:215`) hashes that file, so the pin cannot be swapped
  without `_validate_source_hashes` (`:285`) raising.
- **Fails closed both sides.** Producer, from an accepted clean baseline: 3.4.0 alone,
  both present, unexpected versions (3.9.9, 3.2.1rc1), duplicate 3.2.1 under
  `require_exact_runtime`, malformed entries — all rejected; name normalization
  catches every real alias. Neither-present is admitted only where
  `require_exact_runtime=False`, the tooling contexts where TL absence is correct.
  Consumer, against real requirements bytes: version mismatch (`:3363`), closure
  failure on absence, duplicate rejection, unauthorized hash (`:3382`), closing to the
  live environment via `_installed_distributions()` (`:4853`, real
  `importlib.metadata`) under exact version equality.
- **No bypass**, but a real asymmetry: transitive call-graph analysis shows the
  TL-specific gate is **unreachable from every consumer function** —
  `load_acquisition_manifest`, `validate_acquisition_manifest`,
  `_validate_acquisition_manifest_semantics`, `_validate_install_manifest_consistency`,
  `validate_bundle`, `certification_environment_inputs` all return False. Producer-side
  only. The consumer path carries the same fact by exact version+hash binding rooted in
  a source-hash-bound file, but defence there is single-layered.
- **Pre/post-activation does not apply.** `environment_bundle.py` never imports
  `transformer_lens`; after import `sys.modules` contains no `transformer*`. The gate is
  pure stdlib dict/string logic over declared metadata. Not R9-A4-adjacent. Corollary:
  being declarative it admits a manifest claiming 3.2.1 regardless of what is
  installed — that half is carried by the install manifest's real introspection.
  Neither half suffices alone; together they do.

**V8-F1 — MAJOR coverage defect.** All 11 TL tests exercise **branch 1 only**:
branch 2 (unexpected version) 0 tests; branch 3 (exactly one 3.2.1) 0 tests; 5 of 8
call sites and all consumer-path TL rejection 0 tests. All three branches proven to
fire. Same class as V3's F1, which R9-D4 §4 ruled BLOCKING. Branch 2 guards a future
TL 4.x — the most likely real drift. Reproduction:
`b._reject_transformer_lens_contamination([{"distribution":"transformer-lens","version":"4.0.0"}], context="probe")`
raises `unexpected transformer-lens version: ['4.0.0']`, while
`grep -rc "unexpected transformer-lens version" tests/*.py` returns 0.

**Pattern for the release audit:** the TL gate is producer-side only, and the
acquisition schema reaches no production read path. **Two independent ED-36 controls
are absent from the consumer surface.** That is a pattern, not two isolated findings.
Routed to the Architect as **R9-A5** rather than a third point fix.

## 2026-08-05 — Authoritative R9 path set (Orchestrator ruling, closes an open V3 question)

R9-V3 requested the authoritative seven-path list and never received one. Resolved
from the commit record:

- **R9-C1 `c847e07` changed exactly five:** `interplab/core/environment_bundle.py`,
  `slurm/environment_bundle.tooling.lock.json`, `slurm/setup_env.sh`,
  `tests/test_environment_bundle.py`, `tests/test_environment_bundle_builder.py`.
- **R9-D3** added `tests/test_slurm_setup_env.py` → six, cumulative at `490ae73`.
- **R9-D4** added `schemas/environment_acquisition_manifest/v1.schema.json` → seven,
  cumulative at `1ed3ad9`, `82b028e`, `1aca37d`.
- `schemas/environment_install_manifest/v1.schema.json` **exists in the tree but was
  never modified on this branch**, consistent with R9-D4's finding that the install
  schema requires no present edit.

**Ruling: the V5/V6 set governs.** V3's enumeration contained two transcription
errors — it included the install-manifest schema, which was never in the change set,
and omitted `test_slurm_setup_env.py`. It is not a competing authority. V3's
substantive findings are unaffected; only its path listing was wrong. Row 1 of the
V1-PREP matrix is certified.

## 2026-08-05 — R9-V1-PREP matrix reconstructed: 5 of 13 rows covered

Record: `d:\lodstar\R9_V1_PREP_MATRIX_RECONSTRUCTION.md`.

**Provenance — must survive any future citation.** The Auditor had no original
R9-V1-PREP record; that session began at R9-V6, and V3 independently confirmed the
matrix exists in no ref, filename, or content. The reconstruction is not guesswork:
a durable enumeration survives at `CURRENT_PLAN.md:1387` ("R9-V1-PREP result") naming
all thirteen row spans, and `COMPLETION_LEDGER.md:227`'s eleven reconcile to it
exactly (merging setup + pip check, folding in non-overwrite). **Per-row criteria are
reconstructed from R9-V1's and R9-V2's failing-boundary lists — faithful but lossy:
any criterion that passed at `c847e07` never entered a failure list and is invisible
to this reconstruction. The row set is trustworthy; the criteria are good enough to
drive work, not to claim completeness.**

| # | Row | Covering audit | Verdict |
|---|---|---|---|
| 1 | Scope | V6 (+V5, V3) | COVERED |
| 2 | Derivation | Orchestrator, this entry | **COVERED** (see below) |
| 3 | Target capture | V3, re-anchored V5+V6 | COVERED |
| 4 | Tooling closure | — | NOT COVERED |
| 5 | Derived wheels | V3+V5+V6 | COVERED |
| 6 | Alliance torch | — | NOT COVERED |
| 7 | Atomic finalization | — | NOT COVERED |
| 8 | Setup (D3) | V3, re-anchored | COVERED |
| 9 | Pip check | — | NOT COVERED |
| 10 | Non-overwrite | — | NOT COVERED |
| 11 | 3.2.1 isolation (TL) | — | NOT COVERED |
| 12 | Regression | V3+V5+V6 | COVERED |
| 13 | Retained state | — | NOT COVERED |

**Row 2 (Derivation) is now COVERED** by transcription of the Auditor's read-only
ancestry proof: `4bf0fd8` is an ancestor, and the chain is exactly linear —
`c847e07 → ea65a87 → 490ae73 → 1ed3ad9 → 82b028e → 1aca37d`, no side branches. The
five-path binding is **superseded, not drifted**: D3 added path 6, D4 added path 7.
Behavioural rows re-anchor; rows 3 and 8 re-anchor by proven byte-identity, which is
direct evidence.

Zero obsolete rows. **One obsolete sub-criterion:** under row 5, any demand for
literal `==` build requirements is void, superseded by R9-A3 Option 2 (ranges may map
to the sole exact locked artifact).

**Uncovered, priority order:** row 11 (TL separation — scientific contamination
boundary, enforcement exists but has never been exercised); row 7 (finalization /
rollback — the only unclosed concrete defect: R9-V1's Windows `PermissionError`
masking the intended environment error, which no record since closes); row 6
(Alliance torch); row 9 (pip check); row 4 (tooling cross-binding); row 13 (retained
state, cheap); row 10 (non-overwrite — re-anchor only, V2 passed it).

**Headline for the release audit:** the covered rows are exactly the
schema/validator/regression surface the V3→V6 chain was chartered for. **No single
audit has ever certified the builder end-to-end.** Rows 4, 6, 7, 9, 11 are first-time
work, not re-checks. The release audit is **not queueable** until they are closed.

## 2026-08-05 — R9-C7 stop condition: schema enforcement collides with the bootstrap

Engineer 2 did not implement, correctly. Base `1aca37d` verified against HEAD; all
four do-not-touch hashes reproduced exactly under the V6 convention; worktree
untouched, no commit.

Bootstrap-reachability mapping, tracing every caller of
`load_acquisition_manifest` / `validate_acquisition_manifest`:

| Caller | Subcommand | Invoked by | Interpreter at call time |
|---|---|---|---|
| `validate_bundle` (`:2504`) | `preflight` | `setup_env.sh:78` | bare python, **before** `source $VENV_DIR/bin/activate` (`:97`) |
| `create_virtualenv` (`:3841`) | `create-venv` | `setup_env.sh:88` | same — still pre-activation |
| `record_installed_environment` (`:2601`) | `record-installed` | `setup_env.sh:111` | venv python, post-activation and post-`pip install` |
| `certification_environment_inputs` (`:862`) | library call | `registry/config_lifecycle.py` (certify/characterize/validate/steer) | venv python; that module already imports `_schema_registry` at top level |

`jsonschema` is a real dependency (`pyproject.toml:23`, `slurm/requirements.cluster.txt:609`),
so the two post-activation sites are safe. But **`load_acquisition_manifest` /
`validate_acquisition_manifest` is one shared function body serving all four sites —
there is no fork.** Lazy `jsonschema` enforcement inside it would raise `ImportError`
on every real cluster `setup_env.sh` preflight, before a venv exists — a silent
bootstrap break. Enforcing only at the two safe sites would leave `preflight` — the
gate that decides what gets installed — unenforced, so it would not close the
pre-first-write condition in substance either.

**Genuine architectural ambiguity. R9-A4 opened with the Architect.**

## 2026-08-04 — R9-V6 delta audit: **ACCEPTED** at `1aca37d`

Record: `d:\lodstar\R9_V6_ED36_HARDENING_DELTA_AUDIT.md`.
Verdict bound to the seven blob hashes (sha256[:16] of committed bytes) at
`1aca37d8e437125e70ba793a4882b5aac9760f66`:

| Path | Hash | vs `82b028e` |
|---|---|---|
| `interplab/core/environment_bundle.py` | `8abdacfb3694b577` | changed |
| `schemas/environment_acquisition_manifest/v1.schema.json` | `b69e4dc83bbc9d4a` | unchanged |
| `slurm/environment_bundle.tooling.lock.json` | `4df4f6e701a7562b` | unchanged |
| `slurm/setup_env.sh` | `cb0aecf3d9fd6684` | unchanged |
| `tests/test_environment_bundle.py` | `bc4b3076eb0d2eac` | unchanged |
| `tests/test_environment_bundle_builder.py` | `59ed6c7b602cd050` | changed |
| `tests/test_slurm_setup_env.py` | `a81d12f31344bce0` | unchanged |

The five unchanged rows reproduce V5's recorded values exactly — independent
corroboration that the delta is confined to two files.

**Supersedes the V5 "1 skipped" line.** `tests/test_environment_bundle_builder.py:1381`
**PASSED in-container as a real pass**, not a skip. A falsification control was added
because `--network none` could have made it pass trivially: with the guard the child
dies with `RuntimeError: network access is forbidden…` from `_deny`; without it, a
plain `socket.gaierror` and the asserted message is absent. The assertion is carried
by the guard, so the test fails if the boundary regresses. Real `unshare` observed:
`net:[4026532604] → net:[4026532701]`.

- Not over-tight, verified against the builder rather than the fixture: the real
  builder's `evidence.json` was fed through the live gate. Python emits exactly
  `{error, succeeded}`; native (`:1233-1237`) emits exactly
  `{argv, returncode, stderr, stdout}`. Both accepted; both reject a stray key. The
  python set cannot be wider — `:1204-1205` raises on the `succeeded: True` branch
  before the evidence dict at `:1224` exists, so only the 2-key form can reach a
  manifest.
- Ternary confirmed at `:4269` in both commits; `ast.dump` byte-identical.
- 772 passed / 1 skipped / 3 deselected, exit 0 (770 + 2, no silent loss); the sole
  skip is `:1381`, converted in-container. Exact CI Ruff, `uv lock --check`
  (196 packages), `bash -n` ×6, `git diff --check` on both ranges — green.
  14 worktrees at start and end; branch tip unmoved.

**Documentation defect, closed.** V5 never stated its hash-extraction convention, so
V6 recovered it by brute force against `fee1cc1d` and applied it to the rest. The
convention is: **sha256[:16] of the unit's full line range (LF, trailing newline)
for code, and `json.dumps(sort_keys=True)` for the schema object.** Re-derived from
`1aca37d`'s own bytes: `fee1cc1d5c08a30c` (`_current_target_capture_fields`),
`37d1e3419152854b` (`:3518-3529`), `cec269ddc0d4dfa3` (`:4253-4263`),
`e135248a0473e905` (schema `:357-383`). Both delta hunks land outside the
`:4253-4263` builder gate. Future audits must not repeat the brute-force recovery.

**Stated limitation of the audit environment.** `python:3.11-slim-bookworm` ships no
pytest or jsonschema, and `rpds-py` requires compilation with no Linux wheel
available offline. Dependencies were staged via a separate **prior networked
container**; the measured test run itself was `--network none --pull never` with the
repo mounted read-only. The measurement is sound — the network was closed during
measurement and the falsification control is independent of it — but the audit
container is **not** hash-pinned ED-36-grade offline evidence and must not be cited
as such. Nothing was retained in the repository or any bundle.

**Forward-looking watch item.** That `rpds-py` finding is intelligence for real bundle
construction: `jsonschema` depends on `rpds-py`, which needed compilation and had no
offline Linux wheel here. R5-X2 was already blocked in part by "unavailable locked
packages in the Alliance wheelhouse." Expect `rpds-py` to be among them.

**Carried forward unchanged:** the acquisition schema remains unenforced on any
production read path — `environment_bundle.py` has no `_schema_registry` reference at
`1aca37d`. The pre-first-write blocking condition stands. The R9-V1-PREP matrix is
still absent.

## 2026-08-04 — R11-C00 Engineer completion, one amendment, one Orchestrator error

Evidence root: `D:\interlab_evidence\r11_c00_20260804\` (pre/post hashes, 12-hunk
unified diff). Edited in place; no branch, worktree, or commit, as ruled.

Eight sites corrected across four files. Pre→post SHA-256 and byte sizes recorded
for all four. `git status --porcelain` identical before and after — nothing entered
the index, and the four untracked exclusions were untouched.

- The four target lines remain byte-identical across both `internship_report.md`
  copies, pre and post.
- The pre-existing divergences were **independently re-derived from a raw diff**
  rather than taken from the brief, and resolve to 14 lines: 37, 71, 145, 148, 160,
  194, 206, 209, 229, 292, 358, 385, **394, 409** — all image-path differences. This
  names the "two others" the Orchestrator count had left unspecified. All unchanged.

**Orchestrator error, corrected.** The brief asserted all four files are UTF-8
without BOM. That was generalized from a byte check run on
`reports/internship_report.md` alone. Verified actual state:
`internship_report.md` (both copies) and `script_oral_detaille_interlab_lodestar.md`
have **no BOM**; `fiche_revision_composantes_scientifiques.md` has a **genuine
pre-existing BOM** (`ef bb bf`), before and after. The Engineer preserved it rather
than stripping it — correct. Any audit criterion demanding "no BOM on all four" is
void and must not be used.

**R11-C00-A — one-line amendment authorized.** `fiche` line 685
("Haut alpha : le juge est stable avec lui-même.") uses the prohibited "stable"
framing. The Engineer correctly flagged rather than deciding scope. It is inside a
permitted file and inside the §45 block the work order directed to be "corrected
together"; the `674–681` enumeration simply stopped one line short. Authorized as a
routine application of the ratified rule, not a scope expansion.

Orchestrator sweep for stragglers across all four files, post-edit: **685 is the
only one.** Confirmed non-hits, deliberately left: fiche 690/698 (new approved
wording using the terms in explicit negation), fiche 739/740 (pre-existing correct
guards), fiche 896 (the `sweep_hash` analytic-grouping bug, accurate as written),
fiche 1243 and `script_oral` 347/377/477 (text quality and feature behaviour, not
the judge), `internship_report` 282/490/376 (model reliability and prior practice).

## 2026-08-04 — R9-V3 verdict (recovered) and R9-V5 acceptance

Source records: `d:\lodstar\R9_V3_ED36_BUILDER_REACCEPTANCE_AUDIT.md` and
`d:\lodstar\R9_V5_ED36_BUILDER_FINAL_ACCEPTANCE_AUDIT.md`. F1–F4 below are
transcribed from the Auditor's own §Deliverable 0, **not** from the Engineer
commit message that previously served as their only trace.

### R9-V3 on `1ed3ad98bad03e084a7237263ea7c9d0b69b3a4d`: **REJECT**

Failed on two acceptance criteria — Target 2 ("strictness not traded for
coverage") and Target 3 ("deterministic negative test per stop condition"). Both
additive.

- **F1 — BLOCKING.** Eight of nine R9-D4 §4 stop conditions had no negative test;
  only `undeclared build requirement` was covered. Enforcement itself was correct
  — all nine branches verified live. Coverage gap, not a correctness defect.
- **F2 — MAJOR.** The isolation proof had no floor. Both connection-attempt
  objects were bare `{"type":"object"}`; `{}` validated. Code was asymmetric:
  the python side rejected a missing key via `is not False`, the native side did
  not. Only `returncode: 0` was rejected.
- **F3 — MODERATE.** `inventory_entry.sha256`/`size_bytes` were optional, so a
  `type:"file"` entry with no `sha256` validated. Mitigated by code at `:4246-4248`.
  The aggregate `extraction_inventory_sha256` did not compensate — it binds paths,
  not contents.
- **F4 — MINOR.** `derived_tool_record.backend_path` was optional and code
  tolerated omission. Non-empty backend-path was still enforced at build time.

Certified adequate at V3 and marked do-not-touch: target/build-host identity;
SOABI and ordered compatibility tags in `derived_wheel.builder`; SOABI hard-fail
if unresolvable (`:234`); `compatible_tags` order enforced via list `!=` (`:3526`);
exact-field binding to the manifest target (`:3519-3523`).

### R9-V5 on `82b028e160e62abe6012b60965944b77413817dd`: **ACCEPTED**

Fresh detached `core.autocrlf=false` worktree, created/used/removed/pruned;
14 worktrees at start and end; branch tip unmoved; read-only throughout.

Governing hashes (canonical git blob, sha256[:16]) — the seven authorized paths:

| Path | Hash |
|---|---|
| `interplab/core/environment_bundle.py` | `9b0d0f96203291e8` |
| `schemas/environment_acquisition_manifest/v1.schema.json` | `b69e4dc83bbc9d4a` |
| `slurm/environment_bundle.tooling.lock.json` | `4df4f6e701a7562b` |
| `slurm/setup_env.sh` | `cb0aecf3d9fd6684` |
| `tests/test_environment_bundle.py` | `bc4b3076eb0d2eac` |
| `tests/test_environment_bundle_builder.py` | `5b835ff2158af614` |
| `tests/test_slurm_setup_env.py` | `a81d12f31344bce0` |

- Scope exactly seven paths, no eighth. V4 delta touched three.
- F1 closed: nine branch-unique negatives driving the real builder path via
  `_build_derived_wheel_with_pyproject`; independent attribution matrix with an
  **accepted clean baseline**, proving each raise is attributable to its single
  mutation and no shared earlier guard fires.
- F2, F3, F4 each closed and independently re-derived.
- Real Linux namespace evidence executed: Docker 28.5.1, `desktop-linux`, local
  `python:3.11-slim-bookworm`, `--network none --pull never`. Measured
  `net:[4026532604] → net:[4026532701]`, descendant inherits child namespace,
  `lo` only, no routes, no socket fds, `getent` rc 2.
- Regressions: **770 passed, 1 skipped, 3 deselected, exit 0** (752 + 18 new, no
  silent loss). Exact CI Ruff (`ci.yml:28`), `uv lock --check`, `bash -n` ×6, and
  `git diff --check` all green.
- Builder construction byte-unchanged: `_current_target_capture_fields`
  (`fee1cc1d…`), `current_target`, `marker_environment_for_target`,
  `validate_target_capture_report`. Only `_validate_derived_wheels` and
  `_validate_derived_entry_shape` moved; their builder blocks are byte-identical
  (`37d1e341…`, `cec269dd…`), as is the schema builder object (`e135248a…`).

### Item 3b ruling and the gap behind it

Native `{succeeded: true, returncode: 1}` is admitted by the code layer and
rejected by the schema. Ruled **benign redundancy, not fail-open**: the builder
emits exactly `{argv, returncode, stdout, stderr}` (`:1233-1237`, confirmed in the
container run — no `succeeded` key); the sole reader is `:3693-3696` reading
`returncode`; `returncode: 1` is a genuine failure so the isolation conclusion is
correct; and the unsafe states (`0`, missing, `None`) all remain rejected.

**Orchestrator elevation.** The Auditor also established that
`_validate_derived_entry_shape` applies only `_require_mapping` to the attempts
(`:4313-4314`), and that **the acquisition schema is not applied in any production
path** — `environment_bundle.py` never imports the schema registry and no job
validates this manifest against it. At runtime the Python validators are the sole
gate. This is correctly non-blocking for accepting `82b028e`, because those
validators do reject every unsafe state. But it is **not** non-blocking for real
construction: schema path seven was ratified under R9-D4 precisely to encode the
trust chain, and an unenforced schema records that chain without guaranteeing it.
Recorded as a **pre-first-write blocking condition** — no real acquisition
manifest may be written until the schema is enforced on a production read path.

## 2026-08-04 — R11-D1A ratified (Program Manager), all four as recommended

Verdict: **Accepted.** Quotable rationale per decision:

1. **Instrument continuity — retain temperature 0.** "Judge temperature is retained
   at 0 for the bounded T1.2 instrument so that necessity evidence remains
   measurable on the same instrument that produced the existing sufficiency
   evidence; the three repeats are reclassified as determinism checks under fixed
   settings, and any genuine stochastic-variability study requires a separately
   versioned instrument with its own manifest, prompt_version, and A12 review."
2. **Prose correction — authorized, partially blocking.** "The α ≥ 0.91 figure must
   be restated as near-deterministic repeat agreement under temperature 0 rather
   than as judge reliability, stability, or validated repeatability, in a
   prose-and-evidence-only correction that changes no schema, config value,
   artifact hash, figure, or executable code."
3. **Retrospective instrument manifest — authorized with caveat.** Reconstruction
   from retained run fields plus current source is authorized, carrying an
   on-record statement that temperature and max-token identity are **recovered
   from the present working tree, not proven runtime bytes**, because `D:\lodstar`
   is not a Git repository. Equivalence with the ED-37 v2 instrument is deferred
   to an explicit later A12 decision and is not automatic.
4. **Coherence — reported, non-gating.** "Coherence v1.0 is added to T1.2
   production judging as reported, non-gating diagnostic evidence on the same
   blinded records and identical instrument settings; `concept_relevance` remains
   the sole preregistered acceptance metric, and coherence may not alter the H1/H2
   thresholds or introduce any post-hoc operating-point rule."

Blocking scope is **narrower than originally stated**. The Program Manager
verified `sae.pptx` directly: it carries no stale judge-reliability claim (slide 2
is model safety, slide 5's α is the steering-scale symbol, slide 34's "trois
mesures indépendantes" is the three triangulation streams, slide 38's "stable"
describes text quality). **The deck is safe to present as-is.** Spoken delivery is
what is blocked: `script_oral_detaille_interlab_lodestar.md` lines 171/457 and
`fiche_revision_composantes_scientifiques.md` lines 690/698. The fiche is the most
acute risk because a revision sheet propagates into unscripted answers.

Standing presentation rule: slide 5 teaches the audience that α denotes the
steering scale, so **all French oral and revision material must spell "Krippendorff
alpha" in words and never use the bare symbol.**

## 2026-08-04 — Orchestrator verification of the R11-C00 work-order premises

Commands: SHA-256 of both `internship_report.md` copies; line-by-line comparison;
direct read of all thirteen pre-located sites.

- All pre-located line numbers are **accurate**; text matches the description at
  `internship_report.md` 92/398/470/529, `fiche` 690/698/604/674/681/739/740, and
  `script_oral` 171/457. No discovery is needed.
- The correctly-excluded sites are confirmed excluded: `internship_report.md` 282
  and 490 concern model reliability (feature 19815, base vs instruct), 376
  describes the prior practice Lodestar replaced, and `script_oral` 163 likewise.
- **Premise correction:** the two `internship_report.md` copies are **not
  byte-identical** — SHA-256 `F2BE5AD0…4947` vs `5E84E85F…8159`, differing on 14
  pre-existing lines (37, 71, 145, 148, 160, 194, 206, 209, 229, 292, 358, 385, +2).
  Both are 560 lines. **All four target lines are identical across copies**, so the
  operational instruction holds, but the acceptance criterion must be restated:
  the four corrected lines must remain identical to each other, and the 14
  pre-existing divergences must be left untouched — neither reconciled nor widened.
- Both files are UTF-8 **without BOM** (first bytes `23,20,52,65`). The fiche and
  oral script contain heavy French diacritics; any write-back in CP1252 or with a
  BOM would corrupt them at scale. Encoding preservation is an acceptance criterion.

## 2026-08-04 — Orchestrator repository-state reconciliation (not an audit)

Commands: `git log --oneline 4bf0fd8..r9-ed36-bundle-builder`,
`git worktree list`, `git diff --stat`/`--name-only` across `490ae73`,
`1ed3ad9`, `82b028e`.

- Branch `r9-ed36-bundle-builder` tip is `82b028e160e62abe6012b60965944b77413817dd`;
  chain is `4bf0fd8 → c847e07 → ea65a87 → 490ae73 → 1ed3ad9 → 82b028e`.
- `D:\qwen-sae-interp-r9-repair` and `D:\qwen-sae-interp-r9-v3-audit-1ed3ad98`
  are both clean; no audit worktree exists at `82b028e`.
- Cumulative `4bf0fd8..82b028e` = exactly seven authorized paths.
- **No R9-V3 verdict was ever written here.** This is a durable-memory gap; the
  finding text must be recovered from the Auditor 2 conversation.
- This entry records repository facts only. It is **not** verification of
  `82b028e` and must not be cited as acceptance.

## 2026-08-03 — R9-C4 local Linux isolation capability

- Engineer 2 correctly stopped when native Windows lacked `os.unshare` and the
  direct WSL CLI returned `Wsl/Service/0x80072747`.
- Independent capability probing found Docker Desktop 4.48.0 active through its
  `desktop-linux` context. The server reports Linux amd64 kernel
  `6.18.33.2-microsoft-standard-WSL2`.
- The local image `python:3.11-slim-bookworm` (`b18992999dbe`) is already present.
  Therefore a real offline Linux namespace-positive path exists through Docker
  `--network none`; no image pull, network acquisition, or Tamia access is
  required. R9-C4 may resume rather than escalate a host-repair blocker.

## 2026-08-03 — R9-D4 schema-scope ratification

Verdict: **Accepted.**

- Program Manager confirmed at `490ae73e...` that `$defs.derived_wheel` is a
  closed nine-field object and cannot express the required extraction,
  PEP 508 mapping, full build-host, backend-origin, isolation, two-level argv,
  or derived-output trust evidence.
- Exactly `schemas/environment_acquisition_manifest/v1.schema.json` is added as
  cumulative path seven. No eighth path is authorized.
- This is a v1 clarification before first production write: the registry has no
  environment acquisition manifest to migrate.
- The install-manifest schema already links acquisition provenance by hash and
  needs no change. The frozen cluster export contains no source archive path and
  needs no R9-C4 edit.
- Future real derived-wheel construction will require a separately scoped R9-C5
  update that records the produced wheel filename/hash in runtime requirements.
  It is deliberately deferred because construction is not yet authorized.
- R9-D3 remains binding: setup success uses the fixture's real HEAD; zeroes are
  rejection-only. R9-V3 must use the exact candidate rather than stale local
  `c6ef2df` state.

## 2026-08-03 — R9-A3 derived-build semantics and exact schema inspection

Verdict: **Architecture complete; bounded Human scope ratification required.**

- Both Architects agree on Option 2: upstream PEP 508 declarations are
  compatibility constraints; the checked tooling lock selects the sole exact
  executable artifact. Direct URLs, VCS/path references, unauthorized extras,
  incompatible/ambiguous mappings, backend mismatch, and non-empty backend-path
  remain stop conditions.
- A normal runtime wheel remains authorized by its frozen-export hash. A derived
  runtime wheel is instead bound to the derived record's output hash, while that
  record's retained source-sdist hash must be export-authorized for the same
  normalized name/version. Runtime requirements use only the wheel hash.
- Linux kernel network-namespace isolation is mandatory before backend code;
  absent API support, permission denial, unchanged namespace, or incomplete
  proof aborts. Python socket denial is defense-in-depth only.
- The Architects differed only on schema scope. Read-only inspection of
  `schemas/environment_acquisition_manifest/v1.schema.json` at exact commit
  `490ae73e04cc5bfbfb814746aeab609e5e4f06fb` settles it: `derived_wheels.items`
  references a `$defs.derived_wheel` object with `additionalProperties: false`
  and a fixed field set. It cannot record the required extraction inventory,
  raw/mapped requirement evidence, full build-environment identity, backend
  module/provider/origin, or network-isolation proof.
- Therefore the conditional trigger in the Opus ruling fires and the GPT 5.6
  ruling governs scope: R9-D4 must authorize exactly the acquisition-manifest
  schema as path seven. No eighth path, ED change, dependency-truth change,
  external acquisition, Tamia action, bundle, environment, or experiment is
  authorized.

## 2026-07-28 — R0-CI-LINT

Classification: **Accepted**

- Engineer diff: only `scripts/characterize_lite.py` and
  `scripts/multilingual_rerun.py`.
- Change class: import organization, removal of unused `E402` suppressions,
  and `l` to `other_lang` local variable rename.
- Current exact CI Ruff command: exit 0, all checks passed.
- Verifier isolated default suite: 603 passed, 3 deselected.
- Verifier lock check: exit 0, 196 packages resolved.
- Current `git diff --check`: exit 0; line-ending warnings only.
- No artifact, interface, numerical, CLI, or scientific-output change found.

## Routing-policy update

Architect and Verifier are on-demand roles from this point. Engineer work
does not automatically route through both. The Orchestrator will request
Architect input only for a genuine contract ambiguity and independent
verification only when risk, milestone status, or evidence quality warrants
it.

## 2026-07-28 — R1-CONFIG-LIFECYCLE

Classification: **Accepted**

- Shared implementation: `interplab/registry/config_lifecycle.py`.
- All nine implemented jobs use the shared readable-invalid-config path.
- Existing readable invalid file: exit 3, exactly one failed A10, empty
  inputs/outputs, actual config hash/ref, no domain artifact.
- Certification-lane failure cards include required SAE-stack environment
  fields without entering the baseline gate or heavy work.
- Missing/unreadable paths and valid-run input lineage are unchanged.
- Engineer focused job suite: 103 passed.
- Engineer full default suite: 606 passed, 3 deselected.
- Engineer import-contract suite: 6 passed.
- Independent Orchestrator matrix: 15 passed (nine job lifecycle cases plus
  six import-contract cases).
- Current exact CI Ruff and `git diff --check`: exit 0.
- No separate Verifier activation was required; the bounded independent
  matrix was proportionate to the risk.

## 2026-07-28 — R2-DOC-CONTRACT-DRIFT

Classification: **Accepted**

- Diff is confined to `readme.md`, `slurm/launch_steer.sh`,
  `tests/test_import_contracts.py`, `interplab/evaluation/__init__.py`, and
  `docs/implementation_blueprint.md`.
- Inspection confirmed prose/comment-only changes: no executable, schema,
  dependency, artifact, golden-byte, threshold, or ED change.
- Repository anchors confirm backfill/certify configs exist, training and
  judge are absent, steer exists, the lock resolves SAE-Lens 6.44.2 with
  NumPy 1.26.4, and executable golden tests use a 128-ULP bound with measured
  clamp 32/add-direction 4.
- Independent focused tests: 8 passed.
- Independent exact CI Ruff and lock checks: green.
- Current `git diff --check`: exit 0; line-ending warnings only.
- Engineer full default suite: 606 passed, 3 deselected.
- No separate Verifier activation was required for this bounded
  documentary-only change.

## 2026-07-28 — R3-WP8-JUDGE-PRODUCER review

Classification: **Needs correction**

- Engineer added the expected judge job, config schema, wrapper, evaluation
  boundary, and focused tests without changing dependencies or artifact
  schemas.
- Engineer full default suite: 615 passed, 3 deselected.
- Independent judge/schema/import/statistics matrix: 44 passed.
- The success fixture itself omits
  `(prompt_id=p1, arm=random_direction, scale=2.0)`. The implementation
  verifies returned scores against records that happen to exist but never
  verifies the generation/correlation grid against A9 `payload.arms` or
  equal prompt coverage, so it writes an incomplete A9′.
- Measured boundary probe: `CapabilityMeasurement(n_tokens=1.5, ...)` was
  accepted and normalized to `n_tokens=1`; malformed runtime data must
  instead fail with exit 4 and no A9′.
- Measured input-classification probe: `_validate_unjudged_source()` given a
  wrong artifact type raised `KeyError`. In `run()` that reaches the generic
  exit-4 handler, although a non-A9 input is a contract violation requiring
  exit 3.
- No Architect or independent Verifier activation is needed; these are
  bounded implementation defects under the existing contract.

## 2026-07-29 — R3-C1-JUDGE-BOUNDARY-VALIDATION review

Classification: **Implementation corrected; independent verification pending**

- Engineer repaired the success fixture into the full two-prompt declared
  grid and added the required negative boundary cases.
- Source records/map are reconciled against declared A9 arms before runtime
  invocation; missing, duplicate, and undeclared cells map to exit 3.
- Wrong source artifact type explicitly maps to exit 3.
- Capability coverage is checked against validated declared cells.
- Fractional/boolean `n_tokens` and non-finite score/perplexity values map to
  exit 4 without coercion or A9′ writes.
- Engineer focused judge suite: 17 passed.
- Engineer preserved-contract matrix: 133 passed.
- Engineer full default suite: 626 passed, 3 deselected.
- Independent Orchestrator preserved-contract matrix: 133 passed.
- Independent exact CI Ruff and lock checks: green.
- Current `git diff --check`: exit 0; line-ending warnings only.
- R3-V1 activates the persistent Verifier because this is a new
  claim-bearing artifact producer and its first review exposed a scientific
  coverage hole.

## 2026-07-29 — R3-V1-JUDGE-PRODUCER-VERIFICATION

Classification: **Needs correction**

- Verifier focused judge suite: 17 passed.
- Verifier preserved-contract matrix: 133 passed.
- Exact CI Ruff, lock, and diff checks: green.
- ED-21 adversarial mutation probe: the external runtime mutated the
  in-memory source A9 `sampling.seed`; the registry source bytes remained
  unchanged, but the job later copied the mutated object into A9′ and exited
  0. A9′ therefore failed the identical-payload lineage requirement.
- Empty-grid probe: a zero-record/zero-map bundle produced an empty observed
  prompt set, making expected coverage vacuously empty. The job exited 0
  with zero per-prompt scores instead of input-contract exit 3.
- Import, wrapper, dependency-lock, and production-fake isolation checks
  passed.
- Verifier retained no probe artifacts.

## 2026-07-29 — R3-C2-JUDGE-IMMUTABILITY-EMPTY-GRID review

Classification: **Implementation corrected; targeted re-verification pending**

- Authoritative source hash, schema version, subjects, payload, and
  capability-slice reference are deep-snapshotted before external calls.
- Evaluator and capability runtime receive disposable deep copies of
  records, source artifact, config, and slice reference.
- A9′ is constructed only from sealed pre-runtime snapshots.
- Adversarial test mutates all runtime arguments while proving unchanged
  source bytes and identical A9′ lineage outside the two SS8 output fields.
- Empty records/map fails as input-contract exit 3 before runtime with one
  failed A10 and no A9′.
- Engineer focused judge suite: 19 passed.
- Engineer preserved-contract matrix: 135 passed.
- Engineer full default suite: 628 passed, 3 deselected.
- Independent Orchestrator preserved-contract matrix: 135 passed.
- Independent exact CI Ruff and lock checks: green.
- Current `git diff --check`: exit 0; line-ending warnings only.

## 2026-07-29 — R3-V2-JUDGE-CORRECTION-REVERIFICATION

Classification: **Accepted**

- Verifier focused judge suite: 19 passed.
- Hostile mutation probe exited 0 while preserving source, config, and slice
  bytes.
- Sealed payload, original subjects, appended `judged_from`, complete score
  grid, and original `capability_delta.slice` remained correct.
- Empty-grid probe exited 3 before runtime with exactly one failed A10, no
  A9′, and the source A9 retained.
- Inspection found no remaining authoritative mutable alias.
- Live Lodestar and production A9/A9′ evidence remain unverified under
  ED-19.
- Verifier retained no probe artifacts.

Combined R3 classification: **Accepted for local implementation scope**.

## 2026-07-29 — R4-V1-L28X16-COMPLETION-AUDIT

Classification: **Inconclusive — environment limitation**

- Repository/full-history searches found candidate ID `hm03l7yz` and
  expected path
  `results/sae_checkpoints/hm03l7yz/final_400001024` in historical
  survey/steering launchers at `6a0a03c`, `cf4b8a2`, and `70d40e3`.
- No committed Slurm job ID, completion log, W&B URL, or final artifact was
  found. The original parameter-sweep launcher used `WANDB_MODE=offline`.
- W&B project `qwen-sae-interp` could not be authoritatively queried because
  no API key/account/entity was available.
- Read-only SSH to `yazid@tamia.alliancecan.ca` was rejected, preventing the
  checkpoint and job/log search.
- The historical candidate is supporting evidence only. ED-35 forbids both
  promoting it to a completed checkpoint and dismissing it as never produced
  without authoritative evidence.
- No state was modified and no probe artifacts were retained.

WP2 consequence: **remains open pending R4-X1 external access/evidence**.

## 2026-07-29 — R4-X1-L28X16-AUTHORITATIVE-ACCESS

Classification: **Accepted — checkpoint recovered**

- Authoritative Tamia access confirmed
  `/scratch/y/yazid/qwen-sae-interp/results/sae_checkpoints/hm03l7yz/final_400001024`
  after eight intermediate checkpoints.
- The directory contains the full SAELens checkpoint, including
  `cfg.json`, `sae_weights.safetensors`, `trainer_state.pt`, and
  `runner_cfg.json`.
- `cfg.json` identifies L28×16: `d_sae=81920`,
  `blocks.28.hook_resid_post`, TopK k=100, and
  `sae_lens_version=6.44.2`.
- The checkpoint therefore shares the operative ED-33 6.x baseline. No new
  baseline analysis is required.
- W&B remains unrecoverable under the current entity. ED-30 permits
  `wandb: null`; training telemetry is not a certified metric and does not
  block A5/A6.
- Raw `cfg.json` / `sae_weights.safetensors` hashes are provenance
  cross-checks only. A5 identity must be computed on-cluster with
  `hash_checkpoint_dir` over exactly those two files.
- `training_provenance.transformer_lens` is an honest null.

WP2 consequence: **population settled at five; pending the fifth A5/A6**.

## 2026-07-29 — R5-X1-HM03L7YZ-A5-BACKFILL

Classification: **Accepted**

- Commit `04e88dc` contains exactly four authorized files: the
  `hm03l7yz` backfill config, byte-verbatim runner config, A5
  `3e6fdcb1187a`, and completed A10 `ada8ac14bd48`.
- The source and staged checkpoint directories contain the ED-27 identity
  pair. Staging used a preserving copy and the reported source
  size/mtime inventory was unchanged.
- On-cluster `hash_checkpoint_dir` returned
  `sha256:0f8670c078e843cb1db3691565126c353f1c65ee87d6e3c8ce8253eaab6da85e`.
  The A5 weights subject matches it exactly.
- The runner config is reported byte-verbatim at SHA-256
  `d45577d78df64686be4fee2243f0e7f87e13b2f78365210171b979d20925e242`.
- A5 records `wandb`, unavailable library provenance, and telemetry as
  honest nulls. It records 6.x / SAE Lens 6.44.2 measured from runner config.
- Backfill exited 0 and produced exactly one A5 and one completed A10. No A6
  or executable/contract file changed.
- Independent local `envelope.load` validation confirmed schema, canonical
  self-hashes, A10 completion, and A5 subject identity. The broader pytest
  invocation was unavailable because of the known Windows `uv` cache ACL
  and the existing project venv lacks pytest; this environment limitation
  does not affect the successful direct artifact validation.

WP2 consequence: **five A5 / four A6; pending R5-X2**.

## 2026-07-29 — R5-X2-HM03L7YZ-A6-CERTIFICATION submission

Classification: **Blocked at submission — implementation defect**

- Commit `6e3d044` adds only `configs/certify/hm03l7yz.yaml`; its hash is
  `6dfb9e35d5f179177f8f584b050f0e480fa30bbb3753c29ca7954d6b96c9f326`.
- Preflight confirmed the staged `tamia:` weights, ED-27 hash/A5 subject,
  corpus path, and certification environment. The SAE baseline gate passed
  with SAE Lens 6.44.2.
- Tamia rejected `slurm/launch_certify.sh` before creating a job:
  H100s are allocated only as a whole node (`h100:4`), while the launcher
  requests `h100:1`. The launcher also retains its uncalibrated `--mem=48G`
  instead of the proven `--mem=0`.
- No job ID, allocation, log, A6, A10, or report was created. The operator
  correctly stopped without editing code or changing scientific parameters.
- Four prior successful certifications establish the required allocation
  shape. This is a bounded launcher defect, not an architectural ambiguity.

WP2 consequence: **pending R5-C1 launcher correction, then resumption of the
same R5-X2 certification**.

## 2026-07-29 — R5-C1-CERTIFY-LAUNCHER-WHOLE-NODE

Classification: **Accepted**

- Commit `65ff603` changes only `slurm/launch_certify.sh`.
- Resource arguments are calibrated from `--mem=48G` / `h100:1` to
  `--mem=0` / `h100:4`.
- Only the adjacent provisional-resource comment also changed.
- Engineer `bash -n` passed.
- A non-submitting stubbed-`sbatch` probe found each calibrated argument
  exactly once and preserved job name, output/error paths, time, account,
  config interpolation, and wrapped command.
- `git diff --check` passed apart from unrelated pre-existing line-ending
  warnings.
- Independent commit inspection confirms the one-file scope and unchanged
  remote command/submission behavior.
- No live job, config, A6, A10, schema, dependency, or scientific output was
  produced.

WP2 consequence: **R5-X2 resumes through the corrected canonical launcher**.

## 2026-07-29 — R5-X2 job 387413

Classification: **Failed pre-entrypoint — launcher implementation defect**

- Tamia accepted the corrected whole-node request: `h100:4`, approximately
  500 GB node memory, eight CPUs, one node.
- Job `387413` failed `127:0` after one second. Its error log states:
  `module: not found`.
- `sbatch --wrap` generated a `/bin/sh` script, while the wrapped command
  assumes Bash initialization for the `module` function and uses the
  Bash-specific `source` builtin.
- `scripts/certify.py` never started. Therefore no run-card lifecycle began
  and no A10 was expected; no new A6, report, or registry artifact exists.
- The apparent “new” A6/A10 from an mtime-based monitor were stale
  `rwu04lpb` artifacts. Future monitoring must diff a pre-submission registry
  inventory or match run/output lineage, never infer novelty from newest
  mtime alone.
- Config hash, staged weights, corpus, and SAE Lens 6.44.2 gate were
  reconfirmed unchanged.
- The operator retained the scheduler record and
  `slurm/logs/387413_certify_hm03l7yz.err`, made no edits, and stopped.

WP2 consequence: **pending R5-C2 shell-boundary correction, then resumption
of the same R5-X2 certification**.

## 2026-07-29 — R5-C2-CERTIFY-LAUNCHER-BASH-WRAP Engineer review

Classification: **Implementation complete — Tamia preflight pending**

- Commit `70b7ed8` changes only `slurm/launch_certify.sh`.
- `REMOTE_CMD` operations and order are byte-unchanged.
- The launcher now builds
  `WRAP_CMD` with `printf -v WRAP_CMD 'bash -lc %q' "$REMOTE_CMD"` and passes
  it to `sbatch --wrap`.
- Engineer syntax, one-file diff, diff-check, scheduler-argument preservation,
  literal remote-venv fallback, and non-submitting capture checks passed.
- Independent commit inspection confirms the bounded diff and preserved
  resources/runtime command.
- The requested outer `/bin/sh` execution proof did not complete because of
  Windows Git/MSYS/WSL host failures. This is an evidence gap, not measured
  proof of a repository defect.
- No job or artifact was created.

Acceptance consequence: **R5-V1 must execute the captured payload harmlessly
on Tamia before R5-C2 is accepted and production is resubmitted**.

## 2026-07-30 — R5-V1-CERTIFY-WRAP-TAMIA-PREFLIGHT

Classification: **Accepted**

- Executed harmlessly on the Tamia login node (host-only verification, no
  `sbatch`, no real Python, no GPU allocation — per CURRENT_PLAN "do not
  consume another allocation").
- Repo at `70b7ed8`; `slurm/launch_certify.sh` (blob `ae5687f7…`) and
  `configs/certify/hm03l7yz.yaml` (blob `53692bd9…`) unmodified in the working
  tree.
- A temp `sbatch` stub (outside the repo) captured the launcher's exact
  `--wrap`. Decoded as `/bin/sh` tokenizes it, the argv is exactly
  `bash` / `-lc` / one payload; the venv fallback
  `${INTERPLAB_VENV_DIR:-$HOME/interplab-venv}` is present **unexpanded** (no
  submit-host expansion of the temp path).
- Executing the captured wrap through `/bin/sh` exited 0: login Bash
  initialized `module`, `module purge` + `module load python/3.11 arrow`
  succeeded (loaded `python/3.11.5`, `arrow/25.0.0`), the fake activation was
  sourced via the runtime-resolved `INTERPLAB_VENV_DIR`, the repo `cd`
  succeeded, and the stubbed `python` received exactly
  `scripts/certify.py --config configs/certify/hm03l7yz.yaml`.
- Cleanup left no temp files; no tracked-file change, no new Slurm logs, and
  zero queued certify jobs. The 70b7ed8 shell-boundary fix is verified
  end-to-end.

Acceptance consequence: **R5-C2 accepted. R5-X2 certification may resume — but
see the environment blocker below.**

## 2026-07-30 — R5-X2 resumption blocker: production GPU venv missing

Classification: **Blocked at environment — missing CUDA venv (rebuilding)**

- With the launcher fixed, the wrapped payload sources
  `${INTERPLAB_VENV_DIR:-$HOME/interplab-venv}`, but `~/interplab-venv` **does
  not exist** on Tamia. INTERPLAB_VENV_DIR is unset in env and dotfiles.
- Two venvs exist, neither usable for GPU certification:
  `~/qwen-sae-interp/.venv` (Python 3.12, `uv`) has interplab but a **CPU**
  torch (`2.13.0+cpu`, `cuda=None`); `~/sae-interp` (Python 3.11.5 cvmfs) has
  torch but **no interplab** (superseded project venv).
- `setup_env.sh` documents that the uv/pyproject torch is the CPU build and
  that GPU jobs need the CUDA wheel from the Alliance wheelhouse. The
  wheelhouse serves it: `torch-2.13.0+computecanada-cp311`. Offline rebuild
  inputs (`slurm/requirements.cluster.txt`, `scripts/certify.py`) are present;
  HOME has ~19 GB free.
- Resolution: rebuild the canonical GPU venv at `~/interplab-venv` via
  `bash slurm/setup_env.sh` (offline, idempotent), then resubmit R5-X2 through
  the validated launcher.

WP2 consequence: **R5-X2 pending GPU venv rebuild, then certification
submission.**

## 2026-07-30 — R5-X2 environment diagnosis correction

Classification: **Blocked — architectural ambiguity plus environment
limitation**

- R5-C2 and R5-V1 remain Accepted; the launcher is not the blocker.
- The canonical `~/interplab-venv` is absent. The attempted replacement is
  incomplete and no scheduler job is queued.
- The earlier instruction in this log to run `slurm/setup_env.sh` unchanged
  is superseded by this finding: `slurm/requirements.cluster.txt` is stale.
  It pins SAE Lens 3.23.0, Transformers 4.44.0, and TransformerLens 2.15.4,
  while `pyproject.toml` / `uv.lock` resolve 6.44.2, 5.12.1, and 3.2.1.
- The Alliance wheelhouse cannot supply multiple packages in the current
  lock, so the ED-1 `--no-index` flow cannot currently reconstruct the
  sanctioned dependency truth.
- The user confirms the intended versions are 6.44.2 / 5.12.1 / 3.2.1.
  Four existing A5 manifests nevertheless record measured training-time
  TransformerLens 3.4.0; `hm03l7yz` records null. Those immutable provenance
  facts are not revised by recollection.
- No A6, A10, report, registry artifact, or scientific parameter changed.

WP2 consequence: **pending R6-A004 Architect ruling, then a bounded
environment-build work item; no GPU resubmission yet.**

## 2026-07-30 — ED-36 local repository portion Engineer report

Classification: **Implementation complete — independent verification
required**

- ED-36 closes A-004 and selects a retained, hash-verified external offline
  bundle with production TransformerLens 3.2.1 plus a separate exact 3.2.1 /
  3.4.0 real-Qwen equivalence gate.
- The Engineer's local candidate adds the direct dependency, regenerated
  lock and hash-bearing torch-excluded export, acquisition/install manifest
  schemas and validation, offline setup flow, and cert-lane A10 input refs.
- Reported full suite: 649 passed, 3 deselected. Reported `uv lock --check`,
  `bash -n slurm/setup_env.sh`, and `git diff --check`: passed.
- No bundle, cluster venv, equivalence report, scheduler job, A6, A10, or
  registry artifact was produced.
- No stable commit was made. External construction against this candidate is
  not authorized because ED-36 requires committed source identity.
- Independent review must challenge pre-venv bootstrap assumptions,
  caller-directory behavior, dirty-worktree revision claims, manifest
  closure/path attacks, installed extras, and cert-lane invalid-config /
  environment-failure lifecycle interactions.

WP2 consequence: **R6-V1 is required before stabilization or any external
bundle construction. R5-X2 remains blocked.**

## 2026-07-30 — R6-V1-ED36-LOCAL-VERIFICATION

Classification: **Needs correction**

- Dependency truth passed. The export contains 114 hash-bearing non-torch
  requirements, reproduced byte-for-byte at 184,572 bytes and SHA-256
  `9da00e038f1a6daba4fac4ba7b3a845787349180e339c0d5ca1a79223a678314`.
- Bootstrap failed outside the repository (`interplab` unavailable) and from
  the repository under minimal Python (`jsonschema` unavailable). The later
  `virtualenv` executable is also neither acquired nor validated.
- The real export cannot be preflighted because `platform_machine` is an
  unsupported marker variable.
- Normalized duplicate runtime entries, unexpected tooling, a
  directory-junction escape, semantically inconsistent derived-wheel
  provenance, arbitrary builder identity, and an unapproved build input were
  accepted.
- An unapproved installed distribution was accepted.
- A working tree with 71 dirty entries produced clean-looking HEAD
  `70b7ed8a7c264fd96a7149241a8995e125a3af2a`; source bytes were not
  represented.
- Under cluster detection with missing manifest variables, readable-invalid
  certify config raised before validation and wrote no A10. Arbitrary
  existing files could stand in for the two manifests, and R5-X2 could omit
  its equivalence report.
- Schema discovery and structural strictness passed; A10 v1 is unchanged.
- Focused ED-36: 15 passed. Cert/config/schema/import matrix: 129 passed.
  Full suite: 649 passed, 3 deselected. Lock, Bash syntax, and diff checks
  passed. Exact CI Ruff failed with seven findings.
- No probe artifact, dependency, registry evidence, cluster state, or Tamia
  state was modified.

WP2 consequence: **R6-C1 repairs the validator foundation first. Cert-lane
lifecycle correction and independent re-verification remain required;
R5-X2 stays blocked.**

## 2026-07-30 — R6-C1-ED36-BUNDLE-VALIDATOR Engineer report

Classification: **Engineer complete — combined independent re-verification
pending**

- Dependency truth and frozen export are unchanged: 6.44.2 / 5.12.1 /
  3.2.1; 114 hash-bearing non-torch requirements; SHA-256
  `9da00e038f1a6daba4fac4ba7b3a845787349180e339c0d5ca1a79223a678314`.
- The bootstrap is now stdlib-only and directly invoked by file path, so it
  does not require installed interplab or jsonschema before venv creation.
- Virtualenv identity is checked before mutation. Real-export marker support
  includes `platform_machine` and is tested against `packaging`.
- Normalized duplicates, unapproved tooling/runtime/installed entries,
  traversal/reparse escapes, inconsistent derived-wheel metadata/provenance,
  version mismatches, and dirty source revision now fail closed.
- Engineer evidence: 25 focused tests, 52 cert-lane tests, full suite
  659 passed / 3 deselected; lock, exact CI Ruff, Bash syntax, and diff checks
  passed.
- No production bundle, Tamia environment, registry artifact, or scheduler
  job was created.
- Live junction behavior and Tamia virtualenv identity remain external
  evidence, appropriately unclaimed.

WP2 consequence: **validator correction is ready to combine with R6-C2;
independent re-verification follows both. R5-X2 remains blocked.**

## 2026-07-30 — R6-C2-ED36-CERT-LANE-LIFECYCLE Engineer report

Classification: **Engineer complete — combined independent re-verification
pending**

- Cert-lane environment collection now occurs after readable config
  validation.
- Readable-invalid config under missing cluster evidence is reported as exit
  3 with exactly one failed A10 and no heavy/domain work.
- Valid-config evidence failures are pre-finalized as one failed exit-4 A10.
- Acquisition/install files are now type- and semantics-validated, linked by
  acquisition/source hashes, and checked against current repository truth.
- R5-X2 now requires a content-valid equivalence report tied to the
  `hm03l7yz` checkpoint, configured complete token stream, versions 3.2.1 and
  3.4.0, L28 hook, exact equality checks, and passed SAE forward sanity.
- Engineer evidence: 48 focused tests; full suite 676 passed, 3 deselected;
  lock, exact CI Ruff, and diff checks passed.
- No real bundle, cluster environment, equivalence output, registry
  production artifact, or scheduler job was created.

WP2 consequence: **R6-V2 must accept the combined C1+C2 candidate before a
stable commit or external bundle construction. R5-X2 remains blocked.**

## 2026-07-30 — R6-V2-ED36-COMBINED-REVERIFICATION

Classification: **Needs correction**

- Export reproduced byte-for-byte: 184,572 bytes, 114 hash-bearing non-torch
  requirements, SHA-256
  `9da00e038f1a6daba4fac4ba7b3a845787349180e339c0d5ca1a79223a678314`.
  All five real markers matched Packaging.
- Minimal outside-repo bootstrap and the pre-mutation failure matrix passed.
- An arbitrary `python.exe` spoofing the expected version passed as
  virtualenv; identity is not bound to an approved artifact.
- Runtime `setuptools==83.0.0` plus tooling `setuptools==80.0` was admitted,
  creating an installation-order conflict.
- Empty `LOADEDMODULES` was recorded as fabricated `arrow` and
  `python/3.11`.
- C2 admitted hostile target ABI, schema-extra/missing fields, incomplete
  torch/module facts, fabricated revision, and hostile derived-wheel
  builder/source/command semantics when manifests were mutually relinked.
- All 24 four-job lifecycle cases passed with correct exit 3/4, one A10, and
  no other artifacts.
- Standard equivalence mutations failed correctly, but a modified config
  using the same checkpoint and a matching report passed, allowing the
  authoritative stream/slice/bands to be redefined.
- Focused ED-36: 37 passed. Lifecycle/schema/preservation: 171 passed. Full:
  676 passed, 3 deselected. Lock, exact CI Ruff, Bash syntax, and diff checks
  passed.
- No probe artifacts or repository/external state mutations were retained.

WP2 consequence: **R6-C3 must close the semantic gaps before another combined
verification. R5-X2 remains blocked.**

## 2026-07-30 — R6-C3-ED36-SEMANTIC-CLOSURE Engineer report

Classification: **Engineer complete — final independent re-verification
required**

- Virtualenv creation now executes a retained manifest artifact only after
  its hash and metadata validate.
- Conflicting runtime/tooling overlap fails; identical overlap is filtered
  from the later runtime plan.
- Installed-manifest module provenance comes only from measured
  `LOADEDMODULES`; missing provenance fails.
- Build and admission validators now claim full schema/semantic parity,
  current-target comparison, derived-wheel replay, exact installed closure,
  and exact clean-HEAD revision.
- R5-X2 is anchored to `configs/certify/hm03l7yz.yaml`, SHA-256
  `6dfb9e35d5f179177f8f584b050f0e480fa30bbb3753c29ca7954d6b96c9f326`,
  frozen semantics, and a matching report `config_hash`.
- Direct spoof/hash/overlap/module/revision/config-field probes passed.
  Export count/hash, lock, exact CI Ruff, and diff checks passed.
- Focused/full pytest and Bash syntax were not measured because of sandbox
  temp ACL and MSYS startup failures.
- No production or external state changed.

WP2 consequence: **R6-V3 must independently verify the combined candidate;
R5-X2 remains blocked.**

## 2026-07-30 — R6-V3-ED36-FINAL-LOCAL-REVERIFICATION

Classification: **Needs correction**

- Export/version/hash/marker invariants and isolated bootstrap passed.
- A wheel with internal `evil==9.9` metadata executed as approved
  virtualenv; a spoof interpreter creating an arbitrary directory passed the
  postcondition; creator failure left a partial target.
- Admission accepted non-wheel creator bytes and empty torch CUDA identity.
- Truthful versioned modules `python/3.11.5:arrow/25.0.0` were rejected by
  literal matching.
- Manual install validation accepted an empty installer version rejected by
  the committed schema.
- Runtime/tooling overlap and authoritative R5-X2 config/report mutation
  matrices passed.
- Missing equivalence under an isolated scratch `repo_root` crashed while
  constructing A10 because the authoritative config was not relative to that
  root.
- Ordinary four-job lifecycle matrix passed 24/24.
- Focused ED-36: 32 passed, 6 failed. Lifecycle/schema/import: 133 passed,
  1 failed. Full: 670 passed, 7 failed, 3 deselected. Lock, exact CI Ruff,
  Bash syntax, and diff checks passed.
- No probe artifacts or state mutations were retained.

WP2 consequence: **R6-C4 is required before another final local
re-verification; R5-X2 remains blocked.**

## 2026-07-31 — R6-C4 Engineer report and hidden-consequence review

Classification: **Engineer complete with one production-shape correction
required**

- Creator wheel metadata, functional-vEnv postconditions, transactional
  rollback, admission replay, versioned modules, manual/schema parity, and
  canonical config-ref fallback were implemented and directly probed.
- Missing equivalence now reports exit 4 with one failed A10 at
  `local:configs/certify/hm03l7yz.yaml` and no outputs.
- Lock, exact CI Ruff, and diff checks passed. Full pytest and Bash syntax
  remained environment-blocked by Windows ACL/MSYS failures.
- Hidden review found `_expected_cuda_identity()` accepts only `+cuNNN`,
  while the approved Tamia wheel is `2.13.0+computecanada` and the measured
  runtime CUDA identity is 13.2. The `+cu121` fixture is not production-shaped.
- Three ACL-poisoned scratch directories remain from abandoned local staging
  probes; they are environment debris, not product evidence.

WP2 consequence: **R6-C5 must correct Alliance CUDA identity before final
local re-verification. R5-X2 remains blocked.**

## 2026-07-31 — R6-C5-ED36-ALLIANCE-CUDA-IDENTITY Engineer report

Classification: **Engineer complete — final independent verification
required**

- CUDA identity is no longer inferred from `+cuNNN`.
- Production-shaped fixtures now use approved torch
  `2.13.0+computecanada` and measured CUDA 13.2 while preserving locked
  public version 2.13.0.
- Install manifests record live `torch.version.cuda` and availability;
  cert-lane admission compares exact acquisition version, installed
  distribution version, and live torch/CUDA facts.
- Empty/mismatched CUDA, false availability, CPU runtime, wrong local/public
  version, and manifest/acquisition version mismatches were directly rejected.
- Focused tests: 25 passed, then 5 passed, then export test passed. Lock,
  exact CI Ruff, and diff checks passed.
- Full pytest and Bash syntax remained environment-blocked by the Engineer's
  host ACL/MSYS failures. No external or production state changed.

WP2 consequence: **R6-V4 must accept the full C1–C5 candidate before a
stabilization commit or external bundle construction. R5-X2 remains blocked.**

## 2026-07-31 — R6-V4-ED36-FINAL-ACCEPTANCE

Classification: **Needs correction**

- Export/version/hash/marker and isolated bootstrap invariants passed.
- Creator TOCTOU reproduced: validated hash `c95d0018…c38fb`; path replaced
  before execution by bytes hashing `6096be3a…e9fec`; substituted code created
  a functional venv; success still reported the approved hash.
- Unauthorized torch `2.13.0+cu121`, CUDA 13.2, arbitrary hash, and no
  artifact file passed when acquisition/install/live evidence agreed. The
  validator anchors only public 2.13.0 and does not replay the retained torch
  file at admission.
- Ordinary rollback/sentinel/module/overlap/CUDA/schema and R5 gates passed.
  Lifecycle matrix passed 24/24; R5 config mutations 10/10 and report
  mutations 13/13 were rejected; valid fixture passed.
- Focused boundary: 25 passed. Preservation: 134 passed. Focused ED-36:
  54 passed, 7 failed. Full: 693 passed, 7 failed, 3 deselected. The seven
  failures abort at missing creator fixture before their intended assertions.
- Lock, exact CI Ruff, Bash syntax, diff checks, A10 v1, and interfaces passed.

WP2 consequence: **R6-C6 must close both root-of-trust defects and restore
green regressions before another acceptance audit. R5-X2 remains blocked.**

## 2026-07-31 — A-003 project-management path consolidation

Classification: **Researcher decision implemented / verified**

- Canonical path: `project_management/`.
- Tracking policy: intentionally local-only and ignored; it must not be
  pushed.
- The stale `project-management/` directory is absent.
- All six unique inherited files are present under the canonical directory:
  `DECISION_INDEX.md`, `RESEARCHER_QUEUE.md`, and the four persistent-role
  `SESSION_BOOTSTRAPS` files.
- Current ledger/plan/state/log files remain the newer campaign versions.
- `.gitignore` contains `project_management/`; Git reports the directory as
  ignored and tracks no management files.
- Scientific report/result tracking was not decided and remains A-005.

Campaign consequence: **A-003 is closed. This governance decision does not
change the active R6-C6 implementation route.**

## 2026-07-31 — R7-C1 parallel launcher propagation authorized

Classification: **Implementation defect; isolated parallel lane**

- `launch_characterize.sh`, `launch_steer.sh`, and `launch_validate.sh` retain
  both measured certify defects: single-H100 requests rejected by Tamia and
  module/source payloads passed directly to `/bin/sh` through `--wrap`.
- `launch_train.sh` already requests `h100:4` but retains the wrap defect.
- Train `mem=100G` is explicitly unchanged; it is outside the immediate
  experiment path and lacks a calibration decision.
- Source-of-truth base is commit `70b7ed8`, where the certify fixes are
  present. Work must use an isolated branch/worktree and must not merge into
  main before R6 stabilization.
- The active tree's separate accepted steer prose correction remains outside
  the parallel branch's scope.

Campaign consequence: **R7-C1 may proceed concurrently without changing the
R6-C6 critical path.**

## 2026-07-31 — R7-C1 isolated launcher propagation accepted

Classification: **Accepted in isolation; integration deferred**

- Engineer commit: `b7aad6a2e25a45c5b4fab48951b5bfd92a47ae53` on local
  branch `r7-launcher-propagation`, worktree
  `D:\qwen-sae-interp-r7-launchers`, based on `70b7ed8`.
- Independent repository inspection confirmed exactly four changed files:
  `launch_characterize.sh`, `launch_steer.sh`, `launch_validate.sh`, and
  `launch_train.sh`.
- All four apply the explicit `bash -lc` wrapper. Characterize, steer, and
  validate use `h100:4`/`mem=0`; train retains `h100:4`/`mem=100G`.
- Engineer evidence: Bash syntax 4/4; non-submitting scheduler capture 4/4;
  wrapper decode equal to each original `REMOTE_CMD`; remote venv fallback
  remained unexpanded; preserved scheduler arguments and resource counts all
  passed; `git diff --check` passed.
- No push, merge, live scheduler submission, registry write, scientific
  output, or active-main mutation occurred.

Campaign consequence: **R7-C1 implementation is accepted on its isolated
branch. It must remain parked until R6 stabilization, then be integrated while
preserving the accepted R2 steer-header prose and rechecked in the combined
tree. R6-C6 remains the only active implementation route.**

## 2026-07-31 — R6-C6 Engineer report received

Classification: **Engineer complete; independent verification required**

- Candidate scope: `interplab/core/environment_bundle.py`,
  `tests/job_test_helpers.py`, and `tests/test_environment_bundle.py` within
  the cumulative uncommitted R6 candidate.
- Claimed creator correction: validated bytes are copied to an execution
  snapshot, verified at the child boundary, executed from that snapshot, and
  reported by the executed-byte hash.
- Claimed torch correction: build and cert admission require the retained
  exact `torch==2.13.0+computecanada` Alliance artifact and replay filename,
  size, hash, METADATA, origin, live version, CUDA 13.2, and availability.
- Direct negative-case probes report original-path replacement blocked and
  seven torch mutations rejected. `py_compile`, exact CI Ruff, lock, and diff checks
  passed.
- Focused/full pytest and Bash syntax remain unverified because the Engineer
  host denied temporary-directory enumeration and lacked a working Bash.
- `results/_test_scratch/r6_c6_probes/summary.json` was reported as generated
  evidence but is not acceptance evidence without independent replay.
- Orchestrator inspection found a residual TOCTOU candidate: the child hashes
  the snapshot at `environment_bundle.py:1358`, then imports by reopening the
  same path through `sys.path`/`runpy` at lines 1362–1364. The Engineer probe
  replaced only the original source path, so it does not close this later
  boundary.

Campaign consequence: **R6-C6 is not yet accepted. R6-V5 must independently
verify the immutable execution boundary, retained torch replay, repaired
fixtures, and combined C1–C6 regressions before stabilization or production.**

## 2026-07-31 — R6-V5 audit authorization clarified

Classification: **Verification routing clarification; no contract change**

- The prior verification request was stopped by automated safeguards because
  its wording resembled exploit development.
- R6-V5 is explicitly authorized only as a deterministic, repository-local
  software-correctness audit.
- Its blocking regression may coordinate two local subprocesses and alter only
  a disposable execution snapshot created inside the repository test temporary
  directory between verification and execution.
- It may not access networks, credentials, clusters, external systems, or
  unrelated paths; all temporary fixtures must be removed afterward.
- The invariant is unchanged: approved reported bytes must equal executed
  bytes, every post-verification change must abort execution, and replacement
  module content must never execute.

Campaign consequence: **Route the clarified R6-V5 request back to the
Persistent Interlab Verification Auditor.**

## 2026-07-31 — Persistent Lab Assistant role and prior experiment packet reconciled

Classification: **Workflow governance + Researcher decision gap**

- Added `Persistent Interlab Lab Assistant` as the TamIA execution and
  evidence-acquisition role. Scientific choices remain with the Researcher;
  implementation, architecture, and independent acceptance remain with the
  Engineer, Architect, and Auditor respectively.
- Added a durable Lab Assistant bootstrap with exact preflight, evidence-label,
  failure-stop, provenance, and report requirements.
- Reclassified cluster-dependent queue items into separate Researcher decision,
  Lab Assistant execution, and Auditor acceptance stages.
- Repository inspection confirms the prior T1.2 packet exists at
  `docs/ablation_9056_spec.md`, `configs/characterize/rwu04lpb.yaml`, and
  `configs/steer/ablation_9056.yaml`.
- The packet is draft preparation, not an approved protocol: final paired
  prompts, sampling, positions, characterize `n_docs`, judge mode, and
  quantitative acceptance criteria remain Researcher-owned.
- Both steer lineage hashes are zero placeholders. The local A7, A8, and A9
  registry directories contain only `.gitkeep`, so no production prerequisites
  are present.
- Existing T1.1 multilingual result files and implementation-log claims were
  found. Their scientific sufficiency and any additional cluster-provenance
  requirement remain Q-012 rather than an implicit rerun authorization.
- R7 launcher propagation is accepted only on its parked branch and is not yet
  integrated. R6-V5 remains the active acceptance gate.

Campaign consequence: **Do not route T1.2 execution to the Lab Assistant yet.
Obtain Researcher approval of Q-011, then wait for R6 stabilization, R7
integration, A7/A8 production, and a complete cluster preflight packet.**

## 2026-07-31 — R6-V5 split after Auditor safeguard stop

Classification: **Verification gap + test-contract ambiguity**

- The Auditor environment continued to reject a request that required it to
  design and run a synchronized execution-snapshot boundary procedure.
- `R6-V5A-ED36-REMAINDER-ACCEPTANCE` now excludes all new boundary-test design
  or modification. It covers implementation inspection, every already-existing
  ED-36/preservation test, torch admission, lifecycle, schema, dependency,
  lint, lock, and regression evidence.
- V5A may run a named pre-existing exact-byte regression unchanged if one
  already exists. Otherwise it must record that boundary as `UNVERIFIED` and
  must not infer overall R6 acceptance.
- A separate chain is established:
  `R6-A006-EXACT-BYTE-EXECUTION-TEST-CONTRACT` (Architect) →
  `R6-C7-EXACT-BYTE-EXECUTION-REGRESSION` (Engineer) →
  `R6-V5B-EXACT-BYTE-EXECUTION-VERIFICATION` (Auditor).
- V5B will receive only the committed named test and run it unchanged.

Campaign consequence: **Proceed with V5A now. Overall R6 remains open until
both the audited remainder and the separately committed exact-byte regression
are independently accepted.**

## 2026-07-31 — T1.2 Researcher review and Lab Assistant revision report reconciled

Classification: **Needs correction — scientific protocol and dependency chain**

- Researcher approved H1/H2, paired prompts, `positions: all`, sampling
  hyperparameters, matched-frequency control, and `n_docs: 20000`, conditional
  on multi-seed, judging, statistical, and rerun revisions.
- Lab Assistant created seed-specific steer configs for 0, 42, and 123 and
  removed the ambiguous single-seed file. Orchestrator validation measured:
  four configs schema-valid; seed configs normalize byte-semantically equal
  after seed/output fields; each has 10 prompts and 10 controls; output paths
  are distinct; the old single config is absent.
- The correction that judging is a separate `steer` A9 → `judge` A9′ path is
  repository-accurate. `judge: stub` in characterize is unrelated feature
  autointerpretation. Stage 2 remains blocked by ED-19 and a new approval cycle.
- Blocking dependency defect: the packet says characterize emits A7 and A8.
  Repository contracts show characterize emits only A7; validate emits A8 and
  requires an A7 hash, census A3 hash, concept ID/content, feature index, and
  specificity-judge settings. No `cheese` ConceptBattery, matching census
  evidence, or validate config currently exists.
- Statistical closure remains incomplete: paired prompts conflict with the
  Mann–Whitney alternative; non-significance does not establish
  “indistinguishable”; judge-repeat aggregation, paired effect-size definition,
  equivalence margin, multi-seed gate/multiplicity interpretation, and allowed
  A9 quality review are unspecified.
- Canonical SS9 exposes `bootstrap_ci`, `effect_size`, `seed_variance`, and
  `bh_fdr`; it does not implement the proposed t-test, Wilcoxon, or
  Mann–Whitney path. Keeping those tests would create a separate implementation
  dependency; aligning the protocol to existing grouped-bootstrap primitives
  avoids one.
- The Lab Assistant chose seed set 0/42/123 from alternatives suggested by the
  Researcher and mechanically edited repository files. Those changes are
  proposals pending explicit ratification; the role may not make further
  scientific or repository changes without a bounded authorization.
- The report was local preparation, not TamIA evidence, and did not use the
  required Lab Assistant execution-report format or evidence labels. No job was
  submitted and no production artifact was produced.

Campaign consequence: **Do not execute T1.2. Route Q-011 back to the Researcher
for the compact remaining decisions, then assign mechanical packet changes to
an authorized implementation role.**

## 2026-08-01 — T1.2 authoritative decisions received; four clarifications remain

Classification: **Researcher ruling with execution-material inconsistencies**

- Settled: seeds 0/42/123; seed-0 structural smoke gate; native SS9 grouped
  bootstrap, pooled Cohen's d, relative-reduction alternative, seed variance;
  ±0.5 baseline-control equivalence; corrected A2/A3/A7→A8 dependency chain;
  structural/blinded A9 QC; Stage-1 preparation-only and Stage-2 ED-19 gate.
- Scheduling conflict: the ruling orders seeds 42/123 immediately after seed-0
  structural success and also says their two H100 allocations wait until ED-19
  opens. This cannot be inferred because it changes expensive execution.
- A2 contract conflict: `concept_battery/v1` contains semantic concepts,
  per-language probes/controls/census terms, and concept-ID matched controls.
  It has no feature-index entries. Feature 9056 belongs in validate; the
  matched-frequency feature is resolved and recorded by steer, so 90537 cannot
  be inserted into A2 as a control entry.
- Endpoint omission: baseline-vs-random equivalence is fixed, but the original
  H2 direct `random_feature − steered` positive-difference CI is not explicitly
  retained.
- Aggregation omission: three Lodestar repeats per generation have no fixed
  reduction rule before prompt-level SS9 analysis.
- Stale prose remains mechanical: current gates are R6-V5A plus
  A-006→C7→V5B, and R7 is an accepted parked launcher branch awaiting
  integration—not an unimplemented launcher work order.

Campaign consequence: **Do not route implementation or execution. Obtain the
four-line Q-011-C2 clarification, then issue one bounded Engineer packet-update
work item.**

## 2026-08-01 — Q-011-C2 received; exact scientific strings still absent

Classification: **Researcher content gap; implementation otherwise authorized**

- Resolved: Option B—seed 0 smoke now, seeds 42/123 held until ED-19; before
  later submission, bundle/install-manifest and Interlab revision must match
  seed 0 or seed 0 is rerun with them.
- Resolved: A2 is semantic-only. Feature 9056 belongs in validate; 90537 is
  absent from A2 and the matched-frequency control remains steer-resolved.
- Resolved: H2 requires both a positive `random_feature − steered` bootstrap CI
  and baseline-control equivalence within ±0.5; a centered but wider interval
  is `INCONCLUSIVE`, never pass/refutation or a reason to widen the margin.
- Resolved: three Lodestar repeats are averaged to one prompt-level score;
  fewer than two surviving repeats excludes and flags that generation, with no
  imputation.
- Resolved: English A2 is `probes_only`, `word_absent: []`, GENERAL_TEXT
  `concept_absent` copied from `couscous.yaml`, canonical `cheese` census term,
  and empty matched controls. Stage-1 A8 is explicitly DRAFT/stub-only.
- Remaining blocker: the ruling instructs creation of ten new declarative
  cheese probes but does not provide their exact text. It also requires
  explicit `stub_judge_marker_words` without naming them. Both are scientific
  content/instrument choices and cannot be invented by the Engineer.

Campaign consequence: **Request only those two exact lists from the Researcher.
After receipt, route T1.2-C1 to Engineer; do not send the packet back to the Lab
Assistant for editing or execution.**

## 2026-08-01 — Q-011-C3 scientific lists received; ED-8 derivative gate found

Classification: **Researcher content complete; versioned-golden authorization pending**

- Received twelve exact English declarative cheese-present probes and thirty-nine
  exact lower-case stub marker tokens, including accented/unaccented Comté and
  Gruyère forms. Stored verbatim in the durable T1.2 authority packet.
- Probe wording is intentionally disjoint from the intervention prompt wording,
  preventing certificate/intervention prompt reuse.
- Hidden consequence: `data/concepts/cheese.yaml` changes A2's content-addressed,
  versioned file set. Blueprint ED-8 requires every content change to bump
  `battery_version` and name the author in provenance.
- `tests/test_battery_snapshot.py` hard-requires the pinned tokenization golden
  to cover every concept and language. Adding cheese without regenerating
  `tests/golden/battery_snapshot.json` would knowingly break the hard suite.
- The prior “only these files” authorization did not name `battery.yaml` or the
  golden. The Orchestrator will not infer an author identity, semver, or golden
  rewrite authorization.

Campaign consequence: **Obtain the three-value Q-011-C4 ED-8 ruling, then route
the complete isolated packet to Engineer.**

## 2026-08-01 — Q-011-C4 closes T1.2 scientific authority

Classification: **Researcher decision complete; isolated implementation ready**

- Battery version: `1.1.0`.
- Named author: `Mohamed El Yazid — IID` (IID explicitly governs; not Mila).
- Exact v1.1.0 change record is stored in the T1.2 authority packet.
- Golden update is authorized with four hard-site consequences: generator reads
  `battery_version()` instead of a constant; real snapshot assertion and real
  battery assertion become 1.1.0; synthetic tmp fixtures remain 1.0.0; the
  historical extraction script retains executable v1 behavior and receives
  only a one-shot/historical header comment.
- `battery.yaml` keeps original flat extraction provenance and gains a sibling
  changelog with v1.0.0 plus the authoritative v1.1.0 record.
- Expected golden diff is exactly one version change plus new
  `concepts.cheese.en` containing 12 probes, empty word-absent, copied English
  GENERAL_TEXT concept-absent, and the canonical cheese census term. Any
  existing-concept tokenization change is a stop condition.
- T1.2-C1 is sequenced into an isolated branch/worktree from `70b7ed8`; active
  R6 and parked R7 remain untouched. No merge/push/execution is authorized.

Campaign consequence: **Q-011 is closed. Route T1.2-C1 to the Persistent
Engineer for mechanical repository preparation only.**

## 2026-08-01 — R6-V5A ED-36 remainder acceptance

Verdict: **Needs correction**  
Exact-byte execution: **UNVERIFIED pending R6-A006 → R6-C7 → R6-V5B**

- Focused ED-36: 61 passed, 7 failed; full suite: 702 passed, 7 failed,
  3 deselected.
- Exact Alliance torch group: 20 passed; creator group: 10 passed, 1 failed;
  lifecycle/preservation/schema/import/bootstrap: 93 passed; four-job lifecycle
  matrix: 24 passed.
- Ruff, `uv lock --check` (196 packages), Git Bash syntax, and
  `git diff --check` passed. Frozen export remained 184,572 bytes with SHA-256
  `9da00e038f1a6daba4fac4ba7b3a845787349180e339c0d5ca1a79223a678314`.
- Two failing tests assert a later error boundary although the validator already
  fails closed on size or normalization. Five install-record fixtures omit the
  now-required approved virtualenv wheel and never reach their intended
  success/CUDA/extra/version/dirty-source assertions.
- Explicit torch regressions for wrong filename, wrong recorded size, and an
  out-of-bundle torch path are absent, although generic related checks exist.
- No interface, A10-v1, registry, config, dependency, or production-artifact
  drift was found. Audit temporary directories were removed; repository status
  matched its pre-audit state.

Classification: **test/fixture verification defects plus one still-open
implementation/test-contract boundary**. Route A-006 to Architect, then repair
the bounded fixtures/coverage and implement the approved named boundary test
before combined re-verification.

## 2026-08-01 — R6-A006 exact-byte execution contract

Decision: **Accepted; production correction and deterministic regression
required; no ED amendment.**

- Source inspection found a genuine two-read gap: the child hashes snapshot
  bytes, then zipimport reads the same mutable path again for execution.
- The correction must read once and derive verification plus execution from the
  same in-memory bytes (or a child-private extraction of them), never rereading
  the parent-visible snapshot for import.
- The parent must re-hash the snapshot after child return but before created-venv
  validation. A mismatch must report expected/actual hashes and roll back.
- No environment-variable, argv, sleep, thread-race, permission, or production
  synchronization hook is authorized.
- Required committed test:
  `test_create_virtualenv_executes_only_verified_creator_bytes_and_aborts_on_post_verification_replacement`.
  It runs the real child subprocess on disposable `tmp_path` data: approved
  token A executes, substitute token B does not, mismatch aborts, target/staging/
  snapshot are removed, and an unrelated sentinel is preserved.
- Allowed files: `interplab/core/environment_bundle.py` and
  `tests/test_environment_bundle.py`. Return keys, schemas, manifests,
  dependencies, lock, blueprint, and registry are unchanged.

R6-C6A is absorbed into R6-C7 because its seven fixture repairs and three torch
coverage additions share the same authorized test file and are necessary for
the Architect's full-suite-green acceptance criterion.

## 2026-08-01 — R6-C7 Engineer report and Orchestrator consequence review

Verdict: **Needs correction before V5B.**

- Engineer reported the named regression passing after the fix, focused ED-36
  53 passed, creator 12 passed, torch 20 passed, full environment bundle 73
  passed, and full suite 714 passed/3 deselected. Ruff, lock, Git Bash syntax,
  and scoped diff checks passed.
- The production child uses a verified byte buffer to create a child-private
  wheel and the parent re-hashes the visible snapshot before created-venv
  validation. Reported A/B, expected/actual hash, rollback, and sentinel
  behavior passed.
- Hidden contract violation: production code sets
  `INTERPLAB_CREATOR_SNAPSHOT_PATH` solely so the test creator can locate and
  replace the visible snapshot. A-006 explicitly rejected environment/test
  coordination hooks and required the fake creator to reconstruct the path
  from its staging target plus known filename.
- The named test replaces `bundle.subprocess.run` with a wrapper, although it
  delegates the child call to the real subprocess. A-006 requires the named
  boundary test not to replace that production subprocess function. Because
  mismatch is checked before venv validation, no later subprocess needs to be
  simulated.
- Pre-fix evidence failed via child `SyntaxError`, not the intended observable
  substitution behavior. This is noted as weak before-state evidence, not a
  reason to discard the source-proven two-read defect or the post-fix behavior.

Classification: **implementation/test-contract defect**. Route bounded C8 to
remove the environment seam and subprocess wrapper, then route the unchanged
named test and combined suite to V5B.

## 2026-08-01 — R6-C8 Engineer report

Status: **Engineer complete; independent V5B required.**

- `INTERPLAB_CREATOR_SNAPSHOT_PATH` is absent from code/test trees. The child
  retains verified-buffer → private-wheel execution and the parent retains its
  post-child hash check before created-venv validation.
- The fake creator reconstructs the visible snapshot from the staging target
  and known wheel filename. The named test no longer replaces
  `bundle.subprocess.run` or captures its arguments.
- Named regression passed unchanged after correction; A markers were present,
  B markers absent, exact mismatch hashes reported, target/staging/private paths
  removed, and unrelated sentinel preserved.
- Creator: 12 passed; torch: 20; lifecycle/preservation: 15; full environment
  bundle: 73; full suite: 714 passed/3 deselected. Ruff, lock, Git Bash syntax,
  and diff checks passed.
- Only `interplab/core/environment_bundle.py` and
  `tests/test_environment_bundle.py` changed during C8. Both remain untracked as
  part of the cumulative dirty R6 candidate; no commit or external action was
  performed.

Classification: **verification gap plus later stabilization gap**. Route V5B
to the Auditor now; even an accepted candidate requires a bounded commit and
commit-identity verification before global R6 acceptance.

## 2026-08-01 — R6-V5B conflicting audits reconciled

Applicable verdict: **Accepted for exact local candidate.**

- Accepted audit bound start/end identity to:
  `environment_bundle.py` 93,984 bytes,
  `740dd61164d63e202ffce426d80941a77ae56ab8dbaebeb53588e86211201f7a`;
  `test_environment_bundle.py` 61,153 bytes,
  `7bbc115271d11343bf821b2bd1435637a1a390e9400aedb9ea278eb1ef7bd21b`.
- Named exact-byte test: 1 passed; environment bundle: 73; creator: 12;
  torch: 23; seven V5A repairs: 7; lifecycle matrix: 24; schema/import/bootstrap:
  36; full suite: 714 passed/3 deselected. Ruff, lock, Bash, export, and diff
  checks passed. Start/end status was identical at 34 modified/16 untracked.
- Orchestrator independently re-hashed the current files and obtained the exact
  accepted values and sizes with the same 50-entry status.
- The competing Auditor report is stale/inapplicable: it repeats the pre-C7
  seven-failure fixture pattern and obsolete A006→C7 routing, supplies no file
  hashes, and did not reach the corrected current test population. It is retained
  as historical evidence, not a final-candidate rejection.
- No audit mutation or retained audit state applies to the accepted result.

Classification: **candidate accepted; revision stabilization required**. Route
R6-S1 selective commit, then R6-V5C commit-identity verification. Do not start
external environment construction, R7 integration, or production work yet.

## 2026-08-01 — R6-S1 stabilization report

Status: **Engineer complete; V5C active.**

- Local commit `c6ef2df5bb38791a26e4e9490243f327dc6aeb85`, parent
  `70b7ed8a7c264fd96a7149241a8995e125a3af2a`, message
  `Stabilize Interlab repairs through ED-36`.
- Commit contains exactly the 46 paths in `R6_STABILIZATION_MANIFEST.md`; no
  management, T1.2 isolated, R7, probe, or SSH-named path is included.
- Pre/post accepted core identities remain `740dd611…` at 93,984 bytes and
  `7bbc1152…` at 61,153 bytes.
- Named boundary test, environment bundle 73, full suite 714/3 deselected,
  Ruff, lock, Git Bash syntax, cached diff, and working diff checks passed.
- Tracked worktree is clean. Active-root status contains only the collapsed
  `configs/characterize/`, `configs/steer/`, SSH-named, and probe-directory
  exclusions; the exact six underlying exclusions remain untracked/unstaged.
- Orchestrator independently confirmed HEAD, parent, 46 paths, hashes, zero
  tracked diff, and expected exclusions.

Classification: **final commit-verification gap**. Route V5C to Auditor 2 using
a clean detached worktree; do not infer push, integration, or production
authorization from stabilization alone.

## 2026-08-02 — R6-V5C clean-commit verification

Verdict: **Accepted reproducible local revision.**

- Commit `c6ef2df5bb38791a26e4e9490243f327dc6aeb85`, parent `70b7ed8`,
  exact message and 46-path manifest; 12/12 authorized new files and 3/3 required
  schemas present; no excluded or artifact-state paths committed.
- A clean `core.autocrlf=false` detached worktree imported Interlab from the
  detached checkout and reproduced exact V5B sizes/hashes.
- Named boundary: 1 passed; environment bundle: 73; full suite: 714 passed/3
  deselected; Ruff, lock (196), all launcher/setup Bash syntax, and diff passed.
- The first disposable checkout was rejected due global autocrlf conversion;
  the authoritative second checkout preserved exact bytes. Sandbox ACL failures
  were environmental and rerun successfully without network access.
- Detached/main tracked states were clean; main exclusions and hashes were
  preserved; audit worktrees/basetemps/cache were removed and registrations
  pruned.

Classification: **R6 locally accepted**. Begin R7 integration and T1.2 audit in
parallel; no external environment, cluster, push, or experiment authorization
is implied.

## 2026-08-02 — PI-presentation readiness assessment

Verdict: **Existing findings are presentation-ready; the ablation experiment is
not execution-ready.**

- Measured local evidence exists for the rwu04lpb multilingual rerun and
  characterize-lite features, with committed-style result files and explicit
  method caveats in `docs/`.
- No production A7/A8/A9/A9′ ablation evidence exists. Validate and steer
  configs retain deliberate zero placeholders in the isolated T1.2 packet.
- R6-V5C, T1.2-V1, R7/T1.2 integration, external ED-36 environment/equivalence,
  Lab Assistant preflight, fresh A3/A7/A8, placeholder substitution, seed-0 A9,
  and ED-19 judging remain sequential gates. They cannot responsibly be
  collapsed into one evening.
- Presentation-safe action: report existing multilingual/feature measurements,
  show the preregistered ablation design and exact next steps, and label the
  ablation outcome as pending.

Classification: **research communication action; no new experiment
authorization**. Route P0 to the Lab Assistant for read-only evidence assembly.

## 2026-08-02 — Researcher cancels presentation packet

The Researcher explicitly requested the actual ablation experiment rather than
a presentation-evidence packet. P0 is cancelled with no Lab Assistant action.

Fastest valid critical path:

1. Auditor 2 completes R6-V5C clean-commit verification.
2. Auditor 1 completes T1.2-V1 packet verification in parallel.
3. If both accept, Engineer integrates stabilized R6 + parked R7 + accepted
   T1.2 packet with full integration tests.
4. Lab Assistant performs ED-36 environment/equivalence and experiment
   preflight, then executes the sequential A3→A7→A8 chain.
5. Only after real hashes replace placeholders may seed-0 A9 run.

No shortcut through characterize-lite, zero hashes, unintegrated launchers, or
an unverified environment is authorized. Stage-2 causal interpretation remains
blocked on ED-19/A9′ even if seed-0 A9 is produced.

## 2026-08-02 — T1.2-V1 packet verification

Verdict: **Accepted for isolated preparation packet.**

- Clean `e9ad361`; exact base→candidate 14-file scope and five-file C2/C3
  scopes; all pre/post hashes unchanged.
- Battery v1.1.0, exact IID author/change record, preserved provenance, complete
  changelog, historical extractor, dynamic generator, synthetic fixtures, and
  exact golden delta verified. Golden regenerated byte-identically at
  `21697840f3c7cc82054255c9fa3cbef7a725da708762a00ee2aef9c306c6e039`.
- Cheese authority: 12 probes, 20 negatives, empty word-absent/controls,
  probes-only, canonical census term; 39 markers exact.
- Chain, n_docs 20000, stub, feature 9056, zero scale, positions, paired prompts,
  sampling, seeds, placeholders, stable R6 gate, parked R7, and ED-19 restriction
  all correct; six configs schema-valid.
- Focused 148 and full 603/3-deselected passed; lock/diff passed. Exact Ruff
  showed only identical inherited findings in the two old-base scripts; packet
  Python passed. Audit clone/caches/temp removed with no state mutation.
- The report’s statement that R6-V5C remains blocked is concurrency-stale;
  V5C already accepted `c6ef2df` reproducibly.

Classification: **packet accepted; integration gap**. Run R8-I2 in parallel
with R8-I1, then combine and independently verify the integrated experiment
revision before external environment/preflight work.

## 2026-08-01 — T1.2-C1 isolated packet Engineer report

Verdict: **Needs correction; not ready for ablation execution.**

- Local isolated commit `c4f0da7dc52323798b7b20f8f09b119987f22b49`
  contains the authorized fourteen-file battery/config/spec/test packet; no
  merge, push, registry write, cluster job, or scientific output occurred.
- Exact cheese content, battery v1.1.0, two-entry changelog, historical extractor
  preservation, and the golden stop boundary were reported correct. Targeted
  battery/import/census/schema/validate/steer suites passed; lock and diff passed.
- Characterize returned 12 passed/1 cleanup error; its isolated full-run test and
  full pytest did not complete. Repo-wide Ruff remains red only in pre-existing
  out-of-scope scripts on the old base.
- Inspection found one factual producer defect: the characterize config says it
  emits both A7 and A8, contrary to the authoritative characterize→A7,
  validate→A8 chain.
- The same config incorrectly labels Researcher-approved `n_docs: 20000` as
  awaiting confirmation. Gate prose also predates A-006 acceptance.
- The validate and steer configs intentionally retain zero A3/A7/A8 hashes;
  the packet is isolated and R6/R7/environment/preflight gates remain closed.

Classification: **documentation/config-comment defect plus verification and
production-prerequisite gaps**. Route the comment-only C2 repair to the first
Engineer, then independently audit the combined packet before integration.

## 2026-08-01 — T1.2-C2 Engineer report and concurrent-gate review

Verdict: **Needs one prose-only correction before T1.2-V1.**

- Commit `e92174ada4ae96567783d6e6169350b7f5354837` changes exactly the
  characterize config, three steer configs, and protocol document.
- All four YAML semantic objects are unchanged from C1; schemas passed;
  characterize passed 13/13; full pytest passed 603/3 deselected; lock and diff
  checks passed. Remaining Ruff findings are the same inherited two scripts.
- A7/A8 producer ownership and Researcher-approved `n_docs: 20000` are now
  accurate.
- Concurrent R6 consequence: the packet pins `C7→V5B`, but C7 was subsequently
  returned and C8 inserted. The scientific gate did not change—R6/ED-36 must be
  accepted—but the volatile implementation IDs are stale.

Classification: **documentation defect caused by concurrent routing**. C3
replaces repair IDs with the stable R6/ED-36 acceptance condition; no scientific
or configuration value is reopened.

## 2026-08-01 — T1.2-C3 Engineer report

Status: **Engineer complete; T1.2-V1 queued after R6-V5B.**

- Clean isolated commit `e9ad36172e3cccd2410beef606ab5dde52a597f2`
  changes exactly the characterize config, three steer configs, and protocol
  document relative to `e92174a`.
- All four YAML semantic objects are identical to the prior commit; no schema,
  interface, prompt, marker, hash, seed, path, sampling, or scientific value
  changed.
- `R6-C7`, `R6-V5B`, and `A-006` are absent from the five packet files. Stable
  R6/ED-36 local-acceptance wording appears consistently.
- Characterize passed 13/13; schema validation passed 24/24; lock and diff
  checks passed. Worktrees for active R6 and parked R7 were not modified.

Classification: **verification gap only**. Audit the complete C1–C3 isolated
packet after the already-active R6-V5B Auditor task; do not infer cluster or
experiment readiness from packet acceptance.

## 2026-08-02 — R8-I2 integration and byte-fidelity diagnosis

Verdict: **Needs correction in the verification environment; integrated
content is not implicated.**

- Integration HEAD `7597af0` preserves the three audited packet commits,
  contains exactly the authorized 14 paths, and matches 14/14 source Git blobs.
- Focused packet suites passed (103, characterize 13, schema 24); exact Ruff,
  lock, and diff checks passed.
- Full pytest returned 7 failed/707 passed/3 deselected, all at byte-hash gates
  in `tests/test_environment_bundle.py`.
- Both integration worktrees have accepted committed blobs but CRLF-expanded
  working bytes under global `core.autocrlf=true`: requirements are
  187,043/`3b8e0bfd...f8c` rather than 184,572/`9da00e03...314`; the hm03 config
  is 391/`6628dd29...6822` rather than 379/`6dfb9e35...f326`.
- Main at `c6ef2df` retains the accepted LF bytes and hashes. This is the same
  checkout limitation measured during R6-V5C.

Classification: **environment limitation / verification setup defect**.
Re-verify exact commit `7597af0` from a fresh
`git -c core.autocrlf=false worktree add` checkout. Do not patch tests or
regenerate authoritative files.

## 2026-08-02 — R8-I2-C1 byte-faithful re-verification

Verdict: **Accepted.**

- Detached worktree at exact `7597af0`, created with command-scoped
  `core.autocrlf=false`, was clean before and after.
- Requirements remained 184,572 bytes / `9da00e03...314`; the hm03 certify
  config remained 379 bytes / `6dfb9e35...f326` before and after.
- Environment bundle: 73 passed. Full suite: 714 passed, 3 deselected. Exact
  Ruff, lock, and diff checks passed.
- All protected worktree heads/statuses were unchanged; no commit, push,
  cluster access, registry write, or result generation occurred.

Classification: **R8-I2 accepted; prior failures were checkout-only.** The next
bounded action is combined R7+T1.2 integration from an LF-faithful worktree.

## 2026-08-02 — R8-I3 combined integration Engineer report

Status: **Engineer complete; independent acceptance pending.**

- LF-faithful branch `integration-r7-t12-combined` ends at exact commit
  `4bf0fd88f129549569ca3353ccef965a93b51395`, parent `3f3bb75`, over R7
  integration `a65dfb4` and R6 base `c6ef2df`.
- Diff from R6 is exactly the required 18 paths: four launchers plus 14 T1.2
  packet paths. All 14 packet blobs match accepted `7597af0`.
- The steer launcher preserves the R2 factual header and changes only the R7
  login-Bash/resource/wrap behavior relative to R6. Four non-submitting launcher
  probes and Bash syntax for all five launchers passed.
- Authoritative requirements and hm03 config sizes/hashes remained exact before
  and after. Environment 73, full 714/3-deselected, Ruff, lock, diff, and clean
  status passed.
- No push, cluster access, scheduler job, registry/result generation, or
  protected-worktree mutation occurred.

Classification: **major integration verification gap only**. Route exact commit
`4bf0fd8` to Auditor 2 using a fresh LF-faithful detached checkout.

## 2026-08-02 — R8-V1 first audit attempt

Verdict: **Needs correction — independence requirement not executed.**

- The report declared Accepted but explicitly reused the Engineer worktree
  `D:\qwen-sae-interp-combined-lf` and stated that it did not recreate the
  candidate.
- Repository inspection found no
  `D:\qwen-sae-interp-combined-audit-lf` path and no registered detached audit
  worktree.
- Reported hashes/tests remain supporting evidence for candidate quality, but
  they duplicate the Engineer evidence and cannot satisfy the major-milestone
  independent-audit gate.
- The combined candidate remains clean at `4bf0fd8`; no implementation defect
  or correction is indicated.

Classification: **verification procedure defect**. Retry only the audit from a
fresh detached LF-faithful worktree; do not reroute to Engineer or Architect.

## 2026-08-02 — R8-V1-C1 independent combined acceptance

Verdict: **Accepted.**

- Auditor 2 created and registered
  `D:\qwen-sae-interp-combined-audit-lf` detached at exact `4bf0fd8`; path,
  top-level, HEAD, import, and clean-status proof all resolved inside it.
- Exact ancestry and 18-path union passed; all 14 packet blobs matched
  `7597af0`; six schemas, seed normalization, eight zero placeholders, and
  golden `21697840...c6e039` passed.
- Certify remained unchanged; R2 steer header and four R7 launcher behaviors
  passed independent inspection and non-submitting runtime probes.
- Requirements `9da00e03...314` and hm03 config `6dfb9e35...f326` remained exact
  before/after.
- Environment 73, focused 103, full 714/3-deselected, Bash, Ruff, lock, diff,
and final clean status passed. The Engineer worktree was not used.

## 2026-08-03 — R9-X2 first tooling bootstrap attempt

Verdict: **Needs correction; safe stop, no repository mutation.**

- Retained evidence at `D:\lodstar\r9_tooling_bootstrap_20260803` records Linux
  x86_64 CPython 3.11.15, 14 downloaded artifacts, and a passing disposable
  pip check.
- Literal tag policy rejected `distlib-0.4.3-py2.py3-none-any.whl`; this is a
  universal pure-Python wheel but not the exact `py3-none-any` spelling.
- Additional Orchestrator checks found runtime-overlap conflicts not surfaced in
  the Engineer verdict: filelock 3.32.2 versus runtime 3.29.7, and platformdirs
  4.11.0 versus runtime 4.10.0. Pip's exact origin and a retained uv artifact
  record are also incomplete.
- R9 worktree remains clean at `4bf0fd8`; no tooling lock, code, test, bundle,
  commit, Tamia, or production environment action occurred.

Route the universal-tag rule to the Researcher and independently pre-audit the
retained evidence. A retry must preserve exact runtime overlap identities and
close pip/uv provenance before R9-C1 resumes.

## 2026-08-03 — R9-D1 tooling-tag ruling

Verdict: **Accepted; R9-X2B rebootstrap unblocked.**

- Universal wheels are eligible when all parsed tags are ABI `none` and
  platform `any`, at least one tag supports the exact CPython 3.11 target,
  `Requires-Python` admits it, and filename/WHEEL/METADATA/origin/size/hash all
  agree. The `distlib-0.4.3-py2.py3-none-any.whl` tag is eligible, but its bytes
  and digest remain to be measured and audited.
- `uv==0.8.22` is the sole enumerated compiled/platform-coupled exception. The
  retry must retain the exact compatible Linux x86_64 artifact and expose its
  platform tag and complete provenance; no second exception is implied.
- `virtualenv==20.26.0` must be inspected for embedded pip/setuptools/wheel seed
  wheels. Embedded setuptools other than `83.0.0` is a stop condition.
- Exact runtime-overlap identities remain mandatory: at least filelock 3.29.7,
  platformdirs 4.10.0, setuptools 83.0.0, and packaging 26.2. Pip's direct
  origin and complete uv artifact provenance must be captured.
- One clean networked Linux/CPython-3.11 rebootstrap is authorized under R9-X2.
  Repository edits, R9-C1 implementation, bundle construction, Tamia, torch,
  global installs, pushes, and scientific execution remain out of scope.
- Offline only; no Tamia, network, scheduler, push, registry, or result action.

Classification: **combined local revision accepted**. External publication now
requires explicit Researcher authorization before the cluster lane can consume
the immutable commit.

## 2026-08-02 — R8-X1 combined revision publication

Verdict: **Accepted.**

- Explicit authority named exact commit `4bf0fd8`, destination `origin/main`,
  and fast-forward-only/no-force constraints.
- Remote pre-state `70b7ed8`; post-state `4bf0fd8`; transcript reported
  ordinary `70b7ed8..4bf0fd8` fast-forward. Five commits gained, none lost.
- No merge, rebase, new commit, file change, force semantics, Tamia access, or
  cluster execution occurred.
- Local remote-tracking ref independently resolves `origin/main` to exact
  `4bf0fd8`. Local `main` remains at `c6ef2df` and behind four; its pre-existing
  untracked paths remain preserved.

Classification: **publication accepted**. The next gate is explicit authority
for a bounded Tamia fast-forward and host-only prerequisite preflight.

## 2026-08-03 — R9-X1 Tamia preflight

Verdict: **Needs correction for procedure; discovery evidence accepted.**

- Tamia repository moved `70b7ed8` to exact `4bf0fd8` by fast-forward; five
  commits gained and no path conflict or byte loss was reported.
- One pre-existing tracked modification and 28 untracked paths were preserved.
  The explicit authorization said to stop on dirty state, so performing the
  fast-forward was outside that stop condition even though it was non-conflicting.
- No ED-36 bundle or acquisition/install manifest exists. Existing venvs are
  incomplete, CPU-only, or wrong-stack and are not production evidence.
- hm03 checkpoint, corpus, eight configs, five R7 launchers, and A5 are present;
  three steer configs correctly retain zero lineage placeholders.
- Queue empty; zero jobs and zero scientific/registry artifacts; no environment,
  bundle, equivalence, or experiment mutation.

Repository follow-up found that ED-36 has validators/consumers but no builder:
`environment_bundle.py` offers only `preflight`, `create-venv`, and
`record-installed`; no checked-in tool constructs the offline closure or
acquisition manifest. Classification: **genuine construction-protocol ambiguity
and possible implementation gap**. Route R9-A1 to Architect before authorizing
bundle creation.

## 2026-08-03 — parallel T1.2 staging decision

Actual experiment execution remains unauthorized and inadmissible while the
ED-36 bundle/install evidence, production venv, equivalence report, and real
A7/A8 lineage hashes are absent. To reduce latency without bypassing those
gates, R9-P1 is routed to the Lab Assistant for a repository-only dry-run packet
covering environment → A3 → A7 → A8 → seed-0 A9 commands, artifacts, hashes,
resources, logs, stop conditions, and copy-back. It may not access Tamia, edit
configs, submit jobs, or generate scientific evidence.

## 2026-08-03 — parallel orchestration directive

Researcher directed that every dependency-safe lane be surfaced and run in
parallel across persistent roles. Durable orchestration now requires an active/
unblocked/blocked lane table and explicit collision boundaries. The existing
one-copy-paste-prompt-per-target rule remains: already-running lanes are listed
and preserved rather than redundantly re-prompted. Current safe concurrency is
R9-A1 Architect plus R9-P1 Lab Assistant; implementation, audit execution, and
cluster science remain dependency-blocked.

## 2026-08-03 — R9-A1 dual-Architect reconciliation

Both reviews rule that a checked-in deterministic ED-36 builder is required
before Lab Assistant construction and that no ED amendment is needed. The
selected conservative superset is the multi-phase target capture, locked
runtime build, Alliance torch import, bundle finalization, tooling lock,
derived-wheel repair, transfer/setup hardening, and non-overwrite contract.
The paired first-review finding—mandatory §5 `pip check` is absent—is included
in the same module-boundary Engineer candidate. No manual builder procedure is
authorized.

## 2026-08-03 — R9-P1 staging packet reconciliation

The Lab Assistant mapped environment→A3→A7→A8→seed-0 A9 without execution or
mutation. It used `git show 4bf0fd8:<path>` after one remote-ref-only fetch;
local HEAD and files remained untouched. Orchestrator dispositions:

- TransformerLens equivalence remains a T1.2 policy gate despite narrower code
  enforcement for the hm03 certification configuration.
- Census producing both A1 and A3 is the accepted producer contract.
- Local-only project-management memory is intentional; tracked experiment prose
  must carry the execution-relevant statistical rules.
- Missing census launcher/resources, unknown dataset revision, stale statistics
  prose, placeholder-update authority, and pre-judging review remain explicit
  downstream items.

## 2026-08-03 — Q-013 and parallel Engineer results

Q-013's initial CPU-only resource ruling was superseded. Census uses the proven
Tamia whole-node pattern (`h100:4`, `mem=0`, 8 CPUs baseline; 16 only for
confirmed fast-tokenizer parallelism). Walltime remains evidence-sized or 12h
by fallback. The honest `revision: unknown` limitation, structural/blinded
seed-0 review, and four-check mechanical hash substitution remain unchanged.

R10-C1 Engineer commit `2e8efb` is a clean one-file statistics correction and
is ready for independent audit.

R9-C1 stopped correctly with zero edits. It measured 110 active non-torch
distributions and two source-only packages, but exact operational tooling
artifact metadata is absent locally. The next gate is explicit authority for a
one-time networked Linux/CPython-3.11 tooling-lock bootstrap; no metadata may be
invented from unsanctioned installed versions.

## 2026-08-03 — R10-V1 statistics documentation audit

Verdict: **Accepted.** Exact commit `2e8efb` changes only the tracked T1.2
statistics specification. Required repeat aggregation, bootstrap/equivalence,
independent-seed, variance, anti-selection, and structural-only seed-0 rules
are present; obsolete tests are absent; other scientific sections are byte-
identical. Lock, diff, and pre/post clean-state checks passed. No external or
candidate state changed.

## 2026-08-03 — R9-V1 builder audit preparation

Status: **Accepted for preparation; no implementation verdict.**

Auditor 2 produced an immutable-base/five-path audit matrix with exact governing
hashes, deterministic success/failure cases for every ED-36 builder boundary,
and a fresh-checkout command suite. It explicitly separates local code
acceptance from later real Alliance bundle, installation, and TransformerLens
equivalence evidence. No candidate, worktree, build, network, Tamia, or source
mutation was inspected or performed.

## 2026-08-03 — R9-V0A retained tooling-evidence precheck

Verdict: **Needs correction — evidence completeness only.**

- Auditor 2 recomputed all 14 wheel identities, metadata, tags, closure edges,
  and runtime overlaps without changing the retained 19-file root.
- Filelock 3.32.2 and platformdirs 4.11.0 conflict with runtime truth; pip lacks
  a direct artifact URL; uv 0.8.22 lacks a retained artifact; ABI/SOABI is not
  explicit; and distlib was factually misclassified.
- R9-D1 resolves distlib eligibility. Corrected evidence and virtualenv seed
  inspection remain required. This is not an R9-C1 implementation verdict.

## 2026-08-03 — R10-X1 census runtime/tokenizer recovery

Verdict: **Accepted for launcher calibration.**

- A10 `fb3b861d79dc` and scheduler job 382736 were recovered read-only; the job
  completed exit 0 in `00:29:15`. A10 has `slurm: null`, so exact timestamp
  correspondence supports calibration but is not promoted to recorded lineage.
- The tokenizer resolves to exact revision
  `cf98f3b3bbb457ad9e2bb7baf9a0125b6b88caa8`. It is fast/Rust-backed, while
  parallelism is absent/unconfirmed and historical use is effectively one CPU.
- Q-013 maps this to one hour, eight CPUs, `mem=0`, and `h100:4`.
- No job, artifact, environment, repository file, or registry state changed.

## 2026-08-03 — R9-X2B virtualenv seed preflight

Verdict: **Needs correction — mandatory safe stop.**

- Engineer 2 inspected the retained virtualenv 20.26.0 wheel offline before any
  rebootstrap. It embeds pip 24.0, setuptools 68.0.0 and 69.5.1, and wheel
  0.42.0 and 0.43.0.
- Embedded setuptools is not the required 83.0.0, so the explicit R9-D1 stop
  condition fired. No network, new evidence directory, repository edit,
  tooling lock, R9-C1 implementation, or commit occurred.
- Inspection of current source shows the creator invokes
  `virtualenv --no-download <target>`; this prevents download but leaves default
  embedded seeding enabled. Later installation of pinned tooling would be an
  overwrite/reconciliation and cannot be silently treated as compliant.
- Route the narrow seed-isolation mechanism to the Architect. The retained
  evidence root and R9 builder worktree remain unchanged.

## 2026-08-03 — R10-C2 census launcher Engineer result

Status: **Engineer complete; independent acceptance pending.**

- Commit `9d90ef601822c1cacad0b6aade8a1a265f2b0e39` has parent `2e8efb...` and
  adds only `slurm/launch_census.sh`; no existing file changed.
- Git-Bash syntax and missing-config/missing-run-ID failure paths passed before
  scheduler invocation.
- A non-submitting stub decoded the `bash -lc` payload byte-for-byte, preserved
  the literal remote venv fallback/config/run label, and found every authorized
  scheduler argument exactly once with forbidden scheduler/mtime behavior absent.
- Focused census/schema tests passed 39/39; lock, diff, commit scope, and clean
  state passed. No scheduler, Tamia, registry, result, or artifact action occurred.

## 2026-08-03 — R9-A2 virtualenv seed-isolation architecture

Verdict: **Accepted architecture; Human ratification required.**

- Both Architect reviews independently chose the same design: retain the exact
  virtualenv 20.26.0 artifact, make embedded seed archives inert with mandatory
  unseeded/network-closed creation, prove the fresh environment empty, and
  bootstrap only verified pip 25.0 from isolated offline bytes.
- No ED, schema, frozen-blueprint, dependency-version, or scientific-policy
  amendment is required. Selecting a new creator or stdlib venv was rejected.
- The current implementation additionally lacks `--no-periodic-update`, private
  app-data, explicit creator dependency closure, pre-bootstrap inventory checks,
  and a verified pip bootstrap boundary; these are implementation obligations.
- Human R9-D2 must clarify that R9-D1 prohibits operational use of unapproved
  seeds rather than their inert enumerated bytes inside the unchanged creator.

## 2026-08-03 — R9-D2 unseeded creator ratification

Verdict: **Accepted with required additions.**

- The unchanged virtualenv 20.26.0 artifact may retain fully enumerated embedded
  seeds only as inert bytes; selecting, extracting, installing, importing,
  executing, transiently overwriting, or reconciling them remains prohibited.
- `ensurepip` is forbidden in every form because its interpreter-bundled
  pip/setuptools would create the same provenance defect at a second boundary.
- After verified offline pip-wheel bootstrap, inventory must be exactly
  `pip==25.0`, with setuptools and wheel still absent, before normal tooling.
- The operational pin is explicitly `wheel==0.45.0` with exact artifact
  identity. All later requirements remain exact and hash-bearing.
- This authorizes corrected tooling-evidence acquisition and later local
  implementation/audit only; Tamia, bundle, production venv, publication, and
  science remain unauthorized.

## 2026-08-03 — R10-V2 census launcher acceptance

Verdict: **Accepted.**

- Independent LF-faithful checkout confirmed candidate `9d90ef6`, exact parent
  `2e8efb`, one added launcher, and preserved accepted documentation blob.
- Exact interface, resource comment, remote command order, wrapper, scheduler
  arguments, missing-argument paths, and decoded stub passed.
- Focused tests passed 39/39; full suite 714/3-deselected; Ruff, lock, all six
  launcher syntax checks, diff, and final clean state passed.
- Acceptance is local only; no integration, publication, environment, Tamia,
  scheduler, or scientific action is authorized.

## 2026-08-03 — R9-X2C tooling evidence review

Verdict: **Needs correction before Auditor 2.**

- The retained 15-artifact closure, overlap pins, direct origins, uv exception,
  embedded inventory, and final installed inventory are substantively complete.
- The resolver environment was created by `python -m venv` without
  `--without-pip`, implicitly invoking forbidden ensurepip, followed by
  `pip install --upgrade pip==25.0`.
- Verification transcripts delete pip/wheel script paths before the recorded
  empty-state proof. Deletion cannot establish that the fresh target was empty
  before mutation.
- Preserve this root unchanged as failed procedural evidence. R9-X2D must use
  absent targets, `--without-pip`, verified pip-wheel bootstrap for resolver and
  verifier, no upgrade, and no pre-proof sanitizing deletion.

## 2026-08-03 — R9-X2D corrected tooling evidence

Status: **Complete; independent evidence acceptance pending.**

- New D3 root reports 45 files, two directories, file-only inventory digest
  `f9cc733a4199e39ec497aa3e1352375062f580afae6779ed5c8b9daf286955f0`.
- Prior D1/D2 roots retained identical pre/post file-only inventory digests.
- Resolver and verifier used fresh `--without-pip` environments with empty,
  unsanitized pre-bootstrap inventories; exact verified pip 25.0 was installed
  alone before the other 14 exact artifacts.
- Final inventory is the exact 15-distribution closure and `pip check` passed;
  direct origins, runtime overlaps, uv sole exception, tags, and virtualenv seed
  inventory are retained.
- No executed ensurepip or upgrade operation is reported. Acquisition host
  3.11.15 is explicitly not promoted to Tamia target truth.
- Two failed validation transcripts are retained for import-path and name-
  normalization assertion defects. Auditor 2 must confirm artifact immutability
  and that the successful continuation did not bypass a substantive invariant.
- No repository, tooling lock, R9-C1, Tamia, torch, bundle, global install, or
  production state changed.

## 2026-08-03 — R9-V0B D3 tooling-evidence audit

Verdict: **Needs correction.**

- Counts, reparse-point absence, host labeling, unseeded resolver, no
  ensurepip/upgrade/sanitization, exact closure/origins/overlaps, uv exception,
  nested seeds, offline final inventory, and both pip checks passed.
- Bootstrap code imports pip before a retained command binds a pre-import hash
  check to the exact executed bytes. Claimed read-only source mounting is not
  independently retained.
- The claimed phase-3 normalization failure is absent because its transcript
  path was overwritten by the successful attempt; retry preservation cannot be
  audited.
- Supplied aggregate digests lacked retained byte framing. Auditor-defined
  stable fingerprints use sorted POSIX paths framed as UTF-8
  `path NUL decimal-size NUL lowercase-file-SHA256 LF`.
- D3 is not sufficient for the tooling lock or R9-C1. D4 may reuse its verified
  artifacts offline while correcting only execution and retention evidence.

## 2026-08-03 — R10-X2 accepted publication

Verdict: **Accepted.**

- Observed remote pre-state exactly matched authorized `4bf0fd8`; ancestry and
  merge-base proved strict fast-forward to `9d90ef6`.
- Push transcript was ordinary `4bf0fd8..9d90ef6`; independent `ls-remote`
  confirmed `origin/main` equals the accepted commit.
- No force, merge, rebase, new commit, file edit, stash, reset, clean, Tamia,
  environment, scheduler, or artifact action occurred.
- The reporting checkout at `c6ef2df` is six commits behind `9d90ef6` (R7,
  three T1.2 integration commits, statistics correction, census launcher), not
  two. The branch pointer and its four pre-existing uncommitted entries were
  correctly left unchanged.

## 2026-08-03 — R10-X3 Tamia fast-forward

Verdict: **Accepted.**

- All preconditions passed before a single `git merge --ff-only`; Tamia HEAD
  advanced from exact `4bf0fd8` to exact `9d90ef6` through only the accepted
  statistics document and new census launcher.
- The pre-existing tracked modification retained identical Git blob and
  SHA-256. All 26 untracked paths present at this work item's preflight remained
  present; none was added or removed by the update.
- The launcher working blob matched the committed blob, SHA-256 was recorded,
  and `bash -n` passed without launcher execution.
- Queue and registry remained unchanged: zero jobs, test submissions, bundles,
  venvs, placeholders, artifacts, results, or reports.
- Earlier R9-X1 evidence recorded 28 untracked paths while R10-X3 began with 26.
  This is an honest inter-session state difference, not an R10-X3 mutation.

## 2026-08-03 — R9-X2E D4 tooling-evidence handoff

Status: **Engineer complete; independent verification pending.**

- Immutable root: `D:\lodstar\r9_tooling_bootstrap_20260803_d4`.
- D1-D3 retained their Auditor-framed fingerprints. D4 reports 73 files, five
  directories, payload digest
  `f5fc6ee4a78f632c77a2089aa6313b67cd8d81e0a046c07401f1549e9a4084e6`,
  and a 13,691-byte inventory manifest with SHA-256
  `113c7bb2e2aa67ccdc0a37aae11770181b14a0e2d5ac8eee20c83f8118aca5b5`.
- Retained mount evidence records `/d3ro` read-only and a failed write probe
  (`errno 30`), with the D3 fingerprint unchanged.
- Attempt `0001` is retained as a harness failure; attempt `0002` is declared
  authoritative. Attempt indexing and transcripts are non-overwriting.
- Pip pre-import validation binds the approved 1,841,506-byte wheel hash to a
  private mode-0400 snapshot; device, inode, size, and hash remain stable, and
  loaded pip origins resolve within that snapshot.
- Resolver/verifier inventories are empty before bootstrap, exactly pip 25.0
  afterward, and the exact 15-package closure at completion. All three reported
  `pip check` invocations passed.
- D4 artifacts report exact byte equality with D3. No network, repository,
  Tamia, torch, bundle, global-install, or production mutation is reported.
- R9-V0C must independently recompute these boundaries. R9-C1 remains blocked
  until Auditor 2 explicitly accepts D4.

## 2026-08-03 — R9-V0C D4 tooling-evidence acceptance

Verdict: **Accepted.**

- D1-D4 pre/post identities matched. D4 contains 72 manifest-covered payload
  files plus its self-excluded manifest; framing, ordering, path set, sizes, and
  hashes reproduced exactly.
- No reparse, symlink, traversal, absolute-path, or ZIP boundary violation was
  found.
- `/d3ro` was independently confirmed read-only; the write probe failed with
  errno 30 and D3 remained byte-identical.
- Attempts `0001` and `0002` are distinct and retained; `0001` is an honest
  pre-processing harness failure and `0002` is the sole authoritative success.
- Pip was verified before import and executed only from the private mode-0400
  snapshot whose device, inode, size, and digest remained stable.
- Resolver/verifier states, exact 15-distribution closure, direct provenance,
  runtime overlaps, uv exception, inert virtualenv seeds, and three successful
  pip checks passed independently.
- Auditor 2 explicitly ruled that D4 is sufficient to author
  `slurm/environment_bundle.tooling.lock.json` and that Engineer 2 may resume
  the bounded local R9-C1 implementation.
- No publication, network acquisition, Tamia, bundle, production environment,
  equivalence, or scientific execution authority follows.

## 2026-08-03 — R9-C1 ED-36 builder Engineer candidate

Status: **Engineer complete; independent verification pending.**

- Candidate `c847e075f87a2f5cb871c59d8e94d06c9ec00280` is a direct child of
  `4bf0fd88f129549569ca3353ccef965a93b51395` and changes exactly the five
  authorized R9-C1 paths.
- It reports the four deterministic builder/finalizer commands, D4-derived
  15-artifact tooling lock, exact overlap and uv rules, two derived-wheel paths,
  Alliance torch import boundary, unseeded creator/private pip bootstrap,
  setup revision gates, mandatory target-venv pip check, and non-overwrite.
- Reported results: 7 builder tests, 75 environment tests, 2 setup tests, and
  723 full tests passed; Ruff, lock, Bash syntax, and diff checks passed.
- Governing dependency truth and schemas retain their accepted hashes.
- No push, Tamia, live bundle, production venv, torch acquisition, or external
  execution occurred. R9-V1 must audit the immutable candidate before any such
  action is considered.
- In parallel, a read-only inspection of `D:\lodstar` is authorized to map the
  existing Lodestar interfaces to Interlab's ED-19 Stage-2 boundary. It may not
  modify either repository or perform live judging.

## 2026-08-03 — R11-P1 Lodestar/ED-19 read-only map

Status: **Complete; architectural ruling required.**

- Lodestar exposes a real Anthropic structured-output judge and CLI, with
  pinned-model, budget, concurrency, repeat, retry, cache, and repair support.
- It has no `lodestar.interlab.make_interplab_runtime()`, no object satisfying
  Interlab's combined `evaluate` plus `measure_capability` protocol, and no
  capability/perplexity implementation.
- Interlab's blinded record omits the target concept; judge config cannot carry
  model/rubric/repeats/budget/instrument settings; Lodestar's repeated judgments
  do not map losslessly to one `BlindScore`; prompt/instrument identity is not
  retained through A9; A12 has no production entry; raw run evidence is not
  content-addressed.
- In-process packaging is currently incompatible: Lodestar is not locked in
  Interlab, its declared NumPy floor conflicts with the production NumPy pin,
  and `D:\lodstar` lacks immutable Git revision identity. A subprocess boundary
  could avoid this but changes the current import-hook architecture.
- No files, tests, network, credentials, Tamia, or live calls changed.
- Route `R11-A1-ED19-LIVE-LODESTAR-CAPABILITY-BOUNDARY` to the Architect. Human
  authority is subsequently required for A12 membership, credential/budget
  use, cache retention, and paid external calls.

## 2026-08-03 — R9-V1 ED-36 builder audit

Verdict: **Needs correction.**

- Fresh detached audit confirmed exact five-path scope, unchanged governing
  truth, exact D4 tooling-lock identities, clean retained state, 723 full tests,
  and green Ruff/lock/Bash/diff gates.
- Blocking implementation defects remain in target/source cross-binding,
  SOABI/tag build-host equality, safe sdist extraction, build requirement and
  backend reconciliation, deterministic network denial, independent Alliance
  torch authority, invocation-owned staging/rollback, recursive finalization
  safety, mutually bound receipts, atomic no-clobber promotion, private pip
  snapshot execution, externally supplied expected revision, atomic manifest
  publication, and TransformerLens contamination rejection.
- Only seven builder tests were collected. Most blocking R9-V1-PREP matrix
  boundaries lacked direct deterministic coverage; success tests monkeypatched
  real closure or consumer validation in important places.
- One Windows rollback run raised `PermissionError` and masked the intended
  environment error, although later isolated/combined/full reruns passed. This
  still requires deterministic rollback/error-preservation handling.
- Candidate `c847e075f87a2f5cb871c59d8e94d06c9ec00280` is not accepted and may not
  be integrated or published. Real target capture and bundle construction are
  not admissible.
- Route one bounded same-five-path correction to Engineer 2 as R9-C2, followed
  by a new independent R9-V2 audit.

## 2026-08-03 — R11-A1 Lodestar/ED-19 architecture reviews

Status: **Architecturally resolved; Human ratification required.**

- Both reviews reject in-process Lodestar because judging requires outbound
  access and Lodestar's NumPy/dependency closure conflicts with Interlab's
  certified scientific environment.
- Selected topology: a separately locked, one-shot, off-cluster Lodestar judge
  consumes only content-addressed blinded requests. Interlab retains capability
  measurement on Tamia and alone joins both evidence sets into A9′.
- No A9′ may exist unless source A9, capability evidence, judge request, raw-run
  evidence, environment identities, and A12 compatibility all validate.
- Exact three-repeat QC retains failed slots; two or three survivors are averaged;
  zero or one survivor produces a null excluded row without imputation.
- Recommended synthesis adopts explicit v2 schemas for judge config, A9/A9′ and
  A11; prompt_version is the hash of the full instrument manifest while native
  Lodestar instrument_id is retained separately; A12 v1 remains the exact
  Researcher-authored three-key compatibility registry.
- Production repeat runs must disable response caching to avoid counterfeit
  independence. Frozen cache evidence may exist only for separately authorized
  non-production/canary policy.
- Lodestar requires a clean immutable 0.2.0 source/package release identity; the
  current non-Git workspace and editable environment are not production evidence.
- ED-37 is required as a narrow amendment to ED-19/20/21; ED-36 remains unchanged.
- R11-D1 Human ratification precedes any implementation. It authorizes no
  credentials, paid calls, Tamia action, production artifacts, or science.

## 2026-08-03 — R11-D1 ratification and temperature-0 correction

Status: **ED-37 ratified; narrow Researcher decision remains.**

- The Program Manager ratified ED-37 and confirmed the three-repeat aggregation
  rule: mean of two or three survivors, null/excluded below two, no imputation.
- Historical Lodestar uses judge temperature 0 and max tokens 256. Therefore
  α≥0.91 principally measures deterministic repeat agreement, not independent
  judge stability or reliability. Existing report, Evidence Ledger, and oral
  script wording overstate this result and must be corrected before reuse.
- Recommended Researcher choice is to retain temperature 0 for instrument
  continuity, rename repeats as determinism checks, and reserve genuine
  variability measurement for a separately versioned future instrument.
- Historical sufficiency artifacts lack prompt_version. A retrospective
  instrument manifest may be reconstructed from retained run fields and current
  source, but must explicitly label temperature/max-token source identity as
  recovered rather than proven runtime bytes because `D:\lodstar` is not Git.
  A12 later decides equivalence; no automatic compatibility is allowed.
- Historical cost evidence makes seed/repeat trimming scientifically
  unjustified. Adding coherence as reported, non-gating evidence is proposed;
  it must not silently change the concept-relevance acceptance gate.
- Route R11-D1A to the Researcher, then a prose/evidence correction to Engineer
  1 in parallel with R9-C2. Paid calls and production remain unauthorized.

## 2026-08-03 — R9-C2 intermediate ED-36 correction

Status: **Needs correction; do not audit yet.**

- Clean successor `ea65a8711d7313e0942b75ac84636b04c901fe6e`, parent `c847e075...`,
  modifies four of the five authorized paths and reports 729 full tests plus
  green Ruff/lock/Bash/diff gates.
- It improves target/source binding, invocation-owned staging, full host
  fingerprint checks, bounded sdist extraction, build-system validation,
  no-clobber helpers, atomic install-manifest publication, explicit revision
  propagation, and builder coverage from seven to thirteen tests.
- Engineer 2 correctly reports unresolved direct proof for derived-build
  socket/DNS denial, recursive allowlist/tamper, concurrent no-clobber, complete
  TransformerLens contamination, rollback primary-error preservation, and
  wrong-HEAD shell authority.
- `setup_env.sh` retains an `INTERPLAB_STUB_LOG` fallback that bypasses strict
  external expected-revision authority solely to preserve an existing test.
  Correcting both behavior and test requires adding
  `tests/test_slurm_setup_env.py` to the authorized scope.
- Route R9-D3 to the Human for that one-path expansion. R9-C3 and R9-V2 remain
  blocked; no integration, publication, target capture, bundle, or experiment.

## 2026-08-03 — R9-D3 setup-test scope ratification

Verdict: **Accepted.**

- Program Manager verified `ea65a871...`, its branch, and all six authorized
  paths. No seventh path or external caller update is required.
- The exact defect is the stub-only injection of forty zeroes as expected
  revision. It must be deleted, not moved into the test.
- A success test must obtain and supply the fixture checkout's real 40-character
  HEAD exactly as production authority is supplied. Forty zeroes may occur only
  in an explicit wrong-HEAD rejection test.
- The setup usage block must identify `INTERPLAB_EXPECTED_REVISION` as mandatory.
- R9-C3 may create a successor to `ea65a871...` within exactly six paths.
- Local-main synchronization is not an R9-V2 prerequisite. Because main has
  known untracked config collisions, the audit must instead create a fresh
  detached LF-faithful worktree from the exact successor SHA. This is the same
  isolation pattern successfully used by R9-V1 and avoids mutating local main.

## 2026-08-03 — R9-C3 final-matrix Engineer candidate

Status: **Engineer complete; independent verification pending.**

- Candidate `490ae73e04cc5bfbfb814746aeab609e5e4f06fb`, parent `ea65a871...`,
  changes five paths in the authorized cumulative six-path boundary; the D4
  tooling lock remains unchanged from the earlier commit.
- The stub/all-zero expected-revision bypass is reported removed. Setup success
  uses a real fixture Git HEAD passed through the production environment
  authority path; nine setup cases cover missing/malformed/wrong/dirty/success.
- Builder coverage increased to 23 tests for network denial, recursive
  finalization, no-clobber, TransformerLens contamination, and cleanup error
  preservation. Environment tests increased to 78; focused total is 110.
- Reported full result is 749 passed, 3 deselected; Ruff, lock, all launcher/setup
  Bash syntax, diff, governing identities, scope, and retained state are green.
- Engineer reports no distinct Windows reparse-point fixture beyond symlink
  coverage. R9-V2 must decide whether target-platform enforcement plus static
  rejection is sufficient.
- R9-V2 must also verify that network-denial tests reach non-Python subprocess
  acquisition where required, no-clobber tests simulate a true concurrent
  destination, TransformerLens tests cover every named surface, finalization
  rejects nested links, and torch negative coverage remains complete.
- No integration, publication, target capture, bundle, environment, equivalence,
  or scientific execution authority follows from the Engineer verdict.

## 2026-08-03 — R9-V2 second ED-36 builder audit

Verdict: **Needs correction.**

- Fresh exact-SHA audit confirmed ancestry, six-path cumulative scope, unchanged
  governing truth, exact D4 lock, strict external revision authority, real-HEAD
  setup tests, Windows junction rejection, 749 full tests, and green static gates.
- Real derived-wheel validation remains internally inconsistent: the new wheel
  hash is still required to equal an export-authorized sdist hash, while the
  successful test monkeypatches the build.
- Network isolation fails open when namespace isolation is unavailable; a
  non-Python child executed successfully under the fallback.
- Remaining implementation gaps cover exact build requirement/backend semantics,
  duplicate archive entries, runtime/tooling/torch cross-binding, concurrent
  symlink destinations, cleanup-error preservation, and unexercised private pip.
- Direct tests remain missing across D4 regression, wheel selection, real 110
  closure, both source-only derived paths, build matrices, network fail-closed,
  archive types, torch negatives, nested finalization/substitution, pip bootstrap,
  symlink races, cleanup paths, and all TransformerLens surfaces.
- Windows reparse/junction rejection is independently proven and no longer open.
- One narrow ambiguity is routed to R9-A3: whether a ranged PEP 517 build
  requirement that admits the exact approved locked artifact is acceptable, or
  whether the source declaration itself must be literal `==`. All other defects
  are implementation work after that ruling.

---

## 2026-08-08 — `qwen_max_activating_tokens.json` re-cut under prereg §14.5

Artifact: `scripts/legacy/qwen_max_activating_tokens.json`
Builder: `scripts/legacy/build_qwen_max_activating_tokens.py`

| | sha256 |
|---|---|
| **superseded** | `60e920aa3485fb1981e0d7fd603a1893e2be74dd90e0b557d37dca004acd69b0` |
| **current** | `b6bf9710a92a1bce37089f9ff69663dc951c7e97eab974428ca190a01ccdb3f6` |

**The superseded digest is retained, not deleted.** It is the digest under which the artifact was
accepted for Qwen marker parity (§11.1), and any earlier reference to it remains valid for the
record content it names.

**Reason for the re-cut.** The Gemma marker file was regenerated with a three-signal seam schema
(`is_multi_document_record` / `bos_in_context_window` / `unmarked_fusion_heuristic`), replacing the
single `splice_seam`. The Qwen `_meta` still described the old schema. Per-record parity was
unaffected — the Qwen records already carried all four Gemma fields — but a `_meta` block describing
a schema that no longer exists is a stale claim in a hash-bound artifact.

**Changed:** `_meta` only. Realigned to the Gemma field names; added
`unmarked_fusion_heuristic_caveat` (the ~97%-false-positive finding, recorded on both columns);
added `context_truncation_rule` stating that no truncation is ever applied on Qwen because a `<bos>`
inside ±10 cannot arise, and that a short `context_tokens` list therefore means a window edge and
not a cut seam; retained `splice_seam` on every record as the vestigial Qwen-correct constant
`false`, documented under `splice_seam_note`.

**Assertion, because a metadata-only change is a claim and a claim about bytes is checkable.**
Each of the 972 records was hashed individually before the re-cut and again after, under a canonical
key-sorted serialisation:

```
records before / after : 972 / 972
identical              : 972
differing              : 0
missing after re-cut   : 0
RESULT                 : PASS
```

**All 972 records are byte-identical across the re-cut.** The digest changed for `_meta` alone. The
builder re-derives every record from source and re-runs the tokenizer, so this also re-confirms the
original build: 972/972 emitted, 0 skipped, both per-record gates passing (marker-token identity,
and the nine-token rejoin to `original_excerpt` byte for byte).
