import json

import pytest

from stardust.cli import (
    rde,
    rd,
    ensureWhitespace,
    StringIdx,
    parse_idx,
    barstr,
    wrap_text,
    SettingsCLI,
)


# ------------------------------------------------------------------
# rde
# ------------------------------------------------------------------

def test_rde_zero():
    assert rde(0) == "0"


def test_rde_engineering_notation():
    assert rde(1234.5678) == "1.23e3"


def test_rde_si_prefix():
    assert rde(1500, use_si_prefix=True, unit="V") == "1.5kV"


def test_rde_negative_value():
    assert rde(-2500) == "-2.5e3"


def test_rde_no_exp_suffix_uses_times_notation():
    assert rde(5000, exp_suffix=False) == "5×10^3"


def test_rde_infinite_and_nan_short_circuit():
    assert rde(float("inf")) == "inf"
    assert rde(float("nan")) == "nan"


def test_rde_exponent_zero_has_no_suffix():
    assert rde(42) == "42"


# ------------------------------------------------------------------
# rd
# ------------------------------------------------------------------

def test_rd_rounds_to_decimals():
    assert rd(3.14159, 2) == "3.14"


def test_rd_none_returns_nan_string():
    assert rd(None) == "NaN"


def test_rd_default_two_decimals():
    assert rd(1.005) == "1.0"  # binary float repr of 1.005 rounds down; documents actual behavior
    assert isinstance(rd(1.005), str)


# ------------------------------------------------------------------
# ensureWhitespace
# ------------------------------------------------------------------

def test_ensure_whitespace_adds_padding():
    assert ensureWhitespace("a+b-c", "+-") == "a + b - c"


def test_ensure_whitespace_no_op_when_already_padded():
    assert ensureWhitespace("a + b", "+") == "a + b"


def test_ensure_whitespace_at_string_edges():
    # A target at position 0 only gets trailing padding (no char precedes it
    # to pad before); symmetric for a target at the last position.
    assert ensureWhitespace("+a", "+") == "+ a"
    assert ensureWhitespace("a+", "+") == "a +"


# ------------------------------------------------------------------
# parse_idx / StringIdx
# ------------------------------------------------------------------

def test_parse_idx_splits_on_default_delim():
    result = parse_idx("hello world  foo")
    assert [r.str for r in result] == ["hello", "world", "foo"]


def test_parse_idx_tracks_start_indices():
    result = parse_idx("hello world")
    assert result[0].idx == 0
    assert result[1].idx == 6


def test_stringidx_repr_contains_index_and_value():
    s = StringIdx("abc", 3)
    assert "abc" in str(s)
    assert "3" in str(s)


# ------------------------------------------------------------------
# barstr
# ------------------------------------------------------------------

def test_barstr_pads_to_width():
    result = barstr("hi", width=10)
    assert len(result) == 10
    assert "hi" in result


def test_barstr_no_pad_flag():
    result = barstr("hi", width=10, pad=False)
    assert "hi" in result
    assert len(result) == 10


# ------------------------------------------------------------------
# wrap_text
# ------------------------------------------------------------------

def test_wrap_text_wraps_long_lines():
    result = wrap_text("a b c d e f g", width=5)
    assert all(len(line) <= 5 for line in result.split("\n"))


def test_wrap_text_preserves_explicit_newlines():
    result = wrap_text("line one\nline two", width=80)
    assert result.split("\n") == ["line one", "line two"]


# ------------------------------------------------------------------
# SettingsCLI
# ------------------------------------------------------------------

def test_settings_cli_temp_mode_get_existing():
    s = SettingsCLI(None, temp_settings={"a": {"value": 1, "desc": "test"}})
    assert s.get("a") == {"value": 1, "desc": "test"}


def test_settings_cli_temp_mode_get_missing_creates_none():
    s = SettingsCLI(None, temp_settings={})
    assert s.get("missing") is None
    assert s.settings["missing"] is None


def test_settings_cli_temp_mode_save_is_noop(capsys):
    s = SettingsCLI(None, temp_settings={"a": {"value": 1, "desc": "d"}})
    s.save()
    captured = capsys.readouterr()
    assert "Cannot save when in temporary mode." in captured.out


def test_settings_cli_file_mode_loads_existing_file(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"x": {"value": 5, "desc": "d"}}))
    s = SettingsCLI(str(path))
    assert s.settings == {"x": {"value": 5, "desc": "d"}}


def test_settings_cli_file_mode_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        SettingsCLI(str(tmp_path / "missing.json"))


def test_settings_cli_save_writes_to_disk(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"x": {"value": 5, "desc": "d"}}))
    s = SettingsCLI(str(path))
    s.settings["x"]["value"] = 99
    s.save()
    on_disk = json.loads(path.read_text())
    assert on_disk["x"]["value"] == 99


def test_settings_cli_undo_reverts_to_last_saved(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"x": {"value": 5, "desc": "d"}}))
    s = SettingsCLI(str(path))
    s.settings["x"]["value"] = 999
    s.undo()
    assert s.settings["x"]["value"] == 5


def test_settings_cli_parse_value_bool():
    s = SettingsCLI(None, temp_settings={})
    assert s._parse_value(True, "yes") is True
    assert s._parse_value(True, "no") is False
    with pytest.raises(ValueError):
        s._parse_value(True, "maybe")


def test_settings_cli_parse_value_int():
    s = SettingsCLI(None, temp_settings={})
    assert s._parse_value(5, "10") == 10
    assert isinstance(s._parse_value(5, "10"), int)


def test_settings_cli_parse_value_float():
    s = SettingsCLI(None, temp_settings={})
    assert s._parse_value(1.5, "2.75") == pytest.approx(2.75)
