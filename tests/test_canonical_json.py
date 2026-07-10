import pytest

from interplab.core.canonical_json import CanonicalizationError, canonicalize, canonicalize_str


def test_sorts_keys():
    assert canonicalize_str({"b": 1, "a": 2}) == '{"a":2,"b":1}'


def test_nested_sorting():
    assert canonicalize_str({"b": {"z": 1, "a": 2}, "a": 1}) == '{"a":1,"b":{"a":2,"z":1}}'


def test_no_insignificant_whitespace():
    assert canonicalize_str([1, 2, 3]) == "[1,2,3]"


def test_non_ascii_left_unescaped():
    assert canonicalize_str({"a": "café"}) == '{"a":"café"}'


def test_rejects_nan():
    with pytest.raises(CanonicalizationError):
        canonicalize_str({"a": float("nan")})


def test_rejects_infinity():
    with pytest.raises(CanonicalizationError):
        canonicalize_str({"a": float("inf")})


def test_rejects_non_finite_nested_in_list():
    with pytest.raises(CanonicalizationError):
        canonicalize_str({"a": [1, 2, {"b": float("nan")}]})


def test_bytes_output_is_utf8():
    assert canonicalize({"a": 1}) == b'{"a":1}'


def test_deterministic_across_equivalent_dicts():
    obj_a = {"z": 1, "a": [3, 2, 1], "m": {"y": 2, "x": 1}}
    obj_b = {"a": [3, 2, 1], "m": {"x": 1, "y": 2}, "z": 1}
    assert canonicalize_str(obj_a) == canonicalize_str(obj_b)
