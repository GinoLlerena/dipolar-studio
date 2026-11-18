"""Measure the V1.1 budgets (docs/phase2/v1.0-design.md, D-11) on this machine.

    uv run python tools/bench/v11_fixed_benchmark.py   # writes docs/validation/data/v11-fixed-benchmark.json

Times are CPU seconds (time.process_time), the median of repeats; memory is the tracemalloc peak
during the call, excluding inputs allocated before it (numpy reports its allocations).
"""

from __future__ import annotations

import json
import platform
import statistics
import subprocess
import time
import tracemalloc
from collections.abc import Callable
from pathlib import Path

import numpy as np
from dipolar_core import fixed

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "validation" / "data" / "v11-fixed-benchmark.json"


def measure(fn: Callable[[], object], repeats: int) -> dict[str, float]:
    times = []
    for _ in range(repeats):
        start = time.process_time()
        fn()
        times.append(time.process_time() - start)
    tracemalloc.start()
    fn()
    peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    return {"cpu_s_median": statistics.median(times), "cpu_s_max": max(times), "peak_mb": peak / 2**20}


def cpu_name() -> str:
    try:
        return subprocess.run(
            ["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True
        ).stdout.strip()
    except OSError:
        return platform.processor()


def main() -> int:
    rng = np.random.default_rng(1)
    results: dict[str, object] = {}

    n = fixed.MAX_COVARIANCE_N
    a = rng.normal(size=(n, 5))
    cov = np.diag(rng.uniform(0.5, 1.5, n))
    cov[0, 1] = cov[1, 0] = 0.1
    y = rng.normal(size=n)
    sigma = np.sqrt(np.diag(cov))
    results["covariance_fit_N2000"] = measure(lambda: fixed.fit_fixed(a, y, sigma, covariance=cov), 3) | {
        "budget": "128 MB peak including the caller's 32 MB covariance; i.e. 96 MB beyond it"
    }

    n2 = 20_000
    a2 = rng.normal(size=(n2, 5))
    y2 = rng.normal(size=n2)
    s2 = np.full(n2, 0.5)
    results["diagonal_fit_N20000"] = measure(lambda: fixed.fit_fixed(a2, y2, s2), 5) | {"budget": "2 s, 100 MB"}

    cases = {
        "feasible_at_fitted_point": (fixed.b_from_s5(np.array([-0.3, 0, 0, 0, 0])), fixed.SUBSPACES["C1"][:, 1:]),
        "feasible_away_from_fitted_point": (
            fixed.b_from_matrix(np.diag([-0.6, 0.6, 0.0])),
            fixed.SUBSPACES["C1"][:, :1],
        ),
        "infeasible_m4": (fixed.b_from_s5(np.array([-0.9, 0, 0, 0, 0])), fixed.SUBSPACES["C1"][:, 1:]),
    }
    for name, (b0, nulls) in cases.items():

        def certify(b0: np.ndarray = b0, nulls: np.ndarray = nulls) -> object:
            return fixed.admissibility(b0, nulls)

        results[f"certificate_{name}"] = measure(certify, 5) | {
            "status": fixed.admissibility(b0, nulls).status,
            "budget": "0.1 s (the max includes the first call's one-off import of scipy.optimize)",
        }

    record = {
        "fixed_fit_version": fixed.FIXED_FIT_VERSION,
        "hardware": {"cpu": cpu_name(), "machine": platform.machine(), "python": platform.python_version()},
        "numpy": np.__version__,
        "results": results,
    }
    OUT.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
