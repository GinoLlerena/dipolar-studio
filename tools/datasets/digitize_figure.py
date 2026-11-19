"""Digitize the filled markers of a scanned scatter plot (Phase 2 V0.3).

    uv run --with pypdf==7.1.1 --with pillow==13.0.0 python tools/datasets/digitize_figure.py \\
        --pdf datasets-local/sources/chandrakumar-burnell-1993-bmr-issue.pdf \\
        --couplings datasets-local/odcb-chandrakumar1993/couplings.csv \\
        --out datasets-local/odcb-chandrakumar1993/targets.csv

It reads Chandrakumar & Burnell (1993), Fig. 3 (the order parameters against the reduced
temperature, filled markers only), and writes a condition-by-condition target list. **This tool
holds no data**: the figure, the temperatures and the targets stay local
(docs/phase2/v0.1-selection.md §5). Only counts and precisions are printed.

The method (frozen by docs/phase2/v0.3-preregistration.md):
1. **The page image** is the scan embedded in the PDF, decoded losslessly (1 bit per pixel).
2. **Each panel's frame** is one of the two largest connected components. Its left and right
   edges, and the tick marks on both, are located row by row, so a slightly skewed scan is
   calibrated along each tick line, not along image rows.
3. **The value axis** is piecewise linear through the frame edges and every tick (one per 0.01),
   read at the marker's column. Tick spacing residuals give the calibration precision.
4. **The markers** are connected components of a single marker's size: filled squares (fill
   ≥ 0.8) and filled triangles (0.45 to 0.7). The legend's region is excluded. A component the size
   of two overlapping markers is split by the known marker size (flag ``overlap-resolved``).
5. **The point** is the bounding-box centre. For a triangle the centroid would sit h/6 lower; that
   offset is added to the declared precision.
6. **Assignment** is by rank in the reduced temperature within each series (triangles: Table I;
   squares: Table II), which requires as many markers as conditions. Each marker's own reduced
   temperature is a consistency check against T/T_NI.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from scipy import ndimage

#: The ISMAR issue PDF (v0-sources.json); pages 65–66 of the file are the article's pp. 202–203.
PDF_SHA256 = "f262c2f870e0b98a7c58da174423796620a62153abdf5cc46b37f024b5898c99"
#: The paper's nematic–isotropic temperatures, used for T_r = T / T_NI (p. 203).
T_NI = {"I": 333.0, "II": 317.0}
SERIES = {"triangle": "I", "square": "II"}
TICK_STEP = 0.01


@dataclass(frozen=True)
class Panel:
    """A panel's axes: the value at the frame's top and bottom edges (a tick every 0.01); the
    abscissa's ticks on the bottom edge (first value and step) and its value at the right edge;
    and the legend's box, excluded, as fractions of the frame (x0, x1, y0, y1)."""

    component: str
    top: float
    bottom: float
    x_first: float
    x_step: float
    x_right: float
    legend: tuple[float, float, float, float]


@dataclass(frozen=True)
class Figure:
    name: str
    page: int  # 1-based page of the PDF file
    rows: tuple[int, int]  # the image rows that hold the figure
    panels: tuple[Panel, Panel]


#: Fig. 3 (p. 203): against T_r, filled markers only. The targets.
FIG3 = Figure(
    "Fig. 3",
    66,
    (0, 1700),
    (
        Panel("S_zz", -0.25, -0.10, 0.90, 0.05, 1.0, (0.0, 0.7, 0.70, 1.0)),
        Panel("S_xx-S_yy", 0.15, 0.0, 0.90, 0.05, 1.0, (0.0, 0.7, 0.70, 1.0)),
    ),
)
#: Fig. 2 (p. 202): against T in K, filled with open symbols. The cross-check.
FIG2 = Figure(
    "Fig. 2",
    65,
    (1400, 3377),
    (
        Panel("S_zz", -0.25, -0.10, 290.0, 10.0, 340.0, (0.0, 0.45, 0.55, 1.0)),
        Panel("S_xx-S_yy", 0.15, 0.0, 290.0, 10.0, 340.0, (0.55, 1.0, 0.0, 0.38)),
    ),
)


@dataclass
class Marker:
    kind: str
    x: float  # column of the bounding-box centre
    y: float  # row of the bounding-box centre
    height: float
    flags: list[str] = field(default_factory=list)


