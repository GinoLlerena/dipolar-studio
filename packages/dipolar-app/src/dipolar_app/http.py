"""HTTP adapter (Starlette) with the provisional M0 localhost controls (plan D10).

Routes:
  POST /api/v1/ops/{name}   body {"args": {...}} -> the dispatcher's JSON envelope
  GET  /api/v1/registry     the contract snapshot (no side effects)
  GET  /                    the built browser page, if a static directory is given

Controls in place now: loopback binding (in the CLI), Host allow-list on every request
(DNS-rebinding defence), Origin allow-list when an Origin is present, a bearer token on every API
request (so cross-site forms cannot act: CSRF), JSON content type, a body-size limit, CPU work off
the event loop, and strict security headers. How the browser receives its token is the D10 spike
(M0 step 4); the M0 page asks for it.
"""

from __future__ import annotations

import hmac
import json
import logging
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from dipolar_app.errors import HTTP_STATUS, ErrorCode, OperationError
from dipolar_app.policy import Principal
from dipolar_app.registry import Registry, dispatch
from dipolar_app.session import Session

LOG = logging.getLogger("dipolar_app.http")
MAX_BODY_BYTES = 1 << 20

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


def create_app(
    registry: Registry,
    session: Session,
    tokens: Mapping[str, Principal],
    *,
    port: int,
    static_dir: Path | None = None,
) -> ASGIApp:
    def authenticate(request: Request) -> Principal | None:
        scheme, _, token = request.headers.get("authorization", "").partition(" ")
        if scheme.lower() != "bearer" or not token:
            return None
        for known, principal in tokens.items():
            if hmac.compare_digest(known.encode(), token.encode()):
                return principal
        return None

    async def run_operation(request: Request) -> Response:
        name = request.path_params["name"]
        principal = authenticate(request)
        if principal is None:
            return _error(ErrorCode.UNAUTHENTICATED, "missing or invalid bearer token", operation=name)
        if request.headers.get("content-type", "").split(";")[0].strip() != "application/json":
            return _error(ErrorCode.INVALID_ARGUMENT, "content type must be application/json", operation=name)
        declared = request.headers.get("content-length")
        if declared is not None and (not declared.isdigit() or int(declared) > MAX_BODY_BYTES):
            return _error(ErrorCode.PAYLOAD_TOO_LARGE, f"the body limit is {MAX_BODY_BYTES} bytes", operation=name)
        body = await request.body()
        if len(body) > MAX_BODY_BYTES:
            return _error(ErrorCode.PAYLOAD_TOO_LARGE, f"the body limit is {MAX_BODY_BYTES} bytes", operation=name)
        try:
            envelope_in: Any = json.loads(body or b"{}")
        except ValueError:
            return _error(ErrorCode.INVALID_ARGUMENT, "the body is not valid JSON", operation=name)
        if not isinstance(envelope_in, dict) or set(envelope_in) - {"args"}:
            extra = sorted(set(envelope_in) - {"args"}) if isinstance(envelope_in, dict) else []
            return _error(
                ErrorCode.INVALID_ARGUMENT,
                f"unknown request fields: {extra}" if extra else "the body must be a JSON object",
                operation=name,
                hint='send {"args": {...}}; identity comes from the credential only',
                offending_field=extra[0] if extra else None,
            )
        args = envelope_in.get("args", {})
        if not isinstance(args, dict):
            return _error(ErrorCode.INVALID_ARGUMENT, "args must be a JSON object", operation=name)
        try:
            envelope = await run_in_threadpool(dispatch, registry, session, principal, name, args)
        except Exception:
            LOG.exception("operation %s failed", name)  # arguments are not logged
            return _error(ErrorCode.INTERNAL, "internal error", operation=name)
        status = 200 if envelope["ok"] else HTTP_STATUS[ErrorCode(envelope["error"]["code"])]
        return JSONResponse(envelope, status_code=status)

    async def get_registry(request: Request) -> Response:
        if authenticate(request) is None:
            return _error(ErrorCode.UNAUTHENTICATED, "missing or invalid bearer token")
        return JSONResponse(registry.snapshot())

    routes: list[Route | Mount] = [
        Route("/api/v1/ops/{name:str}", run_operation, methods=["POST"]),
        Route("/api/v1/registry", get_registry, methods=["GET"]),
    ]
    if static_dir is not None:
        routes.append(Mount("/", app=StaticFiles(directory=static_dir, html=True), name="web"))
    return LocalhostGuard(Starlette(routes=routes), port)
