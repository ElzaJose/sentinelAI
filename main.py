import sys
import time
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("SentinelAI")

# Always resolve config relative to this file's directory
_HERE = Path(__file__).parent


def load_config(path: str = None) -> dict:
    config_path = Path(path) if path else _HERE / "config.yaml"
    try:
        import yaml
        with open(config_path, "r") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        logger.warning(f"Config not found at '{config_path}'. Using defaults.")
        return {}


def build_pipeline(config: dict):
    from core.orchestrator import Orchestrator
    from core.llm_client import LLMClient
    from core.executor import Executor
    from agents.observer import ObserverAgent
    from agents.analyst import AnalystAgent
    from agents.planner import PlannerAgent
    from agents.fixer import FixerAgent
    from agents.verifier import VerifierAgent

    llm = LLMClient(config)
    executor = Executor(config)
    app_config = config.get("app", {})

    return Orchestrator([
        ObserverAgent(),
        AnalystAgent(llm_client=llm, app_config=app_config),
        PlannerAgent(llm_client=llm),
        FixerAgent(executor=executor),
        VerifierAgent(llm_client=llm),
    ])


# ------------------------------------------------------------------ #
# Modes
# ------------------------------------------------------------------ #

def run_test_mode(config: dict):
    """Demo mode: analyse a simulated TimeoutError end-to-end."""
    from core.event_bus import EventBus
    from core.state import StateStore
    from plugins.signals.test_adapter import TestAdapter

    event_bus = EventBus()
    state_store = StateStore()
    orchestrator = build_pipeline(config)

    event = TestAdapter().simulate_failure()
    event_bus.publish(event)
    event = event_bus.consume()

    if event:
        orchestrator.handle_event(event, state_store)
        final = state_store.state.get(event.event_id, {})

        print("\n" + "=" * 50)
        print("  SentinelAI — Final Report")
        print("=" * 50)
        print(f"  Resolved    : {final.get('resolved', False)}")
        print(f"  Root Cause  : {final.get('root_cause', 'unknown')}")
        v = final.get("verification", {})
        if v:
            print(f"  Status      : {v.get('status', '?')}")
            print(f"  Confidence  : {v.get('confidence', 0):.0%}")
            print(f"  Notes       : {v.get('notes', '')}")
            if v.get("recommended_follow_up"):
                print(f"  Follow-up   : {v['recommended_follow_up']}")
        print("=" * 50)


def run_http_mode(config: dict):
    """Start the HTTP API server to receive events from external services."""
    import threading
    from core.event_bus import EventBus
    from core.state import StateStore
    from plugins.adapters.http_adapter import HTTPAdapter

    event_bus = EventBus()
    state_store = StateStore()
    orchestrator = build_pipeline(config)

    def consume_loop():
        while True:
            event = event_bus.consume()
            if event:
                orchestrator.handle_event(event, state_store)
            else:
                time.sleep(0.2)

    threading.Thread(target=consume_loop, daemon=True, name="Consumer").start()

    adapter_cfg = config.get("adapters", {}).get("http", {})
    host = adapter_cfg.get("host", "0.0.0.0")
    port = int(adapter_cfg.get("port", 8080))

    HTTPAdapter(event_bus).run(host=host, port=port)


def run_watch_mode(config: dict):
    """Watch a log file for errors and process them automatically."""
    from core.event_bus import EventBus
    from core.state import StateStore
    from core.llm_client import LLMClient
    from plugins.adapters.log_watcher import LogWatcher

    log_path = config.get("adapters", {}).get("log_watcher", {}).get("log_path", "")
    if not log_path:
        logger.error("No log_path configured. Set adapters.log_watcher.log_path in config.yaml")
        sys.exit(1)

    event_bus = EventBus()
    state_store = StateStore()
    orchestrator = build_pipeline(config)
    llm = LLMClient(config)

    LogWatcher(log_path=log_path, event_bus=event_bus, llm_client=llm).start()

    logger.info("Watching logs — press Ctrl+C to stop.")
    try:
        while True:
            event = event_bus.consume()
            if event:
                orchestrator.handle_event(event, state_store)
            else:
                time.sleep(0.3)
    except KeyboardInterrupt:
        logger.info("Stopped.")


# ------------------------------------------------------------------ #

if __name__ == "__main__":
    _config = load_config()
    _mode = sys.argv[1] if len(sys.argv) > 1 else "test"

    if _mode == "http":
        run_http_mode(_config)
    elif _mode == "watch":
        run_watch_mode(_config)
    else:
        run_test_mode(_config)