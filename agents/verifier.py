from agents.base import BaseAgent
import logging

logger = logging.getLogger("SentinelAI")

_SYSTEM_PROMPT = """You are a verification specialist for an autonomous incident response system.
Given the original error and the remediation actions that were executed, assess whether the incident is resolved.

Return a JSON object with EXACTLY these fields:
- "resolved": true or false
- "confidence": float 0.0-1.0
- "status": one of: resolved | likely_resolved | pending | unresolved | escalated
- "notes": 1-2 sentence explanation of your assessment
- "recommended_follow_up": follow-up steps if not resolved, empty string if resolved

Consider:
- "success" action statuses are positive resolution signals
- "skipped" means manual execution is still needed — mark as "pending"
- "escalated" means human intervention was triggered
- If only notify/log actions ran, the underlying issue may persist

Respond ONLY with valid JSON."""


class VerifierAgent(BaseAgent):

    def __init__(self, llm_client):
        self.llm = llm_client

    def should_process(self, event, state):
        return "execution_result" in state

    def process(self, event, state):
        logger.info("[Verifier] Verifying resolution with LLM...")

        analysis = state.get("analysis", {})
        exec_results = state.get("execution_results", [])
        exec_result = state.get("execution_result", {})

        if exec_results:
            lines = []
            for r in exec_results:
                action = r.get("action", {})
                lines.append(f"  [{r['status'].upper()}] {action.get('type', '?')}: {r['details']}")
            actions_summary = "\n".join(lines)
        else:
            actions_summary = f"  [{exec_result.get('status', 'unknown').upper()}] {exec_result.get('details', '')}"

        user_message = (
            f"Original Error:  {event.context.get('error', event.event_type)}\n"
            f"Root Cause:      {state.get('root_cause', 'unknown')}\n"
            f"Analysis:        {analysis.get('summary', 'N/A')}\n\n"
            f"Actions Executed:\n{actions_summary}"
        )

        response = self.llm.chat(
            system_prompt=_SYSTEM_PROMPT,
            user_message=user_message,
            json_mode=True,
        )

        if not response or "resolved" not in response:
            simple_status = exec_result.get("status", "unknown")
            response = {
                "resolved": simple_status == "success",
                "confidence": 0.5,
                "status": "resolved" if simple_status == "success" else "pending",
                "notes": exec_result.get("details", ""),
                "recommended_follow_up": "",
            }

        state["resolved"] = response.get("resolved", False)
        state["verification"] = response

        v_status = response.get("status", "unknown")
        confidence = response.get("confidence", 0)

        if response.get("resolved"):
            logger.info(f"[Verifier] Resolved — {v_status} (confidence: {confidence:.0%})")
        else:
            logger.warning(f"[Verifier] Not resolved — {v_status} (confidence: {confidence:.0%})")

        if response.get("recommended_follow_up"):
            logger.info(f"[Verifier] Follow-up: {response['recommended_follow_up']}")

        return state