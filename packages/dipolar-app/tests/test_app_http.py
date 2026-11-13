"""HTTP adapter, localhost controls, contract parity and the robot (04 §7, §8.5, §8.6; plan D10).

Every test talks to a real ``dipolar serve`` subprocess on a loopback, OS-assigned port.
"""

from __future__ import annotations

import ast
import json
import os
import socket
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from conftest import ROBOT, ROOT, Server, client, expected, new_session, start_server, stop_server

ROBOT_SCRIPT = ROOT / "tools" / "robot" / "robot.py"
JSON = {"Content-Type": "application/json"}


def post(server: Server, name: str, payload: Any, **kw: Any) -> Any:
    headers = {**JSON, **kw.pop("headers", {})}
    return server.request("POST", f"/api/v1/ops/{name}", json.dumps(payload).encode(), headers=headers, **kw)


# --------------------------------------------------------------------------- launch
def test_ready_file_is_private_and_secrets_stay_out_of_output(server: Server) -> None:
    if os.name == "posix":  # Windows has no POSIX mode bits
        assert stat.S_IMODE(server.ready_file.stat().st_mode) == 0o600
    assert server.base_url.startswith("http://127.0.0.1:")
    output = server.stdout_path.read_text()
    assert "127.0.0.1" in output
    for token in server.tokens.values():
        assert token not in output
    stop_server(server)
    if os.name == "posix":  # terminate() is a hard kill on Windows: no graceful clean-up to observe
        assert not server.ready_file.exists()  # removed on shutdown


# --------------------------------------------------------------------------- request checks
def test_host_and_origin_allow_lists(server: Server) -> None:
    ok = post(server, "render.describe_view", {"args": {}})
    assert ok.status == 200
    rebound = post(server, "render.describe_view", {"args": {}}, headers={"Host": f"evil.example:{server.port}"})
    assert rebound.status == 421  # DNS rebinding: a foreign Host never reaches the app
    foreign = post(server, "render.describe_view", {"args": {}}, headers={"Origin": "http://evil.example"})
    assert foreign.status == 403
    same = post(server, "render.describe_view", {"args": {}}, headers={"Origin": f"http://localhost:{server.port}"})
    assert same.status == 200


