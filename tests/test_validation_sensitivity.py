"""SS6 sensitivity (ED-13): status-bearing, complete-languages-only
aggregation, and the separate descriptive cross_lingual_firing field."""

from pathlib import Path

import pytest
import yaml

from interplab.validation.sensitivity import compute_sensitivity_and_cross_lingual_firing

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "synthetic_concepts"


@pytest.fixture
def zorbium():
    return yaml.safe_load((FIXTURES_DIR / "zorbium.yaml").read_text(encoding="utf-8"))


@pytest.fixture
def quixnorf():
    return yaml.safe_load((FIXTURES_DIR / "quixnorf.yaml").read_text(encoding="utf-8"))


def test_measured_when_a_complete_language_exists(tiny_hooked_transformer, tiny_sae, zorbium):
    hook_name = tiny_sae.cfg.metadata.hook_name
    sensitivity, _ = compute_sensitivity_and_cross_lingual_firing(
        tiny_hooked_transformer, tiny_sae, hook_name, 0, zorbium
    )
    assert sensitivity["status"] == "measured"
    assert sensitivity["word_absent_fire_rate"] is not None
    assert "en" in sensitivity["per_language"]


def test_unavailable_when_no_complete_language_exists(tiny_hooked_transformer, tiny_sae, quixnorf):
    """ED-13: unavailable carries nulls, never zeros."""
    hook_name = tiny_sae.cfg.metadata.hook_name
    sensitivity, _ = compute_sensitivity_and_cross_lingual_firing(
        tiny_hooked_transformer, tiny_sae, hook_name, 0, quixnorf
    )
    assert sensitivity["status"] == "unavailable"
    assert sensitivity["word_absent_fire_rate"] is None
    assert sensitivity["per_language"] is None


def test_unavailable_is_never_zero(tiny_hooked_transformer, tiny_sae, quixnorf):
    hook_name = tiny_sae.cfg.metadata.hook_name
    sensitivity, _ = compute_sensitivity_and_cross_lingual_firing(
        tiny_hooked_transformer, tiny_sae, hook_name, 0, quixnorf
    )
    assert sensitivity["word_absent_fire_rate"] != 0.0  # it's None, not 0.0
    assert sensitivity["word_absent_fire_rate"] is None


def test_only_complete_languages_feed_the_aggregate(tiny_hooked_transformer, tiny_sae, zorbium):
    """zorbium has en=complete and fr=probes_only -- fr must not appear in
    sensitivity.per_language, only in the separate cross_lingual_firing."""
    hook_name = tiny_sae.cfg.metadata.hook_name
    sensitivity, cross_lingual = compute_sensitivity_and_cross_lingual_firing(
        tiny_hooked_transformer, tiny_sae, hook_name, 0, zorbium
    )
    assert set(sensitivity["per_language"]) == {"en"}
    assert "fr" not in sensitivity["per_language"]
    assert set(cross_lingual) == {"fr"}


def test_cross_lingual_firing_is_none_when_no_probes_only_language_exists(tiny_hooked_transformer, tiny_sae, quixnorf):
    """quixnorf's only language (en) is probes_only, so it SHOULD populate
    cross_lingual_firing (not the complete-language sensitivity path)."""
    hook_name = tiny_sae.cfg.metadata.hook_name
    _, cross_lingual = compute_sensitivity_and_cross_lingual_firing(
        tiny_hooked_transformer, tiny_sae, hook_name, 0, quixnorf
    )
    assert cross_lingual is not None
    assert "en" in cross_lingual
    assert "probe_fire_rate" in cross_lingual["en"]


def test_cross_lingual_firing_never_appears_inside_sensitivity(tiny_hooked_transformer, tiny_sae, zorbium):
    hook_name = tiny_sae.cfg.metadata.hook_name
    sensitivity, _ = compute_sensitivity_and_cross_lingual_firing(
        tiny_hooked_transformer, tiny_sae, hook_name, 0, zorbium
    )
    assert "cross_lingual_firing" not in sensitivity
    assert "fr" not in str(sensitivity.get("per_language", {}))
