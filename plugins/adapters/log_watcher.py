# plugins/adapters/log_watcher.py
"""
Watches any log file for new error lines and publishes them as Events.

Supports any log format automatically:
- Uses regex heuristics to detect severity from log lines
- Optionally uses the LLM to parse structured context from arbitrary formats
  (JSON logs, plain text, syslog, custom formats) — set llm_client to enable
"""

import re
import time
import threading
import logging
from core.event import Event

logger = logging.getLogger("SentinelAI")

# Ordered severity patterns (highest → lowest)
_SEVERITY_PATTERNS = [
    (re.compile(r'\b(CRITICAL|FATAL)\b', re.IGNORECASE), "critical"),
    (re.compile(r'\b(ERROR)\b|Exception:|Error:', re.IGNORECASE), "error"),
    (re.compile(r'\b(WARN(?:ING)?)\b', re.IGNORECASE), "warning"),
]

# LLM prompt for structured log parsing
_PARSE_PROMPT = """Parse this log line into a JSON object.
Include only the fields that are present:
- "error": the error message or exception name (required)
- "component": the module/service that logged this
- "timestamp": timestamp string if present

Return ONLY valid JSON. If you cannot identify an error message, set "error" to the full line."""


class LogWatcher:
    """
    Watches a log file for new error/critical lines and emits Event objects
    onto the EventBus for the SentinelAI pipeline to process.

    Usage:
        watcher = LogWatcher("/var/log/app.log", event_bus, llm_client=llm)
        watcher.start()          # non-blocking background thread
        ...
        watcher.stop()
    """

    def __init__(
        self,
        log_path: str,
        event_bus,
        source_name: str = None,
        llm_client=None,
    ):
        self.log_path = log_path
        self.event_bus = event_bus
        self.source_name = source_name or log_path
        self.llm = llm_client
        self._running = False
        self._thread = None

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._watch, daemon=True, name="LogWatcher")
        self._thread.start()
        logger.info(f"[LogWatcher] Started watching: {self.log_path}")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        logger.info("[LogWatcher] Stopped.")

    # ------------------------------------------------------------------ #

    def _watch(self):
        try:
            with open(self.log_path, "r", errors="replace") as f:
                f.seek(0, 2)  # Jump to end of file — only watch new lines
                while self._running:
                    line = f.readline()
                    if line:
                        self._process_line(line.rstrip())
                    else:
                        time.sleep(0.3)
        except FileNotFoundError:
            logger.error(f"[LogWatcher] File not found: {self.log_path}")
        except Exception as e:
            logger.error(f"[LogWatcher] Unexpected error: {e}")

    def _process_line(self, line: str):
        if not line:
            return

        severity = self._detect_severity(line)
        if severity not in ("error", "critical"):
            return

        context = self._parse_line(line)

        event = Event(
            source=self.source_name,
            event_type="log_error",
            severity=severity,
            context=context,
        )
        self.event_bus.publish(event)
        logger.info(f"[LogWatcher] Event published — {line[:100]}")

    def _detect_severity(self, line: str) -> str:
        for pattern, severity in _SEVERITY_PATTERNS:
            if pattern.search(line):
                return severity
        return "info"

    def _parse_line(self, line: str) -> dict:
        """Parse a log line into structured context. Uses LLM when available."""
        if self.llm:
            try:
                result = self.llm.chat(
                    system_prompt=_PARSE_PROMPT,
                    user_message=line,
                    json_mode=True,
                )
                if isinstance(result, dict) and result.get("error"):
                    result["log_line"] = line
                    return result
            except Exception:
                pass  # Fall through to regex

        return self._regex_parse(line)

    @staticmethod
    def _regex_parse(line: str) -> dict:
        context = {"log_line": line, "error": line}
        # Try to extract a named exception / error class
        m = re.search(
            r'([A-Z][a-zA-Z]+(?:Error|Exception|Fault|Warning)[:\s].{0,120})', line
        )
        if m:
            context["error"] = m.group(1).strip()
        return context
