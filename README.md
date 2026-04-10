# SentinelAI — Autonomous Error Analysis & Remediation

SentinelAI is an autonomous AIOps agent that receives errors from any application, analyses them with an LLM, generates a remediation plan, attempts to execute it, and verifies resolution — all without manual intervention.

It works with **any error type** from **any language or framework**. You plug it into your app via a Python SDK, an HTTP API, or a log file watcher.

---

## How It Works

```
Your Application
  ├── Python SDK     →
  ├── HTTP POST      →   EventBus → Agent Pipeline → Resolution Report
  └── Log Watcher    →
```

The agent pipeline processes every error through 5 stages:

| Agent | What it does |
|---|---|
| **Observer** | Detects whether the event is an anomaly worth investigating |
| **Analyst** | Uses an LLM to identify root cause, category, and a fix summary |
| **Planner** | Uses an LLM to generate a dynamic, ordered remediation action plan |
| **Fixer** | Executes safe actions automatically; logs risky ones for manual review |
| **Verifier** | Uses an LLM to assess whether the issue was resolved and recommends follow-up |

---

## Quick Start

### 1. Clone & set up

```bash
git clone https://github.com/YOUR_USERNAME/AutonomOps.git
cd AutonomOps/sentinelai

python3 -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure

```bash
cp config.example.yaml config.yaml
```

Open `config.yaml` and add your API key:

```yaml
llm:
  model: gemini-2.0-flash
  api_key: "YOUR_GEMINI_KEY_HERE"
  base_url: https://generativelanguage.googleapis.com/v1beta/openai/
```

> **Free API key:** Get one at [aistudio.google.com/apikey](https://aistudio.google.com/apikey) — 1,500 free requests/day.

### 3. Run the demo

```bash
python main.py
```

This runs a simulated `TimeoutError` through the full pipeline and prints a resolution report.

---

## Integration Options

### Option A — Python SDK

Drop SentinelAI directly into your Python application:

```python
from plugins.sdk.client import SentinelClient

sentinel = SentinelClient(config_path="sentinelai/config.yaml")

# Report any error string
result = sentinel.report_error(
    "ConnectionRefusedError: [Errno 111] Connection refused on port 5432"
)

print(result["resolved"])                          # True / False
print(result["root_cause"])                        # e.g. "database_connection_failure"
print(result["verification"]["recommended_follow_up"])
```

With rich context:

```python
result = sentinel.report_error(
    error="NullPointerException at PaymentService.java:42",
    severity="critical",
    source="payment-service",
    context={
        "traceback": "...",
        "user_id": "u123",
        "transaction_id": "txn-456",
    },
)
```

### Option B — HTTP API

Start the server:

```bash
python main.py http
```

Send any error as a POST request:

```bash
curl -X POST http://localhost:8080/events \
  -H "Content-Type: application/json" \
  -d '{
    "source": "payment-service",
    "error": "java.lang.NullPointerException at PaymentService.java:42",
    "severity": "critical",
    "traceback": "..."
  }'
```

Response:
```json
{ "event_id": "abc-123", "status": "received" }
```

API docs available at `http://localhost:8080/docs` (Swagger UI).

### Option C — Log File Watcher

Watch any log file and auto-process new error lines:

```bash
python main.py watch
```

Set the path in `config.yaml`:

```yaml
adapters:
  log_watcher:
    enabled: true
    log_path: "/var/log/myapp.log"
```

Or from Python:

```python
watcher = sentinel.watch_logs("/var/log/myapp.log")
# Runs in background — call watcher.stop() to halt
```

---

## LLM Providers

SentinelAI uses any OpenAI-compatible endpoint. Update `config.yaml` to switch:

| Provider | Free Tier | `model` | `base_url` |
|---|---|---|---|
| **Gemini** (recommended) | ✅ 1,500 req/day | `gemini-2.0-flash` | `https://generativelanguage.googleapis.com/v1beta/openai/` |
| **Ollama** (local) | ✅ Unlimited | `llama3` | `http://localhost:11434/v1` |
| **OpenAI** | ❌ Paid | `gpt-4o-mini` | `https://api.openai.com/v1` |

---

## Safety & Execution Control

By default, SentinelAI **never runs shell commands automatically**. It logs suggested commands for manual review.

To allow automatic execution of specific trusted commands, update `config.yaml`:

```yaml
safety:
  auto_execute: false   # keep false for production
  allowed_shell_commands:
    - "docker restart"
    - "pm2 restart"
    - "systemctl restart nginx"
  command_timeout_seconds: 30
```

---

## Project Structure

```
sentinelai/
├── main.py                    # Entry point (test / http / watch modes)
├── config.yaml                # Your config (gitignored)
├── config.example.yaml        # Safe template to commit
├── requirements.txt
│
├── core/
│   ├── llm_client.py          # OpenAI-compatible LLM wrapper
│   ├── orchestrator.py        # Runs agents sequentially
│   ├── executor.py            # Executes remediation actions
│   ├── event_bus.py           # In-process event queue
│   ├── event.py               # Event data model
│   └── state.py               # Shared pipeline state store
│
├── agents/
│   ├── base.py                # Abstract base class
│   ├── observer.py            # Anomaly detection
│   ├── analyst.py             # LLM root-cause analysis
│   ├── planner.py             # LLM remediation planning
│   ├── fixer.py               # Action execution
│   └── verifier.py            # LLM resolution verification
│
└── plugins/
    ├── adapters/
    │   ├── log_watcher.py     # Watches log files for errors
    │   └── http_adapter.py    # FastAPI HTTP endpoint
    ├── sdk/
    │   └── client.py          # Python SDK for app integration
    └── signals/
        └── test_adapter.py    # Demo event simulator
```

---

## Requirements

- Python 3.10+
- A Gemini, OpenAI, or Ollama API key

```
openai>=1.0.0
pyyaml>=6.0
fastapi>=0.100.0
uvicorn>=0.22.0
```

---

## Security Notes

- **Never commit `config.yaml`** — it contains your API key. It is gitignored by default.
- Shell command execution is **off by default** (`auto_execute: false`).
- Only add commands to `allowed_shell_commands` that are safe and idempotent.

---

## License

MIT
