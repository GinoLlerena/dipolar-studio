"""The scripted robot user (04 §7, §8.6): a non-LLM client that drives the app over HTTP only.

It uses the Python standard library alone, so it runs in a clean process with no frontend,
browser or dipolar packages (CI runs it with ``python -I``). M0 scenario:

1. read the ready file (port and the robot's credential), check that the instance answering on the
   port is the one the ready file names (a stale file or a reused port fails here), then check the
   registry;
2. ``project.open_example`` at the science revision read from ``render.describe_view``;
3. ``fit.preview`` at the requested φ;
4. ``view.select`` the coupling with the largest |normalized residual|;
5. ``render.describe_view`` and check that the selection is visible there.

Prints one JSON report on stdout and exits 0 on success, 1 on any failed step.

    python -I tools/robot/robot.py --ready-file DIR/serve.ready.json --phi 36.98502906633521
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


class RobotError(Exception):
    pass


class Client:
    def __init__(self, base_url: str, token: str) -> None:
        self.base_url = base_url
        self.token = token

    def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        data = None if body is None else json.dumps(body, allow_nan=False).encode()
        request = urllib.request.Request(self.base_url + path, data=data, method=method)
        request.add_header("Authorization", f"Bearer {self.token}")
        if data is not None:
            request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload: Any = json.loads(response.read())
        except urllib.error.HTTPError as exc:
            payload = json.loads(exc.read())
        if not isinstance(payload, dict):
            raise RobotError(f"{path} did not return a JSON object")
        return payload

    def instance(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/instance")

    def registry(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/registry")

    def call(self, name: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
        envelope = self._request("POST", f"/api/v1/ops/{name}", {"args": args or {}})
        if not envelope.get("ok"):
            raise RobotError(f"{name} failed: {envelope.get('error')}")
        result: dict[str, Any] = envelope["result"]
        return result


def run(ready_file: Path, phi_deg: float) -> dict[str, Any]:
    ready = json.loads(ready_file.read_text("utf-8"))
    client = Client(ready["base_url"], ready["tokens"]["robot"])

    try:
        answered = client.instance().get("instance_id")
    except (RobotError, OSError, ValueError):
        answered = None
    if answered != ready["instance_id"]:
        raise RobotError("the ready file does not describe the server on its port (stopped, or the port was reused)")

    names = [op["name"] for op in client.registry()["operations"]]
    missing = {"project.open_example", "fit.preview", "view.select", "render.describe_view"} - set(names)
    if missing:
        raise RobotError(f"registry lacks {sorted(missing)}")

    view = client.call("render.describe_view")
    opened = client.call(
        "project.open_example",
        {"name": "biphenyl-synthetic", "expected_science_revision": view["science_revision"]},
    )
    preview = client.call("fit.preview", {"phi": {"value": phi_deg, "unit": "deg"}})
    if preview["science_revision"] != opened["science_revision"]:
        raise RobotError("the preview does not reflect the project the robot opened")

    worst = max(preview["couplings"], key=lambda c: abs(c["normalized_residual"]))
    selected = client.call("view.select", {"ids": [worst["id"]]})
    view = client.call("render.describe_view")
    if [s["id"] for s in view["selection"]] != [worst["id"]]:
        raise RobotError("the selection is not visible in render.describe_view")

    return {
        "ok": True,
        "contract_version": ready["contract_version"],
        "opened": opened,
        "preview": preview,
        "worst_coupling": {
            "id": worst["id"],
            "label": worst["label"],
            "normalized_residual": worst["normalized_residual"],
        },
        "select": selected,
        "view": view,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ready-file", type=Path, required=True)
    parser.add_argument("--phi", type=float, default=37.0, help="torsion for fit.preview, degrees")
    ns = parser.parse_args()
    try:
        report = run(ns.ready_file, ns.phi)
    except (RobotError, OSError, KeyError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
