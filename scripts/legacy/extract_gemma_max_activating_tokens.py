"""Extract max-activating token, context, and position for every Gemma-3
Neuronpedia activation record, parsed directly from the raw curl-fetched
JSON (scripts/legacy/gemma_neuronpedia_raw/<idx>.json). No LLM-mediated
reading of the parallel tokens[]/values[] arrays -- json.load + argmax only.

Cross-checks argmax(values) against the source's own maxValueTokenIndex
field and asserts agreement; reports every disagreement rather than
silently trusting either side.

Two DIFFERENT splice-related measurements are reported, and they are not
combined into one "rate":

1. is_multi_document_record (the reported floor, 46.5% top-16-restricted,
   matches the independent audit's number exactly): the record contains
   more than one literal <bos> token anywhere in its full token sequence
   -- i.e. the record itself packs more than one document, full stop,
   regardless of where the argmax token falls.

2. unmarked_fusion_heuristic (kept for the record, NOT reported as a rate):
   a token with no leading whitespace starting with an uppercase letter
   immediately after a token ending in a lowercase letter, inside the
   +/-10 context window -- catches genuine unmarked splices like
   " hyperlink"+"In", but an independent check found ~97% false positives
   (B2B, WinRAR, CompTIA, AZ-16A and similar are tokenizer splits, not
   seams). No defensible unmarked-splice criterion currently exists; the
   true unmarked-splice rate is higher than the marked floor but
   unquantified. This field is diagnostic only.

Context truncation uses ONLY the reliable signal: a literal <bos> falling
strictly inside the +/-10 window (bos_in_context_window). The heuristic
never truncates context, since truncating on a ~97%-false-positive signal
would cut good context on false alarms far more often than it would catch
a real seam.
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


def is_bos_seam(tokens: list[str], j: int) -> bool:
    return j != 0 and tokens[j] == "<bos>"


def is_unmarked_fusion_candidate(tokens: list[str], j: int) -> bool:
    if j == 0:
        return False
    tok = tokens[j]
    if not tok or tok[0].isspace():
        return False
    if not tok[0].isupper():
        return False
    prev = tokens[j - 1]
    if not prev:
        return False
    last = prev[-1]
    return last.isalpha() and last.islower()


def find_in_range(tokens: list[str], lo: int, hi: int, predicate) -> list[int]:
    return [j for j in range(lo, hi) if predicate(tokens, j)]


result: dict[str, list[dict]] = {}
skipped_len_mismatch: list[dict] = []
index_mismatches: list[dict] = []
total_records = 0
total_emitted = 0
multi_document_count = 0
bos_window_count = 0
unmarked_fusion_count = 0

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
        source_index = a.get("maxValueTokenIndex")
        reported_max = a["maxValue"]

        indices_agree = (source_index == argmax_index)
        if not indices_agree:
            source_value = values[source_index] if source_index is not None and 0 <= source_index < len(values) else None
            index_mismatches.append({
                "feature": idx,
                "record_index": rec_i,
                "argmax_index": argmax_index,
                "argmax_value": argmax_value,
                "maxValueTokenIndex": source_index,
                "value_at_maxValueTokenIndex": source_value,
                "reported_maxValue": reported_max,
                "values_tie": (source_value == argmax_value) if source_value is not None else False,
            })

        n = len(tokens)
        ctx_start = max(0, argmax_index - CONTEXT_RADIUS)
        ctx_end = min(n, argmax_index + CONTEXT_RADIUS + 1)

        n_bos_total = sum(1 for t in tokens if t == "<bos>")
        is_multi_document_record = n_bos_total > 1
        if is_multi_document_record:
            multi_document_count += 1

        bos_seams = find_in_range(tokens, ctx_start, ctx_end, is_bos_seam)
        bos_seams = [s for s in bos_seams if s != argmax_index]
        left_seams = [s for s in bos_seams if s <= argmax_index]
        right_seams = [s for s in bos_seams if s > argmax_index]
        trunc_start = max(left_seams) if left_seams else ctx_start
        trunc_end = min(right_seams) if right_seams else ctx_end
        bos_in_context_window = bool(bos_seams)
        if bos_in_context_window:
            bos_window_count += 1

        fusion_hits = find_in_range(tokens, ctx_start, ctx_end, is_unmarked_fusion_candidate)
        fusion_hits = [s for s in fusion_hits if s != argmax_index]
        unmarked_fusion_heuristic = bool(fusion_hits)
        if unmarked_fusion_heuristic:
            unmarked_fusion_count += 1

        position_fraction = argmax_index / (n - 1) if n > 1 else 0.0

        entries.append({
            "record_index": rec_i,
            "n_tokens": n,
            "argmax_index": argmax_index,
            "argmax_token": tokens[argmax_index],
            "argmax_value": argmax_value,
            "reported_maxValue": reported_max,
            "maxValueTokenIndex": source_index,
            "indices_agree": indices_agree,
            "context_tokens": tokens[trunc_start:trunc_end],
            "context_start_index": trunc_start,
            "context_end_index": trunc_end,
            "context_window_requested": [ctx_start, ctx_end],
            "is_multi_document_record": is_multi_document_record,
            "n_bos_total": n_bos_total,
            "bos_in_context_window": bos_in_context_window,
            "unmarked_fusion_heuristic": unmarked_fusion_heuristic,
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
        "n_index_mismatches": len(index_mismatches),
        "index_mismatches": index_mismatches,
        "n_multi_document_records": multi_document_count,
        "multi_document_record_definition": (
            "REPORTED FLOOR. Record contains more than one literal <bos> token "
            "anywhere in its full token sequence -- the record packs more than "
            "one document, independent of where the argmax token falls. Matches "
            "the independently-audited exact-marked rate exactly when restricted "
            "to top-16-by-maxValue."
        ),
        "n_bos_in_context_window": bos_window_count,
        "n_unmarked_fusion_heuristic": unmarked_fusion_count,
        "unmarked_fusion_heuristic_caveat": (
            "NOT a reported rate. An independent check found ~97% false "
            "positives on this signal (B2B, WinRAR, CompTIA, AZ-16A and similar "
            "are tokenizer splits, not document seams). No defensible unmarked-"
            "splice criterion currently exists; kept as a diagnostic field only, "
            "never used for context truncation."
        ),
        "context_radius": CONTEXT_RADIUS,
        "context_truncation_rule": (
            "Truncated only at a literal <bos> strictly inside the +/-10 window "
            "(the reliable signal). Never truncated on unmarked_fusion_heuristic."
        ),
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
print(f"n_index_mismatches={len(index_mismatches)}")
for m in index_mismatches:
    print(f"  MISMATCH: feature={m['feature']} record_index={m['record_index']} "
          f"argmax_index={m['argmax_index']} maxValueTokenIndex={m['maxValueTokenIndex']} "
          f"values_tie={m['values_tie']}")
print(f"n_multi_document_records (reported floor)={multi_document_count} / {total_emitted}")
print(f"n_bos_in_context_window (truncation trigger)={bos_window_count} / {total_emitted}")
print(f"n_unmarked_fusion_heuristic (diagnostic only, ~97% false-positive rate)={unmarked_fusion_count} / {total_emitted}")
print(f"output={OUT_PATH}")
print(f"sha256={sha}")
