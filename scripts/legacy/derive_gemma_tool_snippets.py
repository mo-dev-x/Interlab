"""Derive top-16 max-activating snippets for the 9 sweep TOOL features from
their raw curl-fetched Neuronpedia JSON. Mirrors reorganize_and_derive.py's
protocol for the 40 seeded features: sort by maxValue descending (stable),
take top 16, reconstruct text by joining tokens[] (dropping <bos>).

The raw response objects carry an "explanations" field. It is never read,
quoted, or passed through here -- only "activations" is touched.
"""
import hashlib
import json
from pathlib import Path

FEATURES = [250, 500, 900, 2048, 2500, 3500, 4500, 11000, 12800]

RAW_DIR = Path(__file__).parent / "gemma_neuronpedia_raw"
OUT_PATH = Path(__file__).parent.parent.parent / "results" / "gemma3_sweep" / "gemma3_tool_snippets.json"
TOP_N = 16


def reconstruct_text(tokens: list[str]) -> str:
    return "".join(t for t in tokens if t != "<bos>")


derived: dict[str, list[dict]] = {}
record_counts: dict[str, int] = {}

for idx in FEATURES:
    d = json.loads((RAW_DIR / f"{idx}.json").read_text(encoding="utf-8"))
    acts = d.get("activations", [])
    record_counts[str(idx)] = len(acts)

    ordered = sorted(acts, key=lambda a: a["maxValue"], reverse=True)[:TOP_N]
    entries = []
    for a in ordered:
        text = reconstruct_text(a["tokens"])
        entries.append({"text": text, "maxValue": a["maxValue"], "char_len": len(text)})
    derived[str(idx)] = entries

OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
OUT_PATH.write_text(json.dumps(derived, indent=2, ensure_ascii=False), encoding="utf-8")
sha = hashlib.sha256(OUT_PATH.read_bytes()).hexdigest()

print("=== record counts per feature ===")
for idx in FEATURES:
    print(f"{idx}: {record_counts[str(idx)]}")
print()
print(f"output={OUT_PATH}")
print(f"sha256={sha}")
