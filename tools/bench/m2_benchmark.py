"""The M2 benchmark (plan §8 "Performance is a hypothesis", M2 exit criterion; 04 §8.6).

The plan asks M2 to record the following on named hardware:
- cold and warm timings;
- the kernel alone (dipolar_core) against the whole path (HTTP, registry, session, journal, job);
- one core against the default threads;
- peak RSS and output sizes;
- numerical agreement, with the legacy comparison stated honestly.

The §7 perception check ("the browser shows a highlight within 200 ms") is measured here on the
server side: a ``view.highlight`` followed by ``render.describe_view`` and ``render.view_svg``.
The browser half arrives with M3.

    uv run python tools/bench/m2_benchmark.py [--out docs/validation/data/m2-benchmark.json]

Every figure is a measurement on the machine that ran it, never an estimate. The record names
that machine.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
EXPECTED = ROOT / "datasets" / "biphenyl-synthetic" / "expected"
SINGLE = {
    name: "1" for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS")
}


def _cpu() -> str:
    if sys.platform == "darwin":
        return subprocess.run(
            ["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True
        ).stdout.strip()
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "unknown"


def _memory_bytes() -> int | None:
    if sys.platform == "darwin":
        out = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True).stdout.strip()
        return int(out) if out.isdigit() else None
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (ValueError, OSError):
        return None


def hardware() -> dict[str, Any]:
    import numpy
    import scipy

    commit = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True
    ).stdout.strip()
    return {
        "cpu": _cpu(),
        "logical_cores": os.cpu_count(),
        "memory_bytes": _memory_bytes(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "numpy": numpy.__version__,
        "scipy": scipy.__version__,
        "commit": commit,
    }


def _stats(seconds: list[float]) -> dict[str, float]:
    ms = sorted(1000.0 * s for s in seconds)
    p95 = ms[min(len(ms) - 1, round(0.95 * (len(ms) - 1)))]
    return {"n": len(ms), "median_ms": statistics.median(ms), "p95_ms": p95, "min_ms": ms[0], "max_ms": ms[-1]}


# --------------------------------------------------------------------------- the kernel, in a fresh process
KERNEL = r"""
import json, resource, sys, time
t0 = time.perf_counter()
import numpy as np
from dipolar_app.project import load_example
from dipolar_app.science import problem_for
from dipolar_core.fit import fit
t_import = time.perf_counter() - t0
problem = problem_for(load_example("biphenyl-synthetic"))
t1 = time.perf_counter(); first = fit(problem); t_first = time.perf_counter() - t1
warm = []
for _ in range(5):
    t = time.perf_counter(); fit(problem); warm.append(time.perf_counter() - t)
theta = np.array([36.98502906633521])
preview = []
for _ in range(300):
    t = time.perf_counter(); problem.profile_residual(theta); preview.append(time.perf_counter() - t)
rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
print(json.dumps({"import_s": t_import, "first_fit_s": t_first, "warm_fit_s": warm, "preview_s": preview,
                  "maxrss_raw": rss, "phi": float(first.theta[0]), "order": [float(x) for x in first.order],
                  "chi2": float(first.chi2)}))
