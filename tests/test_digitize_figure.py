"""The figure digitizer (V0.3) on synthetic scans with known markers: no third-party data.

The tool reads only the local ortho-dichlorobenzene figures in use. These tests draw skewed
two-panel figures like them, with ticks every 0.01, and check that:
- every marker, a stacked pair and a side-by-side pair are found and read back within precision;
- assignment is by a frozen match tolerance, so a wrongly keyed or missing condition is *pending*,
  never a silent target (round 73, A3);
- the Fig. 2 cross-check distinguishes agreement, disagreement and unavailability.
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
WIDTH = 920
PANEL = dg.Panel("S_zz", -0.25, -0.10, 0.90, 0.05, 1.0, (0.0, 0.7, 0.70, 1.0))
NO_LEGEND = (0.0, 0.0, 0.0, 0.0)
#: Fig. 3 ticks at T_r 0.90 and 0.95, the right edge at 1.0; Fig. 2 ticks at 290–330 K, edges 285 and 340 K.
FRAC_FIG3 = (0.1, 0.55)
FRAC_FIG2 = tuple((t - 285.0) / 55.0 for t in (290.0, 300.0, 310.0, 320.0, 330.0))
C0S = (100, 1150)


def _draw_frame(ink: np.ndarray, c0: int, tick_fracs: tuple[float, ...] = FRAC_FIG3) -> None:
    """A skewed frame from column c0, with 14 ticks on each side and the given bottom ticks."""
    c1 = c0 + WIDTH
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
    for frac in tick_fracs:
        c = int(c0 + frac * WIDTH)
        r = round(BOTTOM + SKEW * (c - c0))
        ink[r - 14 : r, c : c + 2] = True


def _square(ink: np.ndarray, x: float, y: float) -> None:
    ink[round(y - 10.5) : round(y + 10.5) + 1, round(x - 10.5) : round(x + 10.5) + 1] = True


def _triangle(ink: np.ndarray, x: float, y: float) -> None:
    top = round(y - 10.5)
    for k in range(22):
        half = 12.0 * (k + 1) / 22.0
        ink[top + k, round(x - half) : round(x + half) + 1] = True


def _point(c0: int, frac: float, value: float) -> tuple[float, float]:
    """The image point of (abscissa fraction, value) on the skewed axes."""
    x = c0 + frac * WIDTH
    row = TOP + (value - (-0.25)) / 0.15 * (BOTTOM - TOP) + SKEW * (x - c0)
    return x, row


def _expected(c0: int, x: float, y: float) -> float:
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
    for c0 in C0S:
        _draw_frame(ink, c0)
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
        assert value == pytest.approx(_expected(100, x, y), abs=1.5 / pitch + residual)
    xval, edge = dg.abscissa(frame, PANEL, 100 + 0.55 * WIDTH)
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


def test_a_missing_tick_is_an_error_not_a_guess() -> None:
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


# ---- End to end: synthetic Fig. 3 (against T_r) and Fig. 2 (against T) ---------------------------

TEMPS = {"I": [301.0, 310.0, 320.0], "II": [292.0, 300.0, 311.0]}
TRUE = {  # (table, T, component) -> value, all in the upper part of the axes
    ("I", 301.0, "S_zz"): -0.230, ("I", 310.0, "S_zz"): -0.215, ("I", 320.0, "S_zz"): -0.200,
    ("II", 292.0, "S_zz"): -0.225, ("II", 300.0, "S_zz"): -0.210, ("II", 311.0, "S_zz"): -0.190,
    ("I", 301.0, "S_xx-S_yy"): -0.180, ("I", 310.0, "S_xx-S_yy"): -0.170, ("I", 320.0, "S_xx-S_yy"): -0.160,
    ("II", 292.0, "S_xx-S_yy"): -0.235, ("II", 300.0, "S_xx-S_yy"): -0.220, ("II", 311.0, "S_xx-S_yy"): -0.205,
}  # fmt: skip
SYN3 = dg.Figure("synthetic Fig. 3", 0, (0, 1200), (
    dg.Panel("S_zz", -0.25, -0.10, 0.90, 0.05, 1.0, NO_LEGEND),
    dg.Panel("S_xx-S_yy", -0.25, -0.10, 0.90, 0.05, 1.0, NO_LEGEND),
))  # fmt: skip
SYN2 = dg.Figure("synthetic Fig. 2", 0, (0, 1200), (
    dg.Panel("S_zz", -0.25, -0.10, 290.0, 10.0, 340.0, NO_LEGEND),
    dg.Panel("S_xx-S_yy", -0.25, -0.10, 290.0, 10.0, 340.0, NO_LEGEND),
))  # fmt: skip


def _pages(
    skip3: frozenset[tuple[str, float, str]] = frozenset(),
    skip2: frozenset[tuple[str, float, str]] = frozenset(),
    shift2: dict[tuple[str, float, str], float] | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    ink3 = np.zeros((1200, 2200), dtype=bool)
    ink2 = np.zeros((1200, 2200), dtype=bool)
    for c0 in C0S:
        _draw_frame(ink3, c0, FRAC_FIG3)
        _draw_frame(ink2, c0, FRAC_FIG2)
    for (table, t, comp), value in TRUE.items():
        c0 = C0S[0] if comp == "S_zz" else C0S[1]
        draw = _triangle if table == "I" else _square
        if (table, t, comp) not in skip3:
            t_r = t / dg.T_NI[table]
            draw(ink3, *_point(c0, 0.1 + (t_r - 0.90) * 9.0, value))
        if (table, t, comp) not in skip2:
            draw(ink2, *_point(c0, (t - 285.0) / 55.0, value + (shift2 or {}).get((table, t, comp), 0.0)))
    return ink3, ink2


def _by_key(rows: list[dict[str, str]]) -> dict[tuple[str, float, str], dict[str, str]]:
    return {(r["table"], float(r["T_K"]), r["component"]): r for r in rows}


def test_every_condition_is_read_back_and_cross_checked() -> None:
    ink3, ink2 = _pages()
    rows, _ = dg.digitize(ink3, ink2, TEMPS, SYN3, SYN2)
    got = _by_key(rows)
    assert set(got) == set(TRUE)
    for key, value in TRUE.items():
        row = got[key]
        assert row["status"] == "target" and row["fig2_check"] == "agrees", (key, row)
        assert abs(float(row["value"]) - value) <= float(row["precision"]) + 0.0002


def test_wrongly_keyed_conditions_are_pending_not_targets() -> None:
    """Table I keyed one kelvin up: T_r moves by about 0.003, beyond the frozen tolerance."""
    ink3, ink2 = _pages()
    wrong = {"I": [t + 1.0 for t in TEMPS["I"]], "II": TEMPS["II"]}
    rows, _ = dg.digitize(ink3, ink2, wrong, SYN3, SYN2)
    for row in rows:
        if row["table"] == "I":
            assert row["status"] == "pending" and "no-marker" in row["flags"], row
        else:
            assert row["status"] == "target"


def test_a_missing_marker_leaves_only_its_cell_pending() -> None:
    gone = ("II", 300.0, "S_zz")
    ink3, ink2 = _pages(skip3=frozenset({gone}))
    rows, _ = dg.digitize(ink3, ink2, TEMPS, SYN3, SYN2)
    got = _by_key(rows)
    assert got[gone]["status"] == "pending" and "no-marker" in got[gone]["flags"] and got[gone]["value"] == ""
    assert all(r["status"] == "target" for k, r in got.items() if k != gone)


def test_fig2_disagreement_and_unavailability_are_distinguished() -> None:
    off = ("I", 310.0, "S_zz")
    absent = ("II", 311.0, "S_xx-S_yy")
    ink3, ink2 = _pages(skip2=frozenset({absent}), shift2={off: 0.01})
    rows, _ = dg.digitize(ink3, ink2, TEMPS, SYN3, SYN2)
    got = _by_key(rows)
    assert got[off]["status"] == "pending" and got[off]["fig2_check"] == "disagrees"
    assert "fig2-disagrees" in got[off]["flags"]
    assert got[absent]["status"] == "target" and got[absent]["fig2_check"] == "unavailable"


def test_the_couplings_file_must_be_the_frozen_transcription(tmp_path: Path) -> None:
    fake = tmp_path / "couplings.csv"
    fake.write_text("table,T_K,coupling,D_token,sigma_token,D_Hz,sigma_Hz\nI,1,X,1,1,1,1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="recorded"):
        dg.temperatures(fake)