@dataclass
class Frame:
    top_line: np.ndarray  # (a, b): row = a + b·column
    bottom_line: np.ndarray
    cols: tuple[int, int]
    left: np.ndarray  # (a, b): column = a + b·row
    right: np.ndarray
    left_ticks: np.ndarray  # rows of the ticks on the left edge, top to bottom
    right_ticks: np.ndarray
    bottom_ticks: np.ndarray  # columns of the ticks on the bottom edge


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def page_ink(pdf: Path, page: int) -> np.ndarray:
    """The page's embedded scan as a boolean ink mask (True = black)."""
    from pypdf import PdfReader  # a tool dependency only (see the usage line)

    images = PdfReader(str(pdf)).pages[page - 1].images
    if len(images) != 1:
        raise ValueError(f"page {page}: expected one embedded scan, found {len(images)}")
    gray = np.asarray(images[0].image.convert("L"))
    ink: np.ndarray = gray < 128
    return ink


def _components(ink: np.ndarray) -> tuple[np.ndarray, list[tuple[slice, slice]], np.ndarray]:
    labels, n = ndimage.label(ink, structure=np.ones((3, 3)))
    slices = ndimage.find_objects(labels)
    sizes = np.asarray(ndimage.sum(ink, labels, range(1, n + 1)))
    return labels, slices, sizes


def _runs(mask: np.ndarray) -> np.ndarray:
    """Centres of the runs of True in a 1-D mask."""
    idx = np.flatnonzero(mask)
    if idx.size == 0:
        return np.zeros(0)
    breaks = np.flatnonzero(np.diff(idx) > 1)
    starts = np.r_[idx[0], idx[breaks + 1]]
    stops = np.r_[idx[breaks], idx[-1]]
    return np.asarray((starts + stops) / 2.0)


def find_frames(ink: np.ndarray) -> list[Frame]:
    """The two largest components (each a frame's top, bottom and at least one side), left to
    right, with their edges and ticks located in the page's ink. A side line may be a separate
    component (the scan breaks it at a corner), so the edges are searched in narrow bands."""
    labels, slices, sizes = _components(ink)
    order = np.argsort(sizes)[::-1][:2]
    frames = []
    for i in sorted(order, key=lambda j: slices[j][1].start):
        rs, cs = slices[i]
        frames.append(_frame(ink, labels[rs, cs] == i + 1, rs.start, cs.start))
    return frames


def _edge(ink: np.ndarray, rows: np.ndarray, centre: int, side: str) -> np.ndarray:
    """Fit a side line (column = a + b·row) from the outermost ink in a ±8 px band per row."""
    return _line(ink.T, rows, centre, outer_first=side == "left")


def _line(ink: np.ndarray, along: np.ndarray, centre: int, outer_first: bool) -> np.ndarray:
    """Fit position = a + b·along from the outermost ink in a ±8 px band at each ``along``."""
    pos, used = [], []
    for k in along:
        band = np.flatnonzero(ink[centre - 8 : centre + 9, k])
        if band.size:
            pos.append(centre - 8 + (band[0] if outer_first else band[-1]))
            used.append(k)
    p, u = np.asarray(pos, dtype=float), np.asarray(used, dtype=float)
    keep = np.abs(p - np.median(p)) <= 3
    b, a = np.polyfit(u[keep], p[keep], 1)
    return np.array([a, b])


def _frame(ink: np.ndarray, mask: np.ndarray, r0: int, c0: int) -> Frame:
    w = mask.shape[1]
    probe = [int(f * w) for f in (0.3, 0.4, 0.5, 0.6, 0.7)]
    top0 = r0 + int(np.median([np.flatnonzero(mask[:, c])[0] for c in probe]))
    bottom0 = r0 + int(np.median([np.flatnonzero(mask[:, c])[-1] for c in probe]))
    # The top and bottom lines (row = a + b·column), then the sides (column = a + b·row).
    span = np.arange(c0 + int(0.05 * w), c0 + int(0.95 * w))
    top_line = _line(ink, span, top0, outer_first=True)
    bottom_line = _line(ink, span, bottom0, outer_first=False)
    rows = np.arange(top0 + 12, bottom0 - 12)
    left = _edge(ink, rows, c0, "left")
    right = _edge(ink, rows, c0 + w - 1, "right")

    def ticks(side: np.ndarray, sign: int) -> np.ndarray:
        """Rows of the ticks 6–9 px inside a side line, between the top and bottom lines."""
        col0 = side[0] + side[1] * top0
        r_top = top_line[0] + top_line[1] * col0
        r_bot = bottom_line[0] + bottom_line[1] * col0
        rr = np.arange(int(np.ceil(r_top)) + 6, int(np.floor(r_bot)) - 5)
        cc = np.rint(side[0] + side[1] * rr).astype(int)
        hit = np.array(
            [
                ink[r, c + 6 : c + 10].any() if sign > 0 else ink[r, c - 9 : c - 5].any()
                for r, c in zip(rr, cc, strict=True)
            ]
        )
        return _runs(hit) + rr[0]

    cols = np.arange(c0 + int(0.02 * w), c0 + int(0.98 * w))
    bot = np.rint(bottom_line[0] + bottom_line[1] * cols).astype(int)
    inside_b = np.array([ink[b - 9 : b - 5, c].any() for b, c in zip(bot, cols, strict=True)])
    return Frame(
        top_line=top_line,
        bottom_line=bottom_line,
        cols=(c0, c0 + w),
        left=left,
        right=right,
        left_ticks=ticks(left, +1),
        right_ticks=ticks(right, -1),
        bottom_ticks=_runs(inside_b) + cols[0],
    )