"""


def kernel(single_core: bool) -> dict[str, Any]:
    env = {**os.environ, **(SINGLE if single_core else {})}
    out = subprocess.run([sys.executable, "-c", KERNEL], capture_output=True, text=True, env=env, check=True, cwd=ROOT)
    data = json.loads(out.stdout)
    scale = 1 if sys.platform == "darwin" else 1024  # ru_maxrss: bytes on macOS, KiB on Linux
    return {
        "threads": "1 (OMP/BLAS pinned)" if single_core else "default",
        "cold_import_ms": 1000 * data["import_s"],
        "cold_first_fit_ms": 1000 * data["first_fit_s"],
        "warm_fit": _stats(data["warm_fit_s"]),
        "preview_kernel": _stats(data["preview_s"]),
        "peak_rss_bytes": data["maxrss_raw"] * scale,
        "result": {"phi_deg": data["phi"], "order": data["order"], "chi2": data["chi2"]},
    }


# --------------------------------------------------------------------------- end to end, over HTTP
def _call(base: str, token: str, name: str, args: dict[str, Any]) -> tuple[dict[str, Any], float]:
    body = json.dumps({"args": args}).encode()
    request = urllib.request.Request(f"{base}/api/v1/ops/{name}", data=body, method="POST")
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Content-Type", "application/json")
    t = time.perf_counter()
    with urllib.request.urlopen(request, timeout=120) as response:
        payload = json.loads(response.read())
    return payload, time.perf_counter() - t


def _rss_bytes(pid: int) -> int | None:
    out = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
    return int(out) * 1024 if out.isdigit() else None


def end_to_end() -> dict[str, Any]:
    tmp = Path(tempfile.mkdtemp(prefix="dipolar-bench-"))
    ready = tmp / "serve.ready.json"
    start = time.perf_counter()
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "dipolar_app.cli",
            "serve",
            "--project-dir",
            str(tmp / "project"),
            "--ready-file",
            str(ready),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        while not ready.exists():
            if proc.poll() is not None or time.perf_counter() - start > 30:
                raise RuntimeError("dipolar serve did not start")
            time.sleep(0.02)
        startup = time.perf_counter() - start
        info = json.loads(ready.read_text())
        base, token = info["base_url"], info["tokens"]["user"]

        def call(name: str, args: dict[str, Any] | None = None) -> tuple[dict[str, Any], float]:
            env, dt = _call(base, token, name, args or {})
            assert env["ok"], env
            return env["result"], dt

        call("project.open_example", {"name": "biphenyl-synthetic", "expected_science_revision": 0})
        _, first_preview = call("fit.preview", {"phi": {"value": 36.98502906633521, "unit": "deg"}})
        preview = [call("fit.preview", {"phi": {"value": 30.0 + (k % 20), "unit": "deg"}})[1] for k in range(200)]

        def job(intervals: bool) -> tuple[float, dict[str, Any]]:
            t = time.perf_counter()
            submitted, _ = call("fit.run", {"intervals": intervals, "expected_science_revision": 1})
            while True:
                waited, _ = call("job.wait", {"job_id": submitted["job"]["id"], "timeout_s": 30})
                if waited["finished"]:
                    break
            elapsed = time.perf_counter() - t
            assert waited["job"]["status"] == "succeeded", waited
            return elapsed, waited["job"]

        fits = [job(False) for _ in range(3)]
        interval_time, interval_job = job(True)
        run, _ = call("run.get", {"run_id": interval_job["run_id"]})

        perception = []
        ids = [c["id"] for c in run["result"]["couplings"]]
        for k in range(50):
            t = time.perf_counter()
            call("view.highlight", {"ids": [ids[k % len(ids)]]})
            view, _ = call("render.describe_view")
            assert view["highlights"][0]["id"] == ids[k % len(ids)]
            perception.append(time.perf_counter() - t)
        svg_times = []
        svg = ""
        for _ in range(50):
            result, dt = call("render.view_svg")
            svg = result["svg"]
            svg_times.append(dt)
        exported, _ = call("project.export")
        blob = next((tmp / "project" / "runs").glob(f"{run['run']['result_sha256']}.json"))
        return {
            "server_start_ms": 1000 * startup,
            "first_preview_ms": 1000 * first_preview,
            "preview_http": _stats(preview),
            "fit_job_end_to_end": _stats([t for t, _ in fits]),
            "fit_job_with_intervals_ms": 1000 * interval_time,
            "highlight_then_describe_view": _stats(perception),
            "render_view_svg": _stats(svg_times),
            "server_rss_after_bytes": _rss_bytes(proc.pid),
            "sizes_bytes": {
                "run_result_blob": blob.stat().st_size,
                "svg": len(svg.encode()),
                "project_export": len(exported["text"].encode()),
                "journal": (tmp / "project" / "project.events.jsonl").stat().st_size,
            },
            "fit_with_intervals": run["result"],
        }
    finally:
        proc.terminate()
        proc.wait(10)


def agreement(fit_result: dict[str, Any]) -> dict[str, Any]:
    e = json.loads((EXPECTED / "noisy_fixture.json").read_text())["expected"]
    tol = json.loads((EXPECTED / "spec.json").read_text())["tolerances"]["regression"]
    theta = {x["name"]: x["value"] for x in fit_result["theta"]}
    order = {x["name"]: x["value"] for x in fit_result["order"]}
    return {
        "against": "the frozen fixture from the independent reference implementation (tools/reference)",
        "phi_deg_abs_diff": abs(theta["phi_deg"] - e["phi_deg"]),
        "Szz_abs_diff": abs(order["Szz"] - e["Szz"]),
        "Delta_abs_diff": abs(order["Delta"] - e["Delta"]),
        "chi2_rel_diff": abs(fit_result["chi2"] - e["objective"]) / e["objective"],
        "tolerances": {k: tol[k] for k in ("phi_atol_deg", "S_atol", "objective_rtol")},
        "legacy": (
            "The 1998 fit pipeline (MFC) is not compiled, so its acceptance rate is not measurable here; its "
            "grid search accepts nearly every point (bug report B08). The 1998 solver routines are compiled by "
            "tools/legacy-harness (CI job 'Legacy goldens'): 2 of 7 frozen cases are right there, and the new "
            "engine's linear algebra (NumPy/SciPy) gets all 7. The fit semantics differ (D3: a bounded, refined "
            "optimum with known-σ weighting), so legacy numbers are not a target."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    e2e = end_to_end()
    record = {
        "description": "M2 benchmark (plan §8): timings, memory and sizes on the named hardware below",
        "hardware": hardware(),
        "kernel": {"default_threads": kernel(False), "single_core": kernel(True)},
        "end_to_end_http": {k: v for k, v in e2e.items() if k != "fit_with_intervals"},
        "agreement": agreement(e2e["fit_with_intervals"]),
        "perception_target": (
            "04 §8.6: 'within 200 ms' on named hardware; the server half is highlight_then_describe_view"
        ),
    }
    text = json.dumps(record, indent=1) + "\n"
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
