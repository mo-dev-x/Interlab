"""Shared fake Gemma/Qwen backends for `final_pairing_concept_discovery.py`
-- CPU-only, real (tiny) torch tensors driven by a hand-built embedding
rule, never a real transformer or real weights. Extracted into its own
module (from `tests/test_final_pairing_concept_discovery.py`, which
originally defined the Gemma fake inline) so BOTH the pytest suite and
the pytest-FREE standalone `discovery_preflight.py` can build a full
synthetic Backend for either pairing without duplicating this code or
depending on pytest at import time.

No real Gemma-3-12B-it/Qwen3.5-27B/Gemma-Scope-2/Qwen-Scope weights exist
on any machine used in this investigation (the same standing fact as
`final_pairing_harness.py`'s own test suite). The Qwen fake needs a REAL,
loadable tokenizer directory because `final_pairing_concept_discovery.py`'s
Qwen code paths call `AutoTokenizer.from_pretrained(backend.provenance
["model"]["local_path"])` directly (no tokenizer-injection seam) -- so
this module builds one, from a tiny hand-written vocabulary, entirely
offline (no network, no real Qwen tokenizer files).
"""

from __future__ import annotations

import contextlib
import hashlib
import sys
import tempfile
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_LEGACY_SCRIPT_DIR = _SCRIPT_DIR.parent / "legacy"
sys.path.insert(0, str(_LEGACY_SCRIPT_DIR))
sys.path.insert(0, str(_SCRIPT_DIR))  # inserted LAST -> searched FIRST, so this file's own name never resolves to a scripts/legacy/ compatibility stub of the same name

import final_pairing_concept_discovery as d  # noqa: E402
import final_pairing_targets as targets  # noqa: E402
import torch  # noqa: E402

D_MODEL = 6
D_SAE = 8
CONCEPT_FEATURE = 3
OTHER_FEATURE = 5
HOOK_NAME = "fake.hook"

POSITIVE_MARKER = "POSITIVE"


def text_embedding(text: str) -> torch.Tensor:
    """Deterministic per-text embedding: texts containing 'POSITIVE' get a
    strong push along a fixed 'concept direction' (which the fake SAE's
    `encode()` maps onto `CONCEPT_FEATURE`); every other text gets small,
    text-seeded noise only."""
    seed = int(hashlib.sha256(text.encode()).hexdigest(), 16) % (2**31)
    gen = torch.Generator().manual_seed(seed)
    noise = torch.randn(D_MODEL, generator=gen) * 0.01
    if POSITIVE_MARKER in text:
        concept_direction = torch.zeros(D_MODEL)
        concept_direction[0] = 5.0
        return concept_direction + noise
    return noise


class FakeSAE:
    """`encode()` is a fixed linear map: residual dim 0 drives
    `CONCEPT_FEATURE`; every other SAE feature reads from residual dims
    every embedding leaves near zero, so they stay noise-only."""

    def __init__(self):
        self.d_in = D_MODEL
        self.d_sae = D_SAE
        w = torch.zeros(D_SAE, D_MODEL)
        w[CONCEPT_FEATURE, 0] = 1.0
        w[OTHER_FEATURE, 1] = 1.0
        self.W = w
        self.k = None

    def encode(self, x: torch.Tensor) -> torch.Tensor:
        return torch.relu(x.to(torch.float32) @ self.W.T)

    def decode(self, feats: torch.Tensor) -> torch.Tensor:
        return feats.to(torch.float32) @ self.W


#: A fake but non-empty chat template -- P0 STOP-LINE correction requires
#: `resolve_chat_template_identity`/`resolve_stop_token_ids` to derive a
#: real template/EOS identity from the tokenizer actually used, never
#: accept an arbitrary caller label; a tokenizer with NO template at all is
#: itself a stop condition for real callers, so the fakes must carry one.
_FAKE_CHAT_TEMPLATE = "{% for message in messages %}{{ message['content'] }}{% endfor %}"


class _FakeTokenizer:
    """Owns a back-reference to its `FakeGemmaModel` so `apply_chat_template`
    can register the RENDERED (templated) text through the model's own
    `to_tokens` -- the same one-text-per-token scheme every other fake code
    path already relies on, rather than a second, disconnected tokenization
    mechanism."""

    name_or_path = "fake/gemma-3-12b-it"
    chat_template = _FAKE_CHAT_TEMPLATE
    eos_token_id = 999999
    pad_token_id = 999999
    unk_token_id = None

    def __init__(self, model: FakeGemmaModel):
        self._model = model

    def decode(self, ids, **_kwargs) -> str:
        return "fake-generated-text"

    def convert_tokens_to_ids(self, _token) -> None:
        return None  # this fake vocabulary has no named special tokens at all

    def apply_chat_template(
        self, messages, *, tokenize: bool = True, add_generation_prompt: bool = True,
        return_tensors: str | None = None, return_dict: bool = False, **_kwargs,
    ):
        """Renders via the SAME fixed one-user-turn template every real
        caller now applies (`_FAKE_CHAT_TEMPLATE` is a trivial passthrough,
        so the original prompt text -- and any `POSITIVE` marker inside it
        -- survives verbatim), then tokenizes through the owning model's
        real `to_tokens` registration, never a second bespoke mechanism."""
        rendered = "".join(m["content"] for m in messages)
        if not tokenize:
            return rendered
        tokens = self._model.to_tokens(rendered)
        if return_dict:
            return {"input_ids": tokens, "attention_mask": torch.ones_like(tokens)}
        return tokens


