"""interplab.corpus.battery (SS1, A2) -- loads and validates the
ConceptBattery from `data/concepts/`.

A2 is not an envelope artifact (schemas/concept_battery/v1.schema.json's own
docstring, and its absence from §3.4's registry tree): there is no
`registry.put()` here. Its identity is `core.hashing.hash_battery` (a
directory content hash over `data/concepts/`), consumed by other artifacts'
`subject` entries as `{content_hash: hash_battery(...), location:
"local:data/concepts", role: "concept_battery"}`.

ED-8 authorship policy: this module only *loads* and *validates* whatever
battery content already exists on disk. It has no code path that generates,
translates, or otherwise authors probes/negatives/relationships -- that is
the researcher's exclusive responsibility (`data/concepts/*.yaml`,
`data/concepts/extract_from_find_features.py` for provenance).
"""

from __future__ import annotations

from pathlib import Path

import yaml

from interplab.core import hashing
from interplab.core._schema_registry import SCHEMAS_ROOT
from interplab.core._schema_registry import validate as validate_against_schema

CONCEPT_BATTERY_SCHEMA = SCHEMAS_ROOT / "concept_battery" / "v1.schema.json"

_NON_CONCEPT_FILES = {"battery.yaml", "extract_from_find_features.py"}


def load_battery(concepts_dir: str | Path) -> dict[str, dict]:
    """Loads + schema-validates every `<concept_id>.yaml` under
    `concepts_dir`, keyed by `concept_id`. Raises on the first invalid file
    (Ground Rule 1: schema is the law)."""
    root = Path(concepts_dir)
    concepts: dict[str, dict] = {}
    for path in sorted(root.glob("*.yaml")):
        if path.name in _NON_CONCEPT_FILES:
            continue
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        validate_against_schema(payload, CONCEPT_BATTERY_SCHEMA)
        concepts[payload["concept_id"]] = payload
    return concepts


def battery_hash(concepts_dir: str | Path) -> str:
    """A2 identity: content hash of the `data/concepts/` file set (§2.2)."""
    return hashing.hash_battery(concepts_dir)


def battery_version(concepts_dir: str | Path) -> str:
    battery_path = Path(concepts_dir) / "battery.yaml"
    meta = yaml.safe_load(battery_path.read_text(encoding="utf-8"))
    return meta["battery_version"]
