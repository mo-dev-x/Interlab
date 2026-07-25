"""Seeded generator for tests/fixtures/ (§8.1).

Fixtures are generated once and committed; this script is kept for
provenance only. Tests MUST NOT call this at runtime (blueprint §8.1,
ED-1): cross-platform/cross-version torch RNG determinism is not
guaranteed, and the golden-delta test (WP1) depends on exact bytes.
Regenerating a fixture is a breaking change to every golden test and
requires trunk-level review.

Usage (from the local uv-managed venv only -- ED-1):
    uv run python tests/fixtures/generate.py

Produces:
    tests/fixtures/tiny_model/    -- 2-layer, d_model=64 Qwen2 model, HF format
    tests/fixtures/tiny_sae/      -- TopK (k=8, 256 features) SAE, SAELens format
    tests/fixtures/pinned_text.jsonl -- 200 fixed documents
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import torch
from sae_lens.saes.sae import SAEMetadata
from sae_lens.saes.topk_sae import TopKSAE, TopKSAEConfig
from tokenizers import Tokenizer, decoders, pre_tokenizers, processors
from tokenizers.models import BPE
from transformers import PreTrainedTokenizerFast, Qwen2Config, Qwen2ForCausalLM

SEED = 0
FIXTURES_DIR = Path(__file__).resolve().parent
TINY_MODEL_DIR = FIXTURES_DIR / "tiny_model"
TINY_SAE_DIR = FIXTURES_DIR / "tiny_sae"
PINNED_TEXT_PATH = FIXTURES_DIR / "pinned_text.jsonl"

SPECIAL_TOKENS = ["<pad>", "<bos>", "<eos>", "<unk>"]

HIDDEN_SIZE = 64
NUM_LAYERS = 2
N_DOCS = 200

_WORDS = ["the", "cheese", "model", "fires", "on", "tokens", "that", "mention", "gouda", "cheddar", "brie", "feature", "activation", "residual", "stream", "layer", "attention", "token", "prompt", "sample", "seed", "vector", "concept", "probe", "corpus", "census", "manifest", "checkpoint", "certificate", "steering", "ablate", "clamp", "direction", "decode", "encode", "dense", "sparse", "dictionary", "train", "validate", "report", "quebec", "montreal", "poutine", "maple", "river", "mountain", "lake", "forest", "winter", "summer", "language", "english", "french", "chinese", "arabic", "word", "sentence", "document", "text", "corpus"]


def seed_everything(seed: int) -> None:
    random.seed(seed)
    torch.manual_seed(seed)


def build_tokenizer() -> PreTrainedTokenizerFast:
    """Deterministic byte-level tokenizer: every byte value is its own token,
    so arbitrary UTF-8 text encodes without unknowns. No training, no
    network access -- pure fixed mapping. Implemented as BPE with an empty
    merge table (so it never combines bytes) rather than WordLevel: the
    ByteLevel pre-tokenizer's GPT-2 regex splits text into multi-byte
    chunks, and WordLevel can only match whole chunks, not their
    constituent bytes -- BPE's per-byte base-vocabulary step is what
    actually gives one token per byte here."""
    alphabet = sorted(pre_tokenizers.ByteLevel.alphabet())
    vocab = {tok: i for i, tok in enumerate(SPECIAL_TOKENS)}
    offset = len(SPECIAL_TOKENS)
    for i, ch in enumerate(alphabet):
        vocab[ch] = offset + i

    tokenizer = Tokenizer(BPE(vocab=vocab, merges=[], unk_token="<unk>"))
    tokenizer.pre_tokenizer = pre_tokenizers.ByteLevel(add_prefix_space=False, use_regex=False)
    tokenizer.decoder = decoders.ByteLevel()
    tokenizer.post_processor = processors.TemplateProcessing(
        single="<bos> $A <eos>",
        special_tokens=[("<bos>", vocab["<bos>"]), ("<eos>", vocab["<eos>"])],
    )

    fast_tokenizer = PreTrainedTokenizerFast(
        tokenizer_object=tokenizer,
        pad_token="<pad>",
        bos_token="<bos>",
        eos_token="<eos>",
        unk_token="<unk>",
        model_input_names=["input_ids", "attention_mask"],
    )
    return fast_tokenizer, len(vocab)


def build_tiny_model(vocab_size: int) -> Qwen2ForCausalLM:
    config = Qwen2Config(
        vocab_size=vocab_size,
        hidden_size=HIDDEN_SIZE,
        intermediate_size=HIDDEN_SIZE * 2,
        num_hidden_layers=NUM_LAYERS,
        num_attention_heads=4,
        num_key_value_heads=2,
        max_position_embeddings=128,
        tie_word_embeddings=True,
    )
    return Qwen2ForCausalLM(config)


def build_tiny_sae() -> TopKSAE:
    """ED-33: real P1 checkpoints are `architecture: "topk"` under sae-lens
    6.x's `TopKSAEConfig` -- provenance/hook fields live under `metadata`
    (a loose attribute bag, not a dataclass), not as flat top-level fields
    like the pre-ED-33 3.x `SAEConfig` this fixture used to build."""
    metadata = SAEMetadata(
        model_name="tiny_model",
        hook_name="blocks.1.hook_resid_post",
        hook_layer=1,
        hook_head_index=None,
        context_size=32,
        prepend_bos=True,
        dataset_path="tests/fixtures/pinned_text.jsonl",
        dataset_trust_remote_code=False,
        sae_lens_training_version=None,
    )
    cfg = TopKSAEConfig(
        d_in=HIDDEN_SIZE,
        d_sae=256,
        k=8,
        apply_b_dec_to_input=False,
        normalize_activations="none",
        dtype="float32",
        device="cpu",
        metadata=metadata,
    )
    return TopKSAE(cfg)


def build_pinned_text(n: int = N_DOCS) -> list[dict]:
    rng = random.Random(SEED)
    docs = []
    for i in range(n):
        length = rng.randint(5, 15)
        text = " ".join(rng.choice(_WORDS) for _ in range(length))
        docs.append({"id": i, "text": text[0].upper() + text[1:] + "."})
    return docs


def main() -> None:
    seed_everything(SEED)

    TINY_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    TINY_SAE_DIR.mkdir(parents=True, exist_ok=True)

    tokenizer, vocab_size = build_tokenizer()
    tokenizer.save_pretrained(str(TINY_MODEL_DIR))

    model = build_tiny_model(vocab_size)
    model.save_pretrained(str(TINY_MODEL_DIR), safe_serialization=True)

    sae = build_tiny_sae()
    sae.save_model(str(TINY_SAE_DIR))

    docs = build_pinned_text()
    with PINNED_TEXT_PATH.open("w", encoding="utf-8") as f:
        for doc in docs:
            f.write(json.dumps(doc, ensure_ascii=False))
            f.write("\n")

    print(f"seed={SEED}")
    print(f"tiny_model -> {TINY_MODEL_DIR} (vocab_size={vocab_size})")
    print(f"tiny_sae   -> {TINY_SAE_DIR}")
    print(f"pinned_text -> {PINNED_TEXT_PATH} ({len(docs)} docs)")


if __name__ == "__main__":
    main()