class FakeGemmaModel:
    """Mimics only the surface `final_pairing_concept_discovery.py` calls:
    `.to_tokens`, `.run_with_cache`, `.hooks`, `.generate`, `.tokenizer`,
    `__call__`."""

    def __init__(self):
        self.tokenizer = _FakeTokenizer(self)
        self._active_hooks: list = []
        self._texts_by_token: dict[int, str] = {}
        self._next_token = 0

    def _register_text(self, text: str) -> int:
        token = self._next_token
        self._next_token += 1
        self._texts_by_token[token] = text
        return token

    def to_tokens(self, text: str) -> torch.Tensor:
        return torch.tensor([[self._register_text(text)]])

    def run_with_cache(self, tokens: torch.Tensor, names_filter: str):
        seq = [self._texts_by_token[int(t)] for t in tokens[0].tolist()]
        resid = torch.stack([text_embedding(t) for t in seq]).unsqueeze(0)
        return None, {names_filter: resid}

    @contextlib.contextmanager
    def hooks(self, fwd_hooks):
        # Only a hook registered under the model's own real hook point
        # actually fires -- mirrors real HookedTransformer.hooks(), which
        # silently registers nothing for a hook_name that isn't a real
        # point in the model's graph.
        self._active_hooks = [(name, fn) for name, fn in fwd_hooks if name == HOOK_NAME]
        try:
            yield
        finally:
            self._active_hooks = []

    def __call__(self, tokens: torch.Tensor):
        seq = [self._texts_by_token[int(t)] for t in tokens[0].tolist()]
        resid = torch.stack([text_embedding(t) for t in seq]).unsqueeze(0)
        for _name, fn in self._active_hooks:
            resid = fn(resid, hook=None)
        return resid

    def generate(self, tokens: torch.Tensor, *, max_new_tokens: int, do_sample: bool, verbose: bool = False, **_kwargs):
        seq = [self._texts_by_token[int(t)] for t in tokens[0].tolist()]
        resid = torch.stack([text_embedding(t) for t in seq]).unsqueeze(0)
        for _name, fn in self._active_hooks:
            resid = fn(resid, hook=None)
        out = tokens.clone()
        for _ in range(max_new_tokens):
            step = text_embedding("PAD").unsqueeze(0).unsqueeze(0)
            for _name, fn in self._active_hooks:
                step = fn(step, hook=None)
            out = torch.cat([out, torch.zeros((1, 1), dtype=torch.long)], dim=1)
        return out


def make_fake_gemma_backend() -> d.Backend:
    return d.Backend(
        pairing=targets.GEMMA_3_12B_IT_TARGET.name,
        model_obj=FakeGemmaModel(),
        sae=FakeSAE(),
        hook_name=HOOK_NAME,
        d_sae=D_SAE,
        d_model=D_MODEL,
        layer=targets.GEMMA_3_12B_IT_TARGET.expected_layer,
        provenance={
            "model": {"repository": "google/gemma-3-12b-it", "local_path": "/fake/gemma/model"},
            "sae": {"repository": "google/gemma-scope-2-12b-it"},
        },
        checkpoint_hash="deadbeefgemma",
    )


# ---------------------------------------------------------------------------
# Qwen fake: needs a REAL, loadable tokenizer directory (no injection seam
# exists in final_pairing_concept_discovery.py's Qwen code paths -- they
# call AutoTokenizer.from_pretrained(local_path) directly), plus a real
# nn.Module decoder layer so `register_forward_hook` is the real PyTorch
# mechanism, never a fake stand-in for it.
# ---------------------------------------------------------------------------

_QWEN_VOCAB_WORDS = (
    "[UNK]", "POSITIVE", "example", "neutral", "filler", "PAD", "background",
    "corpus", "document", "unrelated", "text", "concept", "cheese", "0", "1",
    "2", "3", "4", "5", "6", "7", "8", "9",
)


