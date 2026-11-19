"""Measure the V1.1 budgets (docs/phase2/v1.0-design.md, D-11) on this machine.

    uv run python tools/bench/v11_fixed_benchmark.py   # writes docs/validation/data/v11-fixed-benchmark.json

Times are CPU seconds (time.process_time), the median of repeats; memory is the tracemalloc peak
during the call, excluding inputs allocated before it (numpy reports its allocations).
"""

from __future__ import annotations

import json
import math
import platform
import statistics
import subprocess
import sys
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


_RSS_CHILD = """
import resource, sys, numpy as np
from dipolar_core import fixed
def rss():
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return r / 2**20 if sys.platform == "darwin" else r / 2**10  # bytes on macOS, KiB on Linux
rng = np.random.default_rng(1)
fixed.fit_fixed(rng.normal(size=(8, 5)), rng.normal(size=8), np.ones(8), covariance=np.eye(8))  # warm
n = fixed.MAX_COVARIANCE_N
cov = np.full((n, n), 0.0)  # written, so resident: np.diag's calloc pages are not (round 72)
cov[np.diag_indices(n)] = rng.uniform(0.5, 1.5, n); cov[0, 1] = cov[1, 0] = 0.1
a = rng.normal(size=(n, 5)); y = rng.normal(size=n); sigma = np.sqrt(np.diag(cov))
before = rss()
fixed.fit_fixed(a, y, sigma, covariance=cov)
print(before, rss())
"""


def process_peak_rss() -> dict[str, float]:
    """The process's peak resident memory around a dense N = 2000 covariance fit, in a fresh
    process warmed with a small covariance fit, with the caller's matrix already allocated."""
    out = subprocess.run([sys.executable, "-c", _RSS_CHILD], capture_output=True, text=True, check=True)
    before, after = (float(v) for v in out.stdout.split())
    return {"peak_rss_before_mb": before, "peak_rss_after_mb": after, "increase_mb": after - before}


def cpu_name() -> str:
    try:
        return subprocess.run(
            ["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True
        ).stdout.strip()
    except OSError:
        return platform.processor()


def tied_case() -> tuple[np.ndarray, np.ndarray]:
    n = np.diag([1.0, -2.0, 1.0]) / math.sqrt(6.0)
    s0 = np.diag([-0.51, -0.51, 1.02])
    s0 = s0 - float(np.sum(s0 * n)) * n
    return fixed.b_from_matrix(s0), fixed.b_from_matrix(n)[:, None]


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
        "budget": "128 MB peak including the caller's 32 MB covariance; i.e. 96 MB beyond it",
        "process": process_peak_rss(),
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
        "boundary_m4": (fixed.b_from_s5(np.array([-0.5, 0, 0, 0, 0])), fixed.SUBSPACES["C1"][:, 1:]),
        "tied_eigenvectors_m1": tied_case(),
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
