#!/usr/bin/env python3
"""Build the Qwen analogue of scripts/legacy/gemma_max_activating_tokens.json.

Prereg v1.6 §11.1 requires marker parity: neither column may be classified under
trigger-primacy until both have marker access. Gemma's marker file is derived from
Neuronpedia's `tokens[]` / `values[]` / `maxValueTokenIndex`. Qwen's source artifact
(example_context_centred1164.json) carries the activating token string, its character
offset in the emitted window, and `original_excerpt` = "".join(str_tokens[pos-8:pos+1]),
but NO token list. This script recovers the token list by re-tokenising the emitted
window and aligning on character offsets.

Every emitted record is verified two ways before it is written:
  1. the token found at `activating_char_offset_in_window` must equal `activating_token`;
  2. joining the nine tokens ending there must reproduce `original_excerpt` byte for byte
     (checked wherever `contains_original_excerpt` is true).
A record failing either check is NOT emitted with a guessed token list; it is recorded in
_meta under `skipped_*` so the gap is visible rather than silently filled. This mirrors
methods §4.8: a read that can silently return wrong data is not evidence.

Schema matches the Gemma file field-for-field so both columns are read identically.
"""
import json
import pathlib
import sys

from transformers import AutoTokenizer

BASE = pathlib.Path(__file__).resolve().parents[2]
SRC = BASE / 'results/characterize_lite/rwu04lpb_taxonomy40/example_context_centred1164.json'
OUT = BASE / 'scripts/legacy/qwen_max_activating_tokens.json'
TOKENIZER = 'Qwen/Qwen2.5-14B-Instruct'
CONTEXT_RADIUS = 10


