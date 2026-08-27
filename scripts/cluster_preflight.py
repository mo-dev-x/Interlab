#!/usr/bin/env python3
"""Cluster-assumption preflight for the SLURM launch path. It FAILS; it never warns.

WHY THIS EXISTS. Every launcher in slurm/ was written against one cluster
(Tamia: aip-chgag196, gpu:h100:4, --mem=0, StdEnv/2023 + python/3.11 +
arrow/25.0.0, ~/sprint-venv, /scratch/y/yazid). Moving to another Alliance
cluster changes the GPU type and count per node, the account, the wall-clock
caps, the module stack and every filesystem root, while leaving the *launcher*
syntactically valid. That is the dangerous shape: a job that runs on the wrong
partition, or against a half-populated weight cache, still exits 0 and still
writes a grid -- a clean-looking null result indistinguishable from a real one.

So this module has exactly two outcomes per check, PASS and FAIL, and exactly
two exit codes, 0 and 1. There is deliberately:

  * no --warn-only, --skip, --allow-missing or --force of any kind (a test
    asserts the parser exposes no such option, so adding one breaks the suite);
  * no severity below FAIL -- ``CheckResult.passed`` is a bool, so a third
    "it's probably fine" state is unrepresentable rather than discouraged;
  * no green path when nothing ran -- an invocation that verifies zero things
    FAILS, because "no checks configured" reads exactly like "all checks
    passed" in a job log, and that confusion is the whole failure mode here;
  * no exception swallowing -- an unexpected error inside a check becomes a
    FAIL for that check, and the run still exits 1.

SECURITY. Token-shaped environment variables are checked by NAME only. No
value is ever read into a message, a report, or a log line: the check reports
"HF_TOKEN is set" and nothing else. Nothing here prints the environment.

PLATFORM. The whole-node CPU check needs os.sched_getaffinity, and the GPU
checks need nvidia-smi. Where those are unavailable (any non-Linux host) the
checks FAIL rather than skip -- this is a cluster preflight, and a green result
from a laptop would be a lie.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

# Token-shaped variables. Checked by name; values are never read.
TOKEN_ENV_NAMES = (
    "HF_TOKEN",
    "HUGGING_FACE_HUB_TOKEN",
    "HUGGINGFACEHUB_API_TOKEN",
)

# Marker files huggingface_hub leaves behind mid-download. Their presence in a
# snapshot tree is the signature of the half-populated cache this preflight
# exists to refuse.
INCOMPLETE_SUFFIXES = (".incomplete", ".lock", ".part", ".tmp")


class PreflightError(Exception):
    """A check could not be evaluated. Always surfaces as a FAIL, never a skip."""


@dataclass(frozen=True)
class CheckResult:
    """One check's outcome. ``passed`` is a bool: there is no third state."""

    name: str
    passed: bool
    detail: str

    def render(self) -> str:
        return f"{'PASS' if self.passed else 'FAIL'}  {self.name}: {self.detail}"


@dataclass
class NodeFacts:
    """Everything read from the live host, gathered once and injected.

    ``None`` means "this host could not tell us", which every consumer treats
    as a FAIL. Tests construct this directly instead of faking a cluster.
    """

    env: Mapping[str, str]
    gpus: tuple[tuple[str, int], ...] | None = None  # (name, total_bytes)
    cpu_affinity: int | None = None
    cpu_total: int | None = None
    mem_total_bytes: int | None = None
    slurm_mem_per_node_bytes: int | None = None
    pyarrow_origin: str | None = None
    sys_prefix: str = ""
    sys_base_prefix: str = ""
    gpu_probe_error: str = ""


