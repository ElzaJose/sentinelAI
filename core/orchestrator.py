from agents.base import BaseAgent
class Orchestrator:

    def __init__(self, agents):
        self.agents = agents

    def handle_event(self, event, state_store):
        import logging
        logger = logging.getLogger("SentinelAI")
        state = {}

        for agent in self.agents:
            if agent.should_process(event, state):
                state = agent.process(event, state)

        state_store.update({event.event_id: state})
        logger.info(f"[Orchestrator] Pipeline complete for event {event.event_id}")