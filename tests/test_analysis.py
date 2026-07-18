import numpy as np
import matplotlib.pyplot as plt
import pytest

from stardust.analysis import extract_visible_xy


@pytest.fixture
def figure():
    fig, ax = plt.subplots()
    yield fig
    plt.close(fig)


def test_extract_line_trimmed_to_xlim(figure):
    ax = figure.axes[0]
    ax.plot([0, 1, 2, 3, 4], [0, 1, 4, 9, 16], label="line1")
    ax.set_xlim(1, 3)

    results = extract_visible_xy(figure)
    assert len(results) == 1
    r = results[0]
    assert r["type"] == "line"
    assert r["label"] == "line1"
    np.testing.assert_allclose(r["x"], [1, 2, 3])
    np.testing.assert_allclose(r["y"], [1, 4, 9])
    assert r["xlim_used"] == (1, 3)


def test_extract_line_interpolates_at_boundary(figure):
    ax = figure.axes[0]
    ax.plot([0, 10], [0, 100], label="ramp")
    ax.set_xlim(2.5, 7.5)

    r = extract_visible_xy(figure)[0]
    np.testing.assert_allclose(r["x"], [2.5, 7.5])
    np.testing.assert_allclose(r["y"], [25, 75])


def test_extract_scatter_filtered_to_xlim(figure):
    ax = figure.axes[0]
    ax.scatter([0, 2, 4, 6], [0, 4, 16, 36], label="scat1")
    ax.set_xlim(1, 5)

    results = extract_visible_xy(figure)
    assert len(results) == 1
    r = results[0]
    assert r["type"] == "scatter"
    np.testing.assert_allclose(r["x"], [2, 4])
    np.testing.assert_allclose(r["y"], [4, 16])


def test_extract_reversed_xlim_normalized(figure):
    ax = figure.axes[0]
    ax.plot([0, 1, 2, 3, 4], [0, 1, 4, 9, 16], label="line1")
    ax.set_xlim(3, 1)  # reversed axis

    r = extract_visible_xy(figure)[0]
    assert r["xlim_used"] == (1, 3)
    np.testing.assert_allclose(r["x"], [1, 2, 3])


def test_extract_ignores_invisible_artists(figure):
    ax = figure.axes[0]
    line, = ax.plot([0, 1, 2], [0, 1, 2], label="hidden")
    line.set_visible(False)
    ax.set_xlim(0, 2)

    assert extract_visible_xy(figure) == []


def test_extract_multiple_axes():
    fig, (ax1, ax2) = plt.subplots(1, 2)
    try:
        ax1.plot([0, 1, 2], [0, 1, 2], label="a")
        ax1.set_xlim(0, 2)
        ax2.plot([0, 1, 2], [10, 11, 12], label="b")
        ax2.set_xlim(0, 2)

        results = extract_visible_xy(fig)
        assert {r["axes_index"] for r in results} == {0, 1}
        assert {r["label"] for r in results} == {"a", "b"}
    finally:
        plt.close(fig)


def test_extract_no_axes_returns_empty_list():
    fig = plt.figure()
    try:
        assert extract_visible_xy(fig) == []
    finally:
        plt.close(fig)


def test_extract_nan_points_dropped(figure):
    ax = figure.axes[0]
    ax.plot([0, 1, np.nan, 3], [0, 1, 2, 3], label="withnan")
    ax.set_xlim(0, 3)

    r = extract_visible_xy(figure)[0]
    assert not np.any(np.isnan(r["x"]))
    assert not np.any(np.isnan(r["y"]))
