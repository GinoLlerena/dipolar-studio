"""M0 spike 3: D10 localhost security on a packaged build (plan D10, ADR-0010).

Question: can a browser page and scripts use a local ``dipolar serve`` safely, and does the
installed package (not only the source tree) hold the controls? Run against the installed wheel:

    tools/package/build.sh
    uv venv /tmp/dipolar-pkg && uv pip install --python /tmp/dipolar-pkg/bin/python dist/packages/*.whl
    DIPOLAR_BIN=/tmp/dipolar-pkg/bin/dipolar uv run pytest spikes/test_spike_d10_localhost.py

Without ``DIPOLAR_BIN`` the same tests run against the source tree (``python -m dipolar_app.cli``),
serving ``web/dist`` if it was built; the page checks are skipped otherwise.

Evidence:
  * browser hand-off: single-use, expiring launch code in the fragment → tab token;
  * DNS rebinding: every foreign or malformed Host is refused before routing;
  * CSRF: no cross-origin request can act; no CORS header is ever sent; ``Origin: null`` refused;
  * token leakage: no credential in output, process arguments, the journal, the page or headers;
  * instances: a second server on the same project is refused; instances are isolated;
  * port reuse: a stale ready file pointing at a port now held by another process is detected.
"""

from __future__ import annotations

import http.client
import http.server
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
WEB_DIST = ROOT / "web" / "dist"
ROBOT = ROOT / "tools" / "robot" / "robot.py"
PACKAGED = os.environ.get("DIPOLAR_BIN")
BASE_CMD = [PACKAGED] if PACKAGED else [sys.executable, "-m", "dipolar_app.cli"]


def has_page() -> bool:
    return bool(PACKAGED) or (WEB_DIST / "index.html").is_file()


# --------------------------------------------------------------------------- helpers
@dataclass
class Reply:
    status: int
    headers: dict[str, str]
    body: bytes

    def json(self) -> Any:
        return json.loads(self.body)


@dataclass
class Instance:
    process: subprocess.Popen[bytes]
    project_dir: Path
    ready_file: Path
    output: Path
    ready: dict[str, Any]

    @property
    def port(self) -> int:
        return int(self.ready["base_url"].rsplit(":", 1)[1])

    def token(self, name: str) -> str:
        token: str = self.ready["tokens"][name]
        return token

    def raw(
        self,
        method: str,
        path: str,
        *,
        host: str | None = "default",
        headers: dict[str, str] | None = None,
        body: bytes | None = None,
        http10: bool = False,
    ) -> Reply:
        """One request with exactly the headers given (no automatic Host)."""
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        if http10:
            conn._http_vsn, conn._http_vsn_str = 10, "HTTP/1.0"  # type: ignore[attr-defined]
        conn.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
        if host == "default":
            host = f"127.0.0.1:{self.port}"
        if host is not None:
            conn.putheader("Host", host)
        for key, value in (headers or {}).items():
            conn.putheader(key, value)
        if body is not None:
            conn.putheader("Content-Length", str(len(body)))
        conn.endheaders(body)
        resp = conn.getresponse()
        reply = Reply(resp.status, {k.lower(): v for k, v in resp.getheaders()}, resp.read())
        conn.close()
        return reply

    def op(self, name: str, args: dict[str, Any], token: str, **kw: Any) -> Reply:
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json", **kw.pop("headers", {})}
        return self.raw("POST", f"/api/v1/ops/{name}", headers=headers, body=json.dumps({"args": args}).encode(), **kw)

    def exchange(self, code: str, origin: str | None = "own") -> Reply:
        headers = {"Content-Type": "application/json"}
        if origin == "own":
            origin = f"http://127.0.0.1:{self.port}"
        if origin is not None:
            headers["Origin"] = origin
        return self.raw("POST", "/api/v1/auth/session", headers=headers, body=json.dumps({"code": code}).encode())


def is_ours(ready: dict[str, Any], pid: int, ready_file: Path, started: float) -> bool:
    """Whether the ready file is the one the launched process wrote. On POSIX its pid is ours. On
    Windows a virtualenv's python.exe is a launcher that runs the interpreter as a child process,
    so the pid differs; there the file must have been written after the launch."""
    if ready["pid"] == pid:
        return True
    return os.name == "nt" and ready_file.stat().st_mtime >= started


