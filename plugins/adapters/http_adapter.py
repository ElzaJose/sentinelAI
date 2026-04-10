# plugins/adapters/http_adapter.py
"""
FastAPI-based HTTP adapter for SentinelAI.

Exposes two endpoints:
  GET  /health       — liveness check
  POST /events       — submit any error for analysis

Flexible payload — accepts any JSON shape:
  {
    "error": "NullPointerException at PaymentService.java:42",
    "severity": "critical",
    "source": "payment-service",
    "service": "payment-service",
    "traceback": "...",
    "...any extra fields..."
  }

Start:
  adapter = HTTPAdapter(event_bus)
  adapter.run(host="0.0.0.0", port=8080)

Or run via main.py:
  python main.py http
"""

import logging
from core.event import Event

logger = logging.getLogger("SentinelAI")

# Fields lifted to top-level event properties; the rest go into context
_TOP_LEVEL = {"source", "event_type", "type", "severity"}
# Fields copied into context if present at the root level
_CONTEXT_FIELDS = {"error", "message", "traceback", "log_line", "service", "component", "stack_trace"}


class HTTPAdapter:
    """Wraps a FastAPI application that feeds events to the SentinelAI EventBus."""

    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.app = self._build_app()

    def _build_app(self):
        try:
            from fastapi import FastAPI, Request, HTTPException
            from fastapi.responses import JSONResponse
        except ImportError:
            raise ImportError(
                "fastapi is required for the HTTP adapter. "
                "Run: pip install fastapi uvicorn"
            )

        app = FastAPI(
            title="SentinelAI",
            description="Autonomous error analysis and remediation API",
            version="2.0.0",
        )

        @app.get("/health")
        async def health():
            return {"status": "ok", "service": "SentinelAI"}

        @app.post("/events", status_code=202)
        async def receive_event(request: Request):
            try:
                body = await request.json()
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid JSON body")

            if not isinstance(body, dict):
                raise HTTPException(status_code=400, detail="JSON body must be an object")

            # --- Extract top-level event fields ---
            source = body.get("source", "http_client")
            event_type = body.get("event_type") or body.get("type") or "error_report"
            severity = body.get("severity", "error")

            # --- Build context from recognised and extra fields ---
            context = dict(body.get("context") or {})

            # Promote known context fields from the root payload
            for field in _CONTEXT_FIELDS:
                if field in body and field not in context:
                    context[field] = body[field]

            # Also catch "message" as the primary error if "error" not set
            if not context.get("error"):
                context["error"] = body.get("message") or body.get("error") or ""

            # Carry any other custom fields into context
            reserved = _TOP_LEVEL | _CONTEXT_FIELDS | {"context"}
            for key, value in body.items():
                if key not in reserved and key not in context:
                    context[key] = value

            event = Event(
                source=source,
                event_type=event_type,
                severity=severity,
                context=context,
            )
            self.event_bus.publish(event)

            logger.info(f"[HTTPAdapter] Received event {event.event_id} from {source}")
            return {"event_id": event.event_id, "status": "received"}

        return app

    def run(self, host: str = "0.0.0.0", port: int = 8080):
        try:
            import uvicorn
        except ImportError:
            raise ImportError(
                "uvicorn is required to run the HTTP adapter. "
                "Run: pip install uvicorn"
            )
        logger.info(f"[HTTPAdapter] Listening on http://{host}:{port}")
        uvicorn.run(self.app, host=host, port=port, log_level="warning")