def _build_tiny_qwen_tokenizer_dir() -> str:
    """A minimal, offline, real WordLevel tokenizer -- no network, no real
    Qwen tokenizer files. Persisted to a process-lifetime temp directory
    (never cleaned up mid-process; these are short-lived CLI/test runs)."""
    from tokenizers import Tokenizer
    from tokenizers.models import WordLevel
    from tokenizers.pre_tokenizers import Whitespace
    from transformers import PreTrainedTokenizerFast

    vocab = {word: i for i, word in enumerate(_QWEN_VOCAB_WORDS)}
    tokenizer = Tokenizer(WordLevel(vocab=vocab, unk_token="[UNK]"))
    tokenizer.pre_tokenizer = Whitespace()
    # eos_token and chat_template are required for resolve_chat_template_
    # identity/resolve_stop_token_ids/apply_chat_template to have anything
    # real to resolve -- P0 STOP-LINE correction: real callers must derive
    # these from the tokenizer, never accept an arbitrary label, so this
    # fake tokenizer must carry genuine (if trivial) values for both.
    fast = PreTrainedTokenizerFast(
        tokenizer_object=tokenizer, unk_token="[UNK]", pad_token="[UNK]", eos_token="[UNK]",
        chat_template=_FAKE_CHAT_TEMPLATE,
    )
    tmp_dir = tempfile.mkdtemp(prefix="final-pairing-fake-qwen-tokenizer-")
    fast.save_pretrained(tmp_dir)
    return tmp_dir


_TINY_QWEN_TOKENIZER_DIR: str | None = None


def tiny_qwen_tokenizer_dir() -> str:
    """Builds the tiny tokenizer directory once per process and reuses it."""
    global _TINY_QWEN_TOKENIZER_DIR
    if _TINY_QWEN_TOKENIZER_DIR is None:
        _TINY_QWEN_TOKENIZER_DIR = _build_tiny_qwen_tokenizer_dir()
    return _TINY_QWEN_TOKENIZER_DIR


class _FakeQwenDecoderLayer(torch.nn.Module):
    """A REAL `nn.Module` -- `register_forward_hook` is the genuine
    PyTorch mechanism, not simulated. Produces one embedding per input
    position: 'concept' if the POSITIVE token id is anywhere in the
    sequence, noise otherwise -- the per-sequence analogue of the Gemma
    fake's per-text `text_embedding`."""

    def __init__(self, positive_token_id: int):
        super().__init__()
        self._positive_token_id = positive_token_id

    def forward(self, input_ids: torch.Tensor) -> torch.Tensor:
        ids = input_ids[0].tolist()
        is_positive = self._positive_token_id in ids
        seq_len = len(ids)
        if is_positive:
            base = torch.zeros(D_MODEL)
            base[0] = 5.0
        else:
            base = torch.zeros(D_MODEL)
        gen = torch.Generator().manual_seed(sum(ids) + seq_len)
        noise = torch.randn(seq_len, D_MODEL, generator=gen) * 0.01
        return (base.unsqueeze(0) + noise).unsqueeze(0)  # [1, seq_len, d_model]


class FakeQwenModel(torch.nn.Module):
    """Mimics only the surface this discovery runner calls:
    `__call__(**inputs)` (routes through the real `decoder_layer`
    submodule so a registered forward hook genuinely fires) and
    `generate(**inputs, max_new_tokens=..., do_sample=...)`."""

    def __init__(self, decoder_layer: _FakeQwenDecoderLayer):
        super().__init__()
        self.decoder_layer = decoder_layer

    def forward(self, input_ids=None, attention_mask=None, **_kwargs):
        return self.decoder_layer(input_ids)

    def generate(self, *, input_ids, max_new_tokens: int, do_sample: bool, attention_mask=None, **_kwargs):
        out = input_ids.clone()
        # Routes through `self.decoder_layer` on every step (prefill AND
        # each generated token) so a hook registered via the real
        # `register_forward_hook` on that submodule genuinely fires during
        # generation -- mirrors the Gemma fake's own `generate()`, which
        # applies its active hooks at every step rather than only at
        # construction time.
        self.decoder_layer(out)
        for _ in range(max_new_tokens):
            out = torch.cat([out, torch.zeros((1, 1), dtype=torch.long)], dim=1)
            self.decoder_layer(out)
        return out


def make_fake_qwen_backend() -> d.Backend:
    tokenizer_dir = tiny_qwen_tokenizer_dir()
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(tokenizer_dir)
    positive_id = tokenizer(POSITIVE_MARKER, return_tensors="pt")["input_ids"][0, -1].item()
    decoder_layer = _FakeQwenDecoderLayer(positive_token_id=positive_id)
    model = FakeQwenModel(decoder_layer)
    return d.Backend(
        pairing=targets.QWEN_3_5_27B_TARGET.name,
        model_obj=model,
        sae=FakeSAE(),
        hook_name="fake.qwen.decoder_layer",
        d_sae=D_SAE,
        d_model=D_MODEL,
        layer=38,
        provenance={
            "model": {"repository": "Qwen/Qwen3.5-27B", "local_path": tokenizer_dir},
            "sae": {"repository": "Qwen/SAE-Res-Qwen3.5-27B-W80K-L0_50"},
        },
        checkpoint_hash="deadbeefqwen",
        sae_family="L0_100", sparsity=100,
        _qwen_decoder_layer=decoder_layer, _qwen_device="cpu",
    )


POSITIVE_TEXTS = [f"{POSITIVE_MARKER} example {i}" for i in range(6)]
NEGATIVE_TEXTS = [f"neutral filler {i}" for i in range(6)]
