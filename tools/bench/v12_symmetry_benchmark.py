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


IDENTITIES = [
    ("H", None), ("D", None), ("B", None), ("C", None), ("C", 13), ("N", None), ("N", 15), ("O", None),
    ("F", None), ("Si", None), ("P", None), ("S", None), ("Cl", None), ("Br", None), ("I", None),
]  # fmt: skip


def exact_limit(n_atoms: int) -> tuple[np.ndarray, list[str], list[int | None]]:
    """Exactly n_atoms in D6h: generic 24-atom orbits, then 2-atom orbits on the C6 axis (outside
    the generic box) to fill; each orbit cycles through the 15 supported isotope identities."""
    generic = large_d6h(n_atoms)
    orbits = [generic[i : i + 24] for i in range(0, len(generic), 24)]
    z = 25.0
    while sum(len(o) for o in orbits) < n_atoms:
        orbits.append(np.array([[0.0, 0.0, z], [0.0, 0.0, -z]]))
        z += 2.0
    elements: list[str] = []
    masses: list[int | None] = []
    for k, orbit in enumerate(orbits):
        element, mass = IDENTITIES[k % len(IDENTITIES)]
        elements += [element] * len(orbit)
        masses += [mass] * len(orbit)
    return np.vstack(orbits), elements, masses


_RSS_CHILD = """
import resource, sys, numpy as np
sys.path.insert(0, sys.argv[1])
import v12_symmetry_benchmark as b
from dipolar_core import symmetry as sym
def rss():
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return r / 2**20 if sys.platform == "darwin" else r / 2**10
xyz, elements, masses = b.exact_limit(sym.MAX_ATOMS)
decl = sym.Declaration("D6h", np.eye(3))
sym.validate(xyz[:24], elements[:24], masses[:24], decl)  # warm the imports
before = rss()
sym.validate(xyz, elements, masses, decl)
print(before, rss())
"""


def main() -> int:
    xyz, elements, masses = exact_limit(sym.MAX_ATOMS)
    n = len(xyz)
    decl = sym.Declaration("D6h", np.eye(3))
    sym.validate(xyz, elements, masses, decl)  # warm (imports scipy.spatial)
    child = subprocess.run(
        [sys.executable, "-c", _RSS_CHILD, str(Path(__file__).parent)], capture_output=True, text=True, check=True
    )
    before, after = (float(x) for x in child.stdout.split())
    results: dict[str, object] = {
        f"validation_D6h_{n}_atoms_15_identities": measure(lambda: sym.validate(xyz, elements, masses, decl), 5)
        | {
            "peak_mb_note": "tracemalloc peak of Python/numpy allocations during the call",
            "process_rss_mb": {"before": before, "after": after, "increase": after - before},
            "budget": "1 s CPU, 200 MB (1000 atoms, 24 operations)",
        }
    }
    v = sym.validate(xyz, elements, masses, decl)
    protons = [i for i, (e, m) in enumerate(zip(elements, masses, strict=True)) if e == "H" and m is None]
    pairs = [(a, b) for i, a in enumerate(protons) for b in protons[i + 1 :]][:2000]
    per = measure(lambda: [v.pair_orbit(a, b) for a, b in pairs], 5)
    results["pair_orbit_lookup"] = {
        "pairs": len(pairs),
        "cpu_us_per_pair_median": per["cpu_s_median"] / len(pairs) * 1e6,
        "operations": len(v.operations),
        "budget": "O(|G|) per observed pair",
    }
    rng = np.random.default_rng(31)
    c1 = rng.uniform(-60.0, 60.0, size=(201, 3))
    vc1 = sym.validate(c1, ["H"] * 201, [None] * 201, sym.Declaration("C1", np.eye(3)))
    many = [(i, j) for i in range(201) for j in range(i + 1, 201)][:20_000]
    results["fixed_rows_C1_20000_observations"] = measure(lambda: sym.fixed_rows(vc1, many, -120120.0), 3) | {
        "budget": "within the fixed fit's admission budget (2 s, D-11)"
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