def _corner(line: np.ndarray, side: np.ndarray) -> tuple[float, float]:
    """The intersection of a horizontal-ish line (row = a + b·col) and a side (col = c + d·row)."""
    a, b = line
    c, d = side
    row = (a + b * c) / (1 - b * d)
    return row, c + d * row


def value_at(frame: Frame, panel: Panel, x: float, y: float) -> tuple[float, float]:
    """The panel's value at image point (x, y), and the calibration residual (max |tick − linear|,
    in value units), along tick lines joining the left and right edges."""
    n = round(abs(panel.top - panel.bottom) / TICK_STEP) - 1
    if len(frame.left_ticks) != n or len(frame.right_ticks) != n:
        raise ValueError(
            f"{panel.component}: expected {n} ticks per edge, found "
            f"{len(frame.left_ticks)} and {len(frame.right_ticks)}"
        )
    top_left, bottom_left = _corner(frame.top_line, frame.left), _corner(frame.bottom_line, frame.left)
    top_right, bottom_right = _corner(frame.top_line, frame.right), _corner(frame.bottom_line, frame.right)
    lines_l = np.r_[top_left[0], frame.left_ticks, bottom_left[0]].astype(float)
    lines_r = np.r_[top_right[0], frame.right_ticks, bottom_right[0]].astype(float)
    xl = frame.left[0] + frame.left[1] * lines_l
    xr = frame.right[0] + frame.right[1] * lines_r
    t = (x - xl) / (xr - xl)
    rows_at_x = lines_l + t * (lines_r - lines_l)
    values = np.linspace(panel.top, panel.bottom, n + 2)
    linear = np.polyval(np.polyfit(values, rows_at_x, 1), values)
    pitch = abs(rows_at_x[-1] - rows_at_x[0]) / (n + 1)
    residual = float(np.max(np.abs(rows_at_x - linear))) / pitch * TICK_STEP
    return float(np.interp(y, rows_at_x, values)), residual


def abscissa(frame: Frame, panel: Panel, x: float) -> tuple[float, float]:
    """The abscissa at column x, linear through the bottom ticks; and the right edge's deviation
    from its labelled value on that scale (a check of the axis, not used for the values)."""
    n = round((panel.x_right - panel.x_first) / panel.x_step)
    if len(frame.bottom_ticks) != n:
        raise ValueError(f"{panel.component}: expected {n} abscissa ticks, found {len(frame.bottom_ticks)}")
    values = panel.x_first + panel.x_step * np.arange(n)
    slope, intercept = np.polyfit(frame.bottom_ticks, values, 1) if n > 1 else (0.0, values[0])
    right_edge = _corner(frame.bottom_line, frame.right)[1]
    return float(intercept + slope * x), float(intercept + slope * right_edge - panel.x_right)


