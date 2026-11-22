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
import re
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


_SHA256 = re.compile(r"[0-9a-f]{64}")


def spot_check_signed(dataset: str, receipt: dict[str, str] | None, prereg: dict[str, Any]) -> bool:
    """Amendment P-2 (``reporting.spot_check_gating``): a receipt counts only if it is for this
    dataset and for the artifact P-2 names for it, at that artifact's frozen SHA-256, with no
    other field. A protocol without the field (the original V0.3) has no gating: always True."""
    gating = prereg.get("reporting", {}).get("spot_check_gating")
    if gating is None:
        return True
    if receipt is None or set(receipt) != {"dataset", "artifact", "sha256"}:
        return False
    artifact = gating["checked_artifact"].get(dataset)
    if artifact is None or receipt["dataset"] != dataset or receipt["artifact"] != artifact:
        return False
    frozen = prereg["datasets"][dataset][artifact]["sha256"]
    return bool(_SHA256.fullmatch(receipt["sha256"])) and receipt["sha256"] == frozen


def classify_gated(
    condition: str,
    component: str,
    *,
    dataset: str,
    receipt: dict[str, str] | None,
    prereg: dict[str, Any],
    rank_verified: bool,
    target: tuple[float, float] | None,
    s: float | None,
    s_zz_pub: float | None = None,
    reviewed: bool = False,
) -> pl.Cell:
    """``prereg_labels.classify`` with P-2 applied first: until the spot-check is signed, the
    target and the axial scale are withheld (``no-target``, in both tracks); ``rank-unverified``
    keeps its precedence."""
    if not spot_check_signed(dataset, receipt, prereg):
        target, s_zz_pub = None, None
    return pl.classify(
        condition, component, rank_verified=rank_verified, target=target, s=s, s_zz_pub=s_zz_pub, reviewed=reviewed
    )


def label_notes(dataset: str, *, receipt: dict[str, str] | None, prereg: dict[str, Any]) -> list[str]:
    """The notes every label of the dataset carries (V0.3 §7): development data, and for
    ortho-dichlorobenzene the open spot-check note while its check is open (P-2)."""
    notes = ["development data, no independent holdout"]
    gating = prereg.get("reporting", {}).get("spot_check_gating")
    if gating and dataset in gating["open_note_datasets"] and not spot_check_signed(dataset, receipt, prereg):
        notes.append(gating["open_note"])
    return notes


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
