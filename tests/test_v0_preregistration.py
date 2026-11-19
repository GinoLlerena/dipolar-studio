"""The V0.3 preregistration (docs/phase2/v0.3-preregistration.json) is consistent with the code
it freezes, with its closed schema, and with an independent construction of its frames and pair
orbits. No experimental value is fitted here: the fits use synthetic tensors on the declared
geometry. A local-only scan checks that no restricted value is in any tracked file (round 73).
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from dipolar_core import fixed
from dipolar_core.forward import design_rows
from dipolar_core.nuclides import TABLE_VERSION, dipolar_constant_hz_a3

ROOT = Path(__file__).resolve().parents[1]
PHASE2 = ROOT / "docs" / "phase2"
PREREG: dict[str, Any] = json.loads((PHASE2 / "v0.3-preregistration.json").read_text(encoding="utf-8"))
SCHEMA: dict[str, Any] = json.loads((PHASE2 / "v0.3-preregistration.schema.json").read_text(encoding="utf-8"))
K = dipolar_constant_hz_a3("1H", "1H")
BENZENE = PREREG["datasets"]["benzene-taggar2006"]
ODCB = PREREG["datasets"]["odcb-chandrakumar1993"]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _protons(dataset: dict[str, Any]) -> tuple[dict[str, int], np.ndarray]:
    """The declared hexagon's protons at the dataset's ring positions, in its paper frame."""
    g = PREREG["geometry"]
    radius = g["r_cc_angstrom"] + g["r_ch_angstrom"]
    names = sorted(dataset["ring_positions"], key=lambda h: int(h[1:]))
    a = np.radians([dataset["ring_positions"][h] for h in names])
    xyz = np.column_stack([radius * np.cos(a), radius * np.sin(a), np.zeros(len(a))])
    return {h: i for i, h in enumerate(names)}, xyz


# ---- The schema and the frozen settings ------------------------------------------------------------


def _closed(node: Any, where: str = "$") -> list[str]:
    """Every object schema must forbid unknown keys (or constrain them, for maps)."""
    problems = []
    if isinstance(node, dict):
        if node.get("type") == "object" and "additionalProperties" not in node:
            problems.append(where)
        for key, value in node.items():
            problems += _closed(value, f"{where}.{key}")
    elif isinstance(node, list):
        for i, value in enumerate(node):
            problems += _closed(value, f"{where}[{i}]")
    return problems


def test_the_json_satisfies_its_closed_schema() -> None:
    import jsonschema

    jsonschema.Draft202012Validator.check_schema(SCHEMA)
    assert _closed(SCHEMA) == []
    jsonschema.validate(PREREG, SCHEMA, cls=jsonschema.Draft202012Validator)
    for bad in (
        {**PREREG, "extra": 1},
        {**PREREG, "geometry": {**PREREG["geometry"], "r_cc_angstrom": 1.4}},
        {**PREREG, "datasets": {**PREREG["datasets"], "benzene-taggar2006": {**BENZENE, "note": "-0.2"}}},
    ):
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(bad, SCHEMA, cls=jsonschema.Draft202012Validator)


def test_the_frozen_model_is_the_code_in_use() -> None:
    model = PREREG["model"]
    assert model["fixed_fit_version"] == fixed.FIXED_FIT_VERSION
    assert model["adequacy_alpha"] == fixed.ADEQUACY_ALPHA
    assert model["weak_rtol"] == fixed.WEAK_RTOL
    assert model["nuclide_table"] == TABLE_VERSION


def test_the_digitizer_uses_the_frozen_settings() -> None:
    import sys

    sys.path.insert(0, str(ROOT / "tools" / "datasets"))
    import digitize_figure as dg

    d = PREREG["digitization"]
    assert dg.MATCH_TOL_TR == d["match_tolerance_T_r"]
    assert dg.FIG2_MATCH_K == d["fig2_match_kelvin"]
    assert dg.FIG2_DISAGREEMENT_FACTOR == d["fig2_disagreement_factor"]
    assert dg.COUPLINGS_SHA256 == ODCB["couplings"]["sha256"]


# ---- Frames and orbits, from an independent construction -------------------------------------------


def _orbit_of(pair: tuple[int, int], ops: list[dict[int, int]]) -> frozenset[frozenset[int]]:
    return frozenset(frozenset((op[pair[0]], op[pair[1]])) for op in ops)


def _check_orbits(dataset: dict[str, Any], ops: list[dict[int, int]]) -> None:
    """One representative per orbit, every pair covered, and each key names exactly its orbit."""
    index, _ = _protons(dataset)
    n = len(index)
    all_pairs = {frozenset((i, j)) for i in range(n) for j in range(i + 1, n)}
    orbits = []
    for key, (a, b) in dataset["orbits"].items():
        orbit = _orbit_of((index[a], index[b]), ops)
        named = frozenset(frozenset((int(m[1]) - 1, int(m[2]) - 1)) for m in key.split("="))
        assert named <= orbit, (key, named, orbit)
        orbits.append(orbit)
    assert len(set(orbits)) == len(orbits) == dataset["observations_per_condition"]
    assert frozenset().union(*orbits) == all_pairs


def test_the_benzene_orbits_frame_and_signed_couplings() -> None:
    index, h = _protons(BENZENE)
    assert np.linalg.norm(h[0] - h[1]) == pytest.approx(2.4716, abs=1e-12)
    rotations = [{i: (i + k) % 6 for i in range(6)} for k in range(6)]
    reflections = [{i: (k - i) % 6 for i in range(6)} for k in range(6)]
    _check_orbits(BENZENE, rotations + reflections)
    assert BENZENE["frame_map_matrix"] == np.eye(3).astype(int).tolist()
    pairs = [(index[a], index[b]) for a, b in BENZENE["orbits"].values()]
    a5 = design_rows(h, pairs, K)
    s_zz = -0.25  # a negative S_zz (ring normal): the ring lies in the director's plane on average
    d = a5 @ np.array([s_zz, 0.0, 0.0, 0.0, 0.0])
    res = fixed.fit_fixed(a5, d, np.full(3, 0.01), fixed.SUBSPACES["D6h"])
    assert res.rank_verified and res.nu == BENZENE["nu"]
    conv = np.array(BENZENE["conversion_matrix"], dtype=float)
    assert (conv @ res.s5[:1])[0] == pytest.approx(s_zz, abs=1e-12)
    # Signed couplings: the SI's printed couplings are all negative, as the model predicts here.
    with (ROOT / BENZENE["couplings"]["path"]).open(encoding="utf-8", newline="") as handle:
        printed = [float(r["D_obs_Hz"]) for r in csv.DictReader(handle)]
    assert np.all(d < 0) and all(v < 0 for v in printed)


def test_the_odcb_frame_map_conversion_and_orbits() -> None:
    """Axes built independently from the geometry: x_V1 the ring normal, z_V1 the in-plane C2 axis
    (through the midpoint of H2–H3), y_V1 = z × x. They must equal the JSON's map; a synthetic
    paper-frame tensor fitted in the V1 frame must convert back through the JSON's matrix."""
    index, paper = _protons(ODCB)
    normal = np.cross(paper[1] - paper[0], paper[2] - paper[0])
    normal /= np.linalg.norm(normal)
    c2 = (paper[1] + paper[2]) / 2.0
    c2 /= np.linalg.norm(c2)
    axes = np.array([normal, np.cross(c2, normal), c2])
    assert np.allclose(axes, np.array(ODCB["frame_map_matrix"], dtype=float), atol=1e-12)
    assert np.linalg.det(axes) == pytest.approx(1.0)
    c2_op = {index["H1"]: index["H4"], index["H4"]: index["H1"], index["H2"]: index["H3"], index["H3"]: index["H2"]}
    _check_orbits(ODCB, [{i: i for i in range(4)}, c2_op])

    v1 = paper @ axes.T
    pairs = [(index[a], index[b]) for a, b in ODCB["orbits"].values()]
    s_xx, s_yy = 0.03, 0.15  # the paper frame's in-plane order parameters
    s_zz = -(s_xx + s_yy)
    d = design_rows(paper, pairs, K) @ np.array([s_zz, s_xx - s_yy, 0.0, 0.0, 0.0])
    res = fixed.fit_fixed(design_rows(v1, pairs, K), d, np.full(4, 0.01), fixed.SUBSPACES["C2v"])
    assert res.rank_verified and res.nu == ODCB["nu"]
    conv = np.array(ODCB["conversion_matrix"], dtype=float)
    assert conv @ res.s5[:2] == pytest.approx(np.array([s_zz, s_xx - s_yy]), abs=1e-12)


