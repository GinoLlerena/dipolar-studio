"""The V0.3 preregistration as code (round 74): load it, hash its protocol, check its cross-field
invariants, bind a dataset's roster to its hash-verified couplings, and build the labels report
and its shareable summary.

The V1.5 report must go through ``dataset_report``: it refuses cells that do not cover the frozen
roster, always adds the frozen drop-one labels, and names the protocol revision it used. Only
``shareable`` output may leave the machine: per-cell targets, fits and signed discrepancies stay
local, since a reader could recover a restricted target by subtraction (§6).
"""

from __future__ import annotations

import csv
import dataclasses
import hashlib
import json
from collections.abc import Iterable
from pathlib import Path, PurePosixPath
from typing import Any

import numpy as np
import prereg_labels as pl

ROOT = Path(__file__).resolve().parents[2]
PREREG_PATH = ROOT / "docs" / "phase2" / "v0.3-preregistration.json"
#: The number of order parameters each point group's subspace has (V1.0 D-4).
SUBSPACE_DIMENSION = {"D6h": 1, "C2v": 2}


def load(path: Path = PREREG_PATH) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def protocol_sha256(prereg: dict[str, Any]) -> str:
    """The protocol revision: SHA-256 of the canonical JSON without the amendment ledger, so a
    ledger entry can name the revisions before and after it."""
    payload = {k: v for k, v in prereg.items() if k != "amendments"}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _contained(path: str, top: tuple[str, ...]) -> bool:
    parts = PurePosixPath(path).parts
    return bool(parts) and parts[0] in top and ".." not in parts and not PurePosixPath(path).is_absolute()


def validate(prereg: dict[str, Any]) -> list[str]:
    """Cross-field invariants the schema cannot express; an empty list when all hold."""
    problems = []
    for name, d in prereg["datasets"].items():
        est = d["estimands"]
        if len(set(est)) != len(est):
            problems.append(f"{name}: duplicate estimands")
        if d["roster_cells"] != d["conditions"] * len(est):
            problems.append(f"{name}: roster_cells is not conditions × estimands")
        if d["targets"]["count"] != d["roster_cells"]:
            problems.append(f"{name}: the target count is not the roster")
        conv = d["conversion_matrix"]
        if len(conv) != len(est) or any(len(row) != len(est) for row in conv):
            problems.append(f"{name}: the conversion matrix is not {len(est)} × {len(est)}")
        axes = np.array(d["frame_map_matrix"], dtype=float)
        if axes.shape != (3, 3) or not np.allclose(axes @ axes.T, np.eye(3)) or np.linalg.det(axes) <= 0:
            problems.append(f"{name}: the frame map is not a rotation")
        if len(d["orbits"]) != d["observations_per_condition"]:
            problems.append(f"{name}: one orbit per observation")
        if d["nu"] != d["observations_per_condition"] - SUBSPACE_DIMENSION.get(d["point_group"], -1):
            problems.append(f"{name}: nu is not N − d")
        if not _contained(d["couplings"]["path"], ("datasets", "datasets-local")):
            problems.append(f"{name}: the couplings path leaves the data directories")
        if not _contained(d["targets"]["path"], ("datasets-local",)):
            problems.append(f"{name}: the targets path leaves datasets-local")
    return problems


def frozen_roster(dataset: str, prereg: dict[str, Any] | None = None, root: Path = ROOT) -> list[tuple[str, str]]:
    """(condition, component) for every frozen cell, read from the dataset's couplings file after
    its SHA-256 is verified. Conditions are ``run/sample`` (benzene) or ``table/T`` (o-DCB)."""
    p = prereg or load()
    d = p["datasets"][dataset]
    path = root / d["couplings"]["path"]
    if not path.exists():
        raise FileNotFoundError(path)
    if hashlib.sha256(path.read_bytes()).hexdigest() != d["couplings"]["sha256"]:
        raise ValueError(f"{path}: the SHA-256 is not the frozen one")
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    key = ("run", "sample") if rows and "run" in rows[0] else ("table", "T_K")
    conditions = sorted({f"{r[key[0]]}/{r[key[1]]}" for r in rows})
    if len(conditions) != d["conditions"]:
        raise ValueError(f"{dataset}: {len(conditions)} conditions, not {d['conditions']}")
    return [(c, comp) for c in conditions for comp in d["estimands"]]


def dataset_report(
    dataset: str, cells: Iterable[pl.Cell], prereg: dict[str, Any] | None = None, root: Path = ROOT
) -> dict[str, Any]:
    """The full-data label (primary), the frozen drop-one labels, and the protocol revision."""
    p = prereg or load()
    cells = list(cells)
    roster = frozen_roster(dataset, p, root)
    drops = p["criteria"]["sensitivity"].get(dataset, [])
    if drops:
        report: dict[str, Any] = dict(pl.sensitivity(cells, roster, drops))
    else:
        report = {"full": pl.dataset_label(cells, roster), "fragile": False}
    report["dataset"] = dataset
    report["protocol_sha256"] = protocol_sha256(p)
    return report


def shareable(report: dict[str, Any]) -> dict[str, Any]:
    """What may be shared: the labels and their counts, and the protocol revision. No per-cell
    value, fit or discrepancy."""
    labels = {k: dataclasses.asdict(v) for k, v in report.items() if isinstance(v, pl.Label)}
    return {
        "dataset": report["dataset"],
        "protocol_sha256": report["protocol_sha256"],
        "labels": labels,
        "fragile": bool(report["fragile"]),
    }
