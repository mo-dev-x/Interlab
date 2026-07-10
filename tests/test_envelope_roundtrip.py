"""§8.2 test_envelope_roundtrip: self-hash verify on every file under
registry/ -- CI runs this on the real registry, not a synthetic one."""

from pathlib import Path

from interplab.core import envelope

REGISTRY_ROOT = Path(__file__).resolve().parents[1] / "registry"


def test_every_registry_artifact_verifies():
    paths = sorted(REGISTRY_ROOT.rglob("*.json"))
    for path in paths:
        envelope.load(path)  # raises EnvelopeHashMismatchError / SchemaValidationError on failure
