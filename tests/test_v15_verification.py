"""Phase 2 V1.5b: the report workflow's tests, frozen before its implementation.

They are written from the plan (docs/phase2/v1.5-plan.md, "V1.5b" and "Frozen comparison
procedure"), V0.3 §3–§7 (docs/phase2/v0.3-preregistration.md) and the V1.5a ledger
(docs/phase2/verification/gates.md), not from the code they check. What they cover, in the plan's
words: hashes, keys and frames, roster completeness and uniqueness, σ/sign/factor, rank, gated
targets, covariance off-diagonals, both comparison margins, review receipts, drop-one
sensitivity, absent local files, Python and HTTP agreement, and synthetic fit-value sentinels
across outward output and failure paths.

**No experimental coupling is fitted here** (the V1.5a first-fit gate). Every dataset below is
synthetic: its conditions, couplings and targets are made up, written to a temporary root, and
bound to a copy of the preregistration whose SHA-256 fields are those of the synthetic files. The
real files are never read.

**Pending implementation.** ``tools/validation/verification.py`` and the reproduction margin in
``prereg_labels`` are V1.5b's. While that module's file does not exist, these tests xfail through
``_v()``, and through that alone; once it exists, any exception fails (round 82).
"""

from __future__ import annotations

import asyncio
import copy
import csv
import hashlib
import importlib
import io
import json
import math
import subprocess
import sys
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from dipolar_core.nuclides import dipolar_constant_hz_a3

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "validation"))

import prereg  # noqa: E402
import prereg_labels as pl  # noqa: E402

PREREG = prereg.load()
VERIFICATION_PY = ROOT / "tools" / "validation" / "verification.py"
BENZENE, ODCB = "benzene-taggar2006", "odcb-chandrakumar1993"
K = dipolar_constant_hz_a3("1H", "1H")


def _v() -> Any:
    """The V1.5b module, or an xfail while (and only while) its file does not exist."""
    if not VERIFICATION_PY.is_file():
        pytest.xfail("V1.5b: tools/validation/verification.py is not written yet")
    return importlib.import_module("verification")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ------------------------------------------------------------ an independent forward model
def _protons(dataset: str) -> dict[str, np.ndarray]:
    """The declared geometry's protons in the paper's frame (z normal to the ring), built here from
    the frozen radii and ring angles, independently of the engine."""
    g, d = PREREG["geometry"], PREREG["datasets"][dataset]
    r = g["r_cc_angstrom"] + g["r_ch_angstrom"]
    out = {}
    for name, deg in d["ring_positions"].items():
        a = math.radians(deg)
        out[name] = np.array([r * math.cos(a), r * math.sin(a), 0.0])
    return out


def _coupling(dataset: str, pair: tuple[str, str], s_paper: np.ndarray) -> float:
    """The scalar law D = K·uᵀSu/r³ for an order matrix S in the paper's frame."""
    h = _protons(dataset)
    v = h[pair[1]] - h[pair[0]]
    r = float(np.linalg.norm(v))
    u = v / r
    return float(K * (u @ s_paper @ u) / r**3)


def _benzene_s(s_zz: float) -> np.ndarray:
    """Axial: S_xx = S_yy = −S_zz/2 (V0.3 §4)."""
    return np.diag([-s_zz / 2, -s_zz / 2, s_zz])


def _odcb_s(s_zz: float, aniso: float) -> np.ndarray:
    """The paper's frame: S_zz normal to the ring, S_xx − S_yy in its plane."""
    s_xx = (aniso - s_zz) / 2
    return np.diag([s_xx, s_xx - aniso, s_zz])


# ------------------------------------------------------------------- synthetic datasets
#: Synthetic condition keys (run/sample for benzene, table/T for o-DCB), not the sources'. The
#: o-DCB set keeps the frozen drop-one conditions II/300 and II/302 so the sensitivity applies.
BENZENE_CONDITIONS = [("9", f"s{k:02d}") for k in range(1, 16)]
ODCB_CONDITIONS = [("I", str(t)) for t in range(310, 328, 2)] + [("II", str(t)) for t in range(290, 316, 2)]
assert len(BENZENE_CONDITIONS) == PREREG["datasets"][BENZENE]["conditions"]
assert len(ODCB_CONDITIONS) == PREREG["datasets"][ODCB]["conditions"]
assert {"II/300", "II/302"} <= {f"{a}/{b}" for a, b in ODCB_CONDITIONS}

#: Deterministic offsets (Hz) and heterogeneous σ (Hz), so the weights matter and ν > 0 has a residual.
OFFSETS = {BENZENE: (0.31, -0.22, 0.12), ODCB: (0.21, -0.17, 0.09, -0.05)}
SIGMAS = {BENZENE: (0.15, 0.6, 1.1), ODCB: (0.2, 0.9, 0.4, 1.3)}


def _truth(dataset: str, i: int) -> dict[str, float]:
    """A synthetic tensor for condition i: not a value from any source."""
    if dataset == BENZENE:
        return {"S_zz": -0.0612 - 0.0011 * i}
    return {"S_zz": -0.1834 + 0.0013 * i, "S_xx-S_yy": 0.0417 + 0.0009 * i}


def _s_paper(dataset: str, t: dict[str, float]) -> np.ndarray:
    return _benzene_s(t["S_zz"]) if dataset == BENZENE else _odcb_s(t["S_zz"], t["S_xx-S_yy"])


def _condition_keys(dataset: str) -> list[str]:
    return [f"{a}/{b}" for a, b in (BENZENE_CONDITIONS if dataset == BENZENE else ODCB_CONDITIONS)]


def _couplings_rows(dataset: str, truths: dict[str, dict[str, float]], *, offsets: bool = True) -> list[dict[str, str]]:
    d = PREREG["datasets"][dataset]
    rows = []
    for key in _condition_keys(dataset):
        a, b = key.split("/")
        s = _s_paper(dataset, truths[key])
        for j, (orbit, pair) in enumerate(d["orbits"].items()):
            value = _coupling(dataset, tuple(pair), s) + (OFFSETS[dataset][j] if offsets else 0.0)
            sigma = SIGMAS[dataset][j]
            if dataset == BENZENE:
                rows.append(
                    {
                        "run": a,
                        "sample": b,
                        "coupling": orbit,
                        "spin_a": pair[0],
                        "spin_b": pair[1],
                        "D_obs_Hz": repr(value),
                        "sigma_Hz": repr(sigma),
                    }
                )
            else:
                rows.append(
                    {
                        "table": a,
                        "T_K": b,
                        "coupling": orbit,
                        "D_token": repr(value),
                        "sigma_token": repr(sigma),
                        "D_Hz": repr(value),
                        "sigma_Hz": repr(sigma),
                    }
                )
    return rows


def _target_rows(
    dataset: str,
    targets: dict[tuple[str, str], tuple[float, float] | None],
    tokens: dict[str, str] | None = None,
) -> list[dict[str, str]]:
    rows = []
    for (key, comp), t in targets.items():
        a, b = key.split("/")
        if dataset == BENZENE:
            value, sigma = t if t is not None else (math.nan, math.nan)
            token = (tokens or {}).get(key, f"{value}({sigma})")
            rows.append({"run": a, "sample": b, "S_zz_token": token, "S_zz": repr(value), "sigma": repr(sigma)})
        else:
            rows.append(
                {
                    "table": a,
                    "T_K": b,
                    "component": comp,
                    "value": "" if t is None else repr(t[0]),
                    "precision": "" if t is None else repr(t[1]),
                    "status": "pending" if t is None else "target",
                    "flags": "" if t is not None else "no-marker",
                }
            )
    return rows


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    path.write_text(buf.getvalue(), encoding="utf-8")


def _default_targets(dataset: str, truths: dict[str, dict[str, float]]) -> dict[tuple[str, str], tuple[float, float]]:
    """Targets equal to the synthetic truth, with a small precision: every compared cell agrees."""
    return {
        (key, comp): (truths[key][comp], 0.0004) for key in _condition_keys(dataset) for comp in _estimands(dataset)
    }


def _estimands(dataset: str) -> list[str]:
    return list(PREREG["datasets"][dataset]["estimands"])


class Synthetic:
    """A synthetic dataset under a temporary root, with its own copy of the preregistration."""

    def __init__(
        self,
        root: Path,
        dataset: str,
        *,
        truths: dict[str, dict[str, float]] | None = None,
        targets: dict[tuple[str, str], tuple[float, float] | None] | None = None,
        couplings_rows: list[dict[str, str]] | None = None,
        offsets: bool = True,
        tokens: dict[str, str] | None = None,
    ) -> None:
        self.root, self.dataset = root, dataset
        self.truths = truths or {k: _truth(dataset, i) for i, k in enumerate(_condition_keys(dataset))}
        self.targets = targets if targets is not None else _default_targets(dataset, self.truths)
        self.prereg = copy.deepcopy(PREREG)
        d = self.prereg["datasets"][dataset]
        self.couplings_path = root / d["couplings"]["path"]
        self.targets_path = root / d["targets"]["path"]
        _write_csv(self.couplings_path, couplings_rows or _couplings_rows(dataset, self.truths, offsets=offsets))
        _write_csv(self.targets_path, _target_rows(dataset, self.targets, tokens))
        d["couplings"]["sha256"] = _sha(self.couplings_path)
        d["targets"]["sha256"] = _sha(self.targets_path)
        assert prereg.validate(self.prereg) == []

    @property
    def protocol(self) -> str:
        return prereg.protocol_sha256(self.prereg)

    def receipt(self) -> dict[str, str]:
        """The owner's signed spot-check receipt (P-2), bound to the checked artifact's hash."""
        artifact = self.prereg["reporting"]["spot_check_gating"]["checked_artifact"][self.dataset]
        return {
            "dataset": self.dataset,
            "artifact": artifact,
            "sha256": self.prereg["datasets"][self.dataset][artifact]["sha256"],
        }

    def submission(self, **changes: Any) -> dict[str, Any]:
        """The first-fit gate's record, made immediately before the submission (plan, V1.5a)."""
        record: dict[str, Any] = {
            "dataset": self.dataset,
            "runner": "owner",
            "at": datetime(2026, 11, 25, 10, 0, tzinfo=UTC),
            "release_or_commit": "v0.2.0b1",
            "protocol_sha256": self.protocol,
        }
        record.update(changes)
        return record

    def logged(self, **changes: Any) -> dict[str, Any]:
        """The submission record, logged and committed in this root's first-fit log, so the
        runner's own authorization check accepts it (round 84, A1)."""
        record = self.submission(**changes)
        self.log(record)
        return record

    def log(self, record: dict[str, Any]) -> None:
        """Append the record to this root's synthetic first-fit log and commit the ledger. A record
        the log cannot hold (an unknown runner, a time that is not a UTC minute) is not logged."""
        at = record.get("at")
        if not (
            isinstance(at, datetime)
            and at.utcoffset() is not None
            and not (at.second or at.microsecond)
            and record.get("runner") in ("owner", "participant", "agent")
            and record.get("dataset") in (BENZENE, ODCB)
        ):
            return
        row = (
            f"| {at.astimezone(UTC).strftime('%Y-%m-%dT%H:%MZ')} | submission | {record['dataset']} | "
            f"{record['runner']} | {record['release_or_commit']} | {record['protocol_sha256']} |"
        )
        rows = getattr(self, "_log_rows", [])
        if row in rows:
            return
        self._log_rows = [*rows, row]
        ledger = self.root / LEDGER_REL
        ledger.parent.mkdir(parents=True, exist_ok=True)
        ledger.write_text(SYNTHETIC_LEDGER + "".join(f"{r}\n" for r in self._log_rows), encoding="utf-8")
        if not (self.root / ".git").exists():
            _git(self.root, "init", "-q")
        _git(self.root, "add", str(LEDGER_REL))
        _git(self.root, "commit", "-q", "-m", "first-fit log")


# Round 84 (A1): the runner checks the authorization itself, against the ledger committed in its
# root. Each synthetic root that is fitted holds this minimal ledger (its §3 row and its §10
# first-fit log, with every approval before a synthetic freeze) and its logged submissions. The
# runner's clock is fixed just after the synthetic submission time.
LEDGER_REL = Path("docs/phase2/verification/gates.md")
NOW = datetime(2026, 11, 25, 12, 0, tzinfo=UTC)
SYNTHETIC_LEDGER = (
    "# Synthetic ledger (tests only)\n\n"
    "## 3. Chronology (first-fit gate)\n\n"
    "| Field | Value |\n|---|---|\n"
    "| First experimental fit submission (UTC, release or commit, protocol revision, dataset, runner role) "
    "| empty |\n\n"
    "## 10. First-fit log\n\n"
    "| UTC | Event | Dataset | Runner | Release or commit | Protocol revision |\n"
    "|---|---|---|---|---|---|\n"
    "| 2026-11-21T14:59Z | decisions approved | — | — | — | — |\n"
    "| 2026-11-21T15:00Z | amendments approved | — | — | — | — |\n"
    "| 2026-11-22T14:11Z | no-fit attestation | — | — | — | — |\n"
    "| 2026-11-24T09:00Z | freeze approved | — | — | — | — |\n"
)


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@invalid", *args],
        cwd=root,
        check=True,
        capture_output=True,
    )


