# agents/analyst.py
# agents/analyst.py
from agents.base import BaseAgent
import logging

logger = logging.getLogger("SentinelAI")

_SYSTEM_PROMPT = """You are an expert Site Reliability Engineer and DevOps specialist.
Analyze the error event provided and identify its root cause.

Return a JSON object with EXACTLY these fields:
- "root_cause": a short snake_case label (e.g. "database_connection_failure", "memory_leak", "null_pointer_exception")
- "category": one of: infrastructure | application | network | security | data | configuration | unknown
- "summary": 1-2 sentence human-readable explanation of what went wrong
- "confidence": float 0.0-1.0 indicating your confidence in the analysis
- "suggested_resolution": plain text summary of what should be done to fix it

If the application context is provided, use it to give domain-specific analysis.
Respond ONLY with valid JSON."""


class AnalystAgent(BaseAgent):

    def __init__(self, llm_client, app_config: dict = None):
        self.llm = llm_client
        self.app_context = (app_config or {}).get("description", "")

    def should_process(self, event, state):
        return state.get("anomaly_detected", False)

    def process(self, event, state):
        logger.info("[Analyst] Analyzing failure with LLM...")

        user_message = self._build_context(event)

        response = self.llm.chat(
            system_prompt=_SYSTEM_PROMPT,
            user_message=user_message,
            json_mode=True,
        )

        if not response or "root_cause" not in response:
            logger.warning("[Analyst] LLM returned invalid response. Using fallback.")
            response = {
                "root_cause": "unknown",
                "category": "unknown",
                "summary": "Unable to automatically analyze the error.",
                "confidence": 0.0,
                "suggested_resolution": "Manual investigation required.",
            }

        state["root_cause"] = response["root_cause"]
        state["analysis"] = response

        logger.info(
            f"[Analyst] Root cause: {response['root_cause']} "
            f"(confidence: {response.get('confidence', '?')})"
        )
        logger.info(f"[Analyst] Summary: {response.get('summary', '')}")

        return state

    def _build_context(self, event) -> str:
        parts = [
            f"Error Source: {event.source}",
            f"Event Type:   {event.event_type}",
            f"Severity:     {event.severity}",
        ]

        if self.app_context:
            parts.append(f"Application:  {self.app_context}")

        ctx = event.context or {}
        if ctx.get("error"):
            parts.append(f"Error:        {ctx['error']}")
        if ctx.get("traceback"):
            parts.append(f"Traceback:\n{ctx['traceback']}")
        if ctx.get("log_line"):
            parts.append(f"Log Line:     {ctx['log_line']}")

        for key, value in ctx.items():
            if key not in ("error", "traceback", "log_line"):
                parts.append(f"{key}: {value}")

        return "\n".join(parts)