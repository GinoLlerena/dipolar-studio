"""Independent reference implementation for the biphenyl fixtures (M0, step 2).

This module computes the *frozen expected answers* in ``datasets/*/expected/``. It is
deliberately **independent of dipolar-core**: the engine is tested against these numbers, so it
must never be used to produce them. Only NumPy and SciPy are used.

It follows the D3 contract in its simplest form:

* whitened inner linear solve by SVD (``numpy.linalg.lstsq``), never normal equations;
* the outer torsion found on a grid, then refined by bounded 1-D minimisation (the *refined*
  optimum is the expected value, not the grid point);
* profile intervals at a raw Δχ² of 1.00 (other parameters re-minimised);
* covariance from the full Jacobian in the joint coordinates (φ in degrees, Szz, Δ).

Geometry and frame are those of ``datasets/biphenyl-synthetic/generate.py`` (the dataset's own
convention). ``positions()`` re-implements them in vectorised form and is cross-checked against
``generate.proton_positions`` by the fixture tests.
"""

from __future__ import annotations

import importlib.util
import math
from collections.abc import Callable, Sequence
from pathlib import Path
from types import ModuleType

import numpy as np
from numpy.typing import NDArray
from scipy import optimize

ROOT = Path(__file__).resolve().parents[2]
SYNTHETIC_DIR = ROOT / "datasets" / "biphenyl-synthetic"
DIPIETRO_DIR = ROOT / "datasets" / "biphenyl-8CB-dipietro2013"

Array = NDArray[np.float64]
Pair = tuple[str, str]

PHI_DOMAIN = (0.0, 90.0)  # folded torsion domain, degrees
GRID_STEP = 0.5  # grid seeds, degrees
GEOMETRY = {"r_cc": 1.397, "r_ch": 1.084, "r_inter": 1.489}  # Å, regular hexagonal rings