def launch(
    tmp: Path,
    name: str = "a",
    project_dir: Path | None = None,
    *,
    ready_file: Path | None = None,
    cwd: Path | None = None,
    extra: tuple[str, ...] = (),
    env: dict[str, str] | None = None,
) -> Instance:
    """Start ``serve``. ``project_dir`` and ``ready_file`` may be relative to ``cwd``."""
    project_dir = project_dir or tmp / f"project-{name}"
    base = cwd or Path.cwd()
    ready_arg = ready_file
    ready_file = base / (ready_file or project_dir / "serve.ready.json")
    output = tmp / f"server-{name}.out"
    cmd = [*BASE_CMD, "serve", "--project-dir", str(project_dir), *extra]
    if ready_arg is not None:
        cmd += ["--ready-file", str(ready_arg)]
    if not PACKAGED and (WEB_DIST / "index.html").is_file():
        cmd += ["--static-dir", str(WEB_DIST)]
    started = time.time()
    with output.open("wb") as out:
        process = subprocess.Popen(cmd, stdout=out, stderr=subprocess.STDOUT, cwd=cwd, env=env)
    deadline = time.monotonic() + 20
    while True:  # wait for *this* process's ready file (a crashed one may have left an old file)
        try:
            ready = json.loads(ready_file.read_text(encoding="utf-8"))
            if is_ours(ready, process.pid, ready_file, started):
                break
        except (OSError, ValueError):
            pass
        if process.poll() is not None or time.monotonic() > deadline:
            process.kill()
            raise RuntimeError(output.read_text(encoding="utf-8"))
        time.sleep(0.05)
    return Instance(process, base / project_dir, ready_file, output, ready)


def stop(instance: Instance) -> None:
    if instance.process.poll() is None:
        instance.process.terminate()
        try:
            instance.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            instance.process.kill()
            instance.process.wait()


def open_url(ready_file: Path) -> subprocess.CompletedProcess[str]:
    cmd = [*BASE_CMD, "open", "--ready-file", str(ready_file), "--print-url"]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)


def launch_code(instance: Instance) -> str:
    result = open_url(instance.ready_file)
    assert result.returncode == 0, result.stderr
    match = re.fullmatch(rf"http://127\.0\.0\.1:{instance.port}/#launch=([A-Za-z0-9_-]+)\n", result.stdout)
    assert match, result.stdout
    return match.group(1)


@pytest.fixture
def inst(tmp_path: Path) -> Iterator[Instance]:
    instance = launch(tmp_path)
    try:
        yield instance
    finally:
        stop(instance)


# --------------------------------------------------------------------------- browser hand-off
def test_launch_code_hand_off(inst: Instance) -> None:
    code = launch_code(inst)
    assert inst.exchange(code, origin=None).status == 403  # only a browser page (which sends Origin) may exchange
    assert inst.exchange(code, origin="http://evil.example").status == 403
    first = inst.exchange(code)  # the refusals above did not consume the code
    assert first.status == 200, first.body
    tab = first.json()
    assert tab["actor"] == "user" and tab["tier"] == "apply"
    assert tab["token"] not in inst.ready["tokens"].values()  # a new, tab-scoped credential
    again = inst.exchange(code)
    assert (again.status, again.json()["error"]["code"]) == (401, "UNAUTHENTICATED")  # single use
    view = inst.op("render.describe_view", {}, tab["token"])
    assert view.status == 200 and view.json()["ok"]
    opened = inst.op(
        "project.open_example", {"name": "biphenyl-synthetic", "expected_science_revision": 0}, tab["token"]
    )
    assert opened.status == 200  # the tab acts as the human user
    assert inst.exchange("not-a-code").status == 401


def test_only_the_human_launch_credential_mints_codes(inst: Instance) -> None:
    path = "/api/v1/auth/launch-code"
    json_headers = {"Content-Type": "application/json"}
    assert inst.raw("POST", path, headers=json_headers, body=b"{}").status == 401
    robot = inst.raw(
        "POST", path, headers={**json_headers, "Authorization": f"Bearer {inst.token('robot')}"}, body=b"{}"
    )
    assert (robot.status, robot.json()["error"]["code"]) == (403, "CAPABILITY_DENIED")
    get = inst.raw("GET", path, headers={"Authorization": f"Bearer {inst.token('user')}"})
    assert get.status in (404, 405) and b"code" not in get.body  # GET has no side effects


