"""§8.2 test_import_contracts: dependency edges of §1 enforced via AST walk.

Checks every subsystem package that currently exists under interplab/
against §1's allowed-edges table, so the contract stays enforced as later
work packages add packages -- nobody has to remember to extend this test.

`interplab.jobs.*` has its own per-stage rule (§1: "jobs.<stage> -> core,
registry, + that stage's package only"), checked separately below since it
isn't a flat allowed-set like the other packages -- each job module gets
its own extra package. `scripts/*` isn't Python-importable code under
`interplab/` and has no packages of its own to check here.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

INTERPLAB_ROOT = Path(__file__).resolve().parents[1] / "interplab"

ALLOWED_EDGES: dict[str, set[str]] = {
    "core": set(),
    "stats": {"core"},
    "interventions": {"core"},
    "registry": {"core"},
    "corpus": {"core", "registry"},
    "store_qa": {"core", "registry"},
    "training": {"core", "registry"},
    "certification": {"core", "registry"},
    "characterization": {"core", "registry"},
    "validation": {"core", "registry", "characterization", "stats"},
    "evaluation": {"core", "registry", "stats"},
    "reports": {"core", "registry", "stats"},
}

# §1: jobs.<stage> -> core, registry, + that stage's package only (plus the
# named exceptions for jobs.steer and jobs.validate). Keyed by job module
# name (interplab/jobs/<name>.py); pre-populated for present and future job
# names alike, same style as ALLOWED_EDGES above -- harmless since the
# checker only iterates modules that actually exist.
JOBS_ALLOWED_EDGES: dict[str, set[str]] = {
    "census": {"corpus"},
    "store_qa": {"store_qa"},
    "train": {"training"},
    "certify": {"certification"},
    "characterize": {"characterization"},
    "validate": {"validation"},
    "steer": {"interventions", "characterization"},
    "judge": {"evaluation"},
    "report": {"reports"},
    "sync_registry": set(),
    # ED-5: not one of §6.1's named jobs, emits A5 (nominally SS3's
    # artifact) without needing the (not-yet-built) training package.
    "backfill_checkpoint": {"training"},
}


def _interplab_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "interplab" or alias.name.startswith("interplab."):
                    modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module and (
            node.module == "interplab" or node.module.startswith("interplab.")
        ):
            modules.add(node.module)
    return modules


def _top_level_subpackage(module: str) -> str | None:
    parts = module.split(".")
    if len(parts) < 2:
        return None  # bare "import interplab" -- no specific subsystem named
    return parts[1]


def _interplab_qualified_imports(path: Path) -> set[str]:
    """Like `_interplab_imports`, but also resolves `ImportFrom`'s imported
    names as qualified submodule paths (e.g. `from interplab.characterization
    import model_loading` -> `interplab.characterization.model_loading`), not
    just the `from` module. Needed for the qualified-edge check below, which
    must not be foolable by importing a disallowed submodule this way.

    Only expands one level (`interplab.<pkg>` -> `interplab.<pkg>.<name>`):
    every subsystem package in this repo is flat (no nested sub-packages), so
    an `ImportFrom` whose module already has 2+ dots (e.g.
    `interplab.characterization.feature_index`) is importing an *attribute*
    of that module (a class/function), not a further submodule -- expanding
    those too would produce false positives like
    `interplab.characterization.feature_index.FeatureIndex`.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "interplab" or alias.name.startswith("interplab."):
                    modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module and (
            node.module == "interplab" or node.module.startswith("interplab.")
        ):
            modules.add(node.module)
            if node.module.count(".") <= 1:
                for alias in node.names:
                    modules.add(f"{node.module}.{alias.name}")
    return modules


def _existing_subsystem_packages() -> list[str]:
    return [
        p.name
        for p in INTERPLAB_ROOT.iterdir()
        if p.is_dir() and (p / "__init__.py").is_file() and p.name != "jobs"
    ]


def test_no_disallowed_cross_subsystem_imports():
    violations = []
    for package_name in _existing_subsystem_packages():
        if package_name not in ALLOWED_EDGES:
            continue  # unlisted package: no rule authored for it yet
        allowed = ALLOWED_EDGES[package_name] | {package_name}
        package_dir = INTERPLAB_ROOT / package_name
        for py_file in package_dir.rglob("*.py"):
            for module in _interplab_imports(py_file):
                other = _top_level_subpackage(module)
                if other is not None and other not in allowed:
                    violations.append(
                        f"{py_file}: imports {module!r}, not in allowed set {sorted(allowed)}"
                    )
    assert not violations, "\n".join(violations)


def _existing_job_modules() -> list[Path]:
    jobs_dir = INTERPLAB_ROOT / "jobs"
    if not jobs_dir.is_dir():
        return []
    return [p for p in jobs_dir.glob("*.py") if p.stem != "__init__"]


def test_jobs_imports_respect_per_stage_edges():
    violations = []
    for py_file in _existing_job_modules():
        job_name = py_file.stem
        allowed = {"core", "registry"} | JOBS_ALLOWED_EDGES.get(job_name, set())
        for module in _interplab_imports(py_file):
            other = _top_level_subpackage(module)
            if other is not None and other not in allowed:
                violations.append(
                    f"{py_file}: imports {module!r}, not in allowed set {sorted(allowed)}"
                )
    assert not violations, "\n".join(violations)