def test_authentication_and_csrf_shape(server: Server) -> None:
    assert post(server, "render.describe_view", {"args": {}}, token=None).json()["error"]["code"] == "UNAUTHENTICATED"
    wrong = post(server, "render.describe_view", {"args": {}}, token="not-a-token")
    assert (wrong.status, wrong.json()["error"]["code"]) == (401, "UNAUTHENTICATED")
    form = server.request(
        "POST",
        "/api/v1/ops/render.describe_view",
        b"args=1",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert (form.status, form.json()["error"]["code"]) == (400, "INVALID_ARGUMENT")
    assert server.request("GET", "/api/v1/ops/render.describe_view").status == 405  # GET has no side effects
    assert server.request("GET", "/api/v1/registry", token=None).status == 401


def test_identity_comes_from_the_credential_only(server: Server) -> None:
    server.call("project.open_example", {"name": "biphenyl-synthetic", "expected_science_revision": 0})
    smuggled = post(server, "view.select", {"args": {"ids": ["cpl_000001"]}, "actor": "user"}, token="viewer")
    assert (smuggled.status, smuggled.json()["error"]["offending_field"]) == (400, "actor")
    assert "actor" in smuggled.json()["error"]["message"]
    in_args = post(server, "view.select", {"args": {"ids": ["cpl_000001"], "tier": "apply"}}, token="viewer")
    assert in_args.status == 403  # policy runs before argument parsing; a "tier" argument changes nothing
    denied = post(server, "view.select", {"args": {"ids": ["cpl_000001"]}}, token="viewer")
    assert (denied.status, denied.json()["error"]["code"]) == (403, "CAPABILITY_DENIED")
    assert server.call("render.describe_view", token="viewer")["result"]["selection"] == []


def test_body_limit_and_bad_json(server: Server) -> None:
    # The server rejects on the declared length before reading the body, so send headers only (a
    # client still streaming a large body would see the connection close: that is the point).
    with socket.create_connection(("127.0.0.1", server.port), timeout=10) as sock:
        sock.sendall(
            (
                "POST /api/v1/ops/fit.preview HTTP/1.1\r\n"
                f"Host: 127.0.0.1:{server.port}\r\n"
                f"Authorization: Bearer {server.tokens['user']}\r\n"
                "Content-Type: application/json\r\n"
                f"Content-Length: {(1 << 20) + 1}\r\n"
                "Connection: close\r\n\r\n"
            ).encode()
        )
        reply = b""
        while chunk := sock.recv(65536):
            reply += chunk
    assert reply.startswith(b"HTTP/1.1 413")
    assert b"PAYLOAD_TOO_LARGE" in reply
    bad = server.request("POST", "/api/v1/ops/fit.preview", b"{not json", headers=JSON)
    assert (bad.status, bad.json()["error"]["code"]) == (400, "INVALID_ARGUMENT")


@pytest.mark.parametrize(
    ("body", "reason"),
    [
        (b'{"args": {"phi": {"value": NaN, "unit": "deg"}}}', "NaN is not JSON"),
        (b'{"args": {"phi": {"value": -Infinity, "unit": "deg"}}}', "-Infinity is not JSON"),
        (b'{"args": {"phi": {"value": 37, "unit": "deg"}}, "args": {}}', "duplicate key 'args'"),
        ('{"args": {}}'.encode("utf-16"), "not UTF-8"),
        (b'{"args": {}, "\\ud800": 1}', "not valid Unicode"),
        (b'{"args": {"phi": {"value": 37, "unit": "\\udfff"}}}', "not valid Unicode"),
        (b"[" * 10000 + b"]" * 10000, "nested deeper"),
        (b'{"args": ' + b"[" * 70 + b"]" * 70 + b"}", "nested deeper"),
    ],
)
def test_http_json_is_strict(server: Server, body: bytes, reason: str) -> None:
    """Spike 2: RFC 8259 only. Non-standard tokens, duplicate keys and non-UTF-8 bodies are refused."""
    resp = server.request("POST", "/api/v1/ops/fit.preview", body, headers=JSON)
    assert (resp.status, resp.json()["error"]["code"]) == (400, "INVALID_ARGUMENT")
    assert reason in resp.json()["error"]["message"]


def test_http_overflowing_number_is_not_infinity(server: Server) -> None:
    server.call("project.open_example", {"name": "biphenyl-synthetic", "expected_science_revision": 0})
    body = b'{"args": {"phi": {"value": 1e400, "unit": "deg"}}}'
    resp = server.request("POST", "/api/v1/ops/fit.preview", body, headers=JSON)
    assert (resp.status, resp.json()["error"]["code"]) == (400, "INVALID_ARGUMENT")
    assert "finite" in resp.json()["error"]["message"]


def test_error_status_mapping(server: Server) -> None:
    assert post(server, "fit.preview", {"args": {"phi": {"value": 1, "unit": "deg"}}}).status == 409  # NO_PROJECT
    assert post(server, "nope.op", {"args": {}}).status == 404
    server.call("project.open_example", {"name": "biphenyl-synthetic", "expected_science_revision": 0})
    stale = {"args": {"name": "biphenyl-synthetic", "expected_science_revision": 0}}
    conflict = post(server, "project.open_example", stale)
    assert (conflict.status, conflict.json()["error"]["code"]) == (409, "REVISION_CONFLICT")


def test_security_headers_and_static_page(tmp_path: Path) -> None:
    static = tmp_path / "dist"
    static.mkdir()
    (static / "index.html").write_text("<!doctype html><title>t</title>")
    srv = start_server(tmp_path, static_dir=static)
    try:
        page = srv.request("GET", "/", token=None)
        assert page.status == 200 and b"<title>t</title>" in page.body
        assert "script-src 'self'" in page.headers["content-security-policy"]
        assert page.headers["x-content-type-options"] == "nosniff"
        api = post(srv, "render.describe_view", {"args": {}})
        assert api.headers["cache-control"] == "no-store"
        assert srv.request("GET", "/", token=None, headers={"Host": "evil.example"}).status == 421
    finally:
        stop_server(srv)


# --------------------------------------------------------------------------- contract parity
SEQUENCE: list[tuple[str, dict[str, Any]]] = [
    ("render.describe_view", {}),
    ("fit.preview", {"phi": {"value": 37.0, "unit": "deg"}}),
    ("project.open_example", {"name": "biphenyl-synthetic", "expected_science_revision": 0}),
    ("project.describe", {}),
    ("fit.preview", {"phi": {"value": 36.98502906633521, "unit": "deg"}}),
    ("fit.preview", {"phi": {"value": 37.0, "unit": "rad"}}),
    ("view.select", {"ids": ["cpl_000010", "spn_000001"]}),
    ("view.select", {"ids": ["cpl_000999"]}),
    ("project.open_example", {"name": "biphenyl-synthetic", "expected_science_revision": 0}),
    ("render.describe_view", {}),
]


def test_python_and_http_adapters_return_identical_envelopes(server: Server) -> None:
    py = client(new_session(), ROBOT)
    for name, args in SEQUENCE:
        assert server.call(name, args, token="robot") == py.call(name, args), name


def test_http_registry_equals_snapshot(server: Server) -> None:
    from dipolar_app.operations import build_registry

    resp = server.request("GET", "/api/v1/registry")
    assert resp.status == 200
    assert resp.json() == json.loads(json.dumps(build_registry().snapshot()))


# --------------------------------------------------------------------------- the robot
def test_robot_is_standard_library_only() -> None:
    tree = ast.parse(ROBOT_SCRIPT.read_text())
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    assert roots - {"__future__"} <= set(sys.stdlib_module_names), roots


def test_robot_completes_the_slice_in_a_clean_process(server: Server, clean_env: dict[str, str]) -> None:
    e = expected("noisy_fixture.json")["expected"]
    tol = expected("spec.json")["tolerances"]["regression"]
    proc = subprocess.run(
        [sys.executable, "-I", str(ROBOT_SCRIPT), "--ready-file", str(server.ready_file), "--phi", repr(e["phi_deg"])],
        capture_output=True,
        text=True,
        timeout=60,
        env=clean_env,
        cwd=server.project_dir.parent,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    report = json.loads(proc.stdout)
    preview = report["preview"]
    assert {o["name"]: o["value"] for o in preview["order"]}["Szz"] == pytest.approx(e["Szz"], abs=tol["S_atol"])
    assert {o["name"]: o["value"] for o in preview["order"]}["Delta"] == pytest.approx(e["Delta"], abs=tol["S_atol"])
    assert preview["chi2"] == pytest.approx(e["objective"], rel=tol["objective_rtol"])
    assert [c["calculated"]["value"] for c in preview["couplings"]] == pytest.approx(
        e["predictions_Hz"], abs=tol["predictions_atol_Hz"]
    )
    residuals = [abs(c["normalized_residual"]) for c in preview["couplings"]]
    worst = preview["couplings"][residuals.index(max(residuals))]
    assert report["worst_coupling"]["id"] == worst["id"]

    # What the robot did is what every other client now sees, and it is in the journal.
    view = server.call("render.describe_view")["result"]
    assert [s["id"] for s in view["selection"]] == [worst["id"]]
    assert (view["science_revision"], view["workspace_revision"]) == (1, 1)
    journal = [json.loads(line) for line in (server.project_dir / "project.events.jsonl").read_text().splitlines()]
    assert [(r["actor"], r["operation"]) for r in journal] == [
        ("script:robot", "project.open_example"),
        ("script:robot", "view.select"),
    ]


def test_project_load_accepts_a_large_document_over_http(server: Server) -> None:
    """Round 27, finding 4: project.load has its own request limit, so an export loads back."""
    from test_app_science_ops import all_pairs_csv, grid_xyz

    def call(name: str, args: dict[str, Any]) -> Any:
        reply = post(server, name, {"args": args})
        assert reply.status == 200, reply.body[:500]
        return reply.json()["result"]

    call("project.import_xyz", {"xyz": grid_xyz(10), "name": "grid", "expected_science_revision": 0})
    csv = all_pairs_csv(100)
    mapping = call("couplings.reconcile", {"csv": csv})["proposed_mapping"]
    call("couplings.import", {"csv": csv, "confirmed_mapping": mapping, "expected_science_revision": 1})
    exported = call("project.export", {})
    body = json.dumps({"args": {"text": exported["text"], "expected_science_revision": 2}}).encode()
    assert len(body) > 1 << 20  # above the default limit
    reply = server.request("POST", "/api/v1/ops/project.load", body, headers=JSON)
    assert reply.status == 200, reply.body[:500]
    assert reply.json()["result"]["science_hash"] == exported["science_hash"]


def test_a_unicode_project_reloads_over_http(server: Server) -> None:
    """Round 28, finding 1: non-ASCII text escaped by the client still fits project.load's limit."""
    from dipolar_app.formats import dumps_project
    from dipolar_app.project import load_example

    text = dumps_project(load_example("biphenyl-synthetic").model_copy(update={"source": "😀" * 200_000}))
    body = json.dumps({"args": {"text": text, "expected_science_revision": 0}}).encode()  # ASCII-escaped
    assert len(body) > 2 << 20 and len(text) < 1 << 20
    first = server.request("POST", "/api/v1/ops/project.load", body, headers=JSON)
    assert first.status == 200, first.body[:500]
    exported = post(server, "project.export", {"args": {}}).json()["result"]
    again = json.dumps({"args": {"text": exported["text"], "expected_science_revision": 1}}).encode()
    reply = server.request("POST", "/api/v1/ops/project.load", again, headers=JSON)
    assert reply.status == 200, reply.body[:500]
    assert reply.json()["result"]["science_hash"] == exported["science_hash"]
