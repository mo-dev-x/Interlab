"""Extract max-activating token, context, and position for every Gemma-3
Neuronpedia activation record, parsed directly from the raw curl-fetched
JSON (scripts/legacy/gemma_neuronpedia_raw/<idx>.json). No LLM-mediated
reading of the parallel tokens[]/values[] arrays -- json.load + argmax only.
"""
import hashlib
import json
from pathlib import Path

FEATURES = [212, 819, 869, 976, 1041, 1423, 2582, 2848, 3039, 3070, 3169, 3349, 3358, 3648,
            4090, 4572, 5094, 5231, 6515, 7055, 7164, 7223, 7314, 7623, 8024, 8667, 9012, 9105,
            9115, 11029, 11149, 11270, 11763, 12403, 12449, 13746, 13825, 13848, 14719, 15054]

RAW_DIR = Path(__file__).parent / "gemma_neuronpedia_raw"
OUT_PATH = Path(__file__).parent / "gemma_max_activating_tokens.json"
CONTEXT_RADIUS = 10

result: dict[str, list[dict]] = {}
skipped_len_mismatch: list[dict] = []
maxvalue_mismatches: list[dict] = []
total_records = 0
total_emitted = 0

for idx in FEATURES:
    path = RAW_DIR / f"{idx}.json"
    d = json.loads(path.read_text(encoding="utf-8"))
    acts = d.get("activations", [])
    entries = []

    for rec_i, a in enumerate(acts):
        total_records += 1
        tokens = a["tokens"]
        values = a["values"]

        if len(tokens) != len(values):
            skipped_len_mismatch.append({
                "feature": idx,
                "record_index": rec_i,
                "len_tokens": len(tokens),
                "len_values": len(values),
            })
            continue

        argmax_index = max(range(len(values)), key=lambda i: values[i])
        argmax_value = values[argmax_index]
        reported_max = a["maxValue"]
        matches = (argmax_value == reported_max)
        if not matches:
            maxvalue_mismatches.append({
                "feature": idx,
                "record_index": rec_i,
                "argmax_value": argmax_value,
                "reported_maxValue": reported_max,
                "argmax_index": argmax_index,
                "maxValueTokenIndex_field": a.get("maxValueTokenIndex"),
            })

        ctx_start = max(0, argmax_index - CONTEXT_RADIUS)
        ctx_end = min(len(tokens), argmax_index + CONTEXT_RADIUS + 1)
        n = len(tokens)
        position_fraction = argmax_index / (n - 1) if n > 1 else 0.0

        entries.append({
            "record_index": rec_i,
            "n_tokens": n,
            "argmax_index": argmax_index,
            "argmax_token": tokens[argmax_index],
            "argmax_value": argmax_value,
            "reported_maxValue": reported_max,
            "argmax_matches_maxValue": matches,
            "maxValueTokenIndex_field": a.get("maxValueTokenIndex"),
            "context_tokens": tokens[ctx_start:ctx_end],
            "context_start_index": ctx_start,
            "position_fraction": position_fraction,
        })
        total_emitted += 1

    result[str(idx)] = entries

payload = {
    "_meta": {
        "n_features": len(FEATURES),
        "total_records_seen": total_records,
        "total_records_emitted": total_emitted,
        "n_skipped_len_mismatch": len(skipped_len_mismatch),
        "skipped_len_mismatch": skipped_len_mismatch,
        "n_maxvalue_mismatches": len(maxvalue_mismatches),
        "maxvalue_mismatches": maxvalue_mismatches,
        "context_radius": CONTEXT_RADIUS,
        "position_fraction_formula": "argmax_index / (n_tokens - 1), 0.0 if n_tokens <= 1",
    },
    "features": result,
}

OUT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
sha = hashlib.sha256(OUT_PATH.read_bytes()).hexdigest()

print(f"total_records_seen={total_records}")
print(f"total_records_emitted={total_emitted}")
print(f"n_skipped_len_mismatch={len(skipped_len_mismatch)}")
for s in skipped_len_mismatch:
    print(f"  SKIPPED: feature={s['feature']} record_index={s['record_index']} "
          f"len_tokens={s['len_tokens']} len_values={s['len_values']}")
print(f"n_maxvalue_mismatches={len(maxvalue_mismatches)}")
for m in maxvalue_mismatches:
    print(f"  MISMATCH: feature={m['feature']} record_index={m['record_index']} "
          f"argmax_value={m['argmax_value']} reported_maxValue={m['reported_maxValue']} "
          f"argmax_index={m['argmax_index']} maxValueTokenIndex_field={m['maxValueTokenIndex_field']}")
print(f"output={OUT_PATH}")
print(f"sha256={sha}")