def _py_files_under(target: Path) -> list[Path]:
    """`target` may be a package directory or a single job module file.
    Empty (not an error) if the module/package doesn't exist yet -- same
    pre-population style as `JOBS_ALLOWED_EDGES` above: harmless, since
    there's nothing to scan until the file lands."""
    if target.is_dir():
        return list(target.rglob("*.py"))
    if target.is_file():
        return [target]
    return []


# §1 SEARCH API ONLY edges: some allowed-package edges are further
# restricted to one frozen qualified module, not the whole target package
# -- checked at qualified-module granularity, since `ALLOWED_EDGES` /
# `JOBS_ALLOWED_EDGES` above only see package-level granularity.
# `interplab.characterization.feature_index` (the frozen `FeatureIndex`
# interface) is the only module either edge may reach -- never
# `model_loading` or any other characterization-internal module.
#
# WP5 established this for `validation -> characterization`; WP7 extends
# the same mechanism to `jobs.steer -> characterization` (§1: "jobs.steer
# -> also interventions AND characterization [SEARCH API ONLY ...]").
# `jobs/steer.py` now exists, so this edge is exercised on every run of this
# test without any special-case wiring.
SEARCH_API_ONLY_EDGES: list[tuple[str, Path, str, frozenset[str]]] = [
    (
        "validation -> characterization",
        INTERPLAB_ROOT / "validation",
        "characterization",
        frozenset({"interplab.characterization.feature_index"}),
    ),
    (
        "jobs.steer -> characterization",
        INTERPLAB_ROOT / "jobs" / "steer.py",
        "characterization",
        frozenset({"interplab.characterization.feature_index"}),
    ),
]


@pytest.mark.parametrize(
    "target,restricted_package,allowed",
    [entry[1:] for entry in SEARCH_API_ONLY_EDGES],
    ids=[entry[0] for entry in SEARCH_API_ONLY_EDGES],
)
def test_search_api_only_edges_are_qualified_to_frozen_modules(target, restricted_package, allowed):
    violations = []
    for py_file in _py_files_under(target):
        for module in _interplab_qualified_imports(py_file):
            if _top_level_subpackage(module) != restricted_package:
                continue
            if module not in allowed:
                violations.append(f"{py_file}: imports {module!r}, not in allowed set {sorted(allowed)}")
    assert not violations, "\n".join(violations)


def _lodestar_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "lodestar" or alias.name.startswith("lodestar."):
                    modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module and (
            node.module == "lodestar" or node.module.startswith("lodestar.")
        ):
            modules.add(node.module)
    return modules


def _stdlib_or_builtin_top_level_names() -> set[str]:
    stdlib = set(getattr(__import__("sys"), "stdlib_module_names", ()))
    return stdlib | {"__future__"}


def _top_level_import_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_only_evaluation_imports_lodestar():
    """§1: "Lodestar remains a separate installable package (lodestar-eval);
    only interplab.evaluation may import it." Scans every .py file under
    interplab/ outside interplab/evaluation/ for any `lodestar` import."""
    violations = []
    for py_file in INTERPLAB_ROOT.rglob("*.py"):
        if py_file.is_relative_to(INTERPLAB_ROOT / "evaluation"):
            continue
        for module in _lodestar_imports(py_file):
            violations.append(f"{py_file}: imports {module!r} -- only interplab.evaluation may import lodestar")
    assert not violations, "\n".join(violations)


def test_thin_cli_wrappers_only_import_stdlib_and_their_job_module():
    """§6.1 / README wrapper contract: each public CLI wrapper under
    scripts/ is thin arg-parse -> interplab.jobs.<stage>, with no extra
    interplab dependencies hidden in the script layer itself."""
    wrappers = [
        "backfill_checkpoint",
        "census",
        "certify",
        "characterize",
        "judge",
        "report",
        "steer",
        "store_qa",
        "sync_registry",
        "validate",
    ]
    allowed_stdlib = _stdlib_or_builtin_top_level_names()
    violations = []
    scripts_dir = INTERPLAB_ROOT.parents[0] / "scripts"
    for wrapper in wrappers:
        path = scripts_dir / f"{wrapper}.py"
        imports = _top_level_import_names(path)
        expected_job_import = "interplab.jobs"
        for name in imports:
            top = name.split(".", 1)[0]
            if top == "interplab":
                if name != expected_job_import:
                    violations.append(
                        f"{path}: imports {name!r}; wrappers may only import {expected_job_import!r} from interplab"
                    )
                continue
            if top not in allowed_stdlib:
                violations.append(f"{path}: imports non-stdlib module {name!r}")
    assert not violations, "\n".join(violations)


def test_core_has_zero_interplab_dependencies():
    core_dir = INTERPLAB_ROOT / "core"
    violations = []
    for py_file in core_dir.rglob("*.py"):
        for module in _interplab_imports(py_file):
            other = _top_level_subpackage(module)
            if other is not None and other != "core":
                violations.append(f"{py_file}: {module}")
    assert not violations, "core MUST NOT import any other subsystem package: " + "; ".join(violations)
