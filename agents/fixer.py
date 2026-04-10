from agents.base import BaseAgent
from core.executor import Executor
import logging

logger = logging.getLogger("SentinelAI")


class FixerAgent(BaseAgent):

    def __init__(self, executor: Executor):
        self.executor = executor

    def should_process(self, event, state):
        return bool(state.get("actions_queue"))

    def process(self, event, state):
        actions = state["actions_queue"]
        exec_results = []

        logger.info(f"[Fixer] Executing {len(actions)} action(s)...")

        for action in actions:
            action_id = action.get("id", "?")
            action_type = action.get("type", "manual")
            description = action.get("description", "")
            flag = "AUTO" if action.get("auto_executable") else "MANUAL"

            logger.info(f"[Fixer] [{action_id}][{flag}] {action_type}: {description}")

            result = self.executor.execute_action(action, event.context)
            result["action"] = action
            exec_results.append(result)

            logger.info(f"[Fixer]   → {result['status']}: {result['details']}")

        state["execution_results"] = exec_results

        # Summarise for downstream agents
        statuses = {r["status"] for r in exec_results}
        if "success" in statuses:
            state["execution_result"] = {"status": "success", "details": f"Completed {len(exec_results)} action(s)."}
        elif statuses == {"escalated"}:
            state["execution_result"] = {"status": "escalated", "details": "Issue escalated for manual intervention."}
        else:
            state["execution_result"] = {"status": "pending", "details": "Actions logged — manual review required."}

        return state