def test_a_tab_token_cannot_mint_codes(inst: Instance) -> None:
    """Round 10, finding 3: a tab acts as the user but cannot mint further launch codes."""
    tab = inst.exchange(launch_code(inst)).json()["token"]
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {tab}"}
    minted = inst.raw("POST", "/api/v1/auth/launch-code", headers=headers, body=b"{}")
    assert (minted.status, minted.json()["error"]["code"]) == (403, "CAPABILITY_DENIED")


@pytest.mark.parametrize(
    "body", [b'{"code": "\\ud800"}', b'{"code": ' + b"[" * 400 + b"]" * 400 + b"}", b'{"code": 1}']
)
def test_malformed_exchanges_get_structured_errors(inst: Instance, body: bytes) -> None:
    """Round 10, finding 2: no plain 500s from odd Unicode or deep nesting."""
    headers = {"Content-Type": "application/json", "Origin": f"http://127.0.0.1:{inst.port}"}
    reply = inst.raw("POST", "/api/v1/auth/session", headers=headers, body=body)
    assert reply.status == 400 and reply.json()["error"]["code"] == "INVALID_ARGUMENT"


RECORDER = """import json, sys
from pathlib import Path
Path(sys.argv[1]).write_text(json.dumps(sys.argv[2:]))
"""


@pytest.mark.skipif(
    sys.platform == "win32", reason="POSIX only: launch directory modes, symlinks or SIGKILL (ADR-0010)"
)
def test_the_browser_launcher_never_sees_the_code(inst: Instance, tmp_path: Path) -> None:
    """Round 10, finding 1. Browser launchers take the URL as an argument, and other local users
    can read process arguments (ps). ``dipolar open`` therefore gives the launcher only the path of
    a private redirect page; the code is inside that file (0600, in a 0700 directory)."""
    recorder, record = tmp_path / "browser.py", tmp_path / "argv.json"
    recorder.write_text(RECORDER, encoding="utf-8")
    env = {**os.environ, "BROWSER": f"{sys.executable} {recorder} {record} %s"}
    cmd = [*BASE_CMD, "open", "--ready-file", str(inst.ready_file)]
    opened = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=env, check=False)
    assert opened.returncode == 0, opened
    argv = json.loads(record.read_text(encoding="utf-8"))
    assert len(argv) == 1 and argv[0].startswith("file://") and argv[0].endswith(".html"), argv
    assert "launch" not in argv[0].split("/")[-1] and "#" not in argv[0]  # only a path: nothing to steal
    page = Path(argv[0].removeprefix("file://"))
    assert stat.S_IMODE(page.stat().st_mode) == 0o600
    assert stat.S_IMODE(page.parent.stat().st_mode) == 0o700
    match = re.search(
        rf'url=http://127\.0\.0\.1:{inst.port}/#launch=([A-Za-z0-9_-]+)"', page.read_text(encoding="utf-8")
    )
    assert match, page.read_text(encoding="utf-8")
    code = match.group(1)
    assert code not in opened.stdout + opened.stderr
    assert inst.exchange(code).status == 200  # the page that follows the redirect gets the session
    stop(inst)
    assert not list(page.parent.glob("open-*.html"))  # graceful shutdown removes this instance's pages


def recording_browser(tmp_path: Path) -> tuple[dict[str, str], Path]:
    recorder, record = tmp_path / "browser.py", tmp_path / "argv.json"
    recorder.write_text(RECORDER, encoding="utf-8")
    return {**os.environ, "BROWSER": f"{sys.executable} {recorder} {record} %s"}, record


