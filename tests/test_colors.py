import pytest

from stardust import colors

_ALL_COLOR_NAMES = [
    "apl_blue",
    "apl_green",
    "apl_gray",
    "defense_prussian_blue",
    "defense_light_blue",
    "modern_orange",
    "modern_red",
]


@pytest.mark.parametrize("name", _ALL_COLOR_NAMES)
def test_color_is_valid_rgb_tuple(name):
    value = getattr(colors, name)
    assert isinstance(value, tuple)
    assert len(value) == 3
    for channel in value:
        assert 0.0 <= channel <= 1.0
