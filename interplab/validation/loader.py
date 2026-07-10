"""SS6's own boundary onto SS5: `jobs.validate` may only import `core`,
`registry`, and `validation` (§1) -- it may not import `characterization`
directly. This module is the sole point where `interplab.validation`
reaches into characterization's frozen public interface -- and per §1 that
interface is the SEARCH API ONLY, i.e. exactly `FeatureIndex`
(`interplab.characterization.feature_index`), not characterization's
internal implementation modules. Model loading is not part of that
interface, so it is *not* imported from `characterization` here; it is
`interplab.validation.model_loading`, a local duplicate (Ground Rule 2 --
see that module's docstring). Every other `validation` module stays within
the "search API only" boundary via objects handed to it from here, never a
direct import of its own.
"""

from __future__ import annotations

from pathlib import Path

from interplab.characterization.feature_index import FeatureIndex
from interplab.registry.registry import REGISTRY_ROOT
from interplab.validation.model_loading import load_local_hooked_transformer


def open_feature_index(manifest: str, *, registry_root: Path = REGISTRY_ROOT) -> FeatureIndex:
    return FeatureIndex.open(manifest, registry_root=registry_root)


def load_model(model_dir: str):
    return load_local_hooked_transformer(model_dir)