@pytest.mark.skipif(
    sys.platform == "win32", reason="POSIX only: launch directory modes, symlinks or SIGKILL (ADR-0010)"
)
def test_a_symlinked_launch_directory_is_refused_and_never_touched(tmp_path: Path) -> None:
    """Round 11, finding 1: ``browser-launch`` as a symlink must never lead to chmod or deletion
    outside the project, neither when opening nor at shutdown (with or without --open)."""
    victim = tmp_path / "victim"
    victim.mkdir(mode=0o755)
    precious = [victim / "open-important.html", victim / "open-ins_x-y.html"]
    for path in precious:
        path.write_text("keep me", encoding="utf-8")
        os.utime(path, (1, 1))  # "expired", so age-based cleanup would pick it if it looked here
    project = tmp_path / "project-a"
    project.mkdir()
    (project / "browser-launch").symlink_to(victim, target_is_directory=True)
    inst = launch(tmp_path, project_dir=project)
    env, record = recording_browser(tmp_path)
    cmd = [*BASE_CMD, "open", "--ready-file", str(inst.ready_file)]
    opened = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=env, check=False)
    assert opened.returncode == 1 and "not a plain directory" in opened.stderr, opened
    assert not record.exists()  # no browser was started
    stop(inst)
    assert all(path.read_text(encoding="utf-8") == "keep me" for path in precious)
    assert stat.S_IMODE(victim.stat().st_mode) == 0o755
    assert sorted(victim.iterdir()) == sorted(precious)


@pytest.mark.skipif(sys.platform == "win32", reason="the launch directory is validated on POSIX only (ADR-0010)")
def test_relative_paths_and_a_custom_ready_file_location(tmp_path: Path) -> None:
    """Round 11, findings 2 and 3: relative paths give absolute file URIs, and pages live beside
    the ready file wherever it is, so shutdown removes them."""
    (tmp_path / "elsewhere").mkdir()
    inst = launch(tmp_path, project_dir=Path("proj"), ready_file=Path("elsewhere/ready.json"), cwd=tmp_path)
    env, record = recording_browser(tmp_path)
    cmd = [*BASE_CMD, "open", "--ready-file", "elsewhere/ready.json"]
    opened = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=env, cwd=tmp_path, check=False)
    assert opened.returncode == 0, opened
    page = Path(json.loads(record.read_text(encoding="utf-8"))[0].removeprefix("file://"))
    assert page.is_absolute() and page.parent == (tmp_path / "elsewhere" / "browser-launch").resolve()
    assert inst.ready["instance_id"] in page.name
    stop(inst)  # graceful shutdown removes this instance's pages
    assert not page.exists()


@pytest.mark.skipif(
    sys.platform == "win32", reason="POSIX only: launch directory modes, symlinks or SIGKILL (ADR-0010)"
)
@pytest.mark.skipif(not has_page(), reason="web/dist is not built (cd web && pnpm build)")
def test_serve_open_with_a_relative_project(tmp_path: Path) -> None:
    env, record = recording_browser(tmp_path)
    inst = launch(tmp_path, project_dir=Path("proj"), cwd=tmp_path, extra=("--open",), env=env)
    deadline = time.monotonic() + 10
    while not record.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    page = Path(json.loads(record.read_text(encoding="utf-8"))[0].removeprefix("file://"))
    match = re.search(r"#launch=([A-Za-z0-9_-]+)", page.read_text(encoding="utf-8"))
    assert match and inst.exchange(match.group(1)).status == 200
    stop(inst)
    assert not page.exists() and not inst.ready_file.exists()


@pytest.mark.skipif(not has_page(), reason="web/dist is not built (cd web && pnpm build)")
def test_the_page_is_served_with_strict_headers(inst: Instance) -> None:
    page = inst.raw("GET", "/")
    assert page.status == 200 and b'<div id="root">' in page.body
    assert "script-src 'self'" in page.headers["content-security-policy"]
    assert page.headers["x-content-type-options"] == "nosniff"
    for asset in re.findall(rb'(?:src|href)="(/assets/[^"]+)"', page.body):
        assert inst.raw("GET", asset.decode()).status == 200
    assert inst.raw("GET", "/../../etc/passwd").status == 404
    assert inst.raw("GET", "/%2e%2e/%2e%2e/etc/passwd").status == 404


# --------------------------------------------------------------------------- DNS rebinding
HOST_VARIANTS = [
    "evil.example:{port}",
    "evil.example",
    "127.0.0.1",
    "localhost",
    "127.0.0.1:1",
    "LOCALHOST:{port}",
    "localhost.:{port}",
    "0.0.0.0:{port}",
    "127.1:{port}",
    "2130706433:{port}",
    "[::1]:{port}",
    "127.0.0.1:{port}.evil.example",
    "",
]