# ---- Inputs, targets and the roster ------------------------------------------------------------------


def test_the_benzene_inputs_and_roster() -> None:
    path = ROOT / BENZENE["couplings"]["path"]
    if not path.exists():
        pytest.skip("the benzene dataset is not present")
    assert _sha(path) == BENZENE["couplings"]["sha256"]
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    conditions = {(r["run"], r["sample"]) for r in rows}
    assert len(conditions) == BENZENE["conditions"]
    assert BENZENE["roster_cells"] == BENZENE["conditions"] * len(BENZENE["estimands"])
    assert set(BENZENE["flags"]["co_solutes"]) <= {f"{run}/{sample}" for run, sample in conditions}
    targets = ROOT / BENZENE["targets"]["path"]
    if targets.exists():  # local only (© ACS)
        assert _sha(targets) == BENZENE["targets"]["sha256"]
        with targets.open(encoding="utf-8", newline="") as handle:
            assert {(r["run"], r["sample"]) for r in csv.DictReader(handle)} == conditions


def test_the_local_odcb_inputs_targets_and_roster_when_present() -> None:
    couplings = ROOT / ODCB["couplings"]["path"]
    targets = ROOT / ODCB["targets"]["path"]
    if not (couplings.exists() and targets.exists()):
        pytest.skip("the local ortho-dichlorobenzene files are not present (© ISMAR, local only)")
    assert _sha(couplings) == ODCB["couplings"]["sha256"]
    assert _sha(targets) == ODCB["targets"]["sha256"]
    with couplings.open(encoding="utf-8", newline="") as handle:
        conditions = {(r["table"], r["T_K"]) for r in csv.DictReader(handle)}
    with targets.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    cells = {(r["table"], r["T_K"], r["component"]) for r in rows}
    assert len(conditions) == ODCB["conditions"]
    assert cells == {(t, k, c) for t, k in conditions for c in ODCB["estimands"]}
    assert len(rows) == ODCB["roster_cells"] == ODCB["targets"]["count"]
    assert sum(r["status"] == "pending" for r in rows) == ODCB["targets"]["pending"]
    near = {f"{t}/{k}" for t, k in conditions}
    assert (
        set(ODCB["flags"]["near_duplicate"]) <= near
        and set(PREREG["criteria"]["sensitivity"]["odcb-chandrakumar1993"]) <= near
    )


