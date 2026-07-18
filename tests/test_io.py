import io as _io
import os

import numpy as np
import pytest

from stardust.io import (
    dict_to_hdf,
    hdf_to_dict,
    dict_summary,
    dumpsecure,
    loadsecure,
    locate_drive,
)


@pytest.fixture
def hdf_path(tmp_path):
    return str(tmp_path / "data.h5")


# ------------------------------------------------------------------
# dict_to_hdf / hdf_to_dict
# ------------------------------------------------------------------

def test_hdf_roundtrip_basic(hdf_path):
    data = {"a": 1, "b": [1, 2, 3], "nested": {"c": "hello"}}
    assert dict_to_hdf(data, hdf_path) is True
    out = hdf_to_dict(hdf_path)
    # Scalars/lists come back as numpy int64 rather than native int, per the
    # documented behavior of read_level (fh[k][()] is not coerced further).
    assert int(out["a"]) == 1
    assert [int(x) for x in out["b"]] == [1, 2, 3]
    assert out["nested"] == {"c": "hello"}


def test_hdf_roundtrip_to_lists_true_gives_python_lists(hdf_path):
    data = {"a": [1, 2, 3]}
    dict_to_hdf(data, hdf_path)
    out = hdf_to_dict(hdf_path, to_lists=True)
    assert isinstance(out["a"], list)


def test_hdf_roundtrip_to_lists_false_gives_ndarray(hdf_path):
    data = {"a": [1, 2, 3]}
    dict_to_hdf(data, hdf_path)
    out = hdf_to_dict(hdf_path, to_lists=False)
    assert isinstance(out["a"], np.ndarray)


def test_hdf_string_list_decoded_by_default(hdf_path):
    data = {"s": ["x", "y", "z"]}
    dict_to_hdf(data, hdf_path)
    out = hdf_to_dict(hdf_path)  # to_lists=True by default
    assert out["s"] == ["x", "y", "z"]
    assert all(isinstance(x, str) for x in out["s"])


def test_hdf_read_missing_file_raises(tmp_path):
    # Unlike tome_to_dict, hdf_to_dict does not guard file-open with a
    # try/except, so a missing file propagates h5py's own error.
    with pytest.raises(Exception):
        hdf_to_dict(str(tmp_path / "missing.h5"))


def test_hdf_write_failure_reports_false(hdf_path):
    ok = dict_to_hdf({"x": object()}, hdf_path, use_json_backup=False)
    assert ok is False


def test_hdf_write_failure_with_json_backup_still_reports_false(tmp_path):
    path = str(tmp_path / "bad.h5")
    ok = dict_to_hdf({"x": object()}, path, use_json_backup=True)
    assert ok is False
    assert (tmp_path / "bad.json").exists()


# ------------------------------------------------------------------
# dict_summary — smoke tests only (this is a print-formatting helper)
# ------------------------------------------------------------------

@pytest.mark.parametrize("verbose", [0, 1, 2])
def test_dict_summary_does_not_crash(capsys, verbose):
    data = {"a": 1, "b": [1, 2, 3], "nested": {"c": "x" * 200}, "empty_list": []}
    dict_summary(data, verbose=verbose)
    captured = capsys.readouterr()
    assert "a" in captured.out
    assert "nested" in captured.out


# ------------------------------------------------------------------
# dumpsecure / loadsecure
# ------------------------------------------------------------------

def test_secure_roundtrip():
    buf = _io.StringIO()
    dumpsecure(buf, {"secret": 42}, "correct horse", plain={"note": "hi"})
    buf.seek(0)
    plain, encrypted = loadsecure(buf, "correct horse")
    assert plain == {"note": "hi"}
    assert encrypted == {"secret": 42}


def test_secure_wrong_password_raises_valueerror():
    buf = _io.StringIO()
    dumpsecure(buf, {"secret": 42}, "correct horse")
    buf.seek(0)
    with pytest.raises(ValueError):
        loadsecure(buf, "wrong password")


def test_secure_default_plain_is_empty_dict():
    buf = _io.StringIO()
    dumpsecure(buf, {"secret": 1}, "pw")
    buf.seek(0)
    plain, _ = loadsecure(buf, "pw")
    assert plain == {}


# ------------------------------------------------------------------
# locate_drive — light smoke test; scanning real drive letters/mounts
# isn't something a unit test can meaningfully sandbox.
# ------------------------------------------------------------------

def test_locate_drive_no_match_returns_none():
    result = locate_drive("__stardust_test_id_that_should_never_exist__", silence_output=True)
    assert result is None