@pytest.mark.parametrize("variant", HOST_VARIANTS)
def test_dns_rebinding_foreign_hosts_are_refused(inst: Instance, variant: str) -> None:
    host = variant.format(port=inst.port)
    auth = {"Authorization": f"Bearer {inst.token('user')}"}
    for method, path in (("GET", "/"), ("GET", "/api/v1/registry"), ("GET", "/api/v1/instance")):
        assert inst.raw(method, path, host=host, headers=auth).status in (400, 421), (method, path)
    assert inst.op("render.describe_view", {}, inst.token("user"), host=host).status in (400, 421)
    assert inst.raw("POST", "/api/v1/auth/launch-code", host=host, headers=auth, body=b"{}").status in (400, 421)


def test_missing_host_is_refused(inst: Instance) -> None:
    auth = {"Authorization": f"Bearer {inst.token('user')}"}
    assert inst.raw("GET", "/api/v1/registry", host=None, headers=auth, http10=True).status in (400, 421)
    assert inst.raw("GET", "/api/v1/registry", host=None, headers=auth).status in (400, 421)


def test_allowed_hosts_work(inst: Instance) -> None:
    auth = {"Authorization": f"Bearer {inst.token('user')}"}
    for host in (f"127.0.0.1:{inst.port}", f"localhost:{inst.port}"):
        assert inst.raw("GET", "/api/v1/registry", host=host, headers=auth).status == 200


# --------------------------------------------------------------------------- CSRF
def test_cross_site_requests_cannot_act(inst: Instance) -> None:
    form = {"Content-Type": "text/plain", "Origin": "http://evil.example"}
    body = b'{"args": {"ids": []}}'
    assert inst.raw("POST", "/api/v1/ops/view.select", headers=form, body=body).status == 403
    no_origin = {"Content-Type": "text/plain"}
    assert inst.raw("POST", "/api/v1/ops/view.select", headers=no_origin, body=body).status == 401
    user = inst.token("user")
    null_origin = {"Origin": "null"}
    assert inst.op("render.describe_view", {}, user, headers=null_origin).status == 403  # sandboxed frames, file://
    plain = {"Authorization": f"Bearer {user}", "Content-Type": "text/plain"}
    assert inst.raw("POST", "/api/v1/ops/render.describe_view", headers=plain, body=b"{}").status == 400
    other_port = {"Origin": "http://127.0.0.1:1"}  # another local web app is a different origin
    assert inst.op("render.describe_view", {}, user, headers=other_port).status == 403


def test_no_cors_headers_are_ever_sent(inst: Instance) -> None:
    preflight = {
        "Origin": "http://evil.example",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization, content-type",
    }
    replies = [
        inst.raw("OPTIONS", "/api/v1/ops/view.select", headers=preflight),
        inst.raw(
            "OPTIONS", "/api/v1/ops/view.select", headers={**preflight, "Origin": f"http://127.0.0.1:{inst.port}"}
        ),
        inst.op("render.describe_view", {}, inst.token("user")),
        inst.raw("GET", "/"),
    ]
    assert replies[0].status == 403 and replies[1].status == 405
    for reply in replies:
        assert not [h for h in reply.headers if h.startswith("access-control-")], reply.headers


# --------------------------------------------------------------------------- token leakage
def test_no_credential_leaks(inst: Instance) -> None:
    secrets = list(inst.ready["tokens"].values())
    code = launch_code(inst)
    tab = inst.exchange(code).json()["token"]
    secrets.append(tab)
    replies = [
        inst.op("project.open_example", {"name": "biphenyl-synthetic", "expected_science_revision": 0}, tab),
        inst.op("view.select", {"ids": ["cpl_000001"]}, inst.token("robot")),
        inst.op("render.describe_view", {}, "wrong-token"),
        inst.raw("GET", "/api/v1/registry", headers={"Authorization": f"Bearer {tab}"}),
        inst.raw("GET", "/api/v1/instance", headers={"Authorization": f"Bearer {tab}"}),
    ]
    if has_page():
        page = inst.raw("GET", "/")
        replies.append(page)
        replies += [inst.raw("GET", a.decode()) for a in re.findall(rb'(?:src|href)="(/assets/[^"]+)"', page.body)]
    places = {
        "journal": (inst.project_dir / "project.events.jsonl").read_text(encoding="utf-8"),
        "server output (so far)": inst.output.read_text(encoding="utf-8"),
    }
    places.update({f"reply {i}": r.body.decode() + json.dumps(r.headers) for i, r in enumerate(replies)})
    if os.name == "posix":  # the process's command line, read with ps (not available on Windows)
        argv = subprocess.run(["ps", "-o", "command=", "-p", str(inst.process.pid)], capture_output=True, text=True)
        assert "dipolar" in argv.stdout or "dipolar_app" in argv.stdout
        places["process arguments"] = argv.stdout
    stop(inst)
    places["server output (after shutdown)"] = inst.output.read_text(encoding="utf-8")
    for where, text in places.items():
        for secret in secrets:
            assert secret not in text, f"a credential appears in the {where}"
    assert code not in inst.output.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- instances and port reuse
