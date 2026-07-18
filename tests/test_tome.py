import json
import os

import h5py
import numpy as np
import pytest

from stardust.tome import dict_to_tome, tome_to_dict


@pytest.fixture
def tome_path(tmp_path):
    return str(tmp_path / "data.tome")


def roundtrip(data, path):
    assert dict_to_tome(data, path) is True
    return tome_to_dict(path)


# ------------------------------------------------------------------
# dict root — scalars
# ------------------------------------------------------------------

def test_roundtrip_scalar_types(tome_path):
    data = {
        "i": 42,
        "f": 3.14159,
        "s": "hello world",
        "b_true": True,
        "b_false": False,
        "c": 3 + 4j,
        "none": None,
    }
    out = roundtrip(data, tome_path)
    assert out == data
    assert isinstance(out["i"], int)
    assert isinstance(out["f"], float)
    assert isinstance(out["b_true"], bool)
    assert isinstance(out["b_false"], bool)
    assert isinstance(out["c"], complex)


def test_bool_is_not_read_back_as_int(tome_path):
    # bool is a subclass of int; the writer must special-case it or True/False
    # round-trip as 1/0 ints instead of bools.
    out = roundtrip({"flag": True}, tome_path)
    assert out["flag"] is True


def test_unicode_string_roundtrip(tome_path):
    data = {"s": "héllo wörld 漢字 \U0001F389"}
    out = roundtrip(data, tome_path)
    assert out == data


def test_empty_string_roundtrip(tome_path):
    out = roundtrip({"s": ""}, tome_path)
    assert out["s"] == ""


# ------------------------------------------------------------------
# dict root — nested dicts
# ------------------------------------------------------------------

def test_roundtrip_nested_dict(tome_path):
    data = {"a": {"b": {"c": [1, 2, 3], "d": "leaf"}}, "top": 1}
    out = roundtrip(data, tome_path)
    assert out == data


def test_roundtrip_empty_dict(tome_path):
    out = roundtrip({}, tome_path)
    assert out == {}


def test_roundtrip_empty_nested_dict(tome_path):
    data = {"outer": {}}
    out = roundtrip(data, tome_path)
    assert out == data


def test_non_string_keys_stringified(tome_path):
    # dict_to_tome writes with str(k); HDF5 group/dataset names are always
    # strings, so integer keys come back as their string form.
    data = {1: "one", 2: "two"}
    assert dict_to_tome(data, tome_path) is True
    out = tome_to_dict(tome_path)
    assert out == {"1": "one", "2": "two"}


# ------------------------------------------------------------------
# lists
# ------------------------------------------------------------------

def test_roundtrip_list_of_str(tome_path):
    data = {"names": ["alice", "bob", "carol"]}
    out = roundtrip(data, tome_path)
    assert out == data
    assert all(isinstance(x, str) for x in out["names"])


def test_roundtrip_empty_list(tome_path):
    data = {"empty": []}
    out = roundtrip(data, tome_path)
    assert out["empty"] == []


def test_roundtrip_numeric_list_int(tome_path):
    data = {"nums": [1, 2, 3, 4, 5]}
    out = roundtrip(data, tome_path)
    assert out["nums"] == data["nums"]


def test_roundtrip_numeric_list_float(tome_path):
    data = {"nums": [1.5, 2.25, -3.75]}
    out = roundtrip(data, tome_path)
    assert out["nums"] == pytest.approx(data["nums"])


# ------------------------------------------------------------------
# list[dict] — nested value (pre-existing feature)
# ------------------------------------------------------------------

def test_roundtrip_list_of_dicts_nested_value(tome_path):
    data = {"items": [{"x": 1}, {"x": 2, "y": 3}]}
    out = roundtrip(data, tome_path)
    assert out == data


def test_roundtrip_list_of_dicts_preserves_order(tome_path):
    data = {"items": [{"i": i} for i in range(15)]}
    out = roundtrip(data, tome_path)
    # keys "0".."14" sort lexicographically, not numerically, unless the
    # reader sorts by int() — verify order survives past index 9.
    assert out == data
    assert [d["i"] for d in out["items"]] == list(range(15))


# ------------------------------------------------------------------
# list[dict] as the *root* object — the new feature
# ------------------------------------------------------------------

def test_list_of_dicts_as_root(tome_path):
    data = [{"x": 7}, {"x": 8, "y": 10}]
    assert dict_to_tome(data, tome_path) is True
    out = tome_to_dict(tome_path)
    assert out == data
    assert isinstance(out, list)


def test_list_of_dicts_as_root_preserves_order(tome_path):
    data = [{"i": i, "sq": i * i} for i in range(15)]
    out = roundtrip(data, tome_path)
    assert out == data
    assert [d["i"] for d in out] == list(range(15))


def test_list_of_dicts_as_root_with_nested_structures(tome_path):
    data = [
        {"name": "a", "values": [1, 2, 3], "meta": {"ok": True}},
        {"name": "b", "values": [], "meta": {"ok": False, "tags": ["x", "y"]}},
    ]
    out = roundtrip(data, tome_path)
    assert out == data


def test_empty_list_as_root(tome_path):
    assert dict_to_tome([], tome_path) is True
    out = tome_to_dict(tome_path)
    assert out == []


def test_single_dict_in_list_root(tome_path):
    data = [{"only": "one"}]
    out = roundtrip(data, tome_path)
    assert out == data


def test_list_root_rejects_non_dict_elements(tome_path):
    # Root lists are only defined for list[dict]; anything else should fail
    # the write cleanly (return False) rather than silently mis-encoding.
    assert dict_to_tome([1, 2, 3], tome_path) is False