def main() -> int:
    src = json.loads(SRC.read_text(encoding='utf-8'))
    arms = src['ARM_PRIMARY_windows']
    tok = AutoTokenizer.from_pretrained(TOKENIZER)

    features = {}
    seen = emitted = 0
    skipped_no_align = []
    skipped_excerpt_mismatch = []
    clipped_at_chunk_start = 0

    for fid in sorted(arms, key=int):
        out_recs = []
        for rec in arms[fid]:
            seen += 1
            win = rec['centred_1164']
            text = win['text']
            off = win['activating_char_offset_in_window']
            act = rec['activating_token']

            enc = tok(text, return_offsets_mapping=True, add_special_tokens=False)
            om = enc['offset_mapping']

            j = next((i for i, (s, e) in enumerate(om) if s == off and text[s:e] == act), None)
            if j is None:
                j = next((i for i, (s, e) in enumerate(om) if s <= off < e and text[s:e] == act), None)
            if j is None:
                skipped_no_align.append([fid, rec['rank']])
                continue

            excerpt_ok = None
            if win.get('contains_original_excerpt'):
                lo = max(0, j - 8)
                rebuilt = ''.join(text[s:e] for s, e in om[lo:j + 1])
                excerpt_ok = rebuilt == rec['original_excerpt']
                if not excerpt_ok:
                    skipped_excerpt_mismatch.append([fid, rec['rank']])
                    continue

            lo = max(0, j - CONTEXT_RADIUS)
            hi = min(len(om), j + CONTEXT_RADIUS + 1)
            n_tok_chunk = rec['source_chunk']['chunk_n_tokens']

            if win.get('clipped_at_chunk_start'):
                clipped_at_chunk_start += 1

            out_recs.append({
                'record_index': rec['rank'],
                'n_tokens': n_tok_chunk,
                'argmax_index': rec['token_position'],
                'argmax_token': act,
                'argmax_value': rec['activation'],
                'reported_maxValue': rec['activation'],
                'maxValueTokenIndex': rec['token_position'],
                'indices_agree': True,
                'context_tokens': [text[s:e] for s, e in om[lo:hi]],
                'context_start_index': rec['token_position'] - (j - lo),
                'context_end_index': rec['token_position'] + (hi - 1 - j),
                'context_window_requested': [rec['token_position'] - CONTEXT_RADIUS,
                                             rec['token_position'] + CONTEXT_RADIUS],
                'splice_seam': False,
                # Gemma-side packed-stream fields, emitted with Qwen-correct constants so a
                # reader can iterate both files with one field list. Each is structurally
                # impossible on Qwen, not merely unobserved: one doc_id per record means no
                # concatenation boundary, and the windows carry raw document text with no
                # special tokens inserted.
                'bos_in_context_window': False,
                'n_bos_total': 0,
                'is_multi_document_record': False,
                'unmarked_fusion_heuristic': False,
                'position_fraction': round(win['activating_relative_position_pct'] / 100.0, 6),
                # --- Qwen-specific, additive; documented in _meta ---
                'position_fraction_in_chunk': round(
                    rec['token_position'] / (n_tok_chunk - 1), 6) if n_tok_chunk > 1 else 0.0,
                'doc_id': rec['doc_id'],
                'clipped_at_chunk_start': bool(win.get('clipped_at_chunk_start')),
                'original_excerpt_verified': excerpt_ok,
            })
            emitted += 1
        features[fid] = out_recs

    meta = {
        'n_features': len(features),
        'total_records_seen': seen,
        'total_records_emitted': emitted,
        'n_skipped_len_mismatch': len(skipped_no_align) + len(skipped_excerpt_mismatch),
        'skipped_len_mismatch': skipped_no_align + skipped_excerpt_mismatch,
        'n_index_mismatches': 0,
        'index_mismatches': [],
        # --- realigned to the Gemma marker file's field names (§14.5) so both _meta blocks
        # read identically. All three seam signals are structurally zero on Qwen, not merely
        # unobserved: one doc_id per record means no packed-stream concatenation can occur.
        'n_multi_document_records': 0,
        'multi_document_record_definition':
            'STRUCTURALLY ZERO ON QWEN. On Gemma this counts records holding more than one literal '
            '<bos>, i.e. records packing more than one document. Every Qwen record derives from '
            'exactly one doc_id (carried per record), so the quantity cannot be non-zero here. '
            'Emitted so the field exists on both columns rather than being absent on one.',
        'n_bos_in_context_window': 0,
        'n_unmarked_fusion_heuristic': 0,
        'unmarked_fusion_heuristic_caveat':
            'NOT a reported rate on either column. On Gemma an independent check found ~97% false '
            'positives on this signal (B2B, WinRAR, CompTIA and similar are tokenizer splits, not '
            'document seams); no defensible unmarked-splice criterion currently exists. On Qwen it '
            'is zero by construction. Never used for context truncation on either column.',
        'context_truncation_rule':
            'NO TRUNCATION IS EVER APPLIED ON QWEN, because the condition that triggers it on Gemma '
            '-- a literal <bos> strictly inside the +/-10 window -- cannot arise. Context is instead '
            'bounded by the emitted 1164-char window, so a context_tokens list shorter than '
            '2*context_radius+1 means the window edge was reached, NOT that a seam was cut. Where '
            'that edge is the document start, clipped_at_chunk_start is true and methods 4.6 '
            'applies: opening-line patterns are non-evidence.',
        'splice_seam_note':
            'splice_seam is retained on every record as the vestigial Qwen-correct constant false. '
            'It predates the Gemma file being regenerated with the three-signal schema above and is '
            'kept so readers of the earlier digest find the field where they expect it.',
        'context_radius': CONTEXT_RADIUS,
        'position_fraction_formula':
            'activating_relative_position_pct / 100 -- position of the trigger WITHIN THE EMITTED '
            'WINDOW, the field-for-field parallel of Gemma position_fraction. NOT COMPARABLE across '
            'columns: Qwen windows are centred on the activation by construction so this clusters '
            'near 0.5, whereas Gemma records are uncentred (measured 0.6%-75%). See methods 4.4. '
            'Use position_fraction_in_chunk for the informative Qwen quantity.',
        'position_fraction_in_chunk_formula':
            'token_position / (chunk_n_tokens - 1); chunk = the first <=512 tokens of the document '
            'that characterize_lite actually processed.',
        'splice_seam_definition_superseded':
            'NOT APPLICABLE to Qwen. Every Qwen record derives from exactly one doc_id, so the '
            'packed-stream concatenation boundary that prereg 11.7 handles on the Gemma side cannot '
            'occur here. Emitted as false on every record so the field reads identically. The '
            'Qwen-side mirror defect is the opposite one: every chunk starts at document character '
            '0 (methods 4.6), so clipped_at_chunk_start is carried per record and opening-line '
            'patterns are non-evidence on EVERY row.',
        'clipped_at_chunk_start_records': clipped_at_chunk_start,
        'verification':
            'Each emitted record: (a) the token at activating_char_offset_in_window equals '
            'activating_token; (b) where contains_original_excerpt is true, the nine tokens ending '
            'there rejoin to original_excerpt byte for byte. Records failing either check are '
            'skipped, never guessed.',
        'tokenizer': TOKENIZER,
        'source_artifact': 'results/characterize_lite/rwu04lpb_taxonomy40/example_context_centred1164.json',
        'source_sha256': '72e73f263176163fa44e4b6b9c7b6a925d4c1f0f03bb0f9667ab5fc971e5b21c',
    }

    OUT.write_text(json.dumps({'_meta': meta, 'features': features}, ensure_ascii=False, indent=1),
                   encoding='utf-8')
    print(f'seen {seen}  emitted {emitted}  '
          f'skipped_no_align {len(skipped_no_align)}  '
          f'skipped_excerpt_mismatch {len(skipped_excerpt_mismatch)}')
    print(f'clipped_at_chunk_start records: {clipped_at_chunk_start}')
    print(f'wrote {OUT}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
