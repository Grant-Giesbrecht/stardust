import math

import numpy as np
import pytest

from stardust.algorithm import linstep, has_ext, bounded_interp, randrange


# ------------------------------------------------------------------
# linstep
# ------------------------------------------------------------------

def test_linstep_basic():
    assert linstep(0, 10, 2) == [0, 2, 4, 6, 8, 10]


def test_linstep_step_divides_evenly_no_duplicate_endpoint():
    # Regression guard: when step evenly divides (stop - start), the last
    # generated value already lands on stop and must not be appended twice.
    values = linstep(0, 10, 2)
    assert values == [0, 2, 4, 6, 8, 10]
    assert values.count(10) == 1


def test_linstep_includes_stop_with_float_rounding():
    values = linstep(0, 1, 0.1)
    assert values[0] == pytest.approx(0)
    assert values[-1] == pytest.approx(1)
    assert len(values) == 11


def test_linstep_non_exact_stop_not_overshot():
    values = linstep(0, 9, 2)
    assert values[-2] == 8
    assert values[-1] == 9  # exact stop still appended per docstring ("inclusive")


def test_linstep_rejects_nonpositive_step():
    with pytest.raises(ValueError):
        linstep(0, 10, 0)
    with pytest.raises(ValueError):
        linstep(0, 10, -1)


# ------------------------------------------------------------------
# has_ext
# ------------------------------------------------------------------

@pytest.mark.parametrize(
    "path,exts,expected",
    [
        ("file.txt", [".txt"], True),
        ("file.TXT", [".txt"], True),
        ("file.txt", [".csv", ".txt"], True),
        ("file.csv", [".txt"], False),
        ("archive.tar.gz", [".gz"], True),
        ("noext", [".txt"], False),
    ],
)
def test_has_ext(path, exts, expected):
    assert has_ext(path, exts) is expected


# ------------------------------------------------------------------
# bounded_interp
# ------------------------------------------------------------------

def test_bounded_interp_within_bounds():
    x = [0, 1, 2, 3]
    y = [0, 10, 20, 30]
    assert bounded_interp(x, y, 1.5) == pytest.approx(15)


def test_bounded_interp_out_of_bounds_returns_none():
    x = [0, 1, 2, 3]
    y = [0, 10, 20, 30]
    assert bounded_interp(x, y, -1) is None
    assert bounded_interp(x, y, 4) is None


def test_bounded_interp_at_exact_endpoints():
    x = [0, 1, 2, 3]
    y = [0, 10, 20, 30]
    assert bounded_interp(x, y, 0) == pytest.approx(0)
    assert bounded_interp(x, y, 3) == pytest.approx(30)


# ------------------------------------------------------------------
# randrange
# ------------------------------------------------------------------

def test_randrange_within_bounds():
    for _ in range(200):
        v = randrange(5, 10)
        assert 5 <= v <= 10


def test_randrange_respects_bin_size():
    for _ in range(200):
        v = randrange(0, 10, bin_size=1)
        assert math.isclose(v, round(v))


def test_randrange_bin_size_none_is_continuous():
    values = {randrange(0, 1) for _ in range(20)}
    # With no binning, 20 draws from a continuous range should not all
    # collide onto the same value.
    assert len(values) > 1
