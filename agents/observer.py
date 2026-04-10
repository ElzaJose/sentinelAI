# agents/observer.py

from agents.base import BaseAgent
import logging

logger = logging.getLogger("SentinelAI")


class ObserverAgent(BaseAgent):
    """Always runs first. Flags whether the event warrants downstream analysis."""

    def should_process(self, event, state):
        return True

    def process(self, event, state):
        logger.info(f"[Observer] Event: source={event.source} type={event.event_type} severity={event.severity}")

        if event.severity in ("error", "critical"):
            state["anomaly_detected"] = True
            logger.warning("[Observer] Anomaly detected — escalating to analyst.")
        else:
            state["anomaly_detected"] = False
            logger.info("[Observer] No anomaly.")

        return state