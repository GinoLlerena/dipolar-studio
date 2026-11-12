"""HTTP adapter (Starlette) with the localhost controls of plan D10 (decided in M0 spike 3).

Routes:
  POST /api/v1/ops/{name}         body {"args": {...}} -> the dispatcher's JSON envelope
  GET  /api/v1/registry           the contract snapshot (no side effects)
  GET  /api/v1/instance           who answers on this port: instance ID, pid, contract version
  POST /api/v1/auth/launch-code   a single-use browser launch code (human launch credential only)
  POST /api/v1/auth/session       body {"code": ...} -> a tab token; allowed Origin required
  GET  /api/v1/events?after=N     the change feed as NDJSON (authenticated fetch streaming)
  GET  /                          the browser page (bundled, or --static-dir)

Controls: loopback binding and an instance lock (in the CLI); a Host allow-list on every request
(DNS-rebinding defence); an Origin allow-list whenever an Origin is present; a bearer token on every
API request except the code exchange, so cross-site forms cannot act (CSRF); no CORS headers ever;
JSON content type; a streamed body limit; strict RFC 8259 JSON; CPU work off the event loop; strict
security headers. Authentication routes are the explicit exception to "registry operations only"
(04 §8.5).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response, StreamingResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from dipolar_app.auth import LAUNCH_CODE_TTL_S, Credentials
from dipolar_app.errors import HTTP_STATUS, ErrorCode, OperationError
from dipolar_app.policy import Principal
from dipolar_app.registry import Registry, RequestEnvelope, dispatch
from dipolar_app.schemas import MAX_JSON_DEPTH, wire_problem
from dipolar_app.session import Session

LOG = logging.getLogger("dipolar_app.http")
MAX_BODY_BYTES = 1 << 20
MAX_AUTH_BODY_BYTES = 1 << 10
#: Concurrent event streams, and the heartbeat interval of each (M2 step 3).
MAX_STREAMS = 8
HEARTBEAT_S = 15.0

CSP = (
    "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; "
    "font-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
)
SECURITY_HEADERS = {
    "content-security-policy": CSP,
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
    "cross-origin-opener-policy": "same-origin",
    "cross-origin-resource-policy": "same-origin",
}


class LocalhostGuard:
    """ASGI middleware: reject foreign Host/Origin headers and add security headers."""

    def __init__(self, app: ASGIApp, port: int) -> None:
        self.app = app
        self.hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        self.origins = {f"http://{h}" for h in self.hosts}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope["headers"]}
        if headers.get("host") not in self.hosts:
            await PlainTextResponse("host not allowed", status_code=421)(scope, receive, send)
            return
        origin = headers.get("origin")
        if origin is not None and origin not in self.origins:
            await PlainTextResponse("origin not allowed", status_code=403)(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                raw = list(message.get("headers", []))
                raw += [(k.encode(), v.encode()) for k, v in SECURITY_HEADERS.items()]
                if scope["path"].startswith("/api/"):
                    raw.append((b"cache-control", b"no-store"))
                message["headers"] = raw
            await send(message)

        await self.app(scope, receive, send_with_headers)


#: The request body's fields (``RequestEnvelope``); the dispatcher validates their values.
REQUEST_FIELDS = frozenset(RequestEnvelope.model_fields)


class _CountedStream(StreamingResponse):
    """A stream that frees its slot when the response ends, however it ends: a normal close, a
    disconnect before the first chunk, or a failed send (round 33)."""

    def __init__(self, content: Any, counter: dict[str, int], **kw: Any) -> None:
        super().__init__(content, **kw)
        self._counter = counter
        self._released = False

    def _release(self) -> None:
        if not self._released:
            self._released = True
            self._counter["open"] -= 1

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        try:
            await super().__call__(scope, receive, send)
        finally:
            self._release()

    def __del__(self) -> None:  # a response that was never sent still frees its slot
        self._release()


def _reject_constant(token: str) -> None:
    raise ValueError(f"{token} is not JSON")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:  # parsers disagree on duplicates (first or last wins), so refuse them
            raise ValueError(f"duplicate key {key!r}")
        out[key] = value
    return out


def parse_json_body(body: bytes) -> Any:
    """Strict RFC 8259 parsing: UTF-8 only, no NaN or Infinity tokens, no duplicate keys, valid
    Unicode in every string, and bounded nesting. Every failure is a ``ValueError``."""
    try:
        value = json.loads(body.decode("utf-8"), parse_constant=_reject_constant, object_pairs_hook=_unique_object)
    except RecursionError:
        raise ValueError(f"nested deeper than {MAX_JSON_DEPTH} levels") from None
    problem = wire_problem(value)
    if problem:
        raise ValueError(problem)
    return value


def _error(
    code: ErrorCode,
    message: str,
    *,
    operation: str | None = None,
    hint: str | None = None,
    offending_field: str | None = None,
) -> JSONResponse:
    err = OperationError(code, message, hint=hint, offending_field=offending_field)
    body = {"ok": False, "operation": operation, "error": err.to_json()}
    return JSONResponse(body, status_code=HTTP_STATUS[code])


class BodyError(Exception):
    def __init__(self, response: Response) -> None:
        self.response = response


async def read_json_body(request: Request, limit: int, operation: str | None) -> Any:
    """Read and parse a JSON body, counting while streaming so nothing is buffered past ``limit``."""
    if request.headers.get("content-type", "").split(";")[0].strip() != "application/json":
        wrong_type = _error(ErrorCode.INVALID_ARGUMENT, "content type must be application/json", operation=operation)
        raise BodyError(wrong_type)
    too_large = _error(ErrorCode.PAYLOAD_TOO_LARGE, f"the body limit is {limit} bytes", operation=operation)
    declared = request.headers.get("content-length")
    if declared is not None and (not declared.isdigit() or int(declared) > limit):
        raise BodyError(too_large)
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():  # a chunked body (no Content-Length) is bounded here
        size += len(chunk)
        if size > limit:
            raise BodyError(too_large)
        chunks.append(chunk)
    try:
        return parse_json_body(b"".join(chunks) or b"{}")
    except ValueError as exc:  # includes UnicodeDecodeError and JSONDecodeError
        reason = "not UTF-8" if isinstance(exc, UnicodeDecodeError) else str(exc).split(":")[0]
        raise BodyError(
            _error(ErrorCode.INVALID_ARGUMENT, f"the body is not valid JSON ({reason})", operation=operation)
        ) from None


def create_app(
    registry: Registry,
    session: Session,
    credentials: Credentials,
    *,
    port: int,
    instance_id: str = "unnamed",
    pid: int = 0,
    static_dir: Path | None = None,
    heartbeat_s: float = HEARTBEAT_S,
) -> ASGIApp:
    allowed_origins = {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}
    streams = {"open": 0}

    def authenticate(request: Request) -> Principal | None:
        scheme, _, token = request.headers.get("authorization", "").partition(" ")
        if scheme.lower() != "bearer" or not token:
            return None
        return credentials.authenticate(token)

    def unauthenticated(operation: str | None = None) -> Response:
        return _error(ErrorCode.UNAUTHENTICATED, "missing or invalid bearer token", operation=operation)

    async def run_operation(request: Request) -> Response:
        name = request.path_params["name"]
        principal = authenticate(request)
        if principal is None:
            return unauthenticated(name)
        try:
            op = registry.get(name)
            limit = op.max_request_bytes if op is not None else MAX_BODY_BYTES
            envelope_in = await read_json_body(request, limit, name)
        except BodyError as exc:
            return exc.response
        if not isinstance(envelope_in, dict) or set(envelope_in) - REQUEST_FIELDS:
            extra = sorted(set(envelope_in) - REQUEST_FIELDS) if isinstance(envelope_in, dict) else []
            return _error(
                ErrorCode.INVALID_ARGUMENT,
                f"unknown request fields: {extra}" if extra else "the body must be a JSON object",
                operation=name,
                hint='send {"args": {...}}, optionally "request_id" and "dry_run"; identity comes from the credential',
                offending_field=extra[0] if extra else None,
            )
        args = envelope_in.get("args", {})
        if not isinstance(args, dict):
            return _error(ErrorCode.INVALID_ARGUMENT, "args must be a JSON object", operation=name)
        options = {"request_id": envelope_in.get("request_id"), "dry_run": envelope_in.get("dry_run", False)}
        try:
            envelope = await run_in_threadpool(dispatch, registry, session, principal, name, args, **options)
        except Exception:
            LOG.exception("operation %s failed", name)  # arguments are not logged
            return _error(ErrorCode.INTERNAL, "internal error", operation=name)
        status = 200 if envelope["ok"] else HTTP_STATUS[ErrorCode(envelope["error"]["code"])]
        return JSONResponse(envelope, status_code=status)

    async def get_registry(request: Request) -> Response:
        if authenticate(request) is None:
            return unauthenticated()
        return JSONResponse(registry.snapshot())

    async def get_instance(request: Request) -> Response:
        """The authenticated readiness handshake: a client checks that the instance ID matches its
        ready file, so a stale ready file or a port reused by another process is detected."""
        if authenticate(request) is None:
            return unauthenticated()
        contract = registry.snapshot()["contract_version"]
        return JSONResponse({"instance_id": instance_id, "pid": pid, "contract_version": contract})

    async def issue_launch_code(request: Request) -> Response:
        scheme, _, token = request.headers.get("authorization", "").partition(" ")
        if scheme.lower() != "bearer" or not token:
            return unauthenticated()
        try:
            code = credentials.issue_launch_code(token)
        except OperationError as err:
            return JSONResponse({"ok": False, "operation": None, "error": err.to_json()}, HTTP_STATUS[err.code])
        return JSONResponse({"code": code, "expires_in_s": LAUNCH_CODE_TTL_S})

    async def start_tab_session(request: Request) -> Response:
        # Only the browser page exchanges codes, and a browser always sends Origin on a POST fetch.
        if request.headers.get("origin") not in allowed_origins:
            return _error(ErrorCode.CAPABILITY_DENIED, "the code exchange needs an allowed Origin")
        try:
            body = await read_json_body(request, MAX_AUTH_BODY_BYTES, None)
        except BodyError as exc:
            return exc.response
        code = body.get("code") if isinstance(body, dict) and set(body) == {"code"} else None
        if not isinstance(code, str):
            return _error(ErrorCode.INVALID_ARGUMENT, 'send {"code": "<launch code>"}', offending_field="code")
        try:
            token, principal = credentials.redeem(code)
        except OperationError as err:
            return JSONResponse({"ok": False, "operation": None, "error": err.to_json()}, HTTP_STATUS[err.code])
        return JSONResponse({"token": token, "actor": principal.actor, "tier": principal.tier.value})

    async def stream_events(request: Request) -> Response:
        """The change feed (D14 multi-client sync; D10 note: authenticated fetch streaming, since
        EventSource cannot send the bearer token). One JSON object per line:

        - ``hello`` first: the boot ID, the current cursor, sequence and revisions;
        - ``commit`` per acknowledged transaction (operation, actor, revisions, domains, jobs);
        - ``job`` for unjournaled progress (``running``);
        - ``ping`` as a heartbeat;
        - ``resync`` when entries after ``after`` were dropped or belong to an earlier boot: read
          the state again, then continue from the given cursor.

        It is a read: no side effects, any authenticated tier. Arguments and labels never appear.
        """
        if authenticate(request) is None:
            return unauthenticated()
        raw = request.query_params.get("after")
        if raw is not None and not (raw.isdigit() and len(raw) <= 15):
            return _error(ErrorCode.INVALID_ARGUMENT, "after must be a cursor (a non-negative integer)")
        if streams["open"] >= MAX_STREAMS:
            return _error(ErrorCode.QUOTA_EXCEEDED, f"at most {MAX_STREAMS} event streams may be open")
        streams["open"] += 1

        def line(item: dict[str, Any]) -> bytes:
            return (json.dumps(item, separators=(",", ":")) + "\n").encode()

        async def body() -> Any:
            state, now = session.snapshot()  # one consistent (state, cursor) pair (round 33)
            cursor = now if raw is None else int(raw)
            yield line(
                {
                    "kind": "hello",
                    "boot_id": session.boot_id,
                    "cursor": now,
                    "seq": state.seq,
                    "revisions": {"science": state.science_revision, "workspace": state.workspace_revision},
                }
            )
            while not await request.is_disconnected():
                items, latest, resync = await run_in_threadpool(session.feed_after, cursor, heartbeat_s)
                if resync:
                    yield line({"kind": "resync", "cursor": latest})
                    cursor = latest
                elif not items:
                    yield line({"kind": "ping", "cursor": latest})
                for c, item in items:
                    yield line({**item, "cursor": c})
                    cursor = c

        return _CountedStream(body(), streams, media_type="application/x-ndjson")

    routes: list[Route | Mount] = [
        Route("/api/v1/ops/{name:str}", run_operation, methods=["POST"]),
        Route("/api/v1/registry", get_registry, methods=["GET"]),
        Route("/api/v1/instance", get_instance, methods=["GET"]),
        Route("/api/v1/auth/launch-code", issue_launch_code, methods=["POST"]),
        Route("/api/v1/auth/session", start_tab_session, methods=["POST"]),
        Route("/api/v1/events", stream_events, methods=["GET"]),
    ]
    if static_dir is not None:
        routes.append(Mount("/", app=StaticFiles(directory=static_dir, html=True), name="web"))
    return LocalhostGuard(Starlette(routes=routes), port)
