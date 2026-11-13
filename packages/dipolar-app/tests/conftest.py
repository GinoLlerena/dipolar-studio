from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from dipolar_app.client import LocalClient
from dipolar_app.operations import build_registry
from dipolar_app.policy import Principal, Tier
from dipolar_app.registry import CONTRACT_VERSION
from dipolar_app.session import Session

ROOT = Path(__file__).resolve().parents[3]
EXPECTED = ROOT / "datasets" / "biphenyl-synthetic" / "expected"

USER = Principal(actor="user", tier=Tier.APPLY, human=True)
ROBOT = Principal(actor="script:robot", tier=Tier.APPLY, human=False)
VIEWER = Principal(actor="script:viewer", tier=Tier.READ, human=False)
AGENT = Principal(actor="agent:test", tier=Tier.PROPOSE, human=False)


def expected(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((EXPECTED / name).read_text(encoding="utf-8"))
    return data


def new_session(journal_dir: Path | None = None) -> Session:
    """A session with a thread-mode job runner (its workers start with the first job)."""
    from dipolar_app.jobs import JobRunner
    from dipolar_app.journal import Journal

    journal = Journal(journal_dir / "project.events.jsonl") if journal_dir else None
    session = Session(journal, contract_version=CONTRACT_VERSION)
    JobRunner(session, mode="thread")
    return session


def run_fit(c: LocalClient, args: dict[str, Any] | None = None) -> dict[str, Any]:
    """Submit ``fit.run`` at the current revision, wait for the job, and return an envelope like
    the old synchronous ``fit.run``: the run's result, or the submission's or the job's error."""
    revision = c.call("render.describe_view")["revisions"]["science"]
    submitted = c.call("fit.run", {**(args or {}), "expected_science_revision": revision})
    if not submitted["ok"]:
        return submitted
    job_id = submitted["result"]["job"]["id"]
    while True:
        waited = c.call("job.wait", {"job_id": job_id, "timeout_s": 30})
        assert waited["ok"], waited
        if waited["result"]["finished"]:
            break
    job = waited["result"]["job"]
    if job["status"] != "succeeded":
        return {"ok": False, "operation": "fit.run", "error": {**job["error"], "offending_field": None}}
    run = c.call("run.get", {"run_id": job["run_id"]})
    assert run["ok"], run
    return {"ok": True, "operation": "fit.run", "result": run["result"]["result"]}


def client(session: Session, principal: Principal = USER) -> LocalClient:
    return LocalClient(build_registry(), session, principal)


@dataclass
class Response:
    status: int
    headers: dict[str, str]
    body: bytes

    def json(self) -> Any:
        return json.loads(self.body)


@dataclass
class Server:
    base_url: str
    port: int
    tokens: dict[str, str]
    ready_file: Path
    project_dir: Path
    stdout_path: Path
    process: subprocess.Popen[bytes]

    def request(
        self,
        method: str,
        path: str,
        body: bytes | None = None,
        *,
        token: str | None = "user",
        headers: dict[str, str] | None = None,
    ) -> Response:
        req = urllib.request.Request(self.base_url + path, data=body, method=method)
        if token is not None:
            req.add_header("Authorization", f"Bearer {self.tokens.get(token, token)}")
        for key, value in (headers or {}).items():
            req.add_header(key, value)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return Response(resp.status, {k.lower(): v for k, v in resp.headers.items()}, resp.read())
        except urllib.error.HTTPError as exc:
            return Response(exc.code, {k.lower(): v for k, v in exc.headers.items()}, exc.read())

    def call(self, name: str, args: dict[str, Any] | None = None, *, token: str = "user") -> dict[str, Any]:
        body = json.dumps({"args": args or {}}).encode()
        resp = self.request(
            "POST", f"/api/v1/ops/{name}", body, token=token, headers={"Content-Type": "application/json"}
        )
        data: dict[str, Any] = resp.json()
        return data


def start_server(tmp: Path, static_dir: Path | None = None) -> Server:
    project_dir = tmp / "project"
    ready = tmp / "serve.ready.json"
    stdout_path = tmp / "server.out"
    cmd = [sys.executable, "-m", "dipolar_app.cli", "serve", "--project-dir", str(project_dir)]
    cmd += ["--ready-file", str(ready)]
    # A server stopped by a hard kill (terminate() on Windows) leaves its ready file behind; wait for
    # this server's, never an earlier one's.
    ready.unlink(missing_ok=True)
    if static_dir is not None:
        cmd += ["--static-dir", str(static_dir)]
    with stdout_path.open("wb") as out:
        process = subprocess.Popen(cmd, stdout=out, stderr=subprocess.STDOUT)
    deadline = time.monotonic() + 20
    while not ready.exists():
        if process.poll() is not None or time.monotonic() > deadline:
            process.kill()
            raise RuntimeError(f"server did not start: {stdout_path.read_text(encoding='utf-8')}")
        time.sleep(0.05)
    info = json.loads(ready.read_text(encoding="utf-8"))
    port = int(info["base_url"].rsplit(":", 1)[1])
    return Server(info["base_url"], port, info["tokens"], ready, project_dir, stdout_path, process)


def stop_server(server: Server) -> None:
    server.process.terminate()
    try:
        server.process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        server.process.kill()
        server.process.wait()


@pytest.fixture
def server(tmp_path: Path) -> Iterator[Server]:
    srv = start_server(tmp_path)
    try:
        yield srv
    finally:
        stop_server(srv)


@pytest.fixture
def clean_env() -> dict[str, str]:
    """Environment for the robot: no virtualenv or PYTHONPATH leaking into the clean process."""
    return {k: v for k, v in os.environ.items() if not k.startswith(("PYTHON", "VIRTUAL_ENV", "UV_"))}
