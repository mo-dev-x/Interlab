#!/usr/bin/env python
"""
Provenance reconnaissance for T0.0 -- READ ONLY, evidence recovery only.

Recovers whatever facts about the four Interlab campaign checkpoints
(rwu04lpb, d1bgp5v5, o1cx1dow, zf2o13m2) can be established mechanically
from checkpoint directories, the HF model cache, and WandB offline logs.

Hard rules this script follows:
  - Never writes to registry/. Writes exactly one report file, at the
    repository root (REPORT_PATH, gitignored as /provenance_recon_*.json
    -- see .gitignore), and nowhere else.
  - Never guesses. Every field is either read directly from a source file
    (a "recovered" fact, with the exact path it came from) or reported as
    a labelled list of untried candidates for a human to resolve. Nothing
    is ever auto-selected when more than one candidate exists.
  - Makes no architectural changes -- this is a standalone diagnostic
    script, not an interplab job, and does not touch interplab.jobs or
    interplab.registry.

Run from the repo root on the cluster, with the project venv active:
    python scripts/recon_checkpoint_provenance.py              # metadata only, fast, login-node safe
    python scripts/recon_checkpoint_provenance.py --with-hash   # also hashes checkpoint + model dirs (slow, real I/O -- run via sbatch/salloc, not the login node)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None  # config.yaml parsing degrades to "not parsed" rather than crashing

#: Repository root, not this script's own directory: this script was
#: relocated to scripts/ (docs/repo_cleanup_plan.md Phase 5) from repo
#: root, where `.parent` alone used to be correct. `.parents[1]` keeps
#: every relative lookup below (results/sae_checkpoints/, wandb/, the
#: report output path) correct regardless of the invoking cwd.
REPO_ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT_IDS = ["rwu04lpb", "d1bgp5v5", "o1cx1dow", "zf2o13m2"]
MODEL_NAME_HINT = "Qwen2.5-14B-Instruct"

REPORT_PATH = REPO_ROOT / f"provenance_recon_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"


def _try_hash_directory(path: Path):
    """Only imports interplab.core.hashing when actually needed (--with-hash),
    so a metadata-only run never requires interplab to be importable."""
    from interplab.core.hashing import hash_directory
    return hash_directory(path)


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except FileNotFoundError:
        return None, f"not found: {path}"
    except Exception as e:  # malformed json, permissions, etc. -- report, don't crash
        return None, f"error reading {path}: {e}"


def _read_yaml(path: Path):
    if yaml is None:
        return None, "pyyaml not available in this environment"
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")), None
    except FileNotFoundError:
        return None, f"not found: {path}"
    except Exception as e:
        return None, f"error reading {path}: {e}"


def find_checkpoint_dir_candidates(ckpt_id: str) -> list[Path]:
    """All 'final_*' directories under results/sae_checkpoints/<ckpt_id>/,
    at any depth (the Montreal-era checkpoints nest one level deeper:
    <id>/<subrun>/final_*, so we don't assume a fixed depth)."""
    base = REPO_ROOT / "results" / "sae_checkpoints" / ckpt_id
    if not base.exists():
        return []
    return sorted(p for p in base.rglob("final_*") if p.is_dir())


def recover_checkpoint_facts(ckpt_id: str, with_hash: bool) -> dict:
    facts: dict = {"checkpoint_id": ckpt_id}

    dir_candidates = find_checkpoint_dir_candidates(ckpt_id)
    facts["checkpoint_dir_candidates"] = [str(p.relative_to(REPO_ROOT)) for p in dir_candidates]
    if not dir_candidates:
        facts["status"] = "NOT FOUND on this filesystem -- confirm you're running on the machine that holds the weights"
        return facts

    # tokens_trained implied by the directory-name convention, per candidate
    facts["tokens_trained_from_dirname"] = {}
    for d in dir_candidates:
        suffix = d.name.replace("final_", "", 1)
        facts["tokens_trained_from_dirname"][str(d.relative_to(REPO_ROOT))] = (
            int(suffix) if suffix.isdigit() else f"unparseable: {d.name!r}"
        )

    facts["per_candidate"] = []
    for d in dir_candidates:
        entry: dict = {"dir": str(d.relative_to(REPO_ROOT))}

        cfg_path = d / "cfg.json"
        cfg, cfg_err = _read_json(cfg_path)
        if cfg is not None:
            entry["cfg_json"] = {
                "source": str(cfg_path.relative_to(REPO_ROOT)),
                "model_name": cfg.get("model_name"),
                "hook_name": cfg.get("hook_name"),
                "hook_layer": cfg.get("hook_layer"),
                "d_in": cfg.get("d_in"),
                "expansion_factor": cfg.get("expansion_factor") or cfg.get("d_sae"),
                "architecture": cfg.get("architecture"),
                "k": cfg.get("k"),
                "seed": cfg.get("seed"),
                "training_tokens": cfg.get("training_tokens"),
                "dataset_path": cfg.get("dataset_path"),
                "wandb_project": cfg.get("wandb_project"),
                "raw": cfg,  # full config kept verbatim -- nothing summarized away
            }
        else:
            entry["cfg_json"] = {"error": cfg_err, "searched": str(cfg_path.relative_to(REPO_ROOT))}

        if with_hash:
            try:
                entry["weights_dir_hash"] = _try_hash_directory(d)
            except Exception as e:
                entry["weights_dir_hash"] = {"error": f"hash_directory failed: {e}"}
        else:
            entry["weights_dir_hash"] = "SKIPPED (run with --with-hash)"

        facts["per_candidate"].append(entry)

    return facts


def find_hf_model_snapshots() -> dict:
    scratch = os.environ.get("SCRATCH")
    result: dict = {"scratch_env": scratch}
    if not scratch:
        result["error"] = "$SCRATCH is not set in this shell -- cannot search the HF cache"
        return result

    hub_root = Path(scratch) / "hf_cache" / "hub"
    matches = sorted(hub_root.glob(f"models--Qwen--{MODEL_NAME_HINT}")) if hub_root.exists() else []
    result["hub_root"] = str(hub_root)
    result["hub_root_exists"] = hub_root.exists()
    result["model_dirs_found"] = [str(m) for m in matches]

    snapshots: list[dict] = []
    for m in matches:
        refs_main = m / "refs" / "main"
        pinned_revision = None
        if refs_main.is_file():
            try:
                pinned_revision = refs_main.read_text(encoding="utf-8").strip()
            except Exception as e:
                pinned_revision = f"error reading refs/main: {e}"
        snap_dir = m / "snapshots"
        snap_candidates = sorted(p.name for p in snap_dir.iterdir()) if snap_dir.exists() else []
        snapshots.append(
            {
                "model_dir": str(m),
                "pinned_revision_ref_main": pinned_revision,
                "snapshot_candidates": snap_candidates,
            }
        )
    result["snapshots"] = snapshots
    return result


def find_wandb_offline_runs() -> list[dict]:
    """Looks in the conventional location (repo_root/wandb/) first, then
    falls back to a broader search in case WANDB_DIR was set differently
    for some job -- reports where it actually found things rather than
    assuming."""
    search_roots = [REPO_ROOT / "wandb"]
    run_dirs: list[Path] = []
    for root in search_roots:
        if root.exists():
            run_dirs.extend(sorted(p for p in root.glob("offline-run-*") if p.is_dir()))
    if not run_dirs:
        # fallback: broader search, capped, in case wandb/ lives elsewhere
        run_dirs = sorted(REPO_ROOT.rglob("offline-run-*"))[:200]

    runs = []
    for rd in run_dirs:
        entry: dict = {"dir": str(rd.relative_to(REPO_ROOT)) if rd.is_relative_to(REPO_ROOT) else str(rd)}

        meta, meta_err = _read_json(rd / "files" / "wandb-metadata.json")
        if meta is not None:
            entry["metadata"] = {
                "startedAt": meta.get("startedAt"),
                "host": meta.get("host"),
                "program": meta.get("program"),
                "args": meta.get("args"),
            }
        else:
            entry["metadata"] = {"error": meta_err}

        cfg, cfg_err = _read_yaml(rd / "files" / "config.yaml")
        if cfg is not None:
            # wandb config.yaml wraps each key as {"value": ..., "desc": ...}
            flat = {k: (v.get("value") if isinstance(v, dict) and "value" in v else v) for k, v in cfg.items()}
            entry["config"] = {
                "model_name": flat.get("model_name"),
                "hook_layer": flat.get("hook_layer"),
                "expansion_factor": flat.get("expansion_factor"),
                "seed": flat.get("seed"),
                "wandb_project": flat.get("wandb_project"),
            }
        else:
            entry["config"] = {"error": cfg_err}

        summary, summary_err = _read_json(rd / "files" / "wandb-summary.json")
        if summary is not None:
            entry["summary_telemetry"] = {
                "sparsity/dead_features": summary.get("sparsity/dead_features"),
                "metrics/explained_variance": summary.get("metrics/explained_variance"),
                "details/n_training_tokens": summary.get("details/n_training_tokens"),
                "_step": summary.get("_step"),
            }
        else:
            entry["summary_telemetry"] = {"error": summary_err}

        try:
            files = list((rd / "files").iterdir()) if (rd / "files").exists() else []
            mtimes = [f.stat().st_mtime for f in files if f.is_file()]
            if mtimes:
                entry["file_mtime_range"] = [
                    datetime.fromtimestamp(min(mtimes), tz=timezone.utc).isoformat(),
                    datetime.fromtimestamp(max(mtimes), tz=timezone.utc).isoformat(),
                ]
        except Exception as e:
            entry["file_mtime_range"] = f"error: {e}"

        runs.append(entry)
    return runs


def match_wandb_candidates(cfg_json: dict, wandb_runs: list[dict]) -> list[dict]:
    """Returns EVERY wandb run whose recorded config is consistent with
    this checkpoint's cfg.json -- never fewer than all matches, never a
    single 'best' pick. Zero matches and multiple matches are both
    reported as-is."""
    if not cfg_json or "raw" not in cfg_json:
        return []
    matches = []
    for run in wandb_runs:
        c = run.get("config", {})
        if isinstance(c, dict) and "error" not in c:
            if (
                c.get("hook_layer") == cfg_json.get("hook_layer")
                and c.get("expansion_factor") == cfg_json.get("expansion_factor")
                and c.get("seed") == cfg_json.get("seed")
            ):
                matches.append(run)
    return matches


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--with-hash", action="store_true", help="also compute weights/model directory hashes (slow, real I/O)")
    args = parser.parse_args()

    report: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(REPO_ROOT),
        "with_hash": args.with_hash,
        "checkpoints": {},
        "hf_model": None,
        "model_dir_hash": None,
        "wandb_offline_runs_found": None,
    }

    print(f"=== Provenance recon starting: {report['generated_at']} ===")
    print(f"Repo root: {REPO_ROOT}\n")

    for ckpt_id in CHECKPOINT_IDS:
        print(f"--- {ckpt_id} ---")
        facts = recover_checkpoint_facts(ckpt_id, with_hash=args.with_hash)
        report["checkpoints"][ckpt_id] = facts
        n = len(facts.get("checkpoint_dir_candidates", []))
        print(f"  checkpoint dir candidates: {n} -> {facts.get('checkpoint_dir_candidates')}")

    print("\n--- HF model cache ---")
    hf = find_hf_model_snapshots()
    report["hf_model"] = hf
    print(f"  model dirs found: {hf.get('model_dirs_found')}")
    if args.with_hash:
        snaps = hf.get("snapshots", [])
        if len(snaps) == 1 and len(snaps[0]["snapshot_candidates"]) == 1:
            snap_path = Path(snaps[0]["model_dir"]) / "snapshots" / snaps[0]["snapshot_candidates"][0]
            try:
                report["model_dir_hash"] = _try_hash_directory(snap_path)
                print(f"  model_dir_hash: {report['model_dir_hash']}  (computed once, shared by all 4 checkpoints)")
            except Exception as e:
                report["model_dir_hash"] = {"error": f"hash_directory failed: {e}"}
        else:
            report["model_dir_hash"] = "AMBIGUOUS OR NOT FOUND -- see hf_model.snapshots; not hashed automatically"
            print("  model_dir_hash: skipped -- snapshot location is ambiguous or not found, see report")

    print("\n--- WandB offline runs ---")
    wandb_runs = find_wandb_offline_runs()
    report["wandb_offline_runs_found"] = wandb_runs
    print(f"  offline-run directories found: {len(wandb_runs)}")

    print("\n--- Matching WandB candidates to each checkpoint (reporting all matches, choosing none) ---")
    for ckpt_id, facts in report["checkpoints"].items():
        for cand in facts.get("per_candidate", []):
            cfg_json = cand.get("cfg_json", {})
            matches = match_wandb_candidates(cfg_json, wandb_runs)
            cand["wandb_candidate_matches"] = [m["dir"] for m in matches]
            print(f"  {ckpt_id} / {cand['dir']}: {len(matches)} wandb candidate(s) -> {[m['dir'] for m in matches]}")

    REPORT_PATH.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"\n=== Full report written to: {REPORT_PATH} ===")
    print("(This file is NOT part of the registry and was not written into registry/ -- it is raw recon output only.)")


if __name__ == "__main__":
    main()
