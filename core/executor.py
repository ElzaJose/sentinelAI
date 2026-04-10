import logging
import subprocess
import logging

logger = logging.getLogger("SentinelAI")


class Executor:
    """
    Executes LLM-generated remediation actions.

    Shell commands run automatically only when:
      - safety.auto_execute: true  in config.yaml, OR
      - the command prefix is listed in safety.allowed_shell_commands

    Otherwise, commands are logged as suggestions and skipped with
    status "skipped" so the operator can review and run manually.
    """

    def __init__(self, config: dict = None):
        safety = (config or {}).get("safety", {})
        self.auto_execute = bool(safety.get("auto_execute", False))
        self.allowed_commands = list(safety.get("allowed_shell_commands", []))
        self.timeout = int(safety.get("command_timeout_seconds", 30))

    def execute_action(self, action: dict, context: dict) -> dict:
        action_type = action.get("type", "manual")

        dispatch = {
            "shell_command":   self._run_shell,
            "service_restart": self._restart_service,
            "notify":          self._notify,
            "escalate":        self._escalate,
            "config_change":   self._config_change,
            "manual":          self._manual,
        }

        handler = dispatch.get(action_type, self._manual)
        return handler(action, context)

    # ------------------------------------------------------------------ #

    def _run_shell(self, action: dict, context: dict) -> dict:
        command = (action.get("command") or "").strip()
        if not command:
            return {"status": "skipped", "details": "No command specified."}

        auto_ok = action.get("auto_executable", False)
        in_allowlist = any(command.startswith(prefix) for prefix in self.allowed_commands)
        approved = self.auto_execute or auto_ok or in_allowlist

        if not approved:
            logger.warning(f"[Executor] Command requires manual approval: {command}")
            return {
                "status": "skipped",
                "details": f"Suggested command (run manually): {command}",
                "suggested_command": command,
            }

        logger.info(f"[Executor] Running: {command}")
        try:
            proc = subprocess.run(
                command, shell=True, capture_output=True,
                text=True, timeout=self.timeout,
            )
            if proc.returncode == 0:
                output = proc.stdout.strip() or "Command completed successfully."
                return {"status": "success", "details": output}
            error_out = proc.stderr.strip() or f"Exit code {proc.returncode}"
            return {"status": "failed", "details": error_out}
        except subprocess.TimeoutExpired:
            return {"status": "failed", "details": f"Command timed out after {self.timeout}s."}
        except Exception as e:
            return {"status": "failed", "details": str(e)}

    def _restart_service(self, action: dict, context: dict) -> dict:
        service = action.get("service") or context.get("service", "")
        if not service:
            return {"status": "skipped", "details": "No service name provided; restart manually."}
        cmd = {"command": f"sudo systemctl restart {service}", "auto_executable": action.get("auto_executable", False)}
        return self._run_shell(cmd, context)

    def _notify(self, action: dict, context: dict) -> dict:
        msg = action.get("description", "Incident notification")
        logger.info(f"[Executor] NOTIFICATION: {msg}")
        # Extend here to integrate Slack / PagerDuty / email webhooks from config
        return {"status": "success", "details": f"Notification logged: {msg}"}

    def _escalate(self, action: dict, context: dict) -> dict:
        msg = action.get("description", "Escalation triggered")
        logger.warning(f"[Executor] ESCALATION: {msg}")
        return {"status": "escalated", "details": msg}

    def _config_change(self, action: dict, context: dict) -> dict:
        msg = action.get("description", "Configuration change needed")
        logger.info(f"[Executor] CONFIG CHANGE (manual review required): {msg}")
        return {"status": "skipped", "details": f"Config change requires manual review: {msg}"}

    def _manual(self, action: dict, context: dict) -> dict:
        msg = action.get("description", "Manual action required")
        logger.info(f"[Executor] MANUAL ACTION: {msg}")
        return {"status": "skipped", "details": f"Manual action: {msg}"}