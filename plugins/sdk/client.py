# plugins/sdk/client.py
"""
SentinelAI Python SDK
=====================
Drop-in client to integrate SentinelAI into any Python application.

Quick start
-----------
    from plugins.sdk.client import SentinelClient

    # Point to your config file (or pass a dict)
    sentinel = SentinelClient(config_path="sentinelai/config.yaml")

    # Report any error string — gets analysed, planned, fixed, and verified
    result = sentinel.report_error(
        "ConnectionRefusedError: [Errno 111] Connection refused on port 5432"
    )

    # Or with richer context
    result = sentinel.report_error(
        error="java.lang.NullPointerException at PaymentService.java:42",
        severity="critical",
        source="payment-service",
        context={"user_id": "u123", "transaction_id": "txn-456"},
    )

    print(result["resolved"])       # True / False
    print(result["verification"])   # LLM verdict + follow-up steps

Watch a log file
----------------
    watcher = sentinel.watch_logs("/var/log/myapp.log")
    # ... watcher runs in background ...
    watcher.stop()
"""

import time
import threading
import logging

logger = logging.getLogger("SentinelAI")


class SentinelClient:
    """
    Self-contained SentinelAI client.  Builds the full agent pipeline
    from a config file (or dict) and exposes a simple API.
    """

    def __init__(self, config_path: str = "sentinelai/config.yaml", config: dict = None):
        self.config = config if config is not None else self._load_config(config_path)
        self._build_pipeline()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def report_error(
        self,
        error: str,
        severity: str = "error",
        source: str = "sdk",
        event_type: str = "reported_error",
        context: dict = None,
    ) -> dict:
        """
        Report an error for autonomous analysis and remediation.

        Parameters
        ----------
        error     : The error message / exception string.
        severity  : "error" (default) | "critical" | "warning"
        source    : Identifier for the calling service/component.
        context   : Optional dict with extra fields (traceback, service, etc.)

        Returns
        -------
        The final pipeline state dict, including:
          - resolved    : bool
          - root_cause  : str
          - analysis    : dict (LLM analysis)
          - verification: dict (LLM verification + follow-up)
        """
        from core.event import Event

        ctx = dict(context or {})
        ctx["error"] = error

        event = Event(
            source=source,
            event_type=event_type,
            severity=severity,
            context=ctx,
        )
        self._event_bus.publish(event)

        consumed = self._event_bus.consume()
        if consumed:
            self._orchestrator.handle_event(consumed, self._state_store)
            return self._state_store.state.get(consumed.event_id, {})
        return {}

    def watch_logs(self, log_path: str, source_name: str = None):
        """
        Start watching a log file in the background.
        New error lines are automatically processed through the pipeline.

        Returns the LogWatcher instance (call .stop() to halt watching).
        """
        from plugins.adapters.log_watcher import LogWatcher
        from core.llm_client import LLMClient

        llm = LLMClient(self.config)
        watcher = LogWatcher(
            log_path=log_path,
            event_bus=self._event_bus,
            source_name=source_name or log_path,
            llm_client=llm,
        )
        watcher.start()

        # Background consumer so pipeline processes log events continuously
        self._start_consumer()
        return watcher

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _load_config(path: str) -> dict:
        from pathlib import Path
        config_path = Path(path) if Path(path).is_absolute() else Path(__file__).parent.parent.parent / path
        try:
            import yaml
            with open(config_path, "r") as f:
                return yaml.safe_load(f) or {}
        except FileNotFoundError:
            logger.warning(f"[SDK] Config not found at '{config_path}'. Using defaults.")
            return {}

    def _build_pipeline(self):
        from core.event_bus import EventBus
        from core.state import StateStore
        from core.orchestrator import Orchestrator
        from core.llm_client import LLMClient
        from core.executor import Executor
        from agents.observer import ObserverAgent
        from agents.analyst import AnalystAgent
        from agents.planner import PlannerAgent
        from agents.fixer import FixerAgent
        from agents.verifier import VerifierAgent

        llm = LLMClient(self.config)
        executor = Executor(self.config)
        app_config = self.config.get("app", {})

        self._event_bus = EventBus()
        self._state_store = StateStore()
        self._orchestrator = Orchestrator([
            ObserverAgent(),
            AnalystAgent(llm_client=llm, app_config=app_config),
            PlannerAgent(llm_client=llm),
            FixerAgent(executor=executor),
            VerifierAgent(llm_client=llm),
        ])
        self._consumer_started = False

    def _start_consumer(self):
        """Start background thread that drains the EventBus continuously."""
        if self._consumer_started:
            return
        self._consumer_started = True

        def loop():
            while True:
                event = self._event_bus.consume()
                if event:
                    self._orchestrator.handle_event(event, self._state_store)
                else:
                    time.sleep(0.3)

        t = threading.Thread(target=loop, daemon=True, name="SentinelConsumer")
        t.start()