def load_generator() -> ModuleType:
    """Import the synthetic dataset generator by path (it defines K_HH, TRUTH, geometry)."""
    spec = importlib.util.spec_from_file_location("biphenyl_generate", SYNTHETIC_DIR / "generate.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GEN = load_generator()
K_HH: float = GEN.K_HH

LABELS = [f"H{k + 1}" for k in range(1, 6)] + [f"H{k + 1}'" for k in range(1, 6)]
INDEX = {label: i for i, label in enumerate(LABELS)}
SWAP_B = {"H2'": "H6'", "H6'": "H2'", "H3'": "H5'", "H5'": "H3'"}


# --------------------------------------------------------------------------- geometry
def positions(
    phi_deg: float,
    r_cc: float = GEOMETRY["r_cc"],
    r_ch: float = GEOMETRY["r_ch"],
    r_inter: float = GEOMETRY["r_inter"],
) -> Array:
    """Proton coordinates (10×3, order of ``LABELS``) in the bisector frame of generate.py."""
    half = math.radians(phi_deg) / 2
    angles = np.radians(60.0 * np.arange(1, 6))
    out = np.empty((10, 3))
    for block, (uy, side) in enumerate(((math.sin(half), -1.0), (-math.sin(half), +1.0))):
        u = np.array([math.cos(half), uy, 0.0])
        center_z = side * (r_inter / 2 + r_cc)
        toward = np.array([0.0, 0.0, -side])
        d = np.cos(angles)[:, None] * toward + np.sin(angles)[:, None] * u
        pts = (r_cc + r_ch) * d
        pts[:, 2] += center_z
        out[5 * block : 5 * block + 5] = pts
    return out


def coefficient_rows(vectors: Array) -> Array:
    """Rows [∂D/∂Szz, ∂D/∂Δ] for internuclear vectors expressed in the tensor frame (Hz)."""
    r = np.linalg.norm(vectors, axis=1)
    c = vectors / r[:, None]
    pref = K_HH / r**3
    return np.column_stack([pref * (3 * c[:, 2] ** 2 - 1) / 2, pref * (c[:, 0] ** 2 - c[:, 1] ** 2) / 2])


def _vectors(pos: Array, pairs: Sequence[Pair], relabel: dict[str, str] | None = None) -> Array:
    m = relabel or {}
    ia = np.array([INDEX[m.get(a, a)] for a, _ in pairs])
    ib = np.array([INDEX[m.get(b, b)] for _, b in pairs])
    return pos[ib] - pos[ia]


def design_rigid(phi_deg: float, pairs: Sequence[Pair]) -> Array:
    """Rigid model: one conformer, tensor diagonal in its bisector frame."""
    return coefficient_rows(_vectors(positions(phi_deg), pairs))


def design_jump_shortcut(phi_deg: float, pairs: Sequence[Pair]) -> Array:
    """Symmetric four-site jump via the ring-B relabelling, applied to BOTH endpoints."""
    pos = positions(phi_deg)
    return 0.5 * (coefficient_rows(_vectors(pos, pairs)) + coefficient_rows(_vectors(pos, pairs, SWAP_B)))


def design_jump_explicit(phi_deg: float, pairs: Sequence[Pair]) -> Array:
    """Symmetric four-site jump by explicit conformers (+φ, −φ, 180−φ, 180+φ).

    Ring A is held fixed and ring B is rotated about the inter-ring axis. Each conformer's
    tensor is diagonal in *its own* acute-bisector frame, derived here from the coordinates.
    Independent of the relabelling shortcut; valid for 0 < φ < 90 (the acute bisector is
    undefined at 90°).
    """
    base = positions(0.0)
    rows = np.zeros((len(pairs), 2))
    for theta in (phi_deg, -phi_deg, 180.0 - phi_deg, 180.0 + phi_deg):
        t = math.radians(theta)
        rot = np.array([[math.cos(t), math.sin(t), 0.0], [-math.sin(t), math.cos(t), 0.0], [0.0, 0.0, 1.0]])
        pos = base.copy()
        pos[5:] = pos[5:] @ rot.T  # rotate ring B only
        u_a = pos[INDEX["H3"]].copy()
        u_b = pos[INDEX["H3'"]].copy()
        u_a[2] = u_b[2] = 0.0
        u_a /= np.linalg.norm(u_a)
        u_b /= np.linalg.norm(u_b)
        if u_a @ u_b < 0:  # ring planes are lines: take the acute pair
            u_b = -u_b
        x = (u_a + u_b) / np.linalg.norm(u_a + u_b)
        z = np.array([0.0, 0.0, 1.0])
        y = np.cross(z, x)
        frame = np.vstack([x, y, z])
        rows += coefficient_rows(_vectors(pos, pairs) @ frame.T)
    return rows / 4


MODELS: dict[str, Callable[[float, Sequence[Pair]], Array]] = {
    "rigid": design_rigid,
    "jump4": design_jump_shortcut,
}


# --------------------------------------------------------------------------- inference
class Problem:
    """Whitened VarPro problem for one dataset under one model and weighting."""

    def __init__(self, model: str, pairs: Sequence[Pair], y: Array, sigma: Array | None):
        self.model = model
        self.design: Callable[[float, Sequence[Pair]], Array] = MODELS[model]
        self.pairs = list(pairs)
        self.y = np.asarray(y, dtype=float)
        self.w = np.ones_like(self.y) if sigma is None else 1.0 / np.asarray(sigma, dtype=float)
        self.b = self.w * self.y

    def whitened(self, phi: float) -> Array:
        return self.design(phi, self.pairs) * self.w[:, None]

    def inner(self, phi: float) -> tuple[float, Array]:
        bmat = self.whitened(phi)
        s, *_ = np.linalg.lstsq(bmat, self.b, rcond=None)
        r = bmat @ s - self.b
        return float(r @ r), s

    def chi2(self, phi: float) -> float:
        return self.inner(phi)[0]

    def chi2_fixed(self, phi: float, index: int, value: float) -> float:
        """χ² with order parameter ``index`` fixed at ``value``, the other one re-solved."""
        bmat = self.whitened(phi)
        other = 1 - index
        target = self.b - value * bmat[:, index]
        col = bmat[:, other]
        t = float(col @ target) / float(col @ col)
        r = target - t * col
        return float(r @ r)


def refine(problem: Problem) -> dict[str, object]:
    """Grid seeds over the folded domain, then bounded refinement of the best basin."""
    grid = np.arange(PHI_DOMAIN[0], PHI_DOMAIN[1] + GRID_STEP / 2, GRID_STEP)
    prof = np.array([problem.chi2(p) for p in grid])
    i = int(prof.argmin())
    lo, hi = grid[max(i - 1, 0)], grid[min(i + 1, len(grid) - 1)]
    res = optimize.minimize_scalar(
        problem.chi2, bounds=(lo, hi), method="bounded", options={"xatol": 1e-11, "maxiter": 500}
    )
    phi = float(res.x)
    chi2, s = problem.inner(phi)
    local_minima = [
        {"phi_grid_deg": float(grid[k]), "chi2": float(prof[k])}
        for k in range(len(grid))
        if (k == 0 or prof[k] < prof[k - 1]) and (k == len(grid) - 1 or prof[k] < prof[k + 1])
    ]
    return {
        "phi": phi,
        "chi2": chi2,
        "s": s,
        "grid_best_deg": float(grid[i]),
        "grid_local_minima": local_minima,
    }


def _crossing(f: Callable[[float], float], start: float, step: float, limit: float) -> float | None:
    """First root of f beyond ``start`` in the direction of ``step`` (None if ``limit`` is hit)."""
    a = start
    while True:
        b = a + step
        if (step > 0 and b >= limit) or (step < 0 and b <= limit):
            b = limit
        if f(b) > 0:
            return float(optimize.brentq(f, a, b, xtol=1e-13, rtol=1e-15, maxiter=500))
        if b == limit:
            return None
        a = b


def profile_interval_phi(problem: Problem, phi: float, chi2_min: float, delta: float = 1.0) -> list[float | None]:
    def f(p: float) -> float:
        return problem.chi2(p) - chi2_min - delta

    return [_crossing(f, phi, -0.005, PHI_DOMAIN[0]), _crossing(f, phi, +0.005, PHI_DOMAIN[1])]


def profile_chi2_order(problem: Problem, index: int, value: float, phi_hat: float, window: float = 3.0) -> float:
    lo, hi = max(PHI_DOMAIN[0], phi_hat - window), min(PHI_DOMAIN[1], phi_hat + window)
    res = optimize.minimize_scalar(
        lambda p: problem.chi2_fixed(p, index, value),
        bounds=(lo, hi),
        method="bounded",
        options={"xatol": 1e-11, "maxiter": 500},
    )
    return float(res.fun)


def profile_interval_order(
    problem: Problem,
    index: int,
    s_hat: float,
    phi_hat: float,
    chi2_min: float,
    delta: float = 1.0,
    step: float = 1e-3,
) -> list[float | None]:
    def f(v: float) -> float:
        return profile_chi2_order(problem, index, v, phi_hat) - chi2_min - delta

    return [_crossing(f, s_hat, -step, s_hat - 1.0), _crossing(f, s_hat, +step, s_hat + 1.0)]


def full_jacobian(problem: Problem, phi: float, s: Array, h: float = 1e-4) -> Array:
    """Whitened residual Jacobian in joint coordinates (φ in degrees, Szz, Δ)."""
    dphi = (problem.whitened(phi + h) - problem.whitened(phi - h)) @ s / (2 * h)
    return np.column_stack([dphi, problem.whitened(phi)])


def admissible(szz: float, delta: float) -> bool:
    """(2S + I)/3 ⪰ 0 with S = diag((−Szz+Δ)/2, (−Szz−Δ)/2, Szz)."""
    eig = np.array([(-szz + delta) / 2, (-szz - delta) / 2, szz])
    return bool(np.all((2 * eig + 1) / 3 >= 0))


def fit_report(problem: Problem, intervals: bool = True) -> dict[str, object]:
    """Refined optimum with the D3 diagnostics; intervals and covariance only with an error model."""
    opt = refine(problem)
    phi, chi2 = float(opt["phi"]), float(opt["chi2"])  # type: ignore[arg-type]
    s = np.asarray(opt["s"])
    bmat = problem.whitened(phi)
    sv = np.linalg.svd(bmat, compute_uv=False)
    pred = problem.design(phi, problem.pairs) @ s
    n, p_free = len(problem.y), 3
    jac = full_jacobian(problem, phi, s)
    report: dict[str, object] = {
        "phi_deg": phi,
        "Szz": float(s[0]),
        "Delta": float(s[1]),
        "N": n,
        "p_free": p_free,
        "nu": n - p_free,
        "objective": chi2,
        "predictions_Hz": pred.tolist(),
        "residuals_Hz": (pred - problem.y).tolist(),
        "rms_Hz": float(np.sqrt(np.mean((pred - problem.y) ** 2))),
        "grid_best_deg": opt["grid_best_deg"],
        "grid_local_minima": opt["grid_local_minima"],
        "validity": {
            "inner_rank": int(np.linalg.matrix_rank(bmat)),
            "inner_condition_number": float(sv[0] / sv[-1]),
            "joint_rank": int(np.linalg.matrix_rank(jac)),
            "physically_admissible": admissible(float(s[0]), float(s[1])),
        },
    }
    if intervals:
        cov = np.linalg.inv(jac.T @ jac)
        se = np.sqrt(np.diag(cov))
        report["covariance_full_jacobian"] = {
            "parameters": ["phi_deg", "Szz", "Delta"],
            "stderr": se.tolist(),
            "correlation": (cov / np.outer(se, se)).tolist(),
            "note": "known sigma; not rescaled by chi2_nu",
        }
        report["profile_intervals_68pct"] = {
            "delta_chi2": 1.0,
            "phi_deg": profile_interval_phi(problem, phi, chi2),
            "Szz": profile_interval_order(problem, 0, float(s[0]), phi, chi2),
            "Delta": profile_interval_order(problem, 1, float(s[1]), phi, chi2),
        }
    return report
