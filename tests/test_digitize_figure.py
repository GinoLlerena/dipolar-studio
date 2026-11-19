"""The figure digitizer (V0.3) on synthetic scans with known markers: no third-party data.

The tool reads only the local ortho-dichlorobenzene figure in use; these tests draw a skewed
two-panel figure like it, with ticks every 0.01, and check that every marker, a stacked pair and a
side-by-side pair are found and read back within the declared precision.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "datasets"))

import digitize_figure as dg  # noqa: E402

SKEW = 0.006  # rows per column (and columns per row): about a third of a degree
TOP, BOTTOM = 100, 1021
PANEL = dg.Panel("S_zz", -0.25, -0.10, 0.90, 0.05, 1.0, (0.0, 0.7, 0.70, 1.0))


def _draw_frame(ink: np.ndarray, c0: int, c1: int) -> None:
    """A skewed frame from column c0 to c1, with 14 ticks on each side and two on the bottom."""
    cols = np.arange(c0, c1 + 1)
    for base in (TOP, BOTTOM):
        rows = np.rint(base + SKEW * (cols - c0)).astype(int)
        for t in range(3):
            ink[rows + (t if base == TOP else -t), cols] = True
    rows = np.arange(TOP, BOTTOM + int(SKEW * (c1 - c0)) + 1)
    for c_base, inward in ((c0, 1), (c1, -1)):
        side = np.rint(c_base - SKEW * (rows - TOP)).astype(int)
        for t in range(3):
            ink[rows, side + inward * t] = True
    for k in range(1, 15):  # ticks every 0.01 between the edges
        for c_base, inward in ((c0, 1), (c1, -1)):
            r_edge = TOP + SKEW * (c_base - c0) + k * (BOTTOM - TOP) / 15.0
            c_edge = c_base - SKEW * (r_edge - TOP)
            for d in range(12):
                c = round(c_edge + inward * d)
                r = round(r_edge + SKEW * inward * d)
                ink[r : r + 2, c] = True
    for frac in (0.1, 0.55):  # the abscissa ticks at 0.90 and 0.95
        c = int(c0 + frac * (c1 - c0))
        r = round(BOTTOM + SKEW * (c - c0))
        ink[r - 14 : r, c : c + 2] = True


def _square(ink: np.ndarray, x: float, y: float) -> None:
    ink[round(y - 10.5) : round(y + 10.5) + 1, round(x - 10.5) : round(x + 10.5) + 1] = True


def _triangle(ink: np.ndarray, x: float, y: float) -> None:
    top = round(y - 10.5)
    for k in range(22):
        half = 12.0 * (k + 1) / 22.0
        ink[top + k, round(x - half) : round(x + half) + 1] = True


def _expected(c0: int, c1: int, x: float, y: float) -> float:
    """The value at (x, y) on the skewed axis: rows of equal value rise by SKEW per column."""
    row0 = y - SKEW * (x - c0)
    return -0.25 + 0.15 * (row0 - TOP) / (BOTTOM - TOP)


def _figure() -> tuple[np.ndarray, list[tuple[str, float, float]]]:
    ink = np.zeros((1200, 2200), dtype=bool)
    markers = [
        ("triangle", 260.0, 300.0),
        ("square", 330.0, 360.5),
        ("square", 500.5, 420.0),
        ("triangle", 640.0, 520.0),
        ("square", 900.0, 700.0),
    ]
    for c0 in (100, 1150):
        _draw_frame(ink, c0, c0 + 920)
    for kind, x, y in markers:
        (_triangle if kind == "triangle" else _square)(ink, x, y)
    return ink, markers


def test_the_frames_ticks_and_markers_of_a_skewed_scan() -> None:
    ink, markers = _figure()
    frames = dg.find_frames(ink)
    assert len(frames) == 2
    frame = frames[0]
    assert len(frame.left_ticks) == 14 and len(frame.right_ticks) == 14 and len(frame.bottom_ticks) == 2
    found = sorted(dg.find_markers(ink, frame, PANEL), key=lambda m: m.x)
    assert [m.kind for m in found] == [k for k, _, _ in markers]
    pitch = dg._pitch(frame, PANEL)
    for m, (_, x, y) in zip(found, markers, strict=True):
        value, residual = dg.value_at(frame, PANEL, m.x, m.y)
        assert residual < 0.0005
        assert abs(m.x - x) <= 1.0 and abs(m.y - y) <= 1.0
        assert value == pytest.approx(_expected(100, 1020, x, y), abs=1.5 / pitch + residual)
    xval, edge = dg.abscissa(frame, PANEL, 100 + 0.55 * 920)
    assert xval == pytest.approx(0.95, abs=0.001) and abs(edge) < 0.01


@pytest.mark.parametrize("layout", ["stacked", "side-by-side"])
def test_overlapping_markers_are_split_by_their_known_size(layout: str) -> None:
    ink, _ = _figure()
    tri = (700.0, 300.0)
    sq = (702.0, 318.0) if layout == "stacked" else (722.0, 302.0)
    _triangle(ink, *tri)
    _square(ink, *sq)
    frame = dg.find_frames(ink)[0]
    split = [m for m in dg.find_markers(ink, frame, PANEL) if "overlap-resolved" in m.flags]
    assert sorted(m.kind for m in split) == ["square", "triangle"]
    for m in split:
        x, y = tri if m.kind == "triangle" else sq
        assert abs(m.x - x) <= 2.0 and abs(m.y - y) <= 2.0, (m.kind, m.x, m.y)


def test_a_missing_tick_or_marker_is_an_error_not_a_guess() -> None:
    ink, _ = _figure()
    frame = dg.find_frames(ink)[0]
    broken = dg.Frame(
        frame.top_line,
        frame.bottom_line,
        frame.cols,
        frame.left,
        frame.right,
        frame.left_ticks[1:],
        frame.right_ticks,
        frame.bottom_ticks,
    )
    with pytest.raises(ValueError, match="ticks"):
        dg.value_at(broken, PANEL, 500.0, 500.0)
