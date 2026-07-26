"""SS5 `FeatureIndex`: the frozen search API, one of the lab's two live
interfaces (§5.SS5). Index is write-once, content-addressed (D1).

Degraded local operation (§5.SS5 failure mode): `.open()` works against a
synced *columnar subset* (`per_feature_stats.json`) with `examples/`
absent -- `.feature(i)`'s example lists are then empty and
`examples_available` is `False`, never a crash. `corpus_max`, `firing_rate`,
`search_by_cosine`, and `search_by_label` are all columnar-only and work
identically in degraded mode; only per-feature example text needs the
(cluster-only) example shards.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import numpy as np

from interplab.core import hashing, uris
from interplab.registry.registry import REGISTRY_ROOT
from interplab.registry.registry import get as registry_get

PathOrHash = str | Path


class MatchedSampleError(Exception):
    """`sample_matched_frequency`: the multiply/divide-by-band frequency
    window contains no eligible feature. Callers MUST NOT silently widen
    the band -- an empty band is a finding about the target feature, not a
    bug to work around."""


@dataclasses.dataclass(frozen=True)
class FeatureView:
    feature_index: int
    corpus_max: float
    firing_rate: float
    decile_boundaries: list[float]
    activation_histogram: dict
    logit_top_tokens: list[str]
    autointerp_label: str | None
    autointerp_detection_score: float | None
    chat_slice_max: float | None
    chat_slice_firing_rate: float | None
    top_k_examples: list[dict]
    decile_examples: dict[int, list[dict]]
    examples_available: bool


@dataclasses.dataclass(frozen=True)
class Hit:
    feature_index: int
    score: float


def _resolve_index_dir(manifest: PathOrHash, *, registry_root: Path) -> Path:
    """`manifest` is a `PathOrHash`: a local directory path (degraded/local
    use, no registry lookup needed) or a `sha256:...` content hash of the
    A7 `characterization_manifest`, resolved via its `subject` role="index"
    entry."""
    candidate = Path(manifest)
    if candidate.is_dir():
        return candidate

    manifest_str = str(manifest)
    if manifest_str.startswith(hashing.SHA256_PREFIX):
        artifact = registry_get(manifest_str, registry_root=registry_root)
        for ref in artifact["subject"]:
            if ref["role"] == "index":
                parsed = uris.parse(ref["location"])
                if parsed.scheme == "local":
                    return uris.resolve_local(ref["location"])
                if parsed.scheme == "tamia":
                    return uris.resolve_tamia(ref["location"])
                raise NotImplementedError(
                    f"FeatureIndex.open can only resolve local:/tamia: index locations; "
                    f"got {ref['location']!r}"
                )
        raise ValueError(f"characterization_manifest {manifest_str!r} has no subject entry with role 'index'")

    raise ValueError(f"not a directory and not a sha256: hash: {manifest!r}")


class FeatureIndex:
    def __init__(self, index_dir: Path, columnar: dict):
        self._index_dir = index_dir
        self._columnar = columnar
        self._features = {f["feature_index"]: f for f in columnar["features"]}
        self._examples_available = (index_dir / "examples").is_dir()
        self._model = None
        self._sae = None

    @classmethod
    def open(cls, manifest: PathOrHash, *, registry_root: Path = REGISTRY_ROOT) -> FeatureIndex:
        index_dir = _resolve_index_dir(manifest, registry_root=registry_root)
        stats_path = index_dir / "per_feature_stats.json"
        columnar = json.loads(stats_path.read_text(encoding="utf-8"))
        return cls(index_dir, columnar)

    @property
    def n_features(self) -> int:
        return self._columnar["n_features"]

    def _row(self, i: int) -> dict:
        if i not in self._features:
            raise KeyError(f"no feature {i} in this index (n_features={self.n_features})")
        return self._features[i]

    def _load_examples(self, i: int) -> list[dict]:
        if not self._examples_available:
            return []
        path = self._index_dir / "examples" / f"{i}.jsonl"
        if not path.is_file():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]

    def feature(self, i: int) -> FeatureView:
        row = self._row(i)
        examples = self._load_examples(i)
        top_k = [e for e in examples if e.get("decile") == "top_k"]
        deciles: dict[int, list[dict]] = {}
        for e in examples:
            if e.get("decile") != "top_k":
                deciles.setdefault(e["decile"], []).append(e)

        return FeatureView(
            feature_index=i,
            corpus_max=row["corpus_max"],
            firing_rate=row["firing_rate"],
            decile_boundaries=row["decile_boundaries"],
            activation_histogram=row["activation_histogram"],
            logit_top_tokens=row["logit_top_tokens"],
            autointerp_label=row["autointerp_label"],
            autointerp_detection_score=row["autointerp_detection_score"],
            chat_slice_max=row["chat_slice_max"],
            chat_slice_firing_rate=row["chat_slice_firing_rate"],
            top_k_examples=top_k,
            decile_examples=deciles,
            examples_available=self._examples_available,
        )

    def corpus_max(self, i: int) -> float:
        return self._row(i)["corpus_max"]

    def firing_rate(self, i: int) -> float:
        return self._row(i)["firing_rate"]

    def _load_model_and_sae(self):
        if self._model is not None:
            return self._model, self._sae

        from sae_lens import SAE

        from interplab.characterization.model_loading import (
            load_local_hooked_transformer,
            resolve_model_location,
        )

        weights_location = self._columnar["weights_location"]
        model_location = self._columnar["model_location"]
        weights_scheme = uris.parse(weights_location).scheme
        if weights_scheme == "local":
            weights_path = uris.resolve_local(weights_location)
        elif weights_scheme == "tamia":
            weights_path = uris.resolve_tamia(weights_location)
        else:
            raise NotImplementedError(
                f"search_by_activation can only lazily load SAE weights from local:/tamia: URIs; "
                f"got {weights_location!r}"
            )
        self._sae = SAE.load_from_pretrained(str(weights_path), device="cpu")
        self._model = load_local_hooked_transformer(str(resolve_model_location(model_location)))
        return self._model, self._sae

    def search_by_activation(self, texts: list[str], top_n: int) -> list[Hit]:
        """Runs a live model+SAE forward pass over `texts` (the model+SAE
        are lazily loaded from the locations recorded in this index's
        columnar subset at indexing time) and ranks features by their max
        activation across all given texts -- this is the one method that
        cannot work from columnar data alone, since it scores *new* text,
        not anything already in the index."""
        import torch

        model, sae = self._load_model_and_sae()
        hook_name = self._columnar["hook_name"]
        max_activation = np.zeros(self.n_features, dtype=np.float64)

        with torch.no_grad():
            for text in texts:
                tokens = model.to_tokens(text)
                _, cache = model.run_with_cache(tokens, names_filter=hook_name)
                feats = sae.encode(cache[hook_name].to(torch.float32))[0]  # [seq, d_sae]
                per_text_max = feats.max(dim=0).values.numpy()
                max_activation = np.maximum(max_activation, per_text_max)

        hits = [Hit(feature_index=i, score=float(max_activation[i])) for i in range(self.n_features)]
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:top_n]

    def search_by_cosine(self, seed_index: int, top_n: int) -> list[Hit]:
        seed_dir = np.array(self._row(seed_index)["decoder_direction"], dtype=np.float64)
        hits = []
        for i, row in self._features.items():
            if i == seed_index:
                continue
            other_dir = np.array(row["decoder_direction"], dtype=np.float64)
            score = float(np.dot(seed_dir, other_dir))
            hits.append(Hit(feature_index=i, score=score))
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:top_n]

    def search_by_label(self, query: str, top_n: int) -> list[Hit]:
        query_lower = query.lower()
        hits = []
        for i, row in self._features.items():
            label = row.get("autointerp_label")
            if label and query_lower in label.lower():
                hits.append(Hit(feature_index=i, score=row.get("autointerp_detection_score") or 0.0))
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:top_n]

    def sample_matched_frequency(
        self,
        target_index: int,
        *,
        rng_seed: int,
        band: float = 3.0,
        exclude: frozenset[int] = frozenset(),
    ) -> int:
        target_rate = self.firing_rate(target_index)
        lo, hi = target_rate / band, target_rate * band
        excluded = {target_index} | set(exclude)
        eligible = sorted(
            i for i, row in self._features.items()
            if i not in excluded and lo <= row["firing_rate"] <= hi
        )
        if not eligible:
            raise MatchedSampleError(
                f"no feature within band={band} of firing_rate={target_rate!r} for target_index="
                f"{target_index} (window [{lo!r}, {hi!r}], excluding {sorted(excluded)})"
            )
        rng = np.random.default_rng(rng_seed)
        return int(eligible[int(rng.integers(0, len(eligible)))])