@pytest.fixture(autouse=True)
def _clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """The runner's clock (UTC), fixed after the synthetic submissions."""
    if VERIFICATION_PY.is_file():
        monkeypatch.setattr(importlib.import_module("verification"), "_now", lambda: NOW)


# --------------------------------------------------------------------- registry clients
@pytest.fixture
def call() -> Any:
    """The in-process Python adapter (``LocalClient``) over a fresh session."""
    return _v().local_call()


class _Asgi:
    """The HTTP adapter, driven in process: ``POST /api/v1/ops/{name}`` with a bearer token."""

    PORT = 8765

    def __init__(self) -> None:
        from dipolar_app.auth import Credentials
        from dipolar_app.http import create_app
        from dipolar_app.jobs import JobRunner
        from dipolar_app.operations import build_registry
        from dipolar_app.policy import Principal, Tier
        from dipolar_app.registry import CONTRACT_VERSION
        from dipolar_app.session import Session

        session = Session(None, contract_version=CONTRACT_VERSION)
        JobRunner(session, mode="thread")
        robot = Principal(actor="script:verification", tier=Tier.APPLY, human=False)
        self.app = create_app(build_registry(), session, Credentials({"tok": robot}), port=self.PORT)
        self.calls: list[str] = []

    def envelope(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps({"args": args}, allow_nan=False).encode()
        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": f"/api/v1/ops/{name}",
            "raw_path": f"/api/v1/ops/{name}".encode(),
            "query_string": b"",
            "root_path": "",
            "headers": [
                (b"host", f"127.0.0.1:{self.PORT}".encode()),
                (b"authorization", b"Bearer tok"),
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
            "server": ("127.0.0.1", self.PORT),
            "client": ("127.0.0.1", 50000),
        }
        sent: list[dict[str, Any]] = []
        delivered = {"done": False}

        async def receive() -> dict[str, Any]:
            if delivered["done"]:
                await asyncio.sleep(3600)
            delivered["done"] = True
            return {"type": "http.request", "body": body, "more_body": False}

        async def send(message: dict[str, Any]) -> None:
            sent.append(message)

        asyncio.run(self.app(scope, receive, send))
        payload = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
        out: dict[str, Any] = json.loads(payload)
        return out

    def __call__(self, name: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
        self.calls.append(name)
        envelope = self.envelope(name, args or {})
        if not envelope.get("ok"):
            raise _v().RegistryError(name, envelope.get("error", {}).get("code", "UNKNOWN"))
        result: dict[str, Any] = envelope["result"]
        return result


def _never(name: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
    raise AssertionError(f"the registry was called ({name}) although the inputs block the comparison")


# ======================================================================= hashes and inputs
@pytest.mark.parametrize("dataset", [BENZENE, ODCB])
def test_the_inputs_verify_against_their_frozen_hashes(tmp_path: Path, dataset: str) -> None:
    v, syn = _v(), Synthetic(tmp_path, dataset)
    assert v.check_inputs(dataset, prereg=syn.prereg, root=tmp_path) == []
    observed = v.read_couplings(dataset, prereg=syn.prereg, root=tmp_path)
    assert sorted(observed) == sorted(_condition_keys(dataset))


@pytest.mark.parametrize("which", ["couplings", "targets"])
@pytest.mark.parametrize("dataset", [BENZENE, ODCB])
def test_a_changed_input_blocks_its_comparison(tmp_path: Path, dataset: str, which: str) -> None:
    """Corrupt source material blocks the comparison: nothing is fitted, no label is made."""
    v, syn = _v(), Synthetic(tmp_path, dataset)
    path = syn.couplings_path if which == "couplings" else syn.targets_path
    path.write_bytes(path.read_bytes() + b"\n")
    problems = v.check_inputs(dataset, prereg=syn.prereg, root=tmp_path)
    assert problems and any(str(path.relative_to(tmp_path)) in p for p in problems)
    report = v.run_report(
        dataset, call=_never, prereg=syn.prereg, root=tmp_path, submission=syn.logged(), receipt=syn.receipt()
    )
    assert report["status"] == "blocked" and "tracks" not in report and "cells" not in report
    shared = v.shared_output(report)
    assert shared["status"] == "blocked" and "tracks" not in shared


@pytest.mark.parametrize("which", ["couplings", "targets"])
@pytest.mark.parametrize("dataset", [BENZENE, ODCB])
def test_absent_local_files_are_reported_not_certified(tmp_path: Path, dataset: str, which: str) -> None:
    """Public CI has no local evidence: the report says so, names the path, and certifies nothing."""
    v, syn = _v(), Synthetic(tmp_path, dataset)
    path = syn.couplings_path if which == "couplings" else syn.targets_path
    path.unlink()
    report = v.run_report(
        dataset, call=_never, prereg=syn.prereg, root=tmp_path, submission=syn.logged(), receipt=syn.receipt()
    )
    assert report["status"] == "local evidence unavailable"
    assert report["missing"] == [str(path.relative_to(tmp_path))]
    assert "tracks" not in report and "cells" not in report
    shared = v.shared_output(report)
    assert shared == {
        "dataset": dataset,
        "protocol_sha256": syn.protocol,
        "status": "local evidence unavailable",
    }
    with pytest.raises(ValueError):
        v.page_lines(shared)


# ============================================================== keys, roster and frames
def _mutate_rows(dataset: str, rows: list[dict[str, str]], name: str) -> list[dict[str, str]]:
    rows = [dict(r) for r in rows]
    cond_cols = ("run", "sample") if dataset == BENZENE else ("table", "T_K")
    d_col = "D_obs_Hz" if dataset == BENZENE else "D_Hz"
    s_col = "sigma_Hz"
    if name == "an unknown coupling key":
        rows[0]["coupling"] = "D15"
    elif name == "a coupling repeated":
        rows.append(dict(rows[0]))
    elif name == "a coupling missing":
        rows.pop(1)
    elif name == "a condition missing":
        first = (rows[0][cond_cols[0]], rows[0][cond_cols[1]])
        rows = [r for r in rows if (r[cond_cols[0]], r[cond_cols[1]]) != first]
    elif name == "an extra condition":
        extra = [dict(r) for r in rows[: len(PREREG["datasets"][dataset]["orbits"])]]
        for r in extra:
            r[cond_cols[1]] = "999"
        rows += extra
    elif name == "a non-numeric coupling":
        rows[2][d_col] = "-1024.1749x"
    elif name == "a non-finite coupling":
        rows[2][d_col] = "nan"
    elif name == "a zero sigma":
        rows[2][s_col] = "0"
    elif name == "a negative sigma":
        rows[2][s_col] = "-0.5"
    elif name == "an infinite sigma":
        rows[2][s_col] = "inf"
    return rows


KEY_MUTANTS = [
    "an unknown coupling key",
    "a coupling repeated",
    "a coupling missing",
    "a condition missing",
    "an extra condition",
    "a non-numeric coupling",
    "a non-finite coupling",
    "a zero sigma",
    "a negative sigma",
    "an infinite sigma",
]


@pytest.mark.parametrize("name", KEY_MUTANTS)
@pytest.mark.parametrize("dataset", [BENZENE, ODCB])
def test_the_couplings_must_bind_to_the_frozen_roster_and_orbits(tmp_path: Path, dataset: str, name: str) -> None:
    """Each condition has exactly the frozen orbit keys once, with a finite D and a positive σ."""
    v = _v()
    good = Synthetic(tmp_path / "good", dataset)
    rows = _mutate_rows(dataset, _couplings_rows(dataset, good.truths), name)
    syn = Synthetic(tmp_path / "bad", dataset, couplings_rows=rows)
    with pytest.raises(ValueError):
        v.read_couplings(dataset, prereg=syn.prereg, root=syn.root)
    report = v.run_report(
        dataset, call=_never, prereg=syn.prereg, root=syn.root, submission=syn.logged(), receipt=syn.receipt()
    )
    assert report["status"] == "blocked" and "tracks" not in report


TARGET_MUTANTS = ["a target missing", "a target repeated", "an unknown target key", "a non-numeric target"]


@pytest.mark.parametrize("name", TARGET_MUTANTS)
@pytest.mark.parametrize("dataset", [BENZENE, ODCB])
def test_the_targets_must_cover_the_roster_once(tmp_path: Path, dataset: str, name: str) -> None:
    v = _v()
    syn = Synthetic(tmp_path, dataset)
    rows = _target_rows(dataset, syn.targets)
    if name == "a target missing":
        rows.pop(0)
    elif name == "a target repeated":
        rows.append(dict(rows[0]))
    elif name == "an unknown target key":
        rows[0][("sample" if dataset == BENZENE else "T_K")] = "999"
    else:
        rows[0][("S_zz" if dataset == BENZENE else "value")] = "0.0612x"
    _write_csv(syn.targets_path, rows)
    syn.prereg["datasets"][dataset]["targets"]["sha256"] = _sha(syn.targets_path)
    with pytest.raises(ValueError):
        v.read_targets(dataset, prereg=syn.prereg, root=tmp_path)


def test_a_pending_target_is_read_as_no_target(tmp_path: Path) -> None:
    """o-DCB's digitizer marks a cell it cannot assign ``pending``: that cell has no target."""
    v = _v()
    truths = {k: _truth(ODCB, i) for i, k in enumerate(_condition_keys(ODCB))}
    targets: dict[tuple[str, str], tuple[float, float] | None] = dict(_default_targets(ODCB, truths))
    targets[("II/296", "S_xx-S_yy")] = None
    syn = Synthetic(tmp_path, ODCB, truths=truths, targets=targets)
    read = v.read_targets(ODCB, prereg=syn.prereg, root=tmp_path)
    assert read[("II/296", "S_xx-S_yy")] is None
    assert read[("II/296", "S_zz")] == pytest.approx(targets[("II/296", "S_zz")])
    assert set(read) == set(prereg.frozen_roster(ODCB, syn.prereg, tmp_path))


@pytest.mark.parametrize("dataset", [BENZENE, ODCB])
def test_the_declared_geometry_and_axes_are_the_frozen_ones(dataset: str) -> None:
    """The protons sit at the frozen radii and angles; the declared axes are the frozen map."""
    v = _v()
    elements, xyz, index = v.declared_geometry(dataset, PREREG)
    assert len(elements) == len(xyz) and set(index) == set(PREREG["datasets"][dataset]["ring_positions"])
    for name, p in _protons(dataset).items():
        assert elements[index[name]] == "H"
        assert np.allclose(xyz[index[name]], p, atol=1e-12)
    sym = v.symmetry_declaration(dataset, PREREG)
    assert sym["point_group"] == PREREG["datasets"][dataset]["point_group"]
    assert np.allclose(np.array(sym["axes"], dtype=float), np.array(PREREG["datasets"][dataset]["frame_map_matrix"]))


@pytest.mark.parametrize("dataset", [BENZENE, ODCB])
def test_the_fit_recovers_a_synthetic_tensor_in_the_papers_frame(tmp_path: Path, dataset: str, call: Any) -> None:
    """Exact synthetic couplings, fitted through the registry in V1's frame, come back as the
    paper-frame estimands through the frozen map and conversion (V0.3 §5). The o-DCB tensor is
    anisotropic in the ring plane, so a wrong map or conversion changes the answer."""
    v = _v()
    syn = Synthetic(tmp_path, dataset, offsets=False)
    observed = v.read_couplings(dataset, prereg=syn.prereg, root=tmp_path)
    for key in _condition_keys(dataset)[:3]:
        fit = v.paper_fit(dataset, syn.prereg, v.fit_condition(call, dataset, syn.prereg, observed[key]))
        assert fit.rank_verified
        for comp in _estimands(dataset):
            assert fit.estimates[comp] == pytest.approx(syn.truths[key][comp], abs=1e-10), (key, comp)


def test_one_session_fits_each_condition_on_its_own(tmp_path: Path, call: Any) -> None:
    """Nothing is pooled (V0.3 §1): fitting a second condition in the same session gives that
    condition's answer, the same as fitting it first in a fresh session."""
    v = _v()
    syn = Synthetic(tmp_path, ODCB, offsets=False)
    observed = v.read_couplings(ODCB, prereg=syn.prereg, root=tmp_path)
    a, b = _condition_keys(ODCB)[0], _condition_keys(ODCB)[-1]
    v.fit_condition(call, ODCB, syn.prereg, observed[a])
    second = v.paper_fit(ODCB, syn.prereg, v.fit_condition(call, ODCB, syn.prereg, observed[b]))
    fresh = v.paper_fit(ODCB, syn.prereg, v.fit_condition(v.local_call(), ODCB, syn.prereg, observed[b]))
    assert second.estimates == pytest.approx(fresh.estimates, abs=1e-14)
    assert second.estimates["S_zz"] == pytest.approx(syn.truths[b]["S_zz"], abs=1e-10)


# =================================================================== σ, sign and factor
def _design_ac(dataset: str) -> np.ndarray:
    """∂D/∂(estimand) in the paper's frame, from the scalar law: the model is linear."""
    d = PREREG["datasets"][dataset]
    cols = []
    for comp in d["estimands"]:
        unit = {"S_zz": 0.0, "S_xx-S_yy": 0.0, comp: 1.0}
        s = _benzene_s(unit["S_zz"]) if dataset == BENZENE else _odcb_s(unit["S_zz"], unit["S_xx-S_yy"])
        cols.append([_coupling(dataset, tuple(pair), s) for pair in d["orbits"].values()])
    return np.array(cols).T


def _wls(dataset: str, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """The weighted least-squares answer with weights 1/σ², and its covariance (σ as printed)."""
    a = _design_ac(dataset)
    w = np.diag(1.0 / np.array(SIGMAS[dataset]) ** 2)
    cov = np.linalg.inv(a.T @ w @ a)
    return cov @ a.T @ w @ y, cov


@pytest.mark.parametrize("dataset", [BENZENE, ODCB])
def test_the_couplings_enter_as_printed_with_their_sigma(tmp_path: Path, dataset: str, call: Any) -> None:
    """The estimate is the 1/σ² weighted fit of the signed couplings as printed: no factor of
    two, no sign change, no σ rescaling (V0.3 §1, §3)."""
    v = _v()
    syn = Synthetic(tmp_path, dataset)
    observed = v.read_couplings(dataset, prereg=syn.prereg, root=tmp_path)
    key = _condition_keys(dataset)[4]
    d = PREREG["datasets"][dataset]
    y = np.array([observed[key][orbit][0] for orbit in d["orbits"]])
    assert [observed[key][orbit][1] for orbit in d["orbits"]] == list(SIGMAS[dataset])
    expected, cov = _wls(dataset, y)
    fit = v.paper_fit(dataset, syn.prereg, v.fit_condition(call, dataset, syn.prereg, observed[key]))
    got = np.array([fit.estimates[c] for c in d["estimands"]])
    assert got == pytest.approx(expected, abs=1e-12)
    assert np.array([fit.se[c] for c in d["estimands"]]) == pytest.approx(np.sqrt(np.diag(cov)), rel=1e-9)
    resid = y - _design_ac(dataset) @ expected
    chi2 = float(np.sum((resid / np.array(SIGMAS[dataset])) ** 2))
    assert fit.chi2 == pytest.approx(chi2, rel=1e-9) and fit.nu == d["nu"]
    scaled = np.sqrt(np.diag(cov)) * math.sqrt(chi2 / d["nu"])
    assert np.array([fit.scaled_se[c] for c in d["estimands"]]) == pytest.approx(scaled, rel=1e-9)


@pytest.mark.parametrize("dataset", [BENZENE, ODCB])
def test_negated_couplings_give_the_negated_tensor(tmp_path: Path, dataset: str, call: Any) -> None:
    v = _v()
    syn = Synthetic(tmp_path, dataset)
    observed = v.read_couplings(dataset, prereg=syn.prereg, root=tmp_path)
    key = _condition_keys(dataset)[2]
    flipped = {orbit: (-dv, s) for orbit, (dv, s) in observed[key].items()}
    plus = v.paper_fit(dataset, syn.prereg, v.fit_condition(call, dataset, syn.prereg, observed[key]))
    minus = v.paper_fit(dataset, syn.prereg, v.fit_condition(call, dataset, syn.prereg, flipped))
    for comp in _estimands(dataset):
        assert minus.estimates[comp] == pytest.approx(-plus.estimates[comp], abs=1e-12)


# ======================================================================= covariance
def test_the_paper_frame_covariance_keeps_its_off_diagonal(tmp_path: Path, call: Any) -> None:
    """Σ_paper = M Σ_ac Mᵀ from the full fitted covariance (V0.3 §3), reconstructed from the wire's
    basis: compared with the independent weighted fit, cross terms included."""
    v = _v()
    syn = Synthetic(tmp_path, ODCB)
    observed = v.read_couplings(ODCB, prereg=syn.prereg, root=tmp_path)
    key = _condition_keys(ODCB)[7]
    y = np.array([observed[key][orbit][0] for orbit in PREREG["datasets"][ODCB]["orbits"]])
    _, expected = _wls(ODCB, y)
    fit = v.paper_fit(ODCB, syn.prereg, v.fit_condition(call, ODCB, syn.prereg, observed[key]))
    got = np.array(fit.covariance, dtype=float)
    assert got.shape == (2, 2)
    assert got == pytest.approx(expected, rel=1e-9)
    assert abs(expected[0, 1]) > 1e-3 * math.sqrt(expected[0, 0] * expected[1, 1])  # the test can see a loss


def test_the_covariance_is_rebuilt_from_its_supplied_basis() -> None:
    """The wire stores Σ in its own basis (``basis_b``): a rotated basis gives the same paper Σ."""
    v = _v()
    c = np.zeros((5, 2))
    c[0, 0] = c[1, 1] = 1.0
    sigma_reduced = np.array([[2.0e-6, 0.7e-6], [0.7e-6, 1.1e-6]])
    theta = 0.37
    rot = np.array([[math.cos(theta), -math.sin(theta)], [math.sin(theta), math.cos(theta)]])
    c_rot = c @ rot
    sigma_rot = rot.T @ sigma_reduced @ rot
    base = {"coordinates": ["b1", "b2"], "basis_b": c.T.tolist(), "matrix": sigma_reduced.tolist()}
    turned = {"coordinates": ["u1", "u2"], "basis_b": c_rot.T.tolist(), "matrix": sigma_rot.tolist()}
    a = np.array(v.paper_covariance(ODCB, PREREG, base), dtype=float)
    b = np.array(v.paper_covariance(ODCB, PREREG, turned), dtype=float)
    assert b == pytest.approx(a, rel=1e-12)
    j = np.diag([1 / math.sqrt(1.5), math.sqrt(2.0)])
    m = np.array(PREREG["datasets"][ODCB]["conversion_matrix"], dtype=float)
    assert a == pytest.approx(m @ j @ sigma_reduced @ j @ m.T, rel=1e-12)


# ============================================================================= rank
def _unverified(result: dict[str, Any]) -> dict[str, Any]:
    """The wire result of a fit whose rank is not verified: projected coordinates only."""
    out = copy.deepcopy(result)
    out["rank"] = {**out["rank"], "verified": False, "reason": "synthetic: rank unverified"}
    for comp in out["components"]:
        if comp["status"] == "estimated":
            comp.update(status="projected", estimate=None, se=None, intervals=None)
    out["covariance_b"] = None
    return out


def test_an_unverified_rank_estimates_nothing_and_stays_pending(tmp_path: Path, call: Any) -> None:
    """Rank-unverified keeps its precedence over everything, a signed receipt and targets included."""
    v = _v()
    syn = Synthetic(tmp_path, ODCB)
    observed = v.read_couplings(ODCB, prereg=syn.prereg, root=tmp_path)
    key = _condition_keys(ODCB)[0]
    fit = v.paper_fit(ODCB, syn.prereg, _unverified(v.fit_condition(call, ODCB, syn.prereg, observed[key])))
    assert fit.rank_verified is False
    assert all(fit.estimates[c] is None for c in _estimands(ODCB)) and fit.covariance is None
    fits = {k: fit for k in _condition_keys(ODCB)}
    cells = v.independent_cells(ODCB, syn.prereg, fits, syn.targets, receipt=syn.receipt())
    assert {(c.status, c.reason) for c in cells} == {("pending", "rank-unverified")}


# ==================================================================== gated targets
@pytest.mark.parametrize("dataset", [BENZENE, ODCB])
def test_targets_are_withheld_until_the_spot_check_is_signed(tmp_path: Path, dataset: str, call: Any) -> None:
    """P-2: without the signed receipt every cell is pending/no-target in both tracks; with it,
    every cell is compared. The o-DCB note stays while its check is open."""
    v = _v()
    syn = Synthetic(tmp_path, dataset)
    roster = PREREG["datasets"][dataset]["roster_cells"]
    gated = v.run_report(dataset, call=call, prereg=syn.prereg, root=tmp_path, submission=syn.logged())
    assert gated["status"] == "complete"
    for track in ("independent", "reproduction"):
        full = gated["tracks"][track]["full"]
        assert (full.name, full.roster, full.compared, full.pending) == ("pending", roster, 0, roster)
    assert {c["reason"] for c in gated["cells"]["independent"]} == {"no-target"}
    assert all(c["target"] is None for c in gated["cells"]["independent"])  # withheld, not just unused
    open_note = PREREG["reporting"]["spot_check_gating"]["open_note"]
    assert (open_note in gated["notes"]) is (dataset == ODCB)
    assert "development data, no independent holdout" in gated["notes"]

    signed = v.run_report(
        dataset, call=call, prereg=syn.prereg, root=tmp_path, submission=syn.logged(), receipt=syn.receipt()
    )
    full = signed["tracks"]["independent"]["full"]
    assert (full.name, full.compared, full.agreeing) == ("experimentally supported", roster, roster)
    assert open_note not in signed["notes"]
    # The authors' analysis inputs are absent: that track stays pending, with its own counts.
    repro = signed["tracks"]["reproduction"]["full"]
    assert (repro.name, repro.compared, repro.pending) == ("pending", 0, roster)
    assert {c["reason"] for c in signed["cells"]["reproduction"]} == {"inputs-undocumented"}


@pytest.mark.parametrize(
    "bad",
    [
        {"sha256": "0" * 64},
        {"artifact": "couplings"},
        {"dataset": ODCB},
        {"note": "trust me"},
    ],
)
def test_a_receipt_that_does_not_bind_withholds_the_targets(tmp_path: Path, call: Any, bad: dict[str, str]) -> None:
    v = _v()
    syn = Synthetic(tmp_path, BENZENE)
    receipt = {**syn.receipt(), **bad}
    report = v.run_report(
        BENZENE, call=call, prereg=syn.prereg, root=tmp_path, submission=syn.logged(), receipt=receipt
    )
    assert report["tracks"]["independent"]["full"].compared == 0


# =================================================================== the first-fit gate
@pytest.mark.parametrize(
    "change",
    [
        {"dataset": ODCB},
        {"protocol_sha256": "a" * 64},
        {"runner": "someone"},
        {"release_or_commit": ""},
        {"at": "2026-11-25T10:00Z"},
        {"note": "extra"},
    ],
)
def test_no_fit_without_its_submission_record(tmp_path: Path, change: dict[str, Any]) -> None:
    """The owner records the submission before the fit (V1.5a): the workflow refuses to fit
    without a record for this dataset at this protocol revision, before it reads any input."""
    v = _v()
    syn = Synthetic(tmp_path, BENZENE)
    with pytest.raises(ValueError):
        v.run_report(BENZENE, call=_never, prereg=syn.prereg, root=tmp_path, submission=syn.submission(**change))
    with pytest.raises(ValueError):
        v.run_report(BENZENE, call=_never, prereg=syn.prereg, root=tmp_path, submission=None)


def test_the_report_keeps_its_submission_and_protocol(tmp_path: Path, call: Any) -> None:
    v = _v()
    syn = Synthetic(tmp_path, BENZENE)
    sub = syn.logged()
    report = v.run_report(BENZENE, call=call, prereg=syn.prereg, root=tmp_path, submission=sub, receipt=syn.receipt())
    assert report["protocol_sha256"] == syn.protocol
    assert report["submission"] == {**sub, "at": "2026-11-25T10:00Z"}
    assert report["tracks"]["independent"]["protocol_sha256"] == syn.protocol


# ======================================================================= both margins
def _fit(estimates: dict[str, float | None], verified: bool = True) -> Any:
    return _v().PaperFit(rank_verified=verified, estimates=estimates)


def _edge(target: float, margin: float, sign: float) -> tuple[float, float]:
    """The last float with |s − target| ≤ margin on that side, and the next one outward."""
    s = target + sign * margin
    inward = target
    while abs(s - target) > margin:
        s = math.nextafter(s, inward)
    outward = math.nextafter(s, sign * math.inf)
    while abs(outward - target) <= margin:
        outward = math.nextafter(outward, sign * math.inf)
    return s, outward


@pytest.mark.parametrize("sign", [1.0, -1.0])
def test_the_independent_margin_for_s_zz(tmp_path: Path, sign: float) -> None:
    """|S − S_pub| ≤ 0.05·|S_pub| + 2p, inclusive, with p the cell's own precision."""
    v = _v()
    syn = Synthetic(tmp_path, BENZENE)
    keys = _condition_keys(BENZENE)
    value, p = -0.25, 2.0**-8
    margin = pl.RELATIVE_TOLERANCE * abs(value) + pl.PRECISION_FACTOR * p
    inside, outside = _edge(value, margin, sign)
    targets = {(k, "S_zz"): (value, p) for k in keys}
    fits = {k: _fit({"S_zz": inside}) for k in keys}
    fits[keys[3]] = _fit({"S_zz": outside})
    cells = {c.condition: c for c in v.independent_cells(BENZENE, syn.prereg, fits, targets, receipt=syn.receipt())}
    assert cells[keys[0]].status == "agrees"
    assert cells[keys[3]].status == "disagrees"


def test_the_independent_margin_for_the_anisotropy_uses_its_own_condition(tmp_path: Path) -> None:
    """S_xx − S_yy: 0.05·|S_zz,pub| of the same condition + 2p of the anisotropy cell. Using the
    cell's own value, the S_zz cell's precision or another condition's S_zz changes the verdict."""
    v = _v()
    syn = Synthetic(tmp_path, ODCB)
    keys = _condition_keys(ODCB)
    zz, p_zz, p_an = -0.25, 2.0**-5, 2.0**-9
    margin = pl.RELATIVE_TOLERANCE * abs(zz) + pl.PRECISION_FACTOR * p_an
    inside, outside = _edge(0.0, margin, 1.0)
    targets: dict[tuple[str, str], tuple[float, float] | None] = {}
    fits = {}
    for i, k in enumerate(keys):
        targets[(k, "S_zz")] = (zz if i != 1 else -0.9, p_zz)  # condition 1 has a much larger S_zz
        targets[(k, "S_xx-S_yy")] = (0.0, p_an)
        fits[k] = _fit({"S_zz": zz if i != 1 else -0.9, "S_xx-S_yy": inside})
    fits[keys[0]] = _fit({"S_zz": zz, "S_xx-S_yy": outside})
    cells = {
        (c.condition, c.component): c
        for c in v.independent_cells(ODCB, syn.prereg, fits, targets, receipt=syn.receipt())
    }
    assert cells[(keys[2], "S_xx-S_yy")].status == "agrees"
    assert cells[(keys[0], "S_xx-S_yy")].status == "disagrees"  # 2·p_zz or condition 1's S_zz would pass it


def test_the_anisotropy_waits_for_its_conditions_s_zz_target(tmp_path: Path) -> None:
    v = _v()
    syn = Synthetic(tmp_path, ODCB)
    keys = _condition_keys(ODCB)
    targets: dict[tuple[str, str], tuple[float, float] | None] = {
        (k, c): (syn.truths[k][c], 0.0004) for k in keys for c in _estimands(ODCB)
    }
    targets[(keys[5], "S_zz")] = None
    fits = {k: _fit(dict(syn.truths[k])) for k in keys}
    cells = {
        (c.condition, c.component): c
        for c in v.independent_cells(ODCB, syn.prereg, fits, targets, receipt=syn.receipt())
    }
    assert (cells[(keys[5], "S_zz")].status, cells[(keys[5], "S_zz")].reason) == ("pending", "no-target")
    aniso = cells[(keys[5], "S_xx-S_yy")]
    assert (aniso.status, aniso.reason) == ("pending", "s_zz-target-pending")


def test_the_cells_must_cover_the_fitted_conditions_exactly(tmp_path: Path) -> None:
    v = _v()
    syn = Synthetic(tmp_path, BENZENE)
    keys = _condition_keys(BENZENE)
    fits = {k: _fit(dict(syn.truths[k])) for k in keys[1:]}
    with pytest.raises(ValueError):
        v.independent_cells(BENZENE, syn.prereg, fits, syn.targets, receipt=syn.receipt())


# ------------------------------------------------- the reproduction margin (prereg_labels)
def test_the_reproduction_labels_are_the_frozen_ones() -> None:
    _v()
    r = PREREG["criteria"]["reproduction"]
    assert pl.REPRODUCTION_LABEL == r["label"]
    assert pl.FALLBACK_LABEL == r["fallback_label"].replace("1/sigma^2", "1/σ²")
    assert tuple(pl.REPRODUCTION_REQUIREMENTS) == tuple(r["requires"])


@pytest.mark.parametrize(
    ("token", "margin"),
    [
        ("-0.6123(12)", 0.0012),  # printed σ wins
        ("0.61230(5)", 0.00005),  # printed σ wins over half a unit (0.000005)
        ("0.612(0)", 0.0005),  # half a unit wins
        ("0.6120(3)", 0.0003),  # a trailing zero is a printed digit: units of 1e-4
        ("0.61200(3)", 0.00003),
        ("−0.0731(4)", 0.0004),  # U+2212
        ("0.5(0)", 0.05),
    ],
)
def test_the_table_margin_is_the_larger_of_sigma_and_half_a_unit(token: str, margin: float) -> None:
    _v()
    assert pl.table_margin(token) == pytest.approx(margin, rel=1e-12)


@pytest.mark.parametrize("token", ["0.6123", "", "0.61(", "(12)", "abc(1)", "0.61(-1)", "0.61(1.5)", "6.1e-1(2)"])
def test_the_table_margin_needs_a_printed_sigma(token: str) -> None:
    """Missing or malformed precision: no margin (the cell stays pending)."""
    _v()
    assert pl.table_margin(token) is None


def test_the_figure_margin_is_twice_the_precision() -> None:
    _v()
    assert pl.figure_margin(0.00031) == pytest.approx(0.00062, rel=1e-15)
    for bad in (None, 0.0, -0.1, math.nan, math.inf):
        assert pl.figure_margin(bad) is None


@pytest.mark.parametrize(
    ("documented", "mode"),
    [
        ({"geometry", "objective", "weights", "corrections"}, "reproduction"),
        ({"geometry", "corrections"}, "fallback"),  # weights and objective unknown
        ({"geometry", "objective", "corrections"}, "fallback"),  # weights unknown
        ({"geometry", "weights", "corrections"}, "fallback"),  # objective unknown
        ({"geometry"}, "fallback"),
        ({"geometry", "objective", "weights"}, "pending"),  # corrections undocumented: no claim
        ({"objective", "weights", "corrections"}, "pending"),  # no geometry
        (set(), "pending"),
    ],
)
def test_the_reproduction_mode_needs_all_four_documented(documented: set[str], mode: str) -> None:
    _v()
    assert pl.reproduction_mode(documented) == mode
    assert (
        pl.reproduction_track_label(mode)
        == {
            "reproduction": pl.REPRODUCTION_LABEL,
            "fallback": pl.FALLBACK_LABEL,
            "pending": pl.REPRODUCTION_LABEL,
        }[mode]
    )


def test_the_reproduction_mode_refuses_an_unknown_requirement() -> None:
    _v()
    with pytest.raises(ValueError):
        pl.reproduction_mode({"geometry", "vibes"})


@pytest.mark.parametrize("sign", [1.0, -1.0])
@pytest.mark.parametrize("mode", ["reproduction", "fallback"])
def test_the_reproduction_comparison_at_its_margin(sign: float, mode: str) -> None:
    _v()
    value, margin = -0.25, 2.0**-7
    inside, outside = _edge(value, margin, sign)
    ok = pl.classify_reproduction("c", "S_zz", mode=mode, rank_verified=True, s=inside, target=(value, margin))
    bad = pl.classify_reproduction("c", "S_zz", mode=mode, rank_verified=True, s=outside, target=(value, margin))
    assert (ok.status, bad.status) == ("agrees", "disagrees")


@pytest.mark.parametrize(
    ("kw", "reason"),
    [
        ({"mode": "pending", "rank_verified": True, "s": 0.1, "target": (0.1, 0.01)}, "inputs-undocumented"),
        ({"mode": "reproduction", "rank_verified": False, "s": 0.1, "target": (0.1, 0.01)}, "rank-unverified"),
        ({"mode": "reproduction", "rank_verified": True, "s": None, "target": (0.1, 0.01)}, "rank-unverified"),
        ({"mode": "reproduction", "rank_verified": True, "s": 0.1, "target": None}, "no-target"),
        ({"mode": "reproduction", "rank_verified": True, "s": 0.1, "target": (0.1, None)}, "no-precision"),
    ],
)
def test_the_reproduction_comparison_stays_pending(kw: dict[str, Any], reason: str) -> None:
    _v()
    cell = pl.classify_reproduction("c", "S_zz", **kw)
    assert (cell.status, cell.reason) == ("pending", reason)


# =========================================================== review receipts (decision 5B)
def _key(dataset: str, track: str, condition: str, component: str, protocol: str) -> dict[str, str]:
    return {
        "dataset": dataset,
        "track": track,
        "condition": condition,
        "component": component,
        "protocol_sha256": protocol,
    }


def _disagreeing(tmp_path: Path, *, conditions: tuple[str, ...]) -> tuple[Synthetic, list[dict[str, str]]]:
    """A synthetic o-DCB dataset whose S_zz targets are far off in the named conditions."""
    truths = {k: _truth(ODCB, i) for i, k in enumerate(_condition_keys(ODCB))}
    targets: dict[tuple[str, str], tuple[float, float] | None] = dict(_default_targets(ODCB, truths))
    for k in conditions:
        targets[(k, "S_zz")] = (truths[k]["S_zz"] + 0.05, 0.0004)
    syn = Synthetic(tmp_path, ODCB, truths=truths, targets=targets)
    keys = [_key(ODCB, "independent", k, "S_zz", syn.protocol) for k in conditions]
    return syn, keys


# Round 83 (A5), amended before the fix: matching keys alone no longer stand in for a completed
# review. Each disagreeing key needs a reference (path and SHA-256) to an existing local annex entry
# and to an existing local review receipt that links a reviewed public entry by path, SHA-256 and
# heading; each file binds the same dataset, track, cell and protocol revision.
R83B_PY = ROOT / "tools" / "validation" / "evidence.py"


def _r83b() -> Any:
    """The round 83 A4/A5 fixes, or an xfail while (and only while) their module is absent."""
    v = _v()
    if not R83B_PY.is_file():
        pytest.xfail("round 83 (A4, A5): the fixes are not written yet")
    return v


PUBLIC_ENTRY = "datasets/odcb-chandrakumar1993/README.md"


def _write_json(path: Path, record: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")


def _ref(root: Path, path: Path, key: dict[str, str]) -> dict[str, str]:
    return {**key, "path": path.relative_to(root).as_posix(), "sha256": _sha(path)}


# Round 84 (A5), amended before the fix: an annex entry holds the plan's fields (procedure 6:
# frame and observable convention, geometry, vibrational corrections, solvent and sample context,
# numerical comparison, and the likely cause or its limits), each its own non-empty text. Each
# receipt links its own Markdown heading, present once, with a body.
R84_PY = ROOT / "tools" / "validation" / "fit_record.py"
ANNEX_TEXTS = (
    "frame_and_convention",
    "geometry",
    "vibrational_corrections",
    "sample_context",
    "numerical_comparison",
    "cause",
)


def _r84() -> Any:
    """The round 84 fixes, or an xfail while (and only while) their marker module is absent."""
    v = _v()
    if not R84_PY.is_file():
        pytest.xfail("round 84: the fixes are not written yet")
    return v


def _r86() -> Any:
    """Round 86 (round 85's findings): an xfail while ``fit_record`` has no ``SIGNED_LINE``."""
    v = _r84()
    if not hasattr(importlib.import_module("fit_record"), "SIGNED_LINE"):
        pytest.xfail("round 86: the fixes are not written yet")
    return v


def _r87() -> Any:
    """Round 87 (round 86's findings): an xfail while ``fit_record`` has no ``protocol_sha256``."""
    v = _r86()
    if not hasattr(importlib.import_module("fit_record"), "protocol_sha256"):
        pytest.xfail("round 87: the fixes are not written yet")
    return v


def _annex_texts(n: int) -> dict[str, str]:
    return {f: f"synthetic {f.replace('_', ' ')} of discrepancy {n}" for f in ANNEX_TEXTS}


def _evidence(root: Path, keys: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    """Synthetic review evidence for each key: a local annex entry, and a local review receipt
    linking a heading of a value-free public README; returns the references to both."""
    headings = [f"### Discrepancy review {n}" for n in range(1, len(keys) + 1)]
    public = root / PUBLIC_ENTRY
    public.parent.mkdir(parents=True, exist_ok=True)
    body = "".join(f"\n{h}\n\nSynthetic, value-free context of review {n}.\n" for n, h in enumerate(headings, 1))
    public.write_text("# Synthetic README\n" + body, encoding="utf-8")
    annex, receipts = [], []
    for n, (key, heading) in enumerate(zip(keys, headings, strict=True), start=1):
        a = root / "datasets-local" / "reviews" / f"annex-{n}.json"
        _write_json(a, {**key, "kind": "annex", **_annex_texts(n)})
        r = root / "datasets-local" / "reviews" / f"receipt-{n}.json"
        _write_json(
            r,
            {
                **key,
                "kind": "review receipt",
                "reviewer": "a synthetic second reviewer",
                "public_entry": {"path": PUBLIC_ENTRY, "sha256": _sha(public), "heading": heading},
            },
        )
        annex.append(_ref(root, a, key))
        receipts.append(_ref(root, r, key))
    return {"annex": annex, "receipts": receipts}


def test_complete_review_coverage_explains_the_discrepancy(tmp_path: Path, call: Any) -> None:
    """One-to-one coverage of every disagreeing key by existing, current annex entries and review
    receipts sets the review flag: an explained discrepancy, which is not validation (crosswalk:
    unresolved failure, "explained, reviewed")."""
    v = _r84()
    syn, keys = _disagreeing(tmp_path, conditions=("I/314", "II/306"))
    reviews = _evidence(tmp_path, keys)
    report = v.run_report(
        ODCB,
        call=call,
        prereg=syn.prereg,
        root=tmp_path,
        submission=syn.logged(),
        receipt=syn.receipt(),
        reviews=reviews,
    )
    assert report["review_problems"] == []
    full = report["tracks"]["independent"]["full"]
    assert (full.name, full.disagreeing) == ("explained discrepancy", 2)
    shared = v.shared_output(report)
    assert (shared["verification"], shared["annotation"]) == ("unresolved failure", "explained, reviewed")


def test_matching_keys_alone_are_not_a_review(tmp_path: Path, call: Any) -> None:
    """A5: the keys copied into both lists, with no annex entry or reviewed public entry behind
    them, leave the failure unresolved."""
    v = _r83b()
    syn, keys = _disagreeing(tmp_path, conditions=("I/314", "II/306"))
    report = v.run_report(
        ODCB,
        call=call,
        prereg=syn.prereg,
        root=tmp_path,
        submission=syn.logged(),
        receipt=syn.receipt(),
        reviews={"annex": keys, "receipts": keys},
    )
    assert report["review_problems"]
    assert report["tracks"]["independent"]["full"].name == "unresolved failure"


def _rewrite(root: Path, ref: dict[str, str], change: Callable[[dict[str, Any]], None]) -> None:
    """Change a referenced file and refresh the reference's hash, so only the change is wrong."""
    path = root / ref["path"]
    record = json.loads(path.read_text(encoding="utf-8"))
    change(record)
    _write_json(path, record)
    ref["sha256"] = _sha(path)


def _coverage_mutant(name: str, root: Path, keys: list[dict[str, str]], protocol: str) -> dict[str, Any]:
    reviews = _evidence(root, keys)
    annex, receipts = reviews["annex"], reviews["receipts"]
    public = root / PUBLIC_ENTRY
    if name == "an annex entry missing":
        annex.pop()
    elif name == "a receipt missing":
        receipts.pop()
    elif name == "a duplicate annex entry":
        annex.append(dict(annex[0]))
    elif name == "a duplicate receipt":
        receipts.append(dict(receipts[0]))
    elif name == "a stale protocol revision":
        receipts[0]["protocol_sha256"] = "1" * 64
    elif name == "the wrong track":
        receipts[0]["track"] = "reproduction"
    elif name == "the wrong component":
        annex[0]["component"] = "S_xx-S_yy"
    elif name == "the wrong dataset":
        annex[0]["dataset"] = BENZENE
    elif name == "an entry for an agreeing cell":
        return _evidence(root, [*keys, _key(ODCB, "independent", "II/290", "S_zz", protocol)])
    elif name == "an unknown field":
        receipts[0]["reviewer"] = "someone"
    elif name == "no receipts at all":
        receipts.clear()
    elif name == "an annex file missing":
        (root / annex[0]["path"]).unlink()
    elif name == "a stale annex entry":
        path = root / annex[0]["path"]
        path.write_text(path.read_text(encoding="utf-8").replace("synthetic", "edited"), encoding="utf-8")
    elif name == "an annex entry of another cell":
        _rewrite(root, annex[0], lambda r: r.update(condition="II/290"))
    elif name == "an annex entry at another revision":
        _rewrite(root, annex[0], lambda r: r.update(protocol_sha256="2" * 64))
    elif name == "an empty annex entry":
        _rewrite(root, annex[0], lambda r: r.update(cause=" "))
    elif name == "an annex file that is not JSON":
        path = root / annex[0]["path"]
        path.write_text("{not json", encoding="utf-8")
        annex[0]["sha256"] = _sha(path)
    elif name == "an annex file with another field":
        _rewrite(root, annex[0], lambda r: r.update(note="extra"))
    elif name == "a receipt standing in for the annex":
        annex[0] = dict(receipts[0])
    elif name == "a receipt file missing":
        (root / receipts[0]["path"]).unlink()
    elif name == "a stale receipt":
        path = root / receipts[0]["path"]
        path.write_text(path.read_text(encoding="utf-8").replace("synthetic", "edited"), encoding="utf-8")
    elif name == "a receipt with no reviewer":
        _rewrite(root, receipts[0], lambda r: r.update(reviewer=""))
    elif name == "the reviewed public entry missing":
        public.unlink()
    elif name == "a stale public entry":
        public.write_text(public.read_text(encoding="utf-8") + "\nEdited after review.\n", encoding="utf-8")
    elif name == "a public entry without its heading":
        text = public.read_text(encoding="utf-8").replace("### Discrepancy review 1\n", "")
        public.write_text(text, encoding="utf-8")
        for ref in receipts:  # every receipt is current: only the heading is missing
            _rewrite(root, ref, lambda r: r["public_entry"].update(sha256=_sha(public)))
    elif name == "a public entry that is local":
        local = root / "datasets-local" / "public.md"
        local.write_bytes(public.read_bytes())
        _rewrite(root, receipts[0], lambda r: r["public_entry"].update(path="datasets-local/public.md"))
    elif name == "an annex entry outside datasets-local":
        moved = root / "docs" / "annex-1.json"
        moved.parent.mkdir(parents=True, exist_ok=True)
        (root / annex[0]["path"]).rename(moved)
        annex[0]["path"] = "docs/annex-1.json"
    elif name == "a path that leaves the checkout":
        outside = root.parent / f"{root.name}-annex.json"
        outside.write_bytes((root / annex[0]["path"]).read_bytes())
        annex[0]["path"] = f"datasets-local/../../{outside.name}"
    elif name == "a linked annex entry":
        path = root / annex[0]["path"]
        outside = root.parent / f"{root.name}-linked.json"
        outside.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(outside)
    # Round 84 (A5): placeholders and shared headings are not a review.
    elif name == "an annex entry without the plan's fields":
        _rewrite(root, annex[0], lambda r: [r.pop(f) for f in ANNEX_TEXTS] and r.update(entry="placeholder"))
    elif name == "an annex entry with one text in every field":
        _rewrite(root, annex[0], lambda r: r.update(dict.fromkeys(ANNEX_TEXTS, "placeholder")))
    elif name == "an annex field that is not text":
        _rewrite(root, annex[0], lambda r: r.update(cause=["placeholder"]))
    elif name == "two cells with the same annex texts":
        _rewrite(root, annex[1], lambda r: r.update(_annex_texts(1)))
    elif name == "two receipts linking one heading":
        _rewrite(root, receipts[1], lambda r: r["public_entry"].update(heading="### Discrepancy review 1"))
    elif name in ("a heading with no body", "a heading that is not Markdown", "a heading given twice"):
        text = public.read_text(encoding="utf-8")
        if name == "a heading with no body":
            text = text.replace("Synthetic, value-free context of review 1.\n", "")
        elif name == "a heading that is not Markdown":
            text = text.replace("### Discrepancy review 1\n", "Discrepancy review 1\n")
            _rewrite(root, receipts[0], lambda r: r["public_entry"].update(heading="Discrepancy review 1"))
        else:
            text += "\n### Discrepancy review 1\n\nMore synthetic context.\n"
        public.write_text(text, encoding="utf-8")
        for ref in receipts:  # every receipt is current: only the heading is wrong
            _rewrite(root, ref, lambda r: r["public_entry"].update(sha256=_sha(public)))
    # Round 86 (round 85, finding 3): one file has one spelling, and a comment is not a body.
    elif name == "a public path spelled with ./, sharing a heading":
        _rewrite(
            root,
            receipts[1],
            lambda r: r["public_entry"].update(path="./" + PUBLIC_ENTRY, heading="### Discrepancy review 1"),
        )
    elif name == "an annex path spelled with ./":
        annex[0]["path"] = "./" + annex[0]["path"]
    elif name == "a body of HTML comments only":
        text = public.read_text(encoding="utf-8")
        public.write_text(
            text.replace("Synthetic, value-free context of review 1.\n", "<!-- a\nnote -->\n"), encoding="utf-8"
        )
        for ref in receipts:
            _rewrite(root, ref, lambda r: r["public_entry"].update(sha256=_sha(public)))
    # Round 87 (round 86, findings 3 and 4): one file under any letter case, and no hidden body.
    elif name == "a public path in another letter case, sharing a heading":
        _rewrite(
            root,
            receipts[1],
            lambda r: r["public_entry"].update(path=PUBLIC_ENTRY.upper(), heading="### Discrepancy review 1"),
        )
    elif name == "a public entry under datasets-local in capitals":
        local = root / "datasets-local" / "public.md"
        local.write_bytes(public.read_bytes())
        _rewrite(root, receipts[0], lambda r: r["public_entry"].update(path="DATASETS-LOCAL/public.md"))
    elif name == "an unclosed comment as the body":
        text = public.read_text(encoding="utf-8")
        last = "### Discrepancy review 2"
        public.write_text(text.split("\n" + last)[0] + "\n" + last + "\n\n<!-- never closed\n", encoding="utf-8")
        for ref in receipts:
            _rewrite(root, ref, lambda r: r["public_entry"].update(sha256=_sha(public)))
    elif name == "a multiline comment hiding a heading line":
        text = public.read_text(encoding="utf-8")
        public.write_text(
            text.replace("Synthetic, value-free context of review 1.\n", "<!-- a\n### Hidden\nnote -->\n"),
            encoding="utf-8",
        )
        for ref in receipts:
            _rewrite(root, ref, lambda r: r["public_entry"].update(sha256=_sha(public)))
    return reviews


R86_COVERAGE = [
    "a public path spelled with ./, sharing a heading",
    "an annex path spelled with ./",
    "a body of HTML comments only",
]
R87_COVERAGE = [
    "a public path in another letter case, sharing a heading",
    "a public entry under datasets-local in capitals",
    "a multiline comment hiding a heading line",
    "an unclosed comment as the body",  # added with the round 87 fixes, for the unclosed case
]
COVERAGE_MUTANTS = [
    "an annex entry missing",
    "a receipt missing",
    "a duplicate annex entry",
    "a duplicate receipt",
    "a stale protocol revision",
    "the wrong track",
    "the wrong component",
    "the wrong dataset",
    "an entry for an agreeing cell",
    "an unknown field",
    "no receipts at all",
    # Round 83 (A5): the references must reach existing, current, bound evidence.
    "an annex file missing",
    "a stale annex entry",
    "an annex entry of another cell",
    "an annex entry at another revision",
    "an empty annex entry",
    "an annex file that is not JSON",
    "an annex file with another field",
    "a receipt standing in for the annex",
    "a receipt file missing",
    "a stale receipt",
    "a receipt with no reviewer",
    "the reviewed public entry missing",
    "a stale public entry",
    "a public entry without its heading",
    "a public entry that is local",
    "an annex entry outside datasets-local",
    "a path that leaves the checkout",
    "a linked annex entry",
    # Round 84 (A5).
    "an annex entry without the plan's fields",
    "an annex entry with one text in every field",
    "an annex field that is not text",
    "two cells with the same annex texts",
    "two receipts linking one heading",
    "a heading with no body",
    "a heading that is not Markdown",
    "a heading given twice",
    # Round 86.
    *R86_COVERAGE,
    # Round 87.
    *R87_COVERAGE,
]


@pytest.mark.parametrize("name", COVERAGE_MUTANTS)
def test_incomplete_review_evidence_leaves_the_failure_unresolved(tmp_path: Path, call: Any, name: str) -> None:
    """Missing, duplicate, stale or unbound evidence is refused, and no cell is flagged reviewed."""
    v = _r84()
    if name in R86_COVERAGE:
        _r86()
    if name in R87_COVERAGE:
        _r87()
    syn, keys = _disagreeing(tmp_path, conditions=("I/314", "II/306"))
    reviews = _coverage_mutant(name, tmp_path, keys, syn.protocol)
    report = v.run_report(
        ODCB,
        call=call,
        prereg=syn.prereg,
        root=tmp_path,
        submission=syn.logged(),
        receipt=syn.receipt(),
        reviews=reviews,
    )
    assert report["review_problems"], name
    assert report["tracks"]["independent"]["full"].name == "unresolved failure"
    assert not any(c["reviewed"] for c in report["cells"]["independent"])
    assert not any("synthetic" in p or "edited" in p for p in report["review_problems"])  # no file content


def test_review_coverage_alone(tmp_path: Path) -> None:
    v = _r84()
    keys = [_key(ODCB, "independent", "I/314", "S_zz", "a" * 64)]
    refs = _evidence(tmp_path, keys)
    assert v.review_coverage(keys, refs["annex"], refs["receipts"], root=tmp_path) == []
    assert v.review_coverage(keys, [], refs["receipts"], root=tmp_path)
    assert v.review_coverage([], refs["annex"], refs["receipts"], root=tmp_path)
    assert v.review_coverage(keys, keys, keys, root=tmp_path)  # keys without evidence


# =================================================================== drop-one sensitivity
def test_a_label_that_hangs_on_one_dropped_condition_is_fragile(tmp_path: Path, call: Any) -> None:
    """II/300 alone disagrees: the full-data label (primary) is an unresolved failure, without
    II/300 it is supported, so the result is fragile; both drop-one labels have their counts."""
    v = _v()
    syn, _ = _disagreeing(tmp_path, conditions=("II/300",))
    report = v.run_report(
        ODCB, call=call, prereg=syn.prereg, root=tmp_path, submission=syn.logged(), receipt=syn.receipt()
    )
    track = report["tracks"]["independent"]
    assert track["full"].name == "unresolved failure"
    assert track["without II/300"].name == "experimentally supported"
    assert track["without II/300"].roster == 42
    assert track["without II/302"].name == "unresolved failure"
    assert track["fragile"] is True
    shared = v.shared_output(report)
    labels = shared["tracks"]["independent"]["labels"]
    assert set(labels) == {"full", "without II/300", "without II/302"} and shared["tracks"]["independent"]["fragile"]
    assert shared["verification"] == "unresolved failure" and shared["annotation"] is None


def test_benzene_has_no_drop_one(tmp_path: Path, call: Any) -> None:
    v = _v()
    syn = Synthetic(tmp_path, BENZENE)
    report = v.run_report(
        BENZENE, call=call, prereg=syn.prereg, root=tmp_path, submission=syn.logged(), receipt=syn.receipt()
    )
    assert set(v.shared_output(report)["tracks"]["independent"]["labels"]) == {"full"}


# ======================================================================= Python and HTTP
def test_python_and_http_give_the_same_fit(tmp_path: Path) -> None:
    """The browser and scripts are registry clients: the same synthetic inputs through the Python
    adapter and the HTTP adapter give the same estimates, errors and covariance."""
    v = _v()
    syn = Synthetic(tmp_path, ODCB)
    observed = v.read_couplings(ODCB, prereg=syn.prereg, root=tmp_path)
    key = _condition_keys(ODCB)[3]
    http = _Asgi()
    a = v.paper_fit(ODCB, syn.prereg, v.fit_condition(v.local_call(), ODCB, syn.prereg, observed[key]))
    b = v.paper_fit(ODCB, syn.prereg, v.fit_condition(http, ODCB, syn.prereg, observed[key]))
    assert "fit.run" in http.calls and "run.get" in http.calls
    assert a.estimates == pytest.approx(b.estimates, abs=1e-15)
    assert np.array(a.covariance) == pytest.approx(np.array(b.covariance), rel=1e-12)
    assert a.chi2 == pytest.approx(b.chi2, rel=1e-12) and (a.nu, a.adequacy) == (b.nu, b.adequacy)


def test_the_fit_goes_through_the_registry_operations(tmp_path: Path) -> None:
    """The fixed-geometry registry path of the plan, step 2."""
    v = _v()
    syn = Synthetic(tmp_path, BENZENE)
    observed = v.read_couplings(BENZENE, prereg=syn.prereg, root=tmp_path)
    http = _Asgi()
    result = v.fit_condition(http, BENZENE, syn.prereg, observed[_condition_keys(BENZENE)[0]])
    for op in (
        "project.import_xyz",
        "molecule.set_symmetry",
        "model.set",
        "couplings.reconcile",
        "couplings.import",
        "fit.run",
        "job.wait",
        "run.get",
    ):
        assert op in http.calls, op
    assert result["model"]["kind"] == "fixed" and result["provenance"]["fit_version"] == "fixed-linear.1"
    assert result["symmetry"]["point_group"] == "D6h" and result["n_obs"] == 3


# ============================================================ local detail and shared output
def test_local_detail_is_written_only_under_datasets_local(tmp_path: Path, call: Any) -> None:
    v = _v()
    syn = Synthetic(tmp_path, BENZENE)
    report = v.run_report(
        BENZENE, call=call, prereg=syn.prereg, root=tmp_path, submission=syn.logged(), receipt=syn.receipt()
    )
    for bad in ("docs/phase2/verification/x.md", "datasets-local/../docs/x.md", "/tmp/x.md", "datasets/x.md"):
        with pytest.raises(ValueError):
            v.write_local(report, Path(bad), root=tmp_path)
        assert not (tmp_path / bad.lstrip("/")).exists()
    out = v.write_local(report, Path("datasets-local/benzene-taggar2006-targets/verification-v1.5.md"), root=tmp_path)
    text = out.read_text(encoding="utf-8")
    cell = report["cells"]["independent"][0]
    for field in ("target", "fit", "discrepancy", "margin"):
        assert cell[field] is not None
        assert repr(cell[field]) in text, field  # the local report keeps every per-cell number


def test_the_local_cells_carry_target_fit_discrepancy_and_margin(tmp_path: Path, call: Any) -> None:
    v = _v()
    syn = Synthetic(tmp_path, BENZENE)
    report = v.run_report(
        BENZENE, call=call, prereg=syn.prereg, root=tmp_path, submission=syn.logged(), receipt=syn.receipt()
    )
    cells = report["cells"]["independent"]
    assert len(cells) == 15
    for c in cells:
        assert c["discrepancy"] == c["fit"] - c["target"]
        assert c["margin"] == pl.RELATIVE_TOLERANCE * abs(c["target"]) + pl.PRECISION_FACTOR * c["precision"]
        assert c["status"] == ("agrees" if abs(c["discrepancy"]) <= c["margin"] else "disagrees")
    cond = report["conditions"][_condition_keys(BENZENE)[0]]
    assert {"chi2", "nu", "p_value", "adequacy", "se", "scaled_se", "ratio_residuals", "rank_verified"} <= set(cond)


def test_the_shared_output_is_labels_counts_and_revision_only(tmp_path: Path, call: Any) -> None:
    v = _v()
    syn = Synthetic(tmp_path, ODCB)
    report = v.run_report(
        ODCB, call=call, prereg=syn.prereg, root=tmp_path, submission=syn.logged(), receipt=syn.receipt()
    )
    shared = v.shared_output(report)
    assert set(shared) == {
        "dataset",
        "protocol_sha256",
        "status",
        "verification",
        "annotation",
        "tracks",
        "notes",
        "spot_check_signed",
    }
    for track in shared["tracks"].values():
        assert set(track) == {"label", "labels", "fragile"}
        for label in track["labels"].values():
            assert set(label) == {"name", "roster", "compared", "agreeing", "disagreeing", "pending"}
    assert shared["tracks"]["reproduction"]["label"] == pl.REPRODUCTION_LABEL
    json.dumps(shared, allow_nan=False)  # plain JSON


@pytest.mark.parametrize("dataset", [BENZENE, ODCB])
def test_the_page_lines_pass_the_page_gate(tmp_path: Path, dataset: str, call: Any) -> None:
    """The shared output renders the two page lines the V1.5a gate reads."""
    v = _v()
    syn = Synthetic(tmp_path, dataset)
    for receipt in (None, syn.receipt()):
        report = v.run_report(
            dataset, call=call, prereg=syn.prereg, root=tmp_path, submission=syn.logged(), receipt=receipt
        )
        lines = v.page_lines(v.shared_output(report))
        assert len(lines) == 2 and lines[0].startswith("**Verification:** ") and lines[1].startswith("**V0.3 label:** ")
        assert v.check_page("\n\n".join(lines) + "\n", dataset=dataset) == []


# ======================================================================= fit-value sentinels
#: Synthetic sentinel tensors: distinctive digits that must never leave the local report.
SENTINEL_S_ZZ = -0.0731987654321


def _renderings(x: float) -> set[str]:
    """The ways a number could be written: fixed decimals with three or more significant digits."""
    out = set()
    for d in range(3, 13):
        for y in (x, abs(x)):
            s = f"{y:.{d}f}"
            if len(s.lstrip("-0.").replace(".", "")) >= 3:
                out.add(s)
    out.add(repr(x))
    return out


def _leaks(text: str, values: list[float]) -> list[str]:
    return sorted({s for x in values if x is not None and x != 0 for s in _renderings(x) if s in text})


def _sentinel_dataset(tmp_path: Path) -> Synthetic:
    truths = {k: {"S_zz": SENTINEL_S_ZZ - 1.234567e-4 * i} for i, k in enumerate(_condition_keys(BENZENE))}
    targets = {(k, "S_zz"): (t["S_zz"] + 0.00198765, 0.000431) for k, t in truths.items()}
    return Synthetic(tmp_path, BENZENE, truths=truths, targets=targets)


def test_no_fit_or_target_value_reaches_the_shared_output(tmp_path: Path, call: Any) -> None:
    v = _v()
    syn = _sentinel_dataset(tmp_path)
    reviews = None
    report = v.run_report(
        BENZENE,
        call=call,
        prereg=syn.prereg,
        root=tmp_path,
        submission=syn.logged(),
        receipt=syn.receipt(),
        reviews=reviews,
    )
    secret: list[float] = []
    for c in report["cells"]["independent"]:
        secret += [c["fit"], c["target"], c["discrepancy"], c["margin"]]
    for cond in report["conditions"].values():
        secret += [cond["chi2"], *cond["se"].values(), *cond["scaled_se"].values(), *cond["ratio_residuals"]]
    assert len([x for x in secret if x]) > 60
    shared = v.shared_output(report)
    outward = json.dumps(shared, ensure_ascii=False) + "\n" + "\n".join(v.page_lines(shared))
    assert _leaks(outward, secret) == []
    # The local report, by contrast, has them (the sentinels are visible to the scan).
    local = v.write_local(report, Path("datasets-local/benzene-taggar2006-targets/verification-v1.5.md"), root=tmp_path)
    assert _leaks(local.read_text(encoding="utf-8"), secret)


def _failure_messages(tmp_path: Path) -> Iterator[tuple[str, str]]:
    """Each failure path's message, with a sentinel in the faulty input."""
    v = _v()
    token = "-0.0731987654"

    def bad_target(syn: Synthetic) -> None:
        rows = _target_rows(BENZENE, syn.targets)
        rows[0]["S_zz"] = token + "x"
        _write_csv(syn.targets_path, rows)
        syn.prereg["datasets"][BENZENE]["targets"]["sha256"] = _sha(syn.targets_path)

    def bad_coupling(syn: Synthetic) -> None:
        rows = _couplings_rows(BENZENE, syn.truths)
        rows[0]["D_obs_Hz"] = token + "x"
        _write_csv(syn.couplings_path, rows)
        syn.prereg["datasets"][BENZENE]["couplings"]["sha256"] = _sha(syn.couplings_path)

    def bad_sigma(syn: Synthetic) -> None:
        rows = _couplings_rows(BENZENE, syn.truths)
        rows[0]["sigma_Hz"] = "-" + token.lstrip("-")
        _write_csv(syn.couplings_path, rows)
        syn.prereg["datasets"][BENZENE]["couplings"]["sha256"] = _sha(syn.couplings_path)

    def changed_targets(syn: Synthetic) -> None:
        syn.targets_path.write_text(syn.targets_path.read_text(encoding="utf-8") + token + "\n", encoding="utf-8")

    cases: dict[str, Callable[[Synthetic], None]] = {
        "bad target": bad_target,
        "bad coupling": bad_coupling,
        "bad sigma": bad_sigma,
        "changed targets": changed_targets,
    }
    for name, mutate in cases.items():
        syn = _sentinel_dataset(tmp_path / name.replace(" ", "-"))
        mutate(syn)
        messages = []
        for fn in (v.read_couplings, v.read_targets, v.check_inputs):
            try:
                out = fn(BENZENE, prereg=syn.prereg, root=syn.root)
                if fn is v.check_inputs:
                    messages += list(out)
            except ValueError as exc:
                messages.append(str(exc))
        report = v.run_report(
            BENZENE, call=_never, prereg=syn.prereg, root=syn.root, submission=syn.logged(), receipt=syn.receipt()
        )
        yield name, "\n".join(messages) + "\n" + json.dumps(v.shared_output(report)) + json.dumps(report, default=str)


def test_no_sentinel_reaches_a_failure_message(tmp_path: Path) -> None:
    """Refusals name a path, a key or a column, never a value (V0.3 §6, plan V1.5b)."""
    secret = [-0.0731987654, SENTINEL_S_ZZ]
    for name, text in _failure_messages(tmp_path):
        assert text.strip(), name
        assert _leaks(text, secret) == [], name


def test_a_registry_failure_names_the_operation_not_the_values(tmp_path: Path) -> None:
    v = _v()
    syn = _sentinel_dataset(tmp_path)
    observed = v.read_couplings(BENZENE, prereg=syn.prereg, root=tmp_path)
    key = _condition_keys(BENZENE)[0]

    inner = v.local_call()

    def failing(name: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
        if name == "couplings.import":
            raise v.RegistryError(name, "INVALID_ARGUMENT")
        result: dict[str, Any] = inner(name, args)
        return result

    with pytest.raises(v.RegistryError) as info:
        v.fit_condition(failing, BENZENE, syn.prereg, observed[key])
    values = [dv for dv, _ in observed[key].values()]
    assert "couplings.import" in str(info.value) and _leaks(str(info.value), values) == []


# ============================================ round 83 regressions (A3, A6), frozen before the fix
R83_LOG_PY = ROOT / "tools" / "validation" / "first_fit_log.py"


def _r83() -> Any:
    """The round 83 fixes, or an xfail while (and only while) their marker module is absent."""
    v = _v()
    if not R83_LOG_PY.is_file():
        pytest.xfail("round 83: the fixes are not written yet")
    return v


def _blocked_report() -> dict[str, Any]:
    return {"dataset": BENZENE, "protocol_sha256": "ab" * 32, "submission": {}, "status": "blocked", "problems": []}


def _complete_report() -> dict[str, Any]:
    return {
        "dataset": BENZENE,
        "protocol_sha256": "ab" * 32,
        "submission": {"dataset": BENZENE},
        "status": "complete",
        "conditions": {"c00": {"estimates": {"S_zz": 0.1234567}}},
        "cells": {"independent": []},
    }


def test_a_linked_local_directory_is_refused(tmp_path: Path) -> None:
    """A3: datasets-local (or a directory under it) linked to a shared place is not local."""
    v = _r83()
    root, shared = tmp_path / "checkout", tmp_path / "shared"
    root.mkdir()
    shared.mkdir()
    (root / "datasets-local").symlink_to(shared, target_is_directory=True)
    with pytest.raises(ValueError):
        v.write_local(_blocked_report(), Path("datasets-local/report.md"), root=root)
    with pytest.raises(ValueError):
        v.write_fit_values(_complete_report(), root=root)
    assert list(shared.iterdir()) == []

    (root / "datasets-local").unlink()
    (root / "datasets-local").mkdir()
    (root / "datasets-local" / "verification").symlink_to(shared, target_is_directory=True)
    with pytest.raises(ValueError):
        v.write_fit_values(_complete_report(), root=root)
    with pytest.raises(ValueError):
        v.write_local(_blocked_report(), Path("datasets-local/verification/report.md"), root=root)
    assert list(shared.iterdir()) == []


def test_a_linked_local_file_is_replaced_not_followed(tmp_path: Path) -> None:
    """A3: writing replaces a link at the destination; the file it pointed to is untouched."""
    v = _r83()
    outside = tmp_path / "outside.md"
    outside.write_text("untouched\n", encoding="utf-8")
    local = tmp_path / "datasets-local"
    local.mkdir()
    (local / "report.md").symlink_to(outside)
    target = v.write_local(_blocked_report(), Path("datasets-local/report.md"), root=tmp_path)
    assert not target.is_symlink() and target.read_text(encoding="utf-8").startswith("# Verification report")
    assert outside.read_text(encoding="utf-8") == "untouched\n"
    assert sorted(p.name for p in local.iterdir()) == ["report.md"]  # no temporary file left


@pytest.mark.parametrize("change", ["an unknown key", "a frame that is not a rotation"])
def test_an_invalid_protocol_is_never_fitted(tmp_path: Path, change: str) -> None:
    """A6: the closed schema and the cross-field checks run before any fit, even when the
    submission carries the changed protocol's own revision."""
    v = _r83()
    syn = Synthetic(tmp_path, BENZENE)
    if change == "an unknown key":
        syn.prereg["note"] = "changed"
    else:
        syn.prereg["datasets"][BENZENE]["frame_map_matrix"] = [[1, 0, 0], [0, 1, 0], [0, 0, -1]]
    report = v.run_report(BENZENE, call=_never, prereg=syn.prereg, root=tmp_path, submission=syn.logged())
    assert report["status"] == "blocked" and report["problems"]


def test_the_local_report_keeps_each_fits_provenance(tmp_path: Path, call: Any) -> None:
    """A6: the model, frame, science identity, fit version, symmetry, assumptions and warnings of
    each fit, and the dataset's flags and the package versions, stay in the local report."""
    v = _r83()
    syn = Synthetic(tmp_path, BENZENE)
    report = v.run_report(BENZENE, call=call, prereg=syn.prereg, root=tmp_path, submission=syn.logged())
    d = PREREG["datasets"][BENZENE]
    for condition in report["conditions"].values():
        prov = condition["provenance"]
        assert prov["model"]["kind"] == "fixed"
        assert prov["frame"] and prov["estimand"]
        assert prov["science_hash"].startswith("sha256:")
        assert prov["fit_version"] == PREREG["model"]["fixed_fit_version"]
        assert prov["symmetry"]["point_group"] == d["point_group"]
        assert isinstance(prov["assumptions"], list) and isinstance(prov["warnings"], list)
    assert report["provenance"]["flags"] == d["flags"]
    assert set(report["provenance"]["versions"]) == {"dipolar-core", "dipolar-app"}
    local = v.write_local(report, Path("datasets-local/report.md"), root=tmp_path).read_text(encoding="utf-8")
    assert "fit_version" in local and "science_hash" in local
    assert "provenance" not in json.dumps(v.shared_output(report))


# ================================== round 83 regressions (A4): the authors' analysis track, frozen
# before the fix. The owner's local method-evidence record says which of the four inputs the
# source documents, and gives them: the authors' ring radii, the objective, the weights and the
# corrections. All four give a reproduction; the geometry without the objective or the weights
# gives the frozen fallback under its own label; anything else leaves the track pending. P-2 and
# rank precedence apply on this track as on the other.
FOUR = ["geometry", "objective", "weights", "corrections"]
AUTHORS = {"r_cc_angstrom": 1.397, "r_ch_angstrom": 1.089}  # a synthetic authors' geometry


def _lam(geometry: dict[str, float] = AUTHORS) -> float:
    """The authors' ring radius over the declared one: every H–H distance scales by it."""
    g = PREREG["geometry"]
    return float((geometry["r_cc_angstrom"] + geometry["r_ch_angstrom"]) / (g["r_cc_angstrom"] + g["r_ch_angstrom"]))


def _method(syn: Synthetic, documented: list[str] = FOUR, **changes: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "dataset": syn.dataset,
        "protocol_sha256": syn.protocol,
        "documented": list(documented),
        "geometry": dict(AUTHORS) if "geometry" in documented else None,
        "objective": "least squares" if "objective" in documented else None,
        "weights": "1/sigma^2" if "weights" in documented else None,
        "corrections": [] if "corrections" in documented else None,
        "sources": {k: f"where the source documents the {k} (synthetic)" for k in documented},
    }
    record.update(changes)
    return record


def _authors_benzene_fit(truths: dict[str, dict[str, float]], key: str, *, weighted: bool) -> float:
    """S_zz from the scalar law with the authors' radii, independently of the engine: an in-plane
    pair gives D = −K·S_zz/(2r³); least squares with weights 1/σ² or uniform."""
    h = _protons(BENZENE)
    a, y, w = [], [], []
    for r in _couplings_rows(BENZENE, truths):
        if f"{r['run']}/{r['sample']}" != key:
            continue
        dist = float(np.linalg.norm(h[r["spin_b"]] - h[r["spin_a"]])) * _lam()
        a.append(-K / (2 * dist**3))
        y.append(float(r["D_obs_Hz"]))
        w.append(1 / float(r["sigma_Hz"]) ** 2 if weighted else 1.0)
    av, yv, wv = np.array(a), np.array(y), np.array(w)
    return float((wv * av * yv).sum() / (wv * av * av).sum())


def _tokened(x: float) -> tuple[str, tuple[float, float]]:
    """A printed table token at four decimals with σ = 4 in the last place, and its target."""
    value = Decimal(repr(x)).quantize(Decimal("0.0001"))
    return f"{value}(4)", (float(value), 0.0004)


def _authors_benzene(
    root: Path, *, weighted: bool = True, offsets: dict[str, float] | None = None
) -> tuple[Synthetic, dict[str, float], dict[str, str]]:
    """Benzene whose printed targets are the authors' synthetic estimates at four decimals."""
    truths = {k: _truth(BENZENE, i) for i, k in enumerate(_condition_keys(BENZENE))}
    est = {k: _authors_benzene_fit(truths, k, weighted=weighted) for k in truths}
    tokens: dict[str, str] = {}
    targets: dict[tuple[str, str], tuple[float, float] | None] = {}
    for k, x in est.items():
        tokens[k], targets[(k, "S_zz")] = _tokened(x + (offsets or {}).get(k, 0.0))
    return Synthetic(root, BENZENE, truths=truths, targets=targets, tokens=tokens), est, tokens


def _counting(call: Any) -> tuple[Any, list[str]]:
    seen: list[str] = []

    def wrapped(name: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
        seen.append(name)
        out: dict[str, Any] = call(name, args)
        return out

    return wrapped, seen


def _unverified_call(call: Any) -> Any:
    def wrapped(name: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
        out: dict[str, Any] = call(name, args)
        return {**out, "result": _unverified(out["result"])} if name == "run.get" else out

    return wrapped


def test_the_documented_method_runs_the_reproduction(tmp_path: Path, call: Any) -> None:
    """All four inputs documented: the fit uses the authors' geometry, the cell margin is the
    printed token's, and the track carries the reproduction label."""
    v = _r83b()
    syn, est, tokens = _authors_benzene(tmp_path)
    counted, seen = _counting(call)
    report = v.run_report(
        BENZENE,
        call=counted,
        prereg=syn.prereg,
        root=tmp_path,
        submission=syn.logged(),
        receipt=syn.receipt(),
        method=_method(syn),
    )
    assert report["status"] == "complete"
    assert seen.count("fit.run") == 2 * 15  # the independent fit and the authors' analysis
    assert report["reproduction"]["mode"] == "reproduction"
    assert report["track_labels"]["reproduction"] == pl.REPRODUCTION_LABEL
    full = report["tracks"]["reproduction"]["full"]
    assert (full.name, full.compared, full.agreeing, full.pending) == ("experimentally supported", 15, 15, 0)
    for c in report["cells"]["reproduction"]:
        k = c["condition"]
        assert c["fit"] == pytest.approx(est[k], rel=1e-9)
        assert c["target"] == float(tokens[k].split("(")[0])
        assert c["margin"] == pl.table_margin(tokens[k]) == pytest.approx(0.0004)
        assert c["discrepancy"] == pytest.approx(c["fit"] - c["target"], abs=1e-15)
    for k, f in report["conditions"].items():  # the independent track kept the declared geometry
        assert f["estimates"]["S_zz"] * _lam() ** 3 == pytest.approx(est[k], rel=1e-9)
    for f in report["reproduction_conditions"].values():
        assert f["rank_verified"] and f["provenance"]["model"]["kind"] == "fixed"
    assert v.shared_output(report)["tracks"]["reproduction"]["label"] == pl.REPRODUCTION_LABEL


@pytest.mark.parametrize(
    ("documented", "weights"),
    [
        (["geometry"], None),
        (["geometry", "corrections"], None),
        (["geometry", "weights", "corrections"], "uniform"),  # the objective unknown: the frozen fallback
        (["geometry", "objective", "corrections"], None),
    ],
)
def test_the_geometry_alone_runs_the_fallback_under_its_label(
    tmp_path: Path, call: Any, documented: list[str], weights: str | None
) -> None:
    """V0.3 §6: weighted least squares with 1/σ², the authors' geometry, and the fallback label on
    every outcome, whatever weights the record names."""
    v = _r83b()
    syn, est, _ = _authors_benzene(tmp_path, weighted=True)
    method = _method(syn, documented, **({"weights": weights} if weights else {}))
    report = v.run_report(
        BENZENE,
        call=call,
        prereg=syn.prereg,
        root=tmp_path,
        submission=syn.logged(),
        receipt=syn.receipt(),
        method=method,
    )
    assert report["reproduction"]["mode"] == "fallback"
    assert report["track_labels"]["reproduction"] == pl.FALLBACK_LABEL
    assert v.shared_output(report)["tracks"]["reproduction"]["label"] == pl.FALLBACK_LABEL
    for c in report["cells"]["reproduction"]:
        assert c["fit"] == pytest.approx(est[c["condition"]], rel=1e-9)
    assert report["tracks"]["reproduction"]["full"].compared == 15


def test_documented_uniform_weights_are_the_ones_applied(tmp_path: Path, call: Any) -> None:
    v = _r83b()
    syn, est, _ = _authors_benzene(tmp_path, weighted=False)
    truths = {k: _truth(BENZENE, i) for i, k in enumerate(_condition_keys(BENZENE))}
    weighted = {k: _authors_benzene_fit(truths, k, weighted=True) for k in truths}
    assert all(abs(est[k] - weighted[k]) > 1e-6 for k in est)  # the weights matter here
    report = v.run_report(
        BENZENE,
        call=call,
        prereg=syn.prereg,
        root=tmp_path,
        submission=syn.logged(),
        receipt=syn.receipt(),
        method=_method(syn, weights="uniform"),
    )
    assert report["reproduction"]["mode"] == "reproduction"
    for c in report["cells"]["reproduction"]:
        assert c["fit"] == pytest.approx(est[c["condition"]], rel=1e-9)
    assert report["tracks"]["reproduction"]["full"].agreeing == 15


@pytest.mark.parametrize("documented", [None, ["geometry", "objective", "weights"], ["objective", "weights"], []])
def test_without_a_reproduction_or_fallback_the_track_stays_pending(
    tmp_path: Path, call: Any, documented: list[str] | None
) -> None:
    """No record, undocumented corrections with a known objective and weights, or no geometry:
    pending (inputs-undocumented), and no second fit."""
    v = _r83b()
    syn, _, _ = _authors_benzene(tmp_path)
    counted, seen = _counting(call)
    report = v.run_report(
        BENZENE,
        call=counted,
        prereg=syn.prereg,
        root=tmp_path,
        submission=syn.logged(),
        receipt=syn.receipt(),
        method=None if documented is None else _method(syn, documented),
    )
    assert seen.count("fit.run") == 15
    assert report["reproduction"]["mode"] == "pending"
    assert report["reproduction_conditions"] == {}
    assert {(c["status"], c["reason"]) for c in report["cells"]["reproduction"]} == {("pending", "inputs-undocumented")}
    assert all(c["fit"] is None and c["target"] is None for c in report["cells"]["reproduction"])


def test_the_spot_check_gates_the_reproduction_track(tmp_path: Path, call: Any) -> None:
    """P-2 on this track too: until the receipt is signed, the targets are withheld (no-target)."""
    v = _r83b()
    syn, _, _ = _authors_benzene(tmp_path)
    report = v.run_report(
        BENZENE, call=call, prereg=syn.prereg, root=tmp_path, submission=syn.logged(), method=_method(syn)
    )
    assert report["reproduction"]["mode"] == "reproduction"
    assert {(c["status"], c["reason"]) for c in report["cells"]["reproduction"]} == {("pending", "no-target")}
    for c in report["cells"]["reproduction"]:
        assert c["fit"] is not None
        assert (c["target"], c["margin"], c["discrepancy"]) == (None, None, None)
    assert report["tracks"]["reproduction"]["full"].compared == 0


@pytest.mark.parametrize("signed", [True, False])
def test_an_unverified_rank_keeps_its_precedence_on_the_reproduction_track(
    tmp_path: Path, call: Any, signed: bool
) -> None:
    v = _r83b()
    syn, _, _ = _authors_benzene(tmp_path)
    report = v.run_report(
        BENZENE,
        call=_unverified_call(call),
        prereg=syn.prereg,
        root=tmp_path,
        submission=syn.logged(),
        receipt=syn.receipt() if signed else None,
        method=_method(syn),
    )
    assert {(c["status"], c["reason"]) for c in report["cells"]["reproduction"]} == {("pending", "rank-unverified")}
    assert report["tracks"]["reproduction"]["full"].compared == 0


def _odcb_authors(root: Path, *, edges: dict[str, float]) -> Synthetic:
    """o-DCB with exact couplings; each named condition's S_zz target is moved by the given amount."""
    truths = {k: _truth(ODCB, i) for i, k in enumerate(_condition_keys(ODCB))}
    targets: dict[tuple[str, str], tuple[float, float] | None] = dict(_default_targets(ODCB, truths))
    for k, delta in edges.items():
        targets[(k, "S_zz")] = (truths[k]["S_zz"] + delta, 0.0004)
    return Synthetic(root, ODCB, truths=truths, targets=targets, offsets=False)


def test_the_figure_margin_on_the_reproduction_track(tmp_path: Path, call: Any) -> None:
    """A digitized target's margin is 2p: just inside agrees, just outside disagrees, while the
    independent margin accepts both. The disagreement needs its own review on this track."""
    v = _r84()  # amended for round 84 (A5): the evidence format
    syn = _odcb_authors(tmp_path, edges={"I/310": 0.0008 - 1e-6, "I/312": 0.0008 + 1e-6})
    g = PREREG["geometry"]
    method = _method(syn, geometry={"r_cc_angstrom": g["r_cc_angstrom"], "r_ch_angstrom": g["r_ch_angstrom"]})
    kw = {"call": call, "prereg": syn.prereg, "root": tmp_path, "submission": syn.logged()}
    report = v.run_report(ODCB, **kw, receipt=syn.receipt(), method=method)
    cells = {(c["condition"], c["component"]): c for c in report["cells"]["reproduction"]}
    assert all(c["margin"] == pytest.approx(0.0008) for c in cells.values())
    assert cells[("I/310", "S_zz")]["status"] == "agrees"
    assert cells[("I/312", "S_zz")]["status"] == "disagrees"
    assert report["tracks"]["independent"]["full"].name == "experimentally supported"
    full = report["tracks"]["reproduction"]["full"]
    assert (full.name, full.disagreeing, full.agreeing) == ("unresolved failure", 1, 43)
    assert any("reproduction" in p for p in report["review_problems"])

    key = _key(ODCB, "reproduction", "I/312", "S_zz", syn.protocol)
    reviewed = v.run_report(ODCB, **kw, receipt=syn.receipt(), method=method, reviews=_evidence(tmp_path, [key]))
    assert reviewed["review_problems"] == []
    assert reviewed["tracks"]["reproduction"]["full"].name == "explained discrepancy"
    assert reviewed["tracks"]["independent"]["full"].name == "experimentally supported"


METHOD_MUTANTS: dict[str, Callable[[Synthetic], Any]] = {
    "not a record": lambda syn: FOUR,
    "another dataset": lambda syn: _method(syn, dataset=ODCB),
    "another protocol revision": lambda syn: _method(syn, protocol_sha256="0" * 64),
    "an unknown field": lambda syn: _method(syn, note="extra"),
    "a missing field": lambda syn: {k: x for k, x in _method(syn).items() if k != "sources"},
    "an unknown input": lambda syn: _method(syn, documented=[*FOUR, "vibrations"]),
    "a repeated input": lambda syn: _method(syn, documented=["geometry", "geometry"]),
    "a documented geometry that is absent": lambda syn: _method(syn, geometry=None),
    "an undocumented geometry that is given": lambda syn: _method(syn, ["objective"], geometry=dict(AUTHORS)),
    "a non-positive distance": lambda syn: _method(syn, geometry={**AUTHORS, "r_ch_angstrom": 0.0}),
    "a distance as text": lambda syn: _method(syn, geometry={**AUTHORS, "r_cc_angstrom": "1.397"}),
    "a geometry with another field": lambda syn: _method(syn, geometry={**AUTHORS, "shape": "distorted"}),
    "an objective the fitter does not implement": lambda syn: _method(syn, objective="maximum entropy"),
    "weights the fitter does not implement": lambda syn: _method(syn, weights="1/sigma"),
    "a documented correction": lambda syn: _method(syn, corrections=["vibrational"]),
    "an undocumented objective that is given": lambda syn: _method(syn, ["geometry"], objective="least squares"),
    "no source for a documented input": lambda syn: _method(syn, sources={"geometry": "x"}),
    "an empty source": lambda syn: _method(syn, sources={k: " " for k in FOUR}),
}


@pytest.mark.parametrize("name", list(METHOD_MUTANTS))
def test_a_malformed_method_record_blocks_before_any_fit(tmp_path: Path, name: str) -> None:
    v = _r83b()
    syn, _, _ = _authors_benzene(tmp_path)
    report = v.run_report(
        BENZENE,
        call=_never,
        prereg=syn.prereg,
        root=tmp_path,
        submission=syn.logged(),
        receipt=syn.receipt(),
        method=METHOD_MUTANTS[name](syn),
    )
    assert report["status"] == "blocked" and report["problems"], name
    assert not any("1.397" in p or "1.089" in p for p in report["problems"])


def test_a_printed_token_that_is_not_its_target_blocks(tmp_path: Path) -> None:
    """The table margin comes from the hash-verified printed token; a token whose value is not the
    target's is a corrupt input, before any fit."""
    v = _r83b()
    truths = {k: _truth(BENZENE, i) for i, k in enumerate(_condition_keys(BENZENE))}
    targets: dict[tuple[str, str], tuple[float, float] | None] = {
        (k, "S_zz"): (-0.0612, 0.0004) for k in _condition_keys(BENZENE)
    }
    tokens = {k: "-0.0612(4)" for k in _condition_keys(BENZENE)}
    tokens[_condition_keys(BENZENE)[3]] = "-0.0613(4)"
    syn = Synthetic(tmp_path, BENZENE, truths=truths, targets=targets, tokens=tokens)
    kw = {"prereg": syn.prereg, "root": tmp_path, "submission": syn.logged(), "receipt": syn.receipt()}
    report = v.run_report(BENZENE, call=_never, **kw, method=_method(syn))
    assert report["status"] == "blocked" and report["problems"]
    assert not any("0.061" in p for p in report["problems"])


def test_a_token_without_its_sigma_has_no_precision(tmp_path: Path, call: Any) -> None:
    v = _r83b()
    syn0, _, tokens = _authors_benzene(tmp_path / "first")
    k = _condition_keys(BENZENE)[2]
    tokens = {**tokens, k: tokens[k].split("(")[0]}
    syn = Synthetic(tmp_path, BENZENE, truths=syn0.truths, targets=dict(syn0.targets), tokens=tokens)
    report = v.run_report(
        BENZENE,
        call=call,
        prereg=syn.prereg,
        root=tmp_path,
        submission=syn.logged(),
        receipt=syn.receipt(),
        method=_method(syn),
    )
    reasons = {c["condition"]: (c["status"], c["reason"]) for c in report["cells"]["reproduction"]}
    assert reasons[k] == ("pending", "no-precision")
    assert sum(r == ("agrees", "") for r in reasons.values()) == 14


def test_reproduction_values_stay_local_and_reach_the_fit_tier(tmp_path: Path, call: Any) -> None:
    """The authors'-analysis fits and discrepancies are in the local report and the fit-values
    record (for the scan), and none reaches the shared output."""
    v = _r83b()
    syn, _, _ = _authors_benzene(tmp_path, offsets={_condition_keys(BENZENE)[0]: 0.0123})
    report = v.run_report(
        BENZENE,
        call=call,
        prereg=syn.prereg,
        root=tmp_path,
        submission=syn.logged(),
        receipt=syn.receipt(),
        method=_method(syn, ["geometry"]),
    )
    secret: list[float] = []
    for c in report["cells"]["reproduction"]:
        secret += [c["fit"], c["target"], c["discrepancy"], c["margin"]]
    for f in report["reproduction_conditions"].values():
        secret += [f["chi2"], *f["se"].values()]
    shared = v.shared_output(report)
    assert _leaks(json.dumps(shared, ensure_ascii=False) + "\n".join(v.page_lines(shared)), secret) == []
    local = v.write_local(report, Path("datasets-local/report.md"), root=tmp_path).read_text(encoding="utf-8")
    assert "## Cells (" + pl.FALLBACK_LABEL + ")" in local
    assert _leaks(local, [c["fit"] for c in report["cells"]["reproduction"]])

    record = v.fit_values(report)
    got = {(e["condition"], e["component"], e["quantity"]): e["value"] for e in record["values"]}
    for c in report["cells"]["reproduction"]:
        assert got[(c["condition"], c["component"], "reproduction estimate")] == c["fit"]
        if c["discrepancy"] is not None:
            assert got[(c["condition"], c["component"], "reproduction discrepancy")] == c["discrepancy"]
    assert sum(q == "reproduction discrepancy" for _, _, q in got) == 15


def test_the_reproduction_track_reads_the_rank_flag_itself() -> None:
    """Rank precedence does not lean on the estimate being absent: a fit marked rank-unverified is
    pending/rank-unverified on this track even if it carries an estimate."""
    v = _r83b()
    p = copy.deepcopy(PREREG)
    keys = _condition_keys(BENZENE)
    targets = {(k, "S_zz"): (-0.0612, 0.0004) for k in keys}
    fits = {k: v.PaperFit(rank_verified=False, estimates={"S_zz": -0.0612}) for k in keys}
    method = v.ev.Method("reproduction", tuple(FOUR), dict(AUTHORS), "1/sigma^2")
    artifact = p["reporting"]["spot_check_gating"]["checked_artifact"][BENZENE]
    receipt = {"dataset": BENZENE, "artifact": artifact, "sha256": p["datasets"][BENZENE][artifact]["sha256"]}
    for r in (receipt, None):
        cells = v.reproduction_cells(BENZENE, p, method, fits, targets, receipt=r)
        assert {(c.status, c.reason) for c in cells} == {("pending", "rank-unverified")}


# ===================== round 84 (A1): the runner refuses an unauthorized submission itself, frozen
# before the fix. ``run_report`` checks the submission against the first-fit log committed in its
# own root (``authorize``, at the runner's clock) before it reads or fits anything, whoever calls
# it; a refusal is a PermissionError with value-free reasons.
def _unauthorized(name: str, syn: Synthetic) -> dict[str, Any]:
    if name == "no committed ledger":
        return syn.submission()
    if name == "logged in the working copy only":
        syn.logged(release_or_commit="v0.0.0-other")  # commits the log with another submission
        record = syn.submission()
        ledger = syn.root / LEDGER_REL
        row = f"| 2026-11-25T10:00Z | submission | {syn.dataset} | owner | v0.2.0b1 | {syn.protocol} |\n"
        ledger.write_text(ledger.read_text(encoding="utf-8") + row, encoding="utf-8")
        return record
    if name == "an agent runner":
        return syn.logged(runner="agent")
    if name == "a submission at the freeze instant":
        return syn.logged(at=datetime(2026, 11, 24, 9, 0, tzinfo=UTC))
    if name == "a submission in the future":
        return syn.logged(at=datetime(2026, 11, 25, 13, 0, tzinfo=UTC))
    if name == "logged with another release":
        syn.logged(release_or_commit="v0.0.0-other")
        return syn.submission()
    raise AssertionError(name)


UNAUTHORIZED = [
    "no committed ledger",
    "logged in the working copy only",
    "an agent runner",
    "a submission at the freeze instant",
    "a submission in the future",
    "logged with another release",
]


@pytest.mark.parametrize("name", UNAUTHORIZED)
def test_the_runner_refuses_an_unauthorized_submission_whoever_calls_it(tmp_path: Path, call: Any, name: str) -> None:
    """A1: calling ``run_report`` directly fits nothing for a submission the committed log does
    not authorize."""
    v = _r84()
    syn = Synthetic(tmp_path, BENZENE)
    record = _unauthorized(name, syn)
    counted, seen = _counting(call)
    with pytest.raises(PermissionError) as refused:
        v.run_report(BENZENE, call=counted, prereg=syn.prereg, root=tmp_path, submission=record)
    assert seen == [], name
    assert not (tmp_path / "datasets-local" / "verification").exists()
    assert syn.protocol not in str(refused.value) and "authoriz" in str(refused.value)


def test_the_runner_fits_a_committed_authorized_submission(tmp_path: Path, call: Any) -> None:
    v = _r84()
    syn = Synthetic(tmp_path, BENZENE)
    counted, seen = _counting(call)
    report = v.run_report(BENZENE, call=counted, prereg=syn.prereg, root=tmp_path, submission=syn.logged())
    assert report["status"] == "complete" and seen.count("fit.run") == 15