def find_markers(ink: np.ndarray, frame: Frame, panel: Panel, size: float = 22.0, split: bool = True) -> list[Marker]:
    """Filled squares and triangles inside the frame, outside the legend; merged pairs split
    (Fig. 3 only: in Fig. 2 a merged component may hold open symbols)."""
    labels, slices, sizes = _components(ink)
    c0, c1 = frame.cols
    top = float(np.min(frame.top_line[0] + frame.top_line[1] * np.array(frame.cols)))
    bottom = float(np.max(frame.bottom_line[0] + frame.bottom_line[1] * np.array(frame.cols)))
    lx0, lx1, ly0, ly1 = panel.legend
    markers: list[Marker] = []
    for i, (rs, cs) in enumerate(slices):
        if rs.start <= top + 3 or rs.stop >= bottom - 3 or cs.start <= c0 + 12 or cs.stop >= c1 - 12:
            continue
        h, w = rs.stop - rs.start, cs.stop - cs.start
        cx, cy = (cs.start + cs.stop - 1) / 2.0, (rs.start + rs.stop - 1) / 2.0
        fx, fy = (cx - c0) / (c1 - c0), (cy - top) / (bottom - top)
        if lx0 <= fx <= lx1 and ly0 <= fy <= ly1:
            continue
        fill = sizes[i] / (h * w)
        single = 0.8 * size <= h <= 1.25 * size and 0.8 * size <= w <= 1.3 * size
        if single and fill >= 0.8:
            markers.append(Marker("square", cx, cy, h))
        elif single and 0.45 <= fill <= 0.7:
            markers.append(Marker("triangle", cx, cy, h))
        elif split and (h > 1.5 * size or w > 1.5 * size):
            markers.extend(_split(labels[rs, cs] == i + 1, rs.start, cs.start, size))
    return markers