# ---- No restricted value in any tracked file (local only) -------------------------------------------

#: The sources' values were first seen on 2026-11-18 (exposure log). These tokens occur in files
#: added before that, by coincidence (a Phase 1 mockup and two browser tests); a file added later
#: may not be allowlisted. Tokens are kept as SHA-256 prefixes, so this file names no value.
COINCIDENCES = {
    ("docs/panel/mockup-workspace.html", "3c2f47db17b78941"),
    ("web/e2e/preview.spec.ts", "36b17256198109a4"),
    ("web/e2e/tutorial.spec.ts", "36b17256198109a4"),
}
FIRST_EXPOSURE = "2026-11-18"
LOCAL = ROOT / "datasets-local"
RESTRICTED = (
    LOCAL / "odcb-chandrakumar1993" / "couplings.csv",
    LOCAL / "odcb-chandrakumar1993" / "targets.csv",
    LOCAL / "benzene-taggar2006-targets" / "targets.csv",
)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()[:16]


def _significant(token: str) -> int:
    return len(token.replace("-", "").replace(".", "").lstrip("0"))


def _target_values() -> list[float]:
    values = []
    for path, columns in ((RESTRICTED[1], ("value", "fig2_value")), (RESTRICTED[2], ("S_zz",))):
        with path.open(encoding="utf-8", newline="") as h:
            values += [float(r[c]) for r in csv.DictReader(h) for c in columns if r[c]]
    return values


def _restricted_tokens() -> tuple[set[str], set[str]]:
    """Unsigned decimal strings of the restricted cells: the o-dichlorobenzene couplings (© ISMAR)
    and digitized targets, and the benzene paper targets (© ACS).
    - Everywhere: tokens of at least four significant digits (printed couplings, targets as
      written and at 4 decimals). Shorter tokens, such as the printed uncertainties, collide with
      unrelated numbers.
    - In docs/phase2 and docs/validation as well: the targets at 3 decimals, the likeliest form
      of a leak in a write-up."""
    everywhere: set[str] = set()
    with RESTRICTED[0].open(encoding="utf-8", newline="") as h:
        everywhere |= {r["D_token"].lstrip("-") for r in csv.DictReader(h)}
    for v in _target_values():
        everywhere |= {f"{abs(v):.5f}".rstrip("0"), f"{abs(v):.4f}"}
    everywhere = {t for t in everywhere if re.fullmatch(r"\d+\.\d+", t) and _significant(t) >= 4}
    docs = {f"{abs(v):.3f}" for v in _target_values()}
    return everywhere, docs


def _scan(names: list[str], tokens: set[str]) -> list[tuple[str, int, str]]:
    pattern = re.compile(r"(?<![\d.])(" + "|".join(re.escape(t) for t in sorted(tokens)) + r")(?!\d|\.\d)")
    hits = []
    for name in names:
        path = ROOT / name
        if not name or not path.is_file() or path.stat().st_size > 2_000_000:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for number, line in enumerate(text.replace("\u2212", "-").splitlines(), start=1):
            hits += [(name, number, m.group(1)) for m in pattern.finditer(line)]
    return hits


def test_no_restricted_value_is_in_a_tracked_file() -> None:
    if not all(p.exists() for p in RESTRICTED):
        pytest.skip("the local restricted files are not present")

    def tracked(*paths: str) -> list[str]:
        out = subprocess.run(["git", "ls-files", "-z", *paths], cwd=ROOT, capture_output=True, check=True)
        return out.stdout.decode().split("\0")

    everywhere, docs = _restricted_tokens()
    hits = _scan(tracked(), everywhere) + _scan(tracked("docs/phase2", "docs/validation"), docs)
    unexpected = [f"{n}:{line}: {t}" for n, line, t in hits if (n, _token_hash(t)) not in COINCIDENCES]
    assert unexpected == []
    for name, _ in COINCIDENCES:
        added = subprocess.run(
            ["git", "log", "--diff-filter=A", "--format=%ad", "--date=short", "--", name],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split()
        assert added and min(added) < FIRST_EXPOSURE, name
