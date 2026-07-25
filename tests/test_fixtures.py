"""§8.1 fixture presence/shape checks. Fixture *behavioral* correctness
(identity test, golden-delta test) is exercised by SS7's own tests (WP1);
this only guards that WP0's committed, pinned fixtures exist and are
structurally what §8.1 specifies, without pulling torch/transformers into
WP0's own test run.
"""

import json
from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def test_tiny_model_files_present():
    d = FIXTURES_DIR / "tiny_model"
    for name in ["config.json", "model.safetensors", "tokenizer.json", "tokenizer_config.json"]:
        assert (d / name).is_file(), f"missing {name}"

    config = json.loads((d / "config.json").read_text(encoding="utf-8"))
    assert config["num_hidden_layers"] == 2
    assert config["hidden_size"] == 64


def test_tiny_sae_files_present():
    d = FIXTURES_DIR / "tiny_sae"
    assert (d / "cfg.json").is_file()
    assert (d / "sae_weights.safetensors").is_file()

    cfg = json.loads((d / "cfg.json").read_text(encoding="utf-8"))
    assert cfg["d_sae"] == 256
    assert cfg["architecture"] == "topk"
    assert cfg["k"] == 8


def test_pinned_text_has_200_documents():
    path = FIXTURES_DIR / "pinned_text.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 200
    for line in lines:
        doc = json.loads(line)
        assert "id" in doc
        assert "text" in doc and isinstance(doc["text"], str) and doc["text"]
