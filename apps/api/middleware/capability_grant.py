"""Capability grant middleware — identity policy stub.

Replaces the Bearer-token-only auth from the Assistant-class Bootstrap
with a placeholder for Mind-class capability grants.

In the full implementation (Phase 3), this becomes:
- Principal resolution from request context
- Capability grant lookup with purpose, scope, classification ceiling, budget, expiry
- Policy decision point (deterministic, not model-driven)
- Kill switch enforcement

For now, this is a default-deny stub that logs every request for audit.
"""

from __future__ import annotations

import logging
from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger("animus_mind.policy")


class CapabilityGrantMiddleware(BaseHTTPMiddleware):
    """Default-deny middleware with audit logging.

    All requests are logged. In Phase 3, this checks:
    1. Principal identity (device, service, agent, connector)
    2. Capability grant for the requested scope
    3. Approval freshness for R3/R4 actions
    4. Kill switch state
    """

    async def dispatch(self, request: Request, call_next: Callable):
        # Phase 3: replace with real policy decision point
        logger.info(
            f"Request: {request.method} {request.url.path} "
            f"client={request.client.host if request.client else 'unknown'}"
        )

        # Default deny for R3/R4 endpoints until policy module exists
        if self._is_r3_or_r4(request.url.path) and not self._has_local_bypass(request):
            return JSONResponse(
                status_code=403,
                content={
                    "error": "policy.denied",
                    "message": "R3/R4 actions require a capability grant. Identity policy module not yet implemented (Phase 3).",
                    "path": request.url.path,
                },
            )

        response = await call_next(request)
        return response

    def _is_r3_or_r4(self, path: str) -> bool:
        """Heuristic: actions that modify canonical state are R3/R4.

        R1 = read, R2 = idempotent write to projection
        R3 = consequential write to canonical store
        R4 = external action or deletion
        """
        r3_r4_prefixes = (
            "/api/conversations/messages",  # creates messages
            "/api/objects",                 # creates/updates objects
            "/api/agents/execute",          # runs agent contracts
            "/api/actions",                 # external tool calls
        )
        return any(path.startswith(p) for p in r3_r4_prefixes)

    def _has_local_bypass(self, request: Request) -> bool:
        """Local development bypass — to be removed in limited/general promotion.

        Mind-class architecture forbids unconditional local bypass.
        This is a concession for Phase 0–2 development only.
        """
        client = request.client
        if client and client.host in ("127.0.0.1", "localhost", "::1"):
            # Log the bypass for audit
            logger.warning(f"LOCAL BYPASS used for {request.url.path} — remove before Phase 3")
            return True
        return False
