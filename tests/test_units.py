import pytest

from stardust.units import lin_to_dB, dB_to_lin, UnitConverter


# ------------------------------------------------------------------
# lin_to_dB / dB_to_lin
# ------------------------------------------------------------------

def test_lin_to_dB_default_20log():
    assert lin_to_dB(10) == pytest.approx(20.0)


def test_lin_to_dB_use10():
    assert lin_to_dB(10, use10=True) == pytest.approx(10.0)


def test_dB_to_lin_default_roundtrips_with_lin_to_dB():
    x = 3.5
    assert dB_to_lin(lin_to_dB(x)) == pytest.approx(x)


def test_dB_to_lin_default_20log():
    assert dB_to_lin(20) == pytest.approx(10.0)


def test_dB_to_lin_use10():
    assert dB_to_lin(20, use10=True) == pytest.approx(100.0)


def test_dB_to_lin_use10_roundtrips_with_lin_to_dB_use10():
    x = 7.5
    assert dB_to_lin(lin_to_dB(x, use10=True), use10=True) == pytest.approx(x)


# ------------------------------------------------------------------
# UnitConverter
# ------------------------------------------------------------------

@pytest.fixture
def converter():
    return UnitConverter()


def test_convert_identity(converter):
    assert converter.convert(5, "V", "V") == pytest.approx(5)


@pytest.mark.parametrize(
    "value,from_u,to_u,expected",
    [
        (1, "V", "mV", 1000.0),
        (1000, "mV", "V", 1.0),
        (1, "V", "uV", 1_000_000.0),
        (1, "km", "m", 1000.0),
        (1, "mi", "ft", 5280.0),
        (3.28084, "ft", "m", pytest.approx(1.0, rel=1e-3)),
    ],
)
def test_convert_known_pairs(converter, value, from_u, to_u, expected):
    assert converter.convert(value, from_u, to_u) == pytest.approx(expected, rel=1e-3)


def test_convert_ac_potential_dbv_roundtrip(converter):
    # 1 Vrms == 0 dBV by definition
    assert converter.convert(1, "Vrms", "dBV") == pytest.approx(0.0, abs=1e-9)
    assert converter.convert(0, "dBV", "Vrms") == pytest.approx(1.0, rel=1e-6)


def test_convert_unknown_from_unit_raises(converter):
    with pytest.raises(Exception, match="Unrecognized unit type"):
        converter.convert(1, "bogus", "V")


def test_convert_unknown_to_unit_raises(converter):
    with pytest.raises(Exception, match="Unrecognized unit type"):
        converter.convert(1, "V", "bogus")


def test_view_unit_list_does_not_crash(converter, capsys):
    converter.view_unit_list()
    captured = capsys.readouterr()
    assert "UNIT" in captured.out