def _split(mask: np.ndarray, r0: int, c0: int, size: float) -> list[Marker]:
    """Two overlapping markers, a triangle (apex up) and a square, stacked or side by side. The
    square is the block of full-width rows or full-height columns; the triangle is the rest."""
    h, w = mask.shape
    half = (size - 1) / 2.0
    if h > w:  # stacked: which one is on top? A triangle's top rows are narrow.
        widths = mask.sum(axis=1)
        top_is_triangle = widths[:3].mean() < 0.5 * widths.max()
        tri_y = r0 + half if top_is_triangle else r0 + h - 1 - half
        sq_y = r0 + h - 1 - half if top_is_triangle else r0 + half
        cols_sq = np.flatnonzero(mask[int(sq_y - r0)])
        cols_tri = np.flatnonzero(mask[int(tri_y - r0)])
        tri = Marker("triangle", c0 + (cols_tri[0] + cols_tri[-1]) / 2.0, tri_y, size, ["overlap-resolved"])
        sq = Marker("square", c0 + (cols_sq[0] + cols_sq[-1]) / 2.0, sq_y, size, ["overlap-resolved"])
        return [tri, sq]
    heights = mask.sum(axis=0)
    full = heights >= 0.85 * heights.max()
    # The square contributes a run of full-height columns; a triangle only its apex column.
    square_on_right = int(full[w // 2 :].sum()) > int(full[: w // 2].sum())
    sq_x = c0 + w - 1 - half if square_on_right else c0 + half
    tri_x = c0 + half + 1 if square_on_right else c0 + w - 1 - half - 1
    rows_sq = np.flatnonzero(mask[:, int(sq_x - c0)])
    tri_cols = slice(0, int(w / 2)) if square_on_right else slice(int(w / 2), w)
    rows_tri = np.flatnonzero(mask[:, tri_cols].any(axis=1))
    tri = Marker("triangle", tri_x, r0 + (rows_tri[0] + rows_tri[-1]) / 2.0, size, ["overlap-resolved"])
    sq = Marker("square", sq_x, r0 + (rows_sq[0] + rows_sq[-1]) / 2.0, size, ["overlap-resolved"])
    return [tri, sq]


def temperatures(couplings: Path) -> dict[str, list[float]]:
    with couplings.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    out: dict[str, list[float]] = {}
    for table in ("I", "II"):
        out[table] = sorted({float(r["T_K"]) for r in rows if r["table"] == table})
    return out


def _figure_ink(ink: np.ndarray, figure: Figure) -> np.ndarray:
    out = np.zeros_like(ink)
    out[figure.rows[0] : figure.rows[1]] = ink[figure.rows[0] : figure.rows[1]]
    return out


def _pitch(frame: Frame, panel: Panel) -> float:
    """Pixels per unit of the panel's value, at the frame's middle column."""
    mid = (frame.cols[0] + frame.cols[1]) / 2.0
    height = (frame.bottom_line[0] - frame.top_line[0]) + (frame.bottom_line[1] - frame.top_line[1]) * mid
    return float(height / abs(panel.top - panel.bottom))


def _read(ink: np.ndarray, figure: Figure, split: bool) -> list[tuple[Panel, Marker, float, float, float, float]]:
    """Every marker of a figure: (panel, marker, value, precision, abscissa, right-edge check)."""
    frames = find_frames(_figure_ink(ink, figure))
    if len(frames) != len(figure.panels):
        raise ValueError(f"{figure.name}: expected two panels")
    out = []
    for frame, panel in zip(frames, figure.panels, strict=True):
        pitch = _pitch(frame, panel)
        for m in find_markers(ink, frame, panel, split=split):
            value, residual = value_at(frame, panel, m.x, m.y)
            xval, dev = abscissa(frame, panel, m.x)
            # Precision: half a pixel of position, the calibration residual, and for a triangle
            # the bbox-centre/centroid ambiguity (h/6); one more pixel for a split pair.
            prec = 0.5 / pitch + residual + (m.height / 6.0 / pitch if m.kind == "triangle" else 0.0)
            if "overlap-resolved" in m.flags:
                prec += 1.0 / pitch
            out.append((panel, m, value, prec, xval, dev))
    return out


def digitize(
    ink3: np.ndarray, ink2: np.ndarray, temps: dict[str, list[float]]
) -> tuple[list[dict[str, str]], dict[str, object]]:
    """The Fig. 3 targets, assigned by rank, each cross-checked against Fig. 2 where Fig. 2 has a
    single filled marker of its series within ±1 K of that condition, and no other."""
    targets: list[dict[str, str]] = []
    summary: dict[str, object] = {}
    read3 = _read(ink3, FIG3, split=True)
    read2 = _read(ink2, FIG2, split=False)
    for panel in FIG3.panels:
        mine = [r for r in read3 if r[0].component == panel.component]
        for kind, table in SERIES.items():
            series = sorted((r for r in mine if r[1].kind == kind), key=lambda r: r[1].x)
            ts = temps[table]
            if len(series) != len(ts):
                raise ValueError(f"{panel.component}: {len(series)} {kind}s for {len(ts)} conditions")
            fig2 = [r for r in read2 if r[0].component == panel.component and r[1].kind == kind]
            for (_, m, value, prec, tr, _dev), t in zip(series, ts, strict=True):
                near = [r for r in fig2 if abs(r[4] - t) <= 1.0]
                others = [u for u in ts if u != t and any(abs(r[4] - u) <= 1.0 for r in near)]
                row = {
                    "table": table,
                    "T_K": f"{t:g}",
                    "component": panel.component,
                    "value": f"{value:.5f}",
                    "precision": f"{prec:.5f}",
                    "T_r_digitized": f"{tr:.5f}",
                    "T_r_expected": f"{t / T_NI[table]:.5f}",
                    "fig2_value": "",
                    "fig2_precision": "",
                    "status": "target",
                    "flags": ";".join(m.flags),
                }
                if len(near) == 1 and not others:
                    v2, p2 = near[0][2], near[0][3]
                    row["fig2_value"], row["fig2_precision"] = f"{v2:.5f}", f"{p2:.5f}"
                    if abs(v2 - value) > 2.0 * (prec + p2):
                        row["status"] = "pending"
                        row["flags"] = ";".join([*m.flags, "fig2-disagrees"])
                targets.append(row)
        summary[panel.component] = {
            "fig3_markers": len(mine),
            "overlap_resolved": sum("overlap-resolved" in r[1].flags for r in mine),
            "fig2_markers": sum(r[0].component == panel.component for r in read2),
            "right_edge_check": float(np.median([r[5] for r in mine])),
        }
    return targets, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--couplings", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if sha256(args.pdf) != PDF_SHA256:
        print("the PDF is not the recorded file", file=sys.stderr)
        return 1
    rows, summary = digitize(page_ink(args.pdf, FIG3.page), page_ink(args.pdf, FIG2.page), temperatures(args.couplings))
    with args.out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    dr = [abs(float(str(r["T_r_digitized"])) - float(str(r["T_r_expected"]))) for r in rows]
    print(f"{len(rows)} targets written to {args.out}; sha256 {sha256(args.out)}")
    print(f"max |T_r digitized − T/T_NI| = {max(dr):.4f}")
    compared = [r for r in rows if r["fig2_value"]]
    z = [
        abs(float(r["fig2_value"]) - float(r["value"])) / (float(r["precision"]) + float(r["fig2_precision"]))
        for r in compared
    ]
    print(
        f"cross-checked against Fig. 2: {len(compared)} of {len(rows)}; "
        f"max |Fig. 2 − Fig. 3| / (sum of precisions) = {max(z, default=0.0):.2f}"
    )
    print(
        f"targets: {sum(r['status'] == 'target' for r in rows)}; pending: {sum(r['status'] == 'pending' for r in rows)}"
    )
    for name, item in summary.items():
        print(name, item)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