def test_list_root_rejects_mixed_dict_and_non_dict(tome_path):
    assert dict_to_tome([{"a": 1}, 2], tome_path) is False


# ------------------------------------------------------------------
# numpy arrays
# ------------------------------------------------------------------

@pytest.mark.parametrize("dtype", ["int8", "int32", "int64", "float32", "float64"])
def test_roundtrip_numpy_array_dtype_preserved(tome_path, dtype):
    arr = np.array([1, 2, 3, 4], dtype=dtype)
    out = roundtrip({"arr": arr}, tome_path)
    assert isinstance(out["arr"], np.ndarray)
    assert out["arr"].dtype == np.dtype(dtype)
    np.testing.assert_array_equal(out["arr"], arr)


def test_roundtrip_numpy_bool_array(tome_path):
    arr = np.array([True, False, True])
    out = roundtrip({"arr": arr}, tome_path)
    assert out["arr"].dtype == np.dtype(bool)
    np.testing.assert_array_equal(out["arr"], arr)


def test_roundtrip_numpy_2d_array(tome_path):
    arr = np.arange(12).reshape(3, 4)
    out = roundtrip({"arr": arr}, tome_path)
    np.testing.assert_array_equal(out["arr"], arr)


def test_roundtrip_numpy_string_array(tome_path):
    arr = np.array(["red", "green", "blue"])
    out = roundtrip({"arr": arr}, tome_path)
    assert list(out["arr"]) == ["red", "green", "blue"]


def test_roundtrip_numpy_empty_array(tome_path):
    arr = np.array([], dtype=float)
    out = roundtrip({"arr": arr}, tome_path)
    assert len(out["arr"]) == 0


# ------------------------------------------------------------------
# fallback JSON encoding for otherwise-unsupported types
# ------------------------------------------------------------------

def test_tuple_roundtrips_as_list(tome_path):
    # JSON has no tuple type, so this is a documented, expected conversion
    # rather than a bug — the fallback path is exercised here.
    data = {"t": (1, 2, 3)}
    out = roundtrip(data, tome_path)
    assert out["t"] == [1, 2, 3]


def test_unsupported_type_write_fails(tome_path):
    # sets aren't JSON-serialisable, and there's no dedicated branch for
    # them either, so the write should fail rather than silently drop data.
    ok = dict_to_tome({"bad": {1, 2, 3}}, tome_path)
    assert ok is False


def test_json_backup_written_on_failure(tmp_path):
    path = str(tmp_path / "bad.tome")
    ok = dict_to_tome({"bad": {1, 2, 3}}, path, use_json_backup=True)
    assert ok is False
    backup = tmp_path / "bad.json"
    assert backup.exists()
    with open(backup) as f:
        backup_data = json.load(f)
    assert backup_data == {"bad": "{1, 2, 3}"}  # default=str fallback


def test_no_json_backup_when_not_requested(tmp_path):
    path = str(tmp_path / "bad.tome")
    dict_to_tome({"bad": {1, 2, 3}}, path, use_json_backup=False)
    assert not (tmp_path / "bad.json").exists()


# ------------------------------------------------------------------
# read-path error handling
# ------------------------------------------------------------------

def test_read_missing_file_returns_none(tmp_path):
    assert tome_to_dict(str(tmp_path / "does_not_exist.tome")) is None


def test_read_corrupted_file_returns_none(tmp_path):
    path = tmp_path / "corrupt.tome"
    path.write_bytes(b"not a real hdf5 file")
    assert tome_to_dict(str(path)) is None


# ------------------------------------------------------------------
# show_detail flag (verbose logging path) should not alter behavior
# ------------------------------------------------------------------

def test_show_detail_does_not_change_result(tome_path, capsys):
    data = {"a": 1, "b": [{"x": 1}, {"x": 2}]}
    assert dict_to_tome(data, tome_path, show_detail=True) is True
    captured = capsys.readouterr()
    assert "Writing key=" in captured.out
    out = tome_to_dict(tome_path)
    assert out == data


# ------------------------------------------------------------------
# file-format sanity: root __pytype__ attr matches what was written
# ------------------------------------------------------------------

def test_root_pytype_attr_dict(tome_path):
    dict_to_tome({"a": 1}, tome_path)
    with h5py.File(tome_path, "r") as fh:
        assert fh.attrs["__pytype__"] == "dict"


def test_root_pytype_attr_list_of_dicts(tome_path):
    dict_to_tome([{"a": 1}], tome_path)
    with h5py.File(tome_path, "r") as fh:
        assert fh.attrs["__pytype__"] == "list_of_dicts"


# ------------------------------------------------------------------
# mixed-type / ragged lists — fall back to per-element JSON encoding on
# write; the read path must json.loads each element back rather than
# leaving it as a JSON-text string.
# ------------------------------------------------------------------

def test_mixed_type_list_full_roundtrip(tome_path):
    data = {"mixed": [1, "a", 2.5]}
    out = roundtrip(data, tome_path)
    assert out == data


def test_ragged_nested_list_full_roundtrip(tome_path):
    data = {"ragged": [[1, 2], [3, 4, 5]]}
    out = roundtrip(data, tome_path)
    assert out == data


def test_list_of_str_not_double_encoded(tome_path):
    # Regression guard for the elem_encoding marker: a plain list[str] must
    # NOT be routed through json.loads on read (it never goes through the
    # object-dtype JSON-fallback branch on write).
    data = {"names": ["alice", "bob"]}
    out = roundtrip(data, tome_path)
    assert out == data
