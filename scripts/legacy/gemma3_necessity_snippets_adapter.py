#!/usr/bin/env python3
"""Adapter: converts raw Neuronpedia feature-API JSON exports (fetched
directly via curl on the login node -- never through a summarizing
assistant, whose paraphrase-preserving checksums are structurally blind to
token-level corruption) into the exact schema `gemma3_necessity.py`'s
`load_snippets()` requires.

New file, not a change to either frozen harness (gemma3_sweep.py,
gemma3_necessity.py) -- per "duplicate rather than cross-import" / "write
an adapter, not a change to the frozen harness".

INPUT: one raw JSON file per feature, as returned by
  https://www.neuronpedia.org/api/feature/gemma-3-12b/31-gemmascope-2-res-16k/<idx>
Each has an "activations" list; each activation record has "tokens" (a
list of already-tokenized strings, each carrying its own leading space
per the tokenizer's convention -- concatenating them verbatim reproduces
the exact substring, no re-encoding needed) and "maxValue" (the
activation value used to rank "top-16 activating").

OUTPUT (gemma3_necessity.py:196-211, load_snippets()):
    {"250": ["snippet text 1", "snippet text 2", ...], "500": [...], ...}
    a flat list of up to TOP_N_SNIPPETS=16 plain strings per feature --
    confirmed by how it's consumed downstream (build_own_text_matrix /
    build_within_feature_control_candidates iterate the list and pass each
    "snippet" directly into a cell record that later gets tokenized as
    text; a dict there would break tokenization).

Text reconstruction: joins "tokens" verbatim (str.join, no separator,
since each token already carries correct leading whitespace), dropping
only the literal "<bos>" control token (not real snippet content -- the
harness's own model.to_tokens() call re-adds a BOS token per its own
prepend_bos convention). No whitespace normalization, no truncation
beyond the top-16 selection itself.

Does not trust input ordering -- explicitly re-sorts each feature's
activations by "maxValue" descending before truncating to top-16.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REQUIRED_FEATURE_IDXS = [250, 500, 900, 2048, 2500, 3500, 4500, 11000, 12800]
TOP_N_SNIPPETS = 16
EXPECTED_HOOK_NAME = "blocks.31.hook_resid_post"
EXPECTED_MODEL_TLENS_ID = "google/gemma-3-12b-pt"


def reconstruct_text(tokens: list[str]) -> str:
    return "".join(t for t in tokens if t != "<bos>")


def adapt(raw_dir: Path) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for idx in REQUIRED_FEATURE_IDXS:
        path = raw_dir / f"snippets_raw_{idx}.json"
        if not path.exists():
            raise FileNotFoundError(f"missing raw fetch for feature {idx}: {path}")
        d = json.loads(path.read_text(encoding="utf-8"))

        hook_name = d.get("hookName")
        model_tlens_id = (d.get("model") or {}).get("tlensId")
        index_field = d.get("index")
        if hook_name != EXPECTED_HOOK_NAME:
            raise ValueError(f"feature {idx}: hookName={hook_name!r}, expected {EXPECTED_HOOK_NAME!r}")
        if model_tlens_id != EXPECTED_MODEL_TLENS_ID:
            raise ValueError(f"feature {idx}: model.tlensId={model_tlens_id!r}, expected {EXPECTED_MODEL_TLENS_ID!r}")
        if str(index_field) != str(idx):
            raise ValueError(f"feature {idx}: index field={index_field!r}, expected {idx!r}")

        acts = d["activations"]
        if len(acts) < TOP_N_SNIPPETS:
            raise ValueError(f"feature {idx}: only {len(acts)} activations, need >= {TOP_N_SNIPPETS}")

        ordered = sorted(acts, key=lambda a: a["maxValue"], reverse=True)[:TOP_N_SNIPPETS]
        out[str(idx)] = [reconstruct_text(a["tokens"]) for a in ordered]
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--raw-dir", required=True, help="Directory containing snippets_raw_<idx>.json files")
    p.add_argument("--out-file", required=True, help="Adapted output, in gemma3_necessity.py's expected schema")
    args = p.parse_args()

    adapted = adapt(Path(args.raw_dir))
    Path(args.out_file).write_text(json.dumps(adapted, indent=2, ensure_ascii=False), encoding="utf-8")

    for idx in REQUIRED_FEATURE_IDXS:
        texts = adapted[str(idx)]
        print(f"feature {idx}: {len(texts)} snippets, first char_len={len(texts[0])}")
    print(f"wrote {args.out_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
