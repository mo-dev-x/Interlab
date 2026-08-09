"""Build reports/adjudication_ledger_r1.canonical.json from the Rater 1 prose ledger.

Transcription is manual and auditable: every row below is keyed to a section of
reports/adjudication_ledger_r1.md. The script exists so the emitted file is
schema-validated rather than hand-typed JSON, and so the validation is rerunnable.

NO BUCKET FIELD. The class -> bucket mapping lives in the merge instrument only.
NO FREE TEXT. Deciding quotes and evidence stay in the prose ledger.
"""
import json
from collections import Counter

CONF = {"low", "med", "med-high", "high", None}
CODE = {"I-THIN", "I-DIVERSE", "I-SILENT", "I-AMBIGUOUS", None}

# (idx, column, class, conf, reason_code, distinct_sources, n_firings,
#  pre_marker_class, marker_driven_numerator_move)
ROWS = [
    # ---- QWEN, section 7 (marker retrofit of the 9 pre-marker / parked rows) ----
    (14622,  "qwen",  5, "high",     None,         7,    131, 11, False),
    (126804, "qwen",  2, "high",     None,        13,    736,  2, False),
    (107244, "qwen",  5, "med",      None,        16,   4013, 10, False),
    (71905,  "qwen", 10, "med",      "I-DIVERSE", 14,     53, 10, False),
    (70945,  "qwen", 10, "med",      "I-THIN",     2,    841, 10, False),
    (140672, "qwen", 10, "med",      "I-DIVERSE", 16,    125, 10, False),
    (114256, "qwen", 10, "med",      "I-DIVERSE", 15,     32, 10, False),
    (14081,  "qwen",  1, "high",     None,         6,    442, None, True),
    (33008,  "qwen",  7, "med",      None,        15,   5945, None, False),
    # ---- QWEN, section 10 (the remaining 31, marker-native) ----
    (45344,  "qwen",  2, "high",     None,        16,   None, None, False),
    (128052, "qwen",  2, "high",     None,         7,   None, None, False),
    (145471, "qwen",  2, "low",      None,         5,   None, None, False),
    (117551, "qwen",  3, "med",      None,         5,   None, None, False),
    (37230,  "qwen",  5, "high",     None,        14,   None, None, False),
    (73803,  "qwen",  5, "med-high", None,         5,   None, None, False),
    (89363,  "qwen",  5, "med",      None,        14,   None, None, False),
    (73791,  "qwen",  7, "med",      None,         8,   None, None, False),
    (29908,  "qwen", 11, "med",      None,         5,   None, None, False),
    (20990,  "qwen", 12, "high",     None,        15,   None, None, False),
    (105490, "qwen",  2, "high",     None,        16,   None, None, False),  # sec 11.1
    (60751,  "qwen", 10, None,       "I-THIN",     2,   None, None, False),
    (90863,  "qwen", 10, None,       "I-THIN",     2,      2, None, False),
    (134801, "qwen", 10, None,       "I-THIN",     2,   None, None, False),
    (15095,  "qwen", 10, None,       "I-THIN",     6,   None, None, False),
    (15430,  "qwen", 10, "med",      "I-DIVERSE", 16,   None, None, False),
    (86258,  "qwen", 10, "med",      "I-DIVERSE", 14,   None, None, False),
    (159845, "qwen", 10, "med",      "I-DIVERSE",  9,   None, None, False),
    (120545, "qwen", 10, "med",      "I-DIVERSE", 16,   None, None, False),
    (124705, "qwen", 10, "med",      "I-DIVERSE", 15,   None, None, False),
    (128788, "qwen", 10, "med",      "I-DIVERSE", 16,   None, None, False),
    (84087,  "qwen", 10, "med",      "I-DIVERSE", 12,   None, None, False),
    (137584, "qwen", 10, "med",      "I-DIVERSE", 12,   None, None, False),
    (81977,  "qwen", 10, "med",      "I-DIVERSE", 15,   None, None, False),
    (151841, "qwen", 10, "med",      "I-DIVERSE", 14,   None, None, False),
    (65931,  "qwen", 10, "med",      "I-DIVERSE", 12,  15318, None, False),
    (72648,  "qwen", 10, "med",      "I-DIVERSE", 14,   None, None, False),
    (10455,  "qwen", 10, "med",      "I-DIVERSE", 15,   None, None, False),
    (140622, "qwen", 10, "med",      "I-DIVERSE", 16,   None, None, False),
    (135599, "qwen", 10, "med",      "I-DIVERSE", 13,   None, None, False),
    (103491, "qwen", 10, "med",      "I-DIVERSE", 14,   None, None, False),
    # ---- GEMMA, section 3 (early rows; six confidences do not exist, sec 1) ----
    (3039,   "gemma", 4, None,       None,      None,   None, 10, True),
    # 3070: sec 12.1 reconciliation. Recorded class 9 was a passage-level call made without
    # markers; markers are 16/16 coordinating conjunctions. Class 12 by sec 13.3 prong 1(b) +
    # prong 2, on the 869 and 1041 precedents. pre_marker_class stays 9 (sec 1 is immutable).
    # Bucket-neutral: 9 and 12 are both denominator-only.
    (3070,   "gemma", 12, None,      None,      None,   None,  9, False),
    (3169,   "gemma", 11, None,      None,      None,   None, 11, False),
    (3349,   "gemma", 3, None,       None,      None,   None,  3, False),
    (3358,   "gemma", 9, None,       None,      None,   None,  9, False),
    (3648,   "gemma", 11, None,      None,      None,   None, 11, False),
    (4090,   "gemma", 10, "med",     "I-DIVERSE", None, None, 10, False),
    (4572,   "gemma", 11, "med-high", None,     None,   None, 11, False),
    (5094,   "gemma", 2, None,       None,      None,   None,  2, False),
    (5231,   "gemma", 12, None,      None,      None,   None,  2, False),
    (6515,   "gemma", 10, "med",     "I-DIVERSE", None, None, 10, False),
    (7055,   "gemma", 11, "med",     None,      None,   None, 11, False),
    (212,    "gemma", 9, "med",      None,      None,   None,  9, False),
    (976,    "gemma", 7, "med-high", None,      None,   None,  7, False),
    # ---- GEMMA, section 6 (calibration overlap ten, marker-informed) ----
    (9012,   "gemma", 4, "high",     None,        16,   None, None, False),
    (9105,   "gemma", 12, "med",     None,        16,   None, None, False),  # sec 13.3 retrofit
    (11029,  "gemma", 2, "high",     None,        16,   None, None, False),
    (11149,  "gemma", 9, "med",      None,        16,   None, None, False),
    (11763,  "gemma", 12, "med",     None,        16,   None, None, False),  # sec 13.3 retrofit
    (12403,  "gemma", 11, "med",     None,        16,   None, None, False),
    (12449,  "gemma", 11, "high",    None,        16,   None, None, False),
    (13746,  "gemma", 10, "med",     "I-AMBIGUOUS", 16, None, None, False),
    (13825,  "gemma", 2, "high",     None,        16,   None, None, False),
    (14719,  "gemma", 11, "med",     None,        16,   None, None, False),
    # ---- GEMMA, section 8 (nine relay-parked rows, closed from markers) ----
    (819,    "gemma", 11, "low",     None,      None,   None, None, False),  # prose: med-low
    (869,    "gemma", 12, "med",     None,      None,   None, None, False),
    (1041,   "gemma", 12, "high",    None,      None,   None, None, False),
    (1423,   "gemma", 3, "high",     None,      None,   None, None, False),
    (2582,   "gemma", 7, "med",      None,      None,   None, None, False),
    (2848,   "gemma", 10, "med",     "I-DIVERSE", None, None, None, False),
    (7164,   "gemma", 7, "high",     None,      None,   None, None, False),
    (7314,   "gemma", 2, "high",     None,      None,   None, None, False),
    (8024,   "gemma", 11, "med-high", None,     None,   None, None, False),
    # ---- GEMMA, section 9 (the last seven) ----
    (7223,   "gemma", 10, "med",     "I-SILENT", None,  None, None, False),
    (7623,   "gemma", 12, "high",    None,      None,   None, None, False),
    (8667,   "gemma", 10, None,      "I-THIN",  None,      2, None, False),
    (9115,   "gemma", 2, "high",     None,      None,   None, None, False),
    (11270,  "gemma", 10, "med",     "I-DIVERSE", None, None, None, False),
    (13848,  "gemma", 11, "med",     None,      None,   None, None, False),
    (15054,  "gemma", 11, "high",    None,      None,   None, None, False),
]

