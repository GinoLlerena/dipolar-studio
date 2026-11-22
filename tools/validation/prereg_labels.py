"""The V0.3 preregistered comparison and label rules (docs/phase2/v0.3-preregistration.md §6–§7).

The V1.5 report builds one ``Cell`` per frozen (condition, component) with ``classify`` and turns
them into a dataset label with ``dataset_label``; ``sensitivity`` gives the drop-one labels. The
rules are frozen: changing them is an amendment (§8).
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

Status = Literal["agrees", "disagrees", "pending"]
STATUSES: frozenset[str] = frozenset({"agrees", "disagrees", "pending"})

#: From the preregistration's JSON (criteria.independent); tests check that they agree.
RELATIVE_TOLERANCE = 0.05
PRECISION_FACTOR = 2.0
#: The precedence of the dataset labels, first match wins.
PRECEDENCE = (
    "unresolved failure",
    "explained discrepancy",
    "pending",
    "partially supported",
    "experimentally supported",
)
#: The authors' analysis track (V0.3 §6, criteria.reproduction): its label, the fallback's label
#: and the four documented inputs a reproduction claim requires.
REPRODUCTION_LABEL = "reproduction (the authors' analysis)"
FALLBACK_LABEL = "approximate reproduction (assumed weights 1/σ²)"
REPRODUCTION_REQUIREMENTS = ("geometry", "objective", "weights", "corrections")
ReproductionMode = Literal["reproduction", "fallback", "pending"]


@dataclass(frozen=True)
class Cell:
    condition: str
    component: str
    status: Status
    reason: str = ""
    reviewed: bool = False  # a disagreement with a reviewed README entry

    def __post_init__(self) -> None:
        if self.status not in STATUSES:
            raise ValueError(f"unknown cell status {self.status!r}")


@dataclass(frozen=True)
class Label:
    name: str
    roster: int
    compared: int
    agreeing: int
    disagreeing: int
    pending: int


def agrees_independent(component: str, s: float, s_pub: float, p: float, s_zz_pub: float | None = None) -> bool:
    """The independent-support criterion: |S − S_pub| ≤ 0.05·|S_zz,pub| + 2p, where S_zz,pub is
    S_pub itself for S_zz (an axial-scale margin for the anisotropy)."""
    if component == "S_zz":
        scale = abs(s_pub)
    elif s_zz_pub is None:
        raise ValueError("the anisotropy's margin needs the published S_zz of the same condition")
    else:
        scale = abs(s_zz_pub)
    return abs(s - s_pub) <= RELATIVE_TOLERANCE * scale + PRECISION_FACTOR * p


def classify(
    condition: str,
    component: str,
    *,
    rank_verified: bool,
    target: tuple[float, float] | None,
    s: float | None,
    s_zz_pub: float | None = None,
    reviewed: bool = False,
) -> Cell:
    """One cell. Eligibility, in order: a verified rank, a target (value, precision), and, for the
    anisotropy, the published S_zz of the same condition."""
    if not rank_verified or s is None:
        return Cell(condition, component, "pending", "rank-unverified")
    if target is None:
        return Cell(condition, component, "pending", "no-target")
    if component != "S_zz" and s_zz_pub is None:
        return Cell(condition, component, "pending", "s_zz-target-pending")
    value, precision = target
    ok = agrees_independent(component, s, value, precision, s_zz_pub)
    return Cell(condition, component, "agrees" if ok else "disagrees", reviewed=reviewed and not ok)


def dataset_label(cells: Iterable[Cell], roster: Sequence[tuple[str, str]]) -> Label:
    """The dataset label over exactly the frozen roster (one cell per condition and component)."""
    cells = list(cells)
    keys = Counter((c.condition, c.component) for c in cells)
    if set(keys) != set(roster) or any(n != 1 for n in keys.values()) or len(set(roster)) != len(roster):
        raise ValueError("the cells must cover the frozen roster exactly once")
    agreeing = sum(c.status == "agrees" for c in cells)
    disagreeing = [c for c in cells if c.status == "disagrees"]
    pending = sum(c.status == "pending" for c in cells)
    if any(not c.reviewed for c in disagreeing):
        name = "unresolved failure"
    elif disagreeing:
        name = "explained discrepancy"
    elif agreeing == 0:
        name = "pending"
    elif agreeing == len(roster):
        name = "experimentally supported"
    else:
        name = "partially supported"
    return Label(name, len(roster), agreeing + len(disagreeing), agreeing, len(disagreeing), pending)


def sensitivity(cells: Iterable[Cell], roster: Sequence[tuple[str, str]], drop: Sequence[str]) -> dict[str, object]:
    """The full-data label (primary) and the label without each listed condition, with
    ``fragile`` true when any drop-one label differs from the full one."""
    cells = list(cells)
    conditions = {k[0] for k in roster}
    if not drop or any(c not in conditions for c in drop):
        raise ValueError("the sensitivity needs its frozen conditions, each in the roster")
    report: dict[str, object] = {"full": dataset_label(cells, roster)}
    for condition in drop:
        report[f"without {condition}"] = dataset_label(
            [c for c in cells if c.condition != condition], [k for k in roster if k[0] != condition]
        )
    full = report["full"]
    assert isinstance(full, Label)
    report["fragile"] = any(
        isinstance(v, Label) and v.name != full.name for k, v in report.items() if k.startswith("without ")
    )
    return report


# --------------------------------------------------------------- the reproduction track (§6)
#: A printed table token: a plain decimal with its uncertainty in last-place units, "−0.6123(12)".
_TOKEN = re.compile(r"[-\u2212]?(\d+)\.(\d+)\((\d+)\)")


def table_margin(token: str) -> float | None:
    """max(printed σ, half a unit in the last printed digit), from the token's own digits:
    trailing zeros are printed digits. None when the token carries no printed σ."""
    m = _TOKEN.fullmatch(token.strip())
    if m is None:
        return None
    unit = Decimal(1).scaleb(-len(m.group(2)))
    return float(max(Decimal(int(m.group(3))) * unit, unit / 2))


def figure_margin(p: float | None) -> float | None:
    """2p for a digitized target; None without a positive, finite precision."""
    if p is None or not math.isfinite(p) or p <= 0:
        return None
    return PRECISION_FACTOR * p


def reproduction_mode(documented: Iterable[str]) -> ReproductionMode:
    """``reproduction`` when all four inputs are documented; ``fallback`` (weighted least squares
    with 1/σ², the authors' geometry, documented corrections only) when the geometry is but the
    weights or the objective are not; otherwise ``pending``. Undocumented corrections with a known
    objective and weights support neither: pending."""
    have = set(documented)
    if have - set(REPRODUCTION_REQUIREMENTS):
        raise ValueError(f"unknown reproduction inputs: {sorted(have - set(REPRODUCTION_REQUIREMENTS))}")
    if have == set(REPRODUCTION_REQUIREMENTS):
        return "reproduction"
    if "geometry" in have and not {"weights", "objective"} <= have:
        return "fallback"
    return "pending"


def reproduction_track_label(mode: ReproductionMode) -> str:
    """Every fallback result, pass or fail, carries the fallback label: it is not a reproduction claim."""
    if mode not in ("reproduction", "fallback", "pending"):
        raise ValueError(f"unknown reproduction mode {mode!r}")
    return FALLBACK_LABEL if mode == "fallback" else REPRODUCTION_LABEL


def classify_reproduction(
    condition: str,
    component: str,
    *,
    mode: ReproductionMode,
    rank_verified: bool,
    s: float | None,
    target: tuple[float, float | None] | None,
    reviewed: bool = False,
) -> Cell:
    """One cell of the authors' analysis track: agrees when |S − S_pub| ≤ margin (the table or
    figure margin, inclusive). Pending, in order: undocumented inputs, an unverified rank, no
    target, no precision."""
    if mode == "pending":
        return Cell(condition, component, "pending", "inputs-undocumented")
    if not rank_verified or s is None:
        return Cell(condition, component, "pending", "rank-unverified")
    if target is None:
        return Cell(condition, component, "pending", "no-target")
    value, margin = target
    if margin is None:
        return Cell(condition, component, "pending", "no-precision")
    ok = abs(s - value) <= margin
    return Cell(condition, component, "agrees" if ok else "disagrees", reviewed=reviewed and not ok)