def _query_gpus() -> tuple[tuple[tuple[str, int], ...] | None, str]:
    """Read (name, total_bytes) per visible GPU from nvidia-smi."""
    binary = shutil.which("nvidia-smi")
    if binary is None:
        return None, "nvidia-smi is not on PATH"
    try:
        completed = subprocess.run(
            [
                binary,
                "--query-gpu=name,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:  # pragma: no cover - host specific
        return None, f"nvidia-smi could not be executed: {exc.__class__.__name__}"
    if completed.returncode != 0:
        return None, f"nvidia-smi exited {completed.returncode}"
    gpus: list[tuple[str, int]] = []
    for line in completed.stdout.splitlines():
        if not line.strip():
            continue
        name, _, mib = line.partition(",")
        try:
            total = int(float(mib.strip())) * 1024 * 1024
        except ValueError:
            return None, f"nvidia-smi emitted an unparseable memory value: {line.strip()!r}"
        gpus.append((name.strip(), total))
    if not gpus:
        return None, "nvidia-smi reported no GPUs"
    return tuple(gpus), ""


def _read_meminfo_total_bytes() -> int | None:
    try:
        raw = Path("/proc/meminfo").read_bytes().decode("ascii", errors="replace")
    except OSError:
        return None
    for line in raw.splitlines():
        if line.startswith("MemTotal:"):
            parts = line.split()
            if len(parts) >= 2 and parts[1].isdigit():
                return int(parts[1]) * 1024
    return None


def _pyarrow_origin() -> str | None:
    """Where would ``import pyarrow`` come from, without importing it."""
    import importlib.util

    try:
        spec = importlib.util.find_spec("pyarrow")
    except (ImportError, ValueError):  # pragma: no cover - broken sys.path
        return None
    if spec is None:
        return None
    if spec.origin:
        return spec.origin
    locations = list(spec.submodule_search_locations or ())
    return locations[0] if locations else None


def collect_node_facts(env: Mapping[str, str] | None = None) -> NodeFacts:
    """Gather the live host's facts. Never raises; unknowns stay None."""
    environ = dict(os.environ if env is None else env)
    gpus, gpu_error = _query_gpus()
    affinity: int | None = None
    getaffinity = getattr(os, "sched_getaffinity", None)
    if getaffinity is not None:
        try:
            affinity = len(getaffinity(0))
        except OSError:  # pragma: no cover - host specific
            affinity = None
    slurm_mem = environ.get("SLURM_MEM_PER_NODE", "")
    return NodeFacts(
        env=environ,
        gpus=gpus,
        gpu_probe_error=gpu_error,
        cpu_affinity=affinity,
        cpu_total=os.cpu_count(),
        mem_total_bytes=_read_meminfo_total_bytes(),
        slurm_mem_per_node_bytes=int(slurm_mem) * 1024 * 1024 if slurm_mem.isdigit() else None,
        pyarrow_origin=_pyarrow_origin(),
        sys_prefix=sys.prefix,
        sys_base_prefix=sys.base_prefix,
    )


# --------------------------------------------------------------------------
# Checks. Every one is a pure function of injected facts and returns exactly
# one CheckResult. None of them may return "unknown".
# --------------------------------------------------------------------------


def check_inside_allocation(facts: NodeFacts) -> CheckResult:
    job_id = facts.env.get("SLURM_JOB_ID", "")
    if not job_id:
        return CheckResult(
            "inside_allocation",
            False,
            "SLURM_JOB_ID is unset. A login-node run cannot observe the compute node's "
            "GPUs, cgroup CPU set or memory grant, so it cannot verify a single "
            "resource assumption. Run this inside the allocation.",
        )
    return CheckResult("inside_allocation", True, f"SLURM_JOB_ID={job_id}")


def check_gpu_inventory(
    facts: NodeFacts, expected_count: int, min_total_bytes: int
) -> CheckResult:
    if facts.gpus is None:
        return CheckResult(
            "gpu_inventory",
            False,
            f"the GPU inventory could not be read ({facts.gpu_probe_error or 'unknown cause'}). "
            "Refusing to assume the allocation has GPUs.",
        )
    count = len(facts.gpus)
    if count != expected_count:
        names = ", ".join(sorted({name for name, _ in facts.gpus}))
        return CheckResult(
            "gpu_inventory",
            False,
            f"{count} GPU(s) visible ({names}), expected exactly {expected_count}. On a new "
            "cluster this is the wrong --gres/--gpus-per-node type or count for the node, "
            "or a non-whole-node grant.",
        )
    undersized = [(name, total) for name, total in facts.gpus if total < min_total_bytes]
    if undersized:
        name, total = undersized[0]
        return CheckResult(
            "gpu_inventory",
            False,
            f"{name} reports {total} bytes of total memory, below the required "
            f"{min_total_bytes}. The 27B/12B loads and the min-free-VRAM gate in the "
            "matched-configuration job were sized on 80 GB cards.",
        )
    names = ", ".join(sorted({name for name, _ in facts.gpus}))
    return CheckResult("gpu_inventory", True, f"{count} x {names}, all >= {min_total_bytes} bytes")


def check_whole_node_cpu(facts: NodeFacts) -> CheckResult:
    """Whole-node GPU jobs get the whole node's cores; a share means a share."""
    if facts.cpu_affinity is None or facts.cpu_total is None:
        return CheckResult(
            "whole_node_cpu",
            False,
            "the cgroup CPU set could not be read (os.sched_getaffinity is unavailable on "
            "this platform), so whole-node CPU cannot be verified.",
        )
    if facts.cpu_affinity != facts.cpu_total:
        return CheckResult(
            "whole_node_cpu",
            False,
            f"the job may use {facts.cpu_affinity} of the node's {facts.cpu_total} cores. "
            "Whole-node allocation is a standing constraint on every cluster, including "
            "for CPU-bound stages; --cpus-per-task is set for a different node shape.",
        )
    return CheckResult(
        "whole_node_cpu", True, f"all {facts.cpu_total} cores of the node are in the cgroup"
    )


def check_whole_node_memory(facts: NodeFacts, tolerance: float = 0.90) -> CheckResult:
    """``--mem=0`` grants the node's memory; anything materially less is a share."""
    if facts.slurm_mem_per_node_bytes is None:
        return CheckResult(
            "whole_node_memory",
            False,
            "SLURM_MEM_PER_NODE is unset or unparseable, so the memory grant cannot be "
            "compared against the node. --mem=0 must be present in the launcher.",
        )
    if facts.mem_total_bytes is None:
        return CheckResult(
            "whole_node_memory",
            False,
            "/proc/meminfo MemTotal could not be read, so the grant cannot be compared "
            "against the node's real memory.",
        )
    floor = int(facts.mem_total_bytes * tolerance)
    if facts.slurm_mem_per_node_bytes < floor:
        return CheckResult(
            "whole_node_memory",
            False,
            f"the grant is {facts.slurm_mem_per_node_bytes} bytes against a node holding "
            f"{facts.mem_total_bytes}. That is a partial-node grant: --mem=0 is either "
            "missing or overridden.",
        )
    return CheckResult(
        "whole_node_memory",
        True,
        f"grant {facts.slurm_mem_per_node_bytes} bytes vs node {facts.mem_total_bytes}",
    )


def check_modules_loaded(facts: NodeFacts, required: Sequence[str]) -> CheckResult:
    if not required:
        return CheckResult(
            "modules_loaded", False, "no module was required, so nothing about the module stack "
            "was verified. Name every module the payload depends on.",
        )
    raw = facts.env.get("LOADEDMODULES")
    if not raw:
        return CheckResult(
            "modules_loaded",
            False,
            "LOADEDMODULES is unset: no Lmod environment is present in the payload. The "
            "module load must happen inside the job, not only in an interactive shell.",
        )
    loaded = {entry for entry in raw.split(":") if entry}
    missing = [name for name in required if name not in loaded]
    if missing:
        return CheckResult(
            "modules_loaded",
            False,
            f"required module(s) not loaded: {', '.join(missing)}. Version-pinned names are "
            "site-specific -- confirm the exact name this cluster publishes rather than "
            "loading an unpinned alias.",
        )
    return CheckResult("modules_loaded", True, f"loaded: {', '.join(required)}")


def check_venv_active(facts: NodeFacts, venv_dir: Path) -> CheckResult:
    if not facts.sys_prefix or facts.sys_prefix == facts.sys_base_prefix:
        return CheckResult(
            "venv_active", False, "the interpreter is not running inside a virtualenv.",
        )
    active = Path(facts.sys_prefix)
    expected = venv_dir
    try:
        same = active.resolve() == expected.resolve()
    except OSError:  # pragma: no cover - unresolvable path
        same = False
    if not same:
        return CheckResult(
            "venv_active",
            False,
            f"the active environment is {active} but {expected} was required. A second venv "
            "with a different pin set is how two runs stop being comparable.",
        )
    return CheckResult("venv_active", True, f"{active}")


def check_pyarrow_comes_from_the_module(facts: NodeFacts) -> CheckResult:
    """The wheelhouse pyarrow is a stub; only the arrow module provides a real one.

    This is also the ordering check. If the venv is activated BEFORE the arrow
    module is loaded, the stub inside the venv wins the import and this fails --
    which is the only observable difference between the two orderings.
    """
    origin = facts.pyarrow_origin
    if not origin:
        return CheckResult(
            "pyarrow_from_module",
            False,
            "pyarrow is not importable at all. Load the cluster's arrow module; never pip "
            "install pyarrow into the venv.",
        )
    if not facts.sys_prefix:
        return CheckResult(
            "pyarrow_from_module", False, "sys.prefix is unknown, so pyarrow's origin cannot "
            "be compared against the venv.",
        )
    try:
        inside_venv = Path(origin).resolve().is_relative_to(Path(facts.sys_prefix).resolve())
    except OSError:  # pragma: no cover - unresolvable path
        inside_venv = False
    if inside_venv:
        return CheckResult(
            "pyarrow_from_module",
            False,
            f"pyarrow resolves to {origin}, inside the venv. That is the stub wheel, not the "
            "module's build: either the arrow module is not loaded, or it was loaded AFTER "
            "the venv was activated.",
        )
    return CheckResult("pyarrow_from_module", True, f"{origin}")


def check_offline_hf_env(facts: NodeFacts) -> CheckResult:
    offline = facts.env.get("HF_HUB_OFFLINE", "")
    if offline != "1":
        return CheckResult(
            "offline_hf_env",
            False,
            f"HF_HUB_OFFLINE is {offline or 'unset'!r}, not '1'. Compute nodes have no "
            "outbound internet; without this the loader silently attempts a network fetch "
            "and dies deep inside a run instead of here.",
        )
    problems: list[str] = []
    home = facts.env.get("HF_HOME", "")
    cache = facts.env.get("HF_HUB_CACHE", "")
    if not home:
        problems.append("HF_HOME is unset")
    elif not Path(home).is_absolute():
        problems.append(f"HF_HOME is not absolute ({home})")
    elif not Path(home).is_dir():
        problems.append(f"HF_HOME does not exist ({home})")
    if not cache:
        problems.append("HF_HUB_CACHE is unset")
    elif not Path(cache).is_dir():
        problems.append(f"HF_HUB_CACHE does not exist ({cache})")
    elif home and Path(home).is_dir():
        try:
            if not Path(cache).resolve().is_relative_to(Path(home).resolve()):
                problems.append(f"HF_HUB_CACHE {cache} is outside HF_HOME {home}")
        except OSError:  # pragma: no cover - unresolvable path
            problems.append(f"HF_HUB_CACHE {cache} could not be resolved")
    if problems:
        return CheckResult(
            "offline_hf_env",
            False,
            "; ".join(problems)
            + ". Relocating the cache has previously orphaned the credential and turned an "
            "offline run into a 401 an hour in.",
        )
    return CheckResult("offline_hf_env", True, f"HF_HOME={home}, HF_HUB_CACHE={cache}, offline=1")


def check_no_token_in_environment(facts: NodeFacts) -> CheckResult:
    """Reports variable NAMES only. No value is read, formatted or logged."""
    present = [name for name in TOKEN_ENV_NAMES if facts.env.get(name)]
    if present:
        return CheckResult(
            "no_token_in_environment",
            False,
            f"token-shaped variable(s) set in the payload environment: {', '.join(present)}. "
            "Offline runs need no credential, and a shared compute node is the wrong place "
            "to carry one. Put `unset HF_TOKEN` at the top of the payload.",
        )
    return CheckResult(
        "no_token_in_environment", True, f"none of {', '.join(TOKEN_ENV_NAMES)} is set"
    )


def check_scratch_root_writable(root: Path, min_free_bytes: int) -> CheckResult:
    if not root.is_absolute():
        return CheckResult(
            "scratch_root_writable", False, f"{root} is not an absolute path.",
        )
    if not root.is_dir():
        return CheckResult(
            "scratch_root_writable",
            False,
            f"{root} does not exist or is not a directory. Every output path in "
            "configs/final_pairing/*.json is rooted here; a missing root means the run "
            "writes nowhere.",
        )
    probe = root / f".cluster_preflight_probe_{os.getpid()}"
    payload = b"cluster-preflight-write-probe\n"
    try:
        with probe.open("wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        read_back = probe.read_bytes()
    except OSError as exc:
        return CheckResult(
            "scratch_root_writable",
            False,
            f"{root} is not writable from this node ({exc.__class__.__name__}).",
        )
    finally:
        with contextlib.suppress(OSError):
            probe.unlink()
    if read_back != payload:
        return CheckResult(
            "scratch_root_writable", False, f"a write probe under {root} did not read back "
            "identical bytes.",
        )
    try:
        free = shutil.disk_usage(root).free
    except OSError as exc:  # pragma: no cover - host specific
        return CheckResult(
            "scratch_root_writable",
            False,
            f"free space under {root} could not be read ({exc.__class__.__name__}).",
        )
    if free < min_free_bytes:
        return CheckResult(
            "scratch_root_writable",
            False,
            f"{free} bytes free under {root}, below the required {min_free_bytes}. Space, not "
            "purge, has been this project's binding storage constraint.",
        )
    return CheckResult("scratch_root_writable", True, f"{root} writable, {free} bytes free")


def _walk_files(root: Path) -> Iterable[Path]:
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            yield Path(dirpath) / name


def check_snapshot_complete(root: Path) -> CheckResult:
    """A snapshot directory that is present but half-populated is the worst case."""
    name = f"snapshot_complete[{root.name}]"
    if not root.is_absolute():
        return CheckResult(
            name,
            False,
            f"{root} is not an absolute path. A repository id where a local snapshot path is "
            "required is a network fetch waiting to happen.",
        )
    if not root.is_dir():
        return CheckResult(name, False, f"{root} does not exist or is not a directory.")
    files = list(_walk_files(root))
    if not files:
        return CheckResult(name, False, f"{root} contains no files.")
    partial = [str(path) for path in files if path.name.endswith(INCOMPLETE_SUFFIXES)]
    if partial:
        return CheckResult(
            name,
            False,
            f"{len(partial)} in-progress download marker(s) under {root}, first {partial[0]}. "
            "The snapshot is mid-transfer.",
        )
    broken = [str(path) for path in files if path.is_symlink() and not path.exists()]
    if broken:
        return CheckResult(
            name,
            False,
            f"{len(broken)} dangling symlink(s) under {root}, first {broken[0]}. The cache "
            "index survived but its blobs did not.",
        )
    empty = [str(path) for path in files if path.stat().st_size == 0]
    if empty:
        return CheckResult(
            name, False, f"{len(empty)} zero-byte file(s) under {root}, first {empty[0]}.",
        )
    return CheckResult(name, True, f"{len(files)} files under {root}, none partial")


def check_shard_index_complete(index_path: Path) -> CheckResult:
    """Every shard a weight index names must be present next to it."""
    name = f"shard_index_complete[{index_path.name}]"
    if not index_path.is_file():
        return CheckResult(name, False, f"{index_path} does not exist.")
    try:
        document = json.loads(index_path.read_bytes().decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return CheckResult(name, False, f"{index_path} is unreadable ({exc.__class__.__name__}).")
    weight_map = document.get("weight_map")
    if not isinstance(weight_map, dict) or not weight_map:
        return CheckResult(
            name, False, f"{index_path} carries no weight_map, so shard completeness cannot "
            "be established.",
        )
    shards = sorted(set(weight_map.values()))
    missing = [shard for shard in shards if not (index_path.parent / shard).exists()]
    if missing:
        return CheckResult(
            name,
            False,
            f"{len(missing)} of {len(shards)} shard(s) named by the index are absent, first "
            f"{missing[0]}. A partial shard set loads far enough to produce numbers.",
        )
    hollow = [
        shard
        for shard in shards
        if (index_path.parent / shard).exists()
        and (index_path.parent / shard).stat().st_size == 0
    ]
    if hollow:
        return CheckResult(name, False, f"shard(s) present but zero-byte, first {hollow[0]}.")
    return CheckResult(name, True, f"all {len(shards)} shard(s) present and non-empty")


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def normalise_digest(raw: str) -> str:
    """Accept both bare hex and the ``sha256:``-prefixed form the protocols use."""
    value = raw.strip().lower()
    if value.startswith("sha256:"):
        value = value[len("sha256:") :]
    return value


def check_file_digest(path: Path, expected: str) -> CheckResult:
    name = f"file_digest[{path.name}]"
    wanted = normalise_digest(expected)
    if len(wanted) != 64 or any(character not in "0123456789abcdef" for character in wanted):
        return CheckResult(name, False, f"the expected digest for {path} is not 64 hex chars.")
    if not path.is_file():
        return CheckResult(name, False, f"{path} does not exist.")
    try:
        actual = sha256_of(path)
    except OSError as exc:
        return CheckResult(name, False, f"{path} could not be read ({exc.__class__.__name__}).")
    if actual != wanted:
        return CheckResult(
            name,
            False,
            f"{path} hashes to {actual}, expected {wanted}. The recorded revision attests what "
            "was fetched, never what is on disk now: this is a hard stop, not a retry.",
        )
    return CheckResult(name, True, f"{path} matches {wanted}")


def extract_protocol_digests(document: Mapping[str, object]) -> tuple[tuple[str, str], ...]:
    """Pull (relative path, sha256) pairs out of a frozen identity protocol.

    Handles both shapes this repository froze: the Gemma artifact's
    ``runtime_loading.expected_params_sha256.<CONFIG>.{path,sha256}`` and the
    Qwen artifact's ``configurations.<CONFIG>.{params_file,
    params_expected_sha256}``. Returns them in a stable order. An empty result
    is never silently acceptable -- the caller turns it into a FAIL.
    """
    pairs: list[tuple[str, str]] = []
    runtime = document.get("runtime_loading")
    if isinstance(runtime, dict):
        expected = runtime.get("expected_params_sha256")
        if isinstance(expected, dict):
            for _config, entry in sorted(expected.items()):
                if isinstance(entry, dict):
                    path = entry.get("path")
                    digest = entry.get("sha256")
                    if isinstance(path, str) and isinstance(digest, str):
                        pairs.append((path, normalise_digest(digest)))
    configurations = document.get("configurations")
    if isinstance(configurations, dict):
        for _config, entry in sorted(configurations.items()):
            if not isinstance(entry, dict):
                continue
            path = entry.get("params_file")
            digest = entry.get("params_expected_sha256")
            if isinstance(path, str) and isinstance(digest, str):
                pairs.append((path, normalise_digest(digest)))
    return tuple(dict.fromkeys(pairs))


def checks_from_identity_protocol(protocol_path: Path, snapshot_root: Path) -> list[CheckResult]:
    """Digest-check whichever params files the frozen protocol names, if present.

    The protocol names both configurations; only the one staged under this
    snapshot root can be checked here, so an absent path is reported as a
    FAIL only when the protocol names it AND nothing under the root matches --
    see the caller. A protocol yielding zero pairs is always a FAIL.
    """
    label = f"protocol_digests[{protocol_path.name}]"
    try:
        document = json.loads(protocol_path.read_bytes().decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return [CheckResult(label, False, f"{protocol_path} is unreadable ({exc.__class__.__name__}).")]
    if not isinstance(document, dict):
        return [CheckResult(label, False, f"{protocol_path} is not a JSON object.")]
    pairs = extract_protocol_digests(document)
    if not pairs:
        return [
            CheckResult(
                label,
                False,
                f"{protocol_path} yielded no (path, sha256) pair. Either the artifact shape "
                "changed or the wrong file was passed; either way nothing was verified.",
            )
        ]
    present = [(relative, digest) for relative, digest in pairs if (snapshot_root / relative).is_file()]
    if not present:
        named = ", ".join(relative for relative, _ in pairs)
        return [
            CheckResult(
                label,
                False,
                f"none of the params files {protocol_path.name} names ({named}) exists under "
                f"{snapshot_root}. The SAE weights for this configuration are not staged.",
            )
        ]
    results = [CheckResult(label, True, f"{len(present)} of {len(pairs)} named file(s) staged")]
    results.extend(
        check_file_digest(snapshot_root / relative, digest) for relative, digest in present
    )
    return results


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


@dataclass
class Plan:
    """Everything the operator asked to have verified."""

    expected_gpu_count: int
    min_gpu_total_bytes: int
    venv_dir: Path
    scratch_root: Path
    min_free_scratch_bytes: int
    require_modules: list[str] = field(default_factory=list)
    require_snapshots: list[Path] = field(default_factory=list)
    require_shard_indexes: list[Path] = field(default_factory=list)
    require_digests: list[tuple[Path, str]] = field(default_factory=list)
    identity_protocols: list[tuple[Path, Path]] = field(default_factory=list)


def _parse_digest_argument(raw: str) -> tuple[Path, str]:
    path, separator, digest = raw.rpartition("=")
    if not separator or not path or not digest:
        raise argparse.ArgumentTypeError(
            f"expected PATH=SHA256HEX, got {raw!r}",
        )
    return Path(path), digest


def _parse_protocol_argument(raw: str) -> tuple[Path, Path]:
    protocol, separator, root = raw.partition("=")
    if not separator or not protocol or not root:
        raise argparse.ArgumentTypeError(
            f"expected PROTOCOL_JSON=SNAPSHOT_ROOT, got {raw!r}",
        )
    return Path(protocol), Path(root)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cluster_preflight.py",
        description=(
            "Refuse to start when a cluster assumption is unmet. There is no option to "
            "downgrade any finding to a warning, and none will be added."
        ),
    )
    parser.add_argument("--expected-gpu-count", type=int, required=True)
    parser.add_argument("--min-gpu-total-bytes", type=int, required=True)
    parser.add_argument("--venv-dir", type=Path, required=True)
    parser.add_argument("--scratch-root", type=Path, required=True)
    parser.add_argument("--min-free-scratch-bytes", type=int, required=True)
    parser.add_argument("--require-module", action="append", default=[], metavar="NAME/VERSION")
    parser.add_argument("--require-snapshot", action="append", default=[], type=Path)
    parser.add_argument("--require-shard-index", action="append", default=[], type=Path)
    parser.add_argument(
        "--require-digest", action="append", default=[], type=_parse_digest_argument,
        metavar="PATH=SHA256HEX",
    )
    parser.add_argument(
        "--identity-protocol", action="append", default=[], type=_parse_protocol_argument,
        metavar="PROTOCOL_JSON=SNAPSHOT_ROOT",
    )
    parser.add_argument(
        "--report", type=Path, default=None,
        help="write the machine-readable result here (never contains an environment value)",
    )
    return parser


def plan_from_args(args: argparse.Namespace) -> Plan:
    return Plan(
        expected_gpu_count=args.expected_gpu_count,
        min_gpu_total_bytes=args.min_gpu_total_bytes,
        venv_dir=args.venv_dir,
        scratch_root=args.scratch_root,
        min_free_scratch_bytes=args.min_free_scratch_bytes,
        require_modules=list(args.require_module),
        require_snapshots=list(args.require_snapshot),
        require_shard_indexes=list(args.require_shard_index),
        require_digests=list(args.require_digest),
        identity_protocols=list(args.identity_protocol),
    )


def _guarded(name: str, thunk: Callable[[], list[CheckResult]]) -> list[CheckResult]:
    try:
        return thunk()
    # A broad except is deliberate: an unexpected error is a FAIL, never a skip.
    except Exception as exc:
        return [
            CheckResult(
                name, False, f"the check itself raised {exc.__class__.__name__}: {exc}. An "
                "unevaluated assumption is treated as an unmet one.",
            )
        ]


def run_checks(plan: Plan, facts: NodeFacts) -> list[CheckResult]:
    results: list[CheckResult] = []
    results.extend(_guarded("inside_allocation", lambda: [check_inside_allocation(facts)]))
    results.extend(
        _guarded(
            "gpu_inventory",
            lambda: [
                check_gpu_inventory(facts, plan.expected_gpu_count, plan.min_gpu_total_bytes)
            ],
        )
    )
    results.extend(_guarded("whole_node_cpu", lambda: [check_whole_node_cpu(facts)]))
    results.extend(_guarded("whole_node_memory", lambda: [check_whole_node_memory(facts)]))
    results.extend(
        _guarded("modules_loaded", lambda: [check_modules_loaded(facts, plan.require_modules)])
    )
    results.extend(_guarded("venv_active", lambda: [check_venv_active(facts, plan.venv_dir)]))
    results.extend(
        _guarded("pyarrow_from_module", lambda: [check_pyarrow_comes_from_the_module(facts)])
    )
    results.extend(_guarded("offline_hf_env", lambda: [check_offline_hf_env(facts)]))
    results.extend(
        _guarded("no_token_in_environment", lambda: [check_no_token_in_environment(facts)])
    )
    results.extend(
        _guarded(
            "scratch_root_writable",
            lambda: [
                check_scratch_root_writable(plan.scratch_root, plan.min_free_scratch_bytes)
            ],
        )
    )
    for snapshot in plan.require_snapshots:
        results.extend(
            _guarded(
                f"snapshot_complete[{snapshot.name}]",
                lambda snapshot=snapshot: [check_snapshot_complete(snapshot)],
            )
        )
    for index in plan.require_shard_indexes:
        results.extend(
            _guarded(
                f"shard_index_complete[{index.name}]",
                lambda index=index: [check_shard_index_complete(index)],
            )
        )
    for path, digest in plan.require_digests:
        results.extend(
            _guarded(
                f"file_digest[{path.name}]",
                lambda path=path, digest=digest: [check_file_digest(path, digest)],
            )
        )
    for protocol, root in plan.identity_protocols:
        results.extend(
            _guarded(
                f"protocol_digests[{protocol.name}]",
                lambda protocol=protocol, root=root: checks_from_identity_protocol(protocol, root),
            )
        )
    return results


def summarise(results: Sequence[CheckResult]) -> tuple[int, str]:
    """Return (exit code, rendered report). Zero checks is a FAIL, not a pass."""
    lines = [result.render() for result in results]
    if not results:
        lines.append(
            "FAIL  preflight_ran: no check was configured. An invocation that verifies "
            "nothing must not read as green."
        )
        return 1, "\n".join(lines)
    failed = [result for result in results if not result.passed]
    if failed:
        lines.append("")
        lines.append(
            f"PREFLIGHT FAILED: {len(failed)} of {len(results)} checks. Refusing to launch. "
            "Unmet cluster assumptions produce results that look clean and are not."
        )
        return 1, "\n".join(lines)
    lines.append("")
    lines.append(f"PREFLIGHT PASSED: {len(results)} checks.")
    return 0, "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    plan = plan_from_args(args)
    facts = collect_node_facts()
    results = run_checks(plan, facts)
    code, rendered = summarise(results)
    print(rendered)
    if args.report is not None:
        payload = {
            "exit_code": code,
            "checks": [
                {"name": result.name, "passed": result.passed, "detail": result.detail}
                for result in results
            ],
        }
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_bytes((json.dumps(payload, indent=2, sort_keys=True) + "\n").encode())
    return code


if __name__ == "__main__":
    raise SystemExit(main())