FIELDS = ["feature_idx", "column", "class", "confidence", "reason_code",
          "distinct_sources", "n_firings", "pre_marker_class",
          "marker_driven_numerator_move", "disposition"]

out = []
for idx, col, cls, conf, code, src, fir, pre, mv in ROWS:
    assert isinstance(idx, int) and idx > 0, idx
    assert col in ("gemma", "qwen"), idx
    assert isinstance(cls, int) and 1 <= cls <= 12, idx
    assert conf in CONF, idx
    assert code in CODE, idx
    assert src is None or (isinstance(src, int) and src > 0), idx
    assert fir is None or (isinstance(fir, int) and fir > 0), idx
    assert pre is None or (isinstance(pre, int) and 1 <= pre <= 12), idx
    assert isinstance(mv, bool), idx
    out.append(dict(zip(FIELDS, [idx, col, cls, conf, code, src, fir, pre, mv,
                                 "classified"])))

idxs = [r["feature_idx"] for r in out]
assert len(idxs) == len(set(idxs)) == 80, (len(idxs), len(set(idxs)))
cols = Counter(r["column"] for r in out)
assert cols["qwen"] == 40 and cols["gemma"] == 40, cols
assert all(r["disposition"] == "classified" for r in out)
assert all(set(r) == set(FIELDS) for r in out)

with open("reports/adjudication_ledger_r1.canonical.json", "w",
          encoding="utf-8", newline="\n") as f:
    json.dump(out, f, indent=2, ensure_ascii=False)
    f.write("\n")

print("rows", len(out), dict(cols))
# Deliberately NOT printed: any per-class or per-bucket count. A class histogram plus the
# fixed class->bucket mapping IS the composition, and Rater 1 is barred from computing it.
print("classes present (set, not counts)", sorted({r["class"] for r in out}))
print("pre_marker_class present", sum(r["pre_marker_class"] is not None for r in out))
print("numerator moves", sum(r["marker_driven_numerator_move"] for r in out))