def test_second_instance_on_the_same_project_is_refused(inst: Instance, tmp_path: Path) -> None:
    cmd = [*BASE_CMD, "serve", "--project-dir", str(inst.project_dir)]
    second = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)
    assert second.returncode == 3, second
    assert "already using" in second.stderr
    assert (
        json.loads(inst.ready_file.read_text(encoding="utf-8"))["instance_id"] == inst.ready["instance_id"]
    )  # not clobbered
    assert inst.op("render.describe_view", {}, inst.token("robot")).status == 200


def test_instances_are_isolated(tmp_path: Path) -> None:
    a, b = launch(tmp_path, "a"), launch(tmp_path, "b")
    try:
        assert a.port != b.port and a.ready["instance_id"] != b.ready["instance_id"]
        assert b.op("render.describe_view", {}, a.token("user")).status == 401  # A's token means nothing to B
        assert b.op("render.describe_view", {}, b.token("user"), host=f"127.0.0.1:{a.port}").status == 421
    finally:
        stop(a)
        stop(b)


class Impostor(http.server.BaseHTTPRequestHandler):
    """Another program that took over the port: it answers 200 with plausible JSON to anything."""

    def _answer(self) -> None:
        body = json.dumps({"instance_id": "ins_impostor", "ok": True, "operations": []}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    do_GET = do_POST = _answer

    def log_message(self, format: str, *args: Any) -> None:
        pass


@pytest.mark.skipif(
    sys.platform == "win32", reason="POSIX only: launch directory modes, symlinks or SIGKILL (ADR-0010)"
)
def test_stale_ready_file_and_port_reuse_are_detected(tmp_path: Path, clean_robot_env: dict[str, str]) -> None:
    a = launch(tmp_path, "a")
    stale_copy = tmp_path / "stale.ready.json"
    shutil.copy(a.ready_file, stale_copy)
    a.process.send_signal(signal.SIGKILL)  # a crash: no clean-up, the ready file stays behind
    a.process.wait()
    assert a.ready_file.exists()
    impostor = http.server.HTTPServer(("127.0.0.1", a.port), Impostor)
    thread = threading.Thread(target=impostor.serve_forever, daemon=True)
    thread.start()
    try:
        robot = subprocess.run(
            [sys.executable, "-I", str(ROBOT), "--ready-file", str(stale_copy)],
            capture_output=True,
            text=True,
            timeout=60,
            env=clean_robot_env,
            check=False,
        )
        assert robot.returncode == 1 and "does not describe the server" in robot.stdout, robot
        opener = open_url(stale_copy)
        assert opener.returncode == 4 and "does not describe the server" in opener.stderr, opener
    finally:
        impostor.shutdown()
        impostor.server_close()
    # The kernel released the dead instance's lock: a new server on the same project starts at once
    # and replaces the stale ready file.
    b = launch(tmp_path, "b", project_dir=a.project_dir)
    try:
        assert b.ready["instance_id"] != a.ready["instance_id"]
        assert json.loads(b.ready_file.read_text(encoding="utf-8"))["instance_id"] == b.ready["instance_id"]
        robot = subprocess.run(
            [sys.executable, "-I", str(ROBOT), "--ready-file", str(b.ready_file)],
            capture_output=True,
            text=True,
            timeout=60,
            env=clean_robot_env,
            check=False,
        )
        assert robot.returncode == 0, robot
    finally:
        stop(b)


@pytest.fixture
def clean_robot_env() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if not k.startswith(("PYTHON", "VIRTUAL_ENV", "UV_"))}
