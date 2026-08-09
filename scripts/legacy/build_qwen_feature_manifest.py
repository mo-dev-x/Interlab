"""Build a Qwen feature manifest in the SAME schema
gemma3_sweep.write_feature_manifest() emits, from
results/characterize_lite/rwu04lpb_taxonomy40/characterize_lite.json (64
features already characterized offline -- no cluster, no network).

Field mapping from characterize_lite's own names to Gemma-manifest names:
    firing_rate      -> density
    max_activation   -> maxActApprox
    top_examples     -> source for the companion snippets file (see
                         write_qwen_tool_snippets) and for label
                         verification; not copied into the manifest itself,
                         matching Gemma's manifest (which also keeps
                         snippets in a separate file).

selectivity_vs_median is NOT used for selection. Verified against the raw
data (see build script history / commit message): it is EXACTLY
firing_rate / population_median_firing_rate, a density ratio, not a
specificity or monosemanticity measure -- despite its name. Surfaced here
(if at all) under an honest name, never the source name alone, per the
field-naming lesson this repo has already paid for twice on OUTPUT
artifacts and once here on an INPUT artifact.

Selection procedure (PM-directed, superseding an earlier selectivity-based
draft that turned out to double-count firing_rate):
    1. Rank all 64 features by firing_rate DESCENDING (Gemma's own 9 were
       drawn from the ACTIVE end of its density range, 0.000782-0.021364 --
       not the rare end).
    2. Take the top 15 as the candidate pool.
    3. Apply the real bar: read top_examples for each candidate and reject
       any whose label does not survive them (mirrors Gemma's own
       REJECTED_FEATURE_IDXS bar exactly, with reasons recorded).
    4. Keep 9 + 1 optional from the survivors, in ranked order. Do not
       reach further down the ranking to manufacture domain-class spread
       if the survivors don't span it.
    5. Tiebreaker among features that already passed step 3 only: prefer
       higher mean_activation_when_firing. This is a DEPARTURE from
       Gemma's procedure (Gemma had no such tiebreaker) -- recorded as
       such, and not decisive for any slot in the run that produced this
       manifest (no genuine near-tie arose in firing_rate rank alone).

The control feature is a single GLOBAL random draw via
gemma3_sweep.pick_control_feature_idx (same mechanism as Gemma, per
explicit instruction not to introduce an unmatched control axis between
the two columns) -- NOT characterize_lite's own per-feature
matched_control_feature, which is surfaced as displayed metadata only.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "legacy"))

import gemma3_sweep as gemma  # noqa: E402

CHARACTERIZE_LITE_PATH = REPO_ROOT / "results" / "characterize_lite" / "rwu04lpb_taxonomy40" / "characterize_lite.json"
OUT_DIR = REPO_ROOT / "results" / "qwen_sweep"
MANIFEST_FILENAME = "feature_manifest.json"
SNIPPETS_FILENAME = "qwen_tool_snippets.json"

CONTROL_RNG_SEED = 1337  # same default gemma3_sweep.py uses

MODEL_ID = "Qwen/Qwen2.5-14B-Instruct"
SAE_RELEASE = gemma.QWEN_REFERENCE_METADATA["checkpoint_id"]  # "rwu04lpb" -- not a HF hub release; this checkpoint has no repo_id
SAE_REPO_ID = None  # locally trained checkpoint, never published to a HF hub repo -- see sae_repo_id_caveat
LAYER = gemma.QWEN_REFERENCE_METADATA["layer"]
WIDTH = gemma.QWEN_REFERENCE_METADATA["d_sae"]
L0_VARIANT = f"topk_{gemma.QWEN_REFERENCE_METADATA['topk_k']}"  # architecture is topk, not JumpReLU -- no L0 concept; this is the closest analogous label
SAE_ID = f"layer_{LAYER}_width_{WIDTH}_{L0_VARIANT}"

MAX_ACT_APPROX_CAVEAT = (
    "maxActApprox here is Qwen's own max_activation (~30-50 typical), NOT comparable to "
    "Gemma's maxActApprox (~2000-10000+): different SAE architectures (topk vs JumpReLU), "
    "different training corpora and token counts, different activation scales entirely. "
    "Never compare these two columns' maxActApprox numbers directly."
)

LABELS_AUTO_DERIVED_CAVEAT = (
    "Labels in this manifest are auto-derived by reading top_examples for a consistent "
    "trailing token/phrase pattern and are NOT human-adjudicated. Gemma's 9 labels went "
    "through the project's full adjudication process; these did not and will not this week."
)

CAUSAL_SCREENING_CAVEAT = (
    "These 9 features are label-verified (the auto-derived label was checked against "
    "top_examples and survived) but have NOT been causally screened. Gemma's 9 went through "
    "a 1736-record steer/ablate sweep and a 288-record necessity run; these features have had "
    "neither, and will not get either this week."
)

DENSITY_CROSS_SAE_CAVEAT = (
    "Absolute density (firing_rate) is not comparable across these two SAEs. Qwen's SAE is "
    "163840-wide vs Gemma's 16384-wide (10x) -- a Qwen feature firing at the same rate as a "
    "Gemma feature corresponds to a much smaller share of the width-163840 feature budget "
    "firing at all, for reasons of SAE width, not model behavior. 'Qwen's features are rarer' "
    "would be a false reading of the raw density numbers alone."
)

SELECTIVITY_VS_MEDIAN_CAVEAT = (
    "characterize_lite.json's own 'selectivity_vs_median' field is named for specificity but "
    "computes firing_rate / population_median_firing_rate -- a pure density ratio, verified "
    "exactly (max abs diff 0.0 across all 64 features). It carries zero information beyond "
    "density and was NOT used to select these features. Surfaced here (as "
    "density_ratio_to_population_median) under an honest name, not the source name alone."
)

TIEBREAKER_DEPARTURE_NOTE = (
    "Departure from Gemma's procedure: Gemma's selection had no tiebreaker beyond the density "
    "band and snippet verification. This selection adds one -- among candidates that already "
    "passed snippet verification, prefer higher mean_activation_when_firing -- but it was not "
    "decisive for any of the 10 slots filled here (no two verified candidates were close enough "
    "in firing-rate rank to need it); recorded because the rule exists and could bind on a "
    "future re-selection, not because it changed this one. Feature 105490's "
    "mean_activation_when_firing (13.836) is notably high against a ~5 typical among the other "
    "9 candidates -- consistent with the tiebreaker's intent even though it wasn't invoked."
)

# --- Selection (see module docstring for full procedure) --------------------

SELECTED_FEATURES: list[dict[str, Any]] = [
    {"idx": 89549, "label": "prepositions (of/to/for/against) trailing a truncated complement", "domain_class": "syntax"},
    {"idx": 33008, "label": "the paired quantifier 'two'/'both'", "domain_class": "numeric"},
    {"idx": 105490, "label": "the demonstrative pronoun 'that' as a clause-final object", "domain_class": "syntax"},
    {"idx": 20990, "label": "sentence-initial 'As' opening a new clause", "domain_class": "syntax"},
    {"idx": 107244, "label": "title-case phrase completions (titles/headings)", "domain_class": "syntax", "low_confidence": True},
    {"idx": 59622, "label": "'line' in music/festival 'line-up' contexts", "domain_class": "entity"},
    {"idx": 45344, "label": "the idiom 'play(ed) a [pivotal/major/vital] role'", "domain_class": "syntax"},
    {"idx": 37230, "label": "the brand name 'iPod'", "domain_class": "entity"},
    {"idx": 134801, "label": "'company' following a corporate-descriptor phrase", "domain_class": "entity",
     "verification_note": "top_examples heavily dominated by one document (BD's own press description, ~6 of 12); "
                           "at least one independent confirming example from a different company ('the world's "
                           "leading live entertainment and ecommerce company') keeps the word-level pattern real, "
                           "but treat with more caution than the other 8."},
]
OPTIONAL_FEATURE: dict[str, Any] = {
    "idx": 145471, "label": "'Best' in awards/rankings contexts (readers' poll)", "domain_class": "abstract",
    "verification_note": "top_examples show heavy overlap with one recurring readers'-poll context "
                          "('Atlanta Creative Loafing's Best', ~4 of 12); word-level 'Best' pattern still holds "
                          "across genuinely distinct award mentions ('voted as Best DJ', 'Readers Poll Winner'), "
                          "but treat with more caution than the primary 9.",
}

# Verified (label survives top_examples) but not selected -- ranked below
# the top-9-plus-optional cutoff by firing_rate. Recorded so a future
# editor can see the full candidate pool's disposition, not just the
# winners and the outright rejects.
VERIFIED_NOT_SELECTED: list[dict[str, Any]] = [
    {"idx": 126804, "label": "the word family 'revise/revised/revision'", "domain_class": "syntax",
     "reason": "verified, clean pattern, ranked 11th by firing_rate -- outside the 9+1 cutoff"},
    {"idx": 11128, "label": "the word 'forecast' (weather forecasting)", "domain_class": "topic",
     "reason": "verified, clean pattern, ranked 12th by firing_rate -- outside the 9+1 cutoff; domain_class "
               "'topic' is not one of Gemma's six values -- none of Gemma's fit this feature honestly"},
]

REJECTED_FEATURES: list[dict[str, Any]] = [
    {"idx": 65931,
     "reason": "no consistent activating pattern across all 25 top_examples (technology/home/personal-life "
               "topics -- surrogate, cable modem, Domain Controller, fried rice, SSDI, water heaters, IP "
               "addresses -- with no shared token, phrase, or syntactic role). Falls inside Gemma's density "
               "band by firing_rate alone but does not survive snippet verification."},
    {"idx": 121794,
     "reason": "no consistent activating pattern (mixed named entities, phone/call-sign numbers, and unrelated "
               "phrases: 'Congressman', 'MIT OpenCourseWare', a phone number, a call sign, a name)."},
    {"idx": 70945,
     "reason": "top_examples dominated by a single recurring document/caption ('...dressed: The Queen...', "
               "'In her element:', 'Close:') with no independent confirming example from a different document -- "
               "unlike 134801/145471, which had at least one confirming instance outside the dominant document."},
]

DENSITY_BAND_DISCLOSURE = (
    "Gemma's 9 features span firing_rate/density [0.000782, 0.021364]. Exactly 8 of Qwen's 64 characterized "
    "features fall inside that exact band by firing_rate alone: 89549, 65931, 33008, 105490, 20990, 107244, "
    "59622, 45344. One of those eight (65931) failed snippet verification and was rejected (see rejected_features). "
    "The primary 9 therefore comprises 7 in-band survivors plus 2 features below Gemma's floor (37230 at "
    "0.000716, 134801 at 0.000673) promoted from further down the firing_rate ranking to fill the two open slots. "
    "This is not the '8 in-band, 1 below floor' split a first pass anticipated -- it is 7 and 2 -- because "
    "verification, not the density band alone, is the real gate."
)

DOMAIN_CLASS_SPREAD_DISCLOSURE = (
    "Gemma's 9 span 6 domain classes: instruction(1), entity(4), temporal(1), abstract(1), numeric(1), syntax(1). "
    "The primary 9 selected here span only 3: syntax(5: 89549, 105490, 20990, 107244, 45344), "
    "entity(3: 59622, 37230, 134801), numeric(1: 33008). Zero instruction, temporal, or abstract features survive "
    "in the top-9-by-firing-rate ranking. The optional 10th (145471) adds 'abstract', bringing the primary+optional "
    "total to 4 classes. Per instruction, this gap is disclosed rather than filled by reaching further down the "
    "ranking to manufacture spread."
)


def _selectivity_ratio_matches(feat: dict[str, Any], pop_median: float) -> bool:
    return abs(feat["firing_rate"] / pop_median - feat["selectivity_vs_median"]) < 1e-9


def build_manifest() -> dict[str, Any]:
    raw = json.loads(CHARACTERIZE_LITE_PATH.read_text(encoding="utf-8"))
    pop_median = raw["population_median_firing_rate"]
    raw_features = raw["features"]

    for idx_str, feat in raw_features.items():
        if not _selectivity_ratio_matches(feat, pop_median):
            raise ValueError(
                f"selectivity_vs_median no longer matches firing_rate/population_median_firing_rate for "
                f"feature {idx_str} -- the verified field-identity this build relies on has changed; stop "
                f"and re-derive rather than trusting a stale assumption."
            )

    def record_for(idx: int, extra: dict[str, Any]) -> dict[str, Any]:
        f = raw_features[str(idx)]
        return {
            "idx": idx,
            "label": extra["label"],
            "domain_class": extra["domain_class"],
            "maxActApprox": f["max_activation"],
            "maxActApprox_caveat": MAX_ACT_APPROX_CAVEAT,
            "density": f["firing_rate"],
            "sae_id": SAE_ID,
            "layer": LAYER,
            "width": WIDTH,
            "l0_variant": L0_VARIANT,
            "low_confidence": bool(extra.get("low_confidence", False)),
            # --- extensions beyond Gemma's schema, documented as such ---
            "density_ratio_to_population_median": f["selectivity_vs_median"],
            "density_ratio_to_population_median_caveat": SELECTIVITY_VS_MEDIAN_CAVEAT,
            "mean_activation_when_firing": f["mean_activation_when_firing"],
            "n_firings": f["n_firings"],
            "matched_control_feature": f["matched_control_feature"],
            "matched_control_firing_rate": f["matched_control_firing_rate"],
            "matched_control_max_activation": f["matched_control_max_activation"],
            "matched_control_caveat": (
                "Displayed metadata only -- NOT the control used by this manifest's own "
                "control_feature_idx, which is a single global random draw shared across all "
                "features (same mechanism as Gemma's), per explicit instruction not to introduce "
                "a second, unmatched control axis between the two columns."
            ),
            **({"verification_note": extra["verification_note"]} if "verification_note" in extra else {}),
        }

    feature_records = [record_for(f["idx"], f) for f in SELECTED_FEATURES]
    optional_record = record_for(OPTIONAL_FEATURE["idx"], OPTIONAL_FEATURE)

    exclude = (
        {f["idx"] for f in SELECTED_FEATURES}
        | {OPTIONAL_FEATURE["idx"]}
        | {r["idx"] for r in REJECTED_FEATURES}
        | {v["idx"] for v in VERIFIED_NOT_SELECTED}
    )
    control_feature_idx = gemma.pick_control_feature_idx(exclude=exclude, control_rng_seed=CONTROL_RNG_SEED, d_sae=WIDTH)

    checkpoint_hash = raw["checkpoint_hash"]

    return {
        "schema_note": (
            "One record per feature: idx, label, domain_class, maxActApprox, density, sae_id, layer, "
            "width, l0_variant, low_confidence, plus documented extensions beyond gemma3_sweep's schema "
            "(density_ratio_to_population_median, mean_activation_when_firing, n_firings, "
            "matched_control_feature and related fields). Open schema, same convention as Gemma's manifest."
        ),
        "maxActApprox_caveat": MAX_ACT_APPROX_CAVEAT,
        "sae_release": SAE_RELEASE,
        "sae_repo_id": SAE_REPO_ID,
        "sae_repo_id_caveat": "Locally trained checkpoint, never published to a HF hub repo -- unlike Gemma's sae_repo_id, this is genuinely None, not an omission.",
        "sae_repo_revision": checkpoint_hash,
        "model_id": MODEL_ID,
        "control_feature_idx": control_feature_idx,
        "control_rng_seed": CONTROL_RNG_SEED,
        "control_mechanism_note": (
            "Single global random draw via gemma3_sweep.pick_control_feature_idx (same mechanism as "
            "Gemma), not characterize_lite's own per-feature matched_control_feature -- kept identical "
            "across both columns so the control mechanism is not an additional unmatched axis."
        ),
        "labels_auto_derived_caveat": LABELS_AUTO_DERIVED_CAVEAT,
        "causal_screening_caveat": CAUSAL_SCREENING_CAVEAT,
        "density_cross_sae_caveat": DENSITY_CROSS_SAE_CAVEAT,
        "density_band_disclosure": DENSITY_BAND_DISCLOSURE,
        "domain_class_spread_disclosure": DOMAIN_CLASS_SPREAD_DISCLOSURE,
        "tiebreaker_departure_note": TIEBREAKER_DEPARTURE_NOTE,
        "features": feature_records,
        "optional_feature": optional_record,
        "verified_not_selected": VERIFIED_NOT_SELECTED,
        "rejected_features": REJECTED_FEATURES,
    }


def write_qwen_tool_snippets(manifest: dict[str, Any]) -> dict[str, list[str]]:
    raw = json.loads(CHARACTERIZE_LITE_PATH.read_text(encoding="utf-8"))
    raw_features = raw["features"]
    all_records = manifest["features"] + [manifest["optional_feature"]]
    snippets: dict[str, list[str]] = {}
    for rec in all_records:
        idx = rec["idx"]
        examples = raw_features[str(idx)]["top_examples"]
        snippets[str(idx)] = [ex["text"] for ex in examples]
    return snippets


def main() -> None:
    manifest = build_manifest()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path = OUT_DIR / MANIFEST_FILENAME
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    snippets = write_qwen_tool_snippets(manifest)
    snippets_path = OUT_DIR / SNIPPETS_FILENAME
    snippets_path.write_text(json.dumps(snippets, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"control_feature_idx={manifest['control_feature_idx']} (control_rng_seed={CONTROL_RNG_SEED})")
    print(f"manifest: {manifest_path}  sha256={hashlib.sha256(manifest_path.read_bytes()).hexdigest()}")
    print(f"snippets: {snippets_path}  sha256={hashlib.sha256(snippets_path.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
