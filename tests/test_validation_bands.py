"""SS6 bands (ED-13): verdict assignment and verdict_basis."""

from interplab.validation.bands import apply_bands, load_bands


def _spec(decile_means):
    return {"decile_means": decile_means, "rubric_version": "v1", "judge_model": "m", "prompt_version": "v1"}


def _sens(status, rate=None, per_lang=None):
    return {"status": status, "word_absent_fire_rate": rate, "per_language": per_lang}


def _sel(neighbors):
    return {"neighbors": neighbors}


def test_all_healthy_is_green_with_full_basis():
    bands = load_bands()
    verdict, basis = apply_bands(
        specificity=_spec([2.9, 2.8, 2.7]),
        sensitivity=_sens("measured", 0.5, {"en": 0.5}),
        selectivity=_sel([{"index": 1, "cosine": 0.1, "note": "n"}]),
        probe={"gap": 0.02},
        bands=bands,
    )
    assert verdict == "green"
    assert basis == ["specificity", "sensitivity", "selectivity", "probe"]


def test_unavailable_sensitivity_excluded_from_basis_but_does_not_fail_verdict():
    bands = load_bands()
    verdict, basis = apply_bands(
        specificity=_spec([2.9, 2.8]),
        sensitivity=_sens("unavailable"),
        selectivity=_sel([{"index": 1, "cosine": 0.1, "note": "n"}]),
        probe={"gap": 0.02},
        bands=bands,
    )
    assert "sensitivity" not in basis
    assert verdict == "green"


def test_empty_decile_means_excludes_specificity_from_basis():
    bands = load_bands()
    _verdict, basis = apply_bands(
        specificity=_spec([]),
        sensitivity=_sens("unavailable"),
        selectivity=_sel([{"index": 1, "cosine": 0.1, "note": "n"}]),
        probe={"gap": 0.02},
        bands=bands,
    )
    assert "specificity" not in basis
    assert basis == ["selectivity", "probe"]


def test_empty_neighbors_excludes_selectivity_from_basis():
    bands = load_bands()
    _verdict, basis = apply_bands(
        specificity=_spec([2.9]),
        sensitivity=_sens("unavailable"),
        selectivity=_sel([]),
        probe={"gap": 0.02},
        bands=bands,
    )
    assert "selectivity" not in basis


def test_probe_always_in_basis():
    bands = load_bands()
    _verdict, basis = apply_bands(
        specificity=_spec([]), sensitivity=_sens("unavailable"), selectivity=_sel([]),
        probe={"gap": 0.02}, bands=bands,
    )
    assert basis == ["probe"]


def test_bad_probe_gap_drives_red_verdict():
    bands = load_bands()
    verdict, basis = apply_bands(
        specificity=_spec([2.9]), sensitivity=_sens("unavailable"), selectivity=_sel([]),
        probe={"gap": 0.9}, bands=bands,
    )
    assert verdict == "red"
    assert "probe" in basis


def test_high_neighbor_cosine_drives_red_selectivity():
    bands = load_bands()
    verdict, _basis = apply_bands(
        specificity=_spec([2.9]), sensitivity=_sens("unavailable"),
        selectivity=_sel([{"index": 1, "cosine": 0.99, "note": "n"}]),
        probe={"gap": 0.02}, bands=bands,
    )
    assert verdict == "red"


def test_cross_lingual_firing_never_participates():
    """Not a parameter of apply_bands at all -- structurally cannot
    influence the verdict."""
    import inspect

    sig = inspect.signature(apply_bands)
    assert "cross_lingual_firing" not in sig.parameters
