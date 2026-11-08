"""Python adapter: an in-process client over the same dispatcher the HTTP adapter uses."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from dipolar_app.policy import Principal
from dipolar_app.registry import Registry, dispatch
from dipolar_app.session import Session


class LocalClient:
    def __init__(self, registry: Registry, session: Session, principal: Principal) -> None:
        self._registry = registry
        self._session = session
        self._principal = principal

    def call(self, name: str, args: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Return the same JSON envelope as ``POST /api/v1/ops/{name}``.

        The arguments go through a JSON round trip so that the Python path accepts exactly what
        the HTTP path accepts (no Python-only types).
        """
        wire_args = json.loads(json.dumps(dict(args or {}), allow_nan=False))
        envelope = dispatch(self._registry, self._session, self._principal, name, wire_args)
        return json.loads(json.dumps(envelope, allow_nan=False))  # type: ignore[no-any-return]
