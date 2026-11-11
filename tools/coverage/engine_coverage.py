"""Gate (c), interval coverage, run on the engine (M1 step 5; plan §8 M1, spec.json "coverage").

The frozen protocol lives in ``datasets/biphenyl-synthetic/expected/spec.json``:
- 1000 seeds, ``SeedSequence(19980101, spawn_key=(k,))``;
- the noise is added to the 14 noiseless couplings in CSV row order;
- each parameter gets a 68.3% profile interval at raw Δχ² = 1;
- the acceptance band is 64.5–72.1%.

The reference implementation's coverage is frozen in ``coverage_reference.json``. This script
measures the engine's coverage under the same protocol, seed by seed, so the two can be compared
directly.

    uv run python -I tools/coverage/engine_coverage.py [--seeds N] [--workers W] [--out FILE]

A fit plus three profile intervals takes about 9 s per seed on one core, so the full ensemble
runs in parallel (about 15–25 min on 10 workers). The slow test
``tests/test_m1_acceptance.py::test_gate_c_engine_coverage`` runs it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
EXPECTED = ROOT / "datasets" / "biphenyl-synthetic" / "expected"
PARAMETERS = ("phi_deg", "Szz", "Delta")


def _single_threaded() -> None:
    # One BLAS thread per worker: the pool supplies the parallelism.
    for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
        os.environ[name] = "1"


def _inputs() -> tuple[dict[str, Any], dict[str, Any]]:
    spec = json.loads((EXPECTED / "spec.json").read_text())
    noiseless = json.loads((EXPECTED / "noiseless.json").read_text())
    return spec, noiseless


def provenance() -> dict[str, Any]:
    """What the record depends on: the fitter version and the frozen inputs (round 25). A record
    whose provenance differs from the current one is stale and must be regenerated."""
    from dipolar_core.fit import FIT_VERSION

    names = ("spec.json", "noiseless.json")
    inputs = {name: hashlib.sha256((EXPECTED / name).read_bytes()).hexdigest() for name in names}
    return {"fit_version": FIT_VERSION, "inputs_sha256": inputs}


def seed_result(k: int) -> dict[str, Any]:
    """One seed of the frozen protocol: the fit and the three profile intervals."""
    import numpy as np
    from dipolar_core.biphenyl import PROTON_LABELS, rigid_problem
    from dipolar_core.fit import fit, profile_interval

    spec, nl = _inputs()
    cov = spec["coverage"]
    index = {label: i for i, label in enumerate(PROTON_LABELS)}
    pairs = tuple((index[a], index[b]) for a, b in nl["pairs"])
    y0, sigma = np.array(nl["D_Hz"]), np.array(nl["sigma_Hz"])
    rng = np.random.default_rng(np.random.SeedSequence(19980101, spawn_key=(k,)))
    y = y0 + rng.normal(0.0, 0.5, size=len(y0))
    assert cov["n_seeds"] == 1000 and len(y0) == 14  # the protocol this code implements
    problem = rigid_problem(pairs, y, sigma)
    result = fit(problem)
    estimate = dict(zip(PARAMETERS, map(float, (*result.theta, *result.order)), strict=True))
    out: dict[str, Any] = {"seed": k, "estimate": estimate}
    for name in PARAMETERS:
        interval = profile_interval(problem, result, name, cov_delta(spec))
        out[name] = [interval.lower, interval.upper] if interval.supported else None
    return out


def cov_delta(spec: dict[str, Any]) -> float:
    interval = spec["coverage"]["interval"]
    assert "raw delta chi2 = 1.00" in interval, interval
    return 1.0


def run(n_seeds: int, workers: int) -> dict[str, Any]:
    _single_threaded()
    spec, nl = _inputs()
    truth, band = nl["truth"], spec["coverage"]["acceptance_band"]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        seeds = list(pool.map(seed_result, range(n_seeds), chunksize=4))
    hits = dict.fromkeys(PARAMETERS, 0)
    unsupported = dict.fromkeys(PARAMETERS, 0)
    for s in seeds:
        for name in PARAMETERS:
            if s[name] is None:
                unsupported[name] += 1
            elif s[name][0] <= truth[name] <= s[name][1]:
                hits[name] += 1
    return {
        "description": "coverage achieved by the engine (dipolar-core) under spec.json 'coverage'",
        "provenance": provenance(),
        "n_seeds": n_seeds,
        "hits": hits,
        "coverage": {k: v / n_seeds for k, v in hits.items()},
        "interval_not_supported": unsupported,
        "within_band": {k: band[0] <= v / n_seeds <= band[1] for k, v in hits.items()},
        "seeds": seeds,
    }


def dumps_record(report: dict[str, Any]) -> str:
    """The summary indented, then one compact line per seed (a reviewable, diffable record)."""
    head = json.dumps({k: v for k, v in report.items() if k != "seeds"}, indent=1)
    seeds = ",\n".join(json.dumps(s, separators=(",", ":")) for s in report["seeds"])
    return head[:-2] + ',\n "seeds": [\n' + seeds + "\n ]\n}\n"


def default_workers() -> int:
    return max(1, (os.cpu_count() or 2) - 2)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--seeds", type=int, default=1000)
    parser.add_argument("--workers", type=int, default=default_workers())
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    report = run(args.seeds, args.workers)
    summary = {k: v for k, v in report.items() if k != "seeds"}
    print(json.dumps(summary, indent=2))
    if args.out:
        args.out.write_text(dumps_record(report))
    return 0 if all(report["within_band"].values()) and not any(report["interval_not_supported"].values()) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
