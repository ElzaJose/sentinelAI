from agents.base import BaseAgent
import logging

logger = logging.getLogger("SentinelAI")

_SYSTEM_PROMPT = """You are an expert Site Reliability Engineer creating an incident remediation plan.
Given an error analysis, generate an ordered list of actions to resolve the issue.

Return a JSON object with:
- "actions": list of action objects (3-5 max), each with:
    - "id": sequential integer starting at 1
    - "type": one of: shell_command | service_restart | notify | escalate | config_change | manual
    - "description": human-readable explanation of what this action does
    - "command": (shell_command type only) the exact shell command to run
    - "service": (service_restart type only) name of the service to restart
    - "auto_executable": true if safe to run automatically, false if risky or needs human review

Guidelines:
- Order from safest/fastest to most disruptive
- Mark as auto_executable: false anything that could cause downtime or data loss
- Always include a notify or escalate action if the issue is severe
- If the fix is unclear, use type "manual" with step-by-step instructions in "description"

Respond ONLY with valid JSON."""


class PlannerAgent(BaseAgent):

    def __init__(self, llm_client):
        self.llm = llm_client

    def should_process(self, event, state):
        return "root_cause" in state

    def process(self, event, state):
        logger.info("[Planner] Generating remediation plan with LLM...")

        analysis = state.get("analysis", {})
        user_message = (
            f"Root Cause:          {state.get('root_cause', 'unknown')}\n"
            f"Category:            {analysis.get('category', 'unknown')}\n"
            f"Summary:             {analysis.get('summary', 'N/A')}\n"
            f"Suggested Fix:       {analysis.get('suggested_resolution', 'N/A')}\n"
            f"Event Source:        {event.source}\n"
            f"Error Context:       {event.context}"
        )

        response = self.llm.chat(
            system_prompt=_SYSTEM_PROMPT,
            user_message=user_message,
            json_mode=True,
        )

        actions = response.get("actions", []) if response else []

        if not actions:
            logger.warning("[Planner] No actions generated. Adding escalate fallback.")
            actions = [
                {
                    "id": 1,
                    "type": "escalate",
                    "description": "Manual investigation required — LLM could not generate a plan.",
                    "auto_executable": False,
                }
            ]

        state["actions_queue"] = actions
        state["current_attempt"] = 0

        logger.info(f"[Planner] {len(actions)} action(s) planned:")
        for a in actions:
            flag = "AUTO" if a.get("auto_executable") else "MANUAL"
            logger.info(f"  [{a.get('id')}][{flag}] {a.get('type')}: {a.get('description')}")

        return state