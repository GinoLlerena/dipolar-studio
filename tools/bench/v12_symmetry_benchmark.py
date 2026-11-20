"""Measure the V1.2 budgets (docs/phase2/v1.0-design.md, D-11) on this machine.

    uv run python tools/bench/v12_symmetry_benchmark.py   # writes docs/validation/data/v12-symmetry-benchmark.json

Symmetry validation: at most 1000 atoms and 24 operations, budget 1 s CPU and 200 MB. Orbits:
O(|G|) per observed pair. Times are CPU seconds (time.process_time), the median of repeats; memory
is the tracemalloc peak during the call.
"""

from __future__ import annotations

import json
import platform
import statistics
import subprocess
import sys
import time
import tracemalloc
from collections.abc import Callable
from pathlib import Path

import numpy as np
from dipolar_core import symmetry as sym

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "validation" / "data" / "v12-symmetry-benchmark.json"


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


def large_d6h(n_max: int) -> np.ndarray:
    """Generic 24-atom orbits of D6h, at least 1 Å apart, up to n_max atoms."""
    ops = sym.operations("D6h")
    rng = np.random.default_rng(12)
    points: list[np.ndarray] = []
    while len(points) + len(ops) <= n_max:
        p = rng.uniform(-20.0, 20.0, size=3)
        images = np.array([g @ p for g in ops])
        gaps = np.linalg.norm(images[:, None] - images[None], axis=-1)[np.triu_indices(len(ops), 1)]
        if gaps.min() < 1.0:
            continue
        if points and np.min(np.linalg.norm(np.array(points)[:, None] - images[None], axis=-1)) < 1.0:
            continue
        points.extend(images)
    return np.array(points)


def cpu_name() -> str:
    try:
        return subprocess.run(
            ["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True
        ).stdout.strip()
    except OSError:
        return platform.processor()


def main() -> int:
    xyz = large_d6h(sym.MAX_ATOMS)
    n = len(xyz)
    elements, masses = ["H"] * n, [None] * n
    decl = sym.Declaration("D6h", np.eye(3))
    sym.validate(xyz, elements, masses, decl)  # warm (imports scipy.spatial)
    results: dict[str, object] = {
        f"validation_D6h_{n}_atoms": measure(lambda: sym.validate(xyz, elements, masses, decl), 5)
        | {"budget": "1 s CPU, 200 MB (1000 atoms, 24 operations)"}
    }
    v = sym.validate(xyz, elements, masses, decl)
    pairs = [(i, j) for i in range(0, n, 7) for j in range(i + 1, n, 97)][:2000]
    per = measure(lambda: [v.pair_orbit(a, b) for a, b in pairs], 5)
    results["pair_orbit_lookup"] = {
        "pairs": len(pairs),
        "cpu_us_per_pair_median": per["cpu_s_median"] / len(pairs) * 1e6,
        "operations": len(v.operations),
        "budget": "O(|G|) per observed pair",
    }
    record = {
        "hardware": {"cpu": cpu_name(), "machine": platform.machine(), "python": platform.python_version()},
        "numpy": np.__version__,
        "results": results,
    }
    OUT.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
