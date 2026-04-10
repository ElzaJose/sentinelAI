# core/llm_client.py
import os
import json
import logging

logger = logging.getLogger("SentinelAI")


class LLMClient:
    """
    OpenAI-compatible LLM client.
    Works with OpenAI, Azure OpenAI, Ollama, or any compatible endpoint.

    Configure via config.yaml:
        llm:
          model: gpt-4o-mini
          api_key: ${OPENAI_API_KEY}
          base_url: https://api.openai.com/v1

    For Ollama (local, free):
          model: llama3
          api_key: ollama
          base_url: http://localhost:11434/v1
    """

    def __init__(self, config: dict):
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("openai package required. Run: pip install openai")

        llm_cfg = config.get("llm", {})

        raw_key = llm_cfg.get("api_key") or os.getenv("OPENAI_API_KEY", "")
        api_key = self._resolve_env(raw_key)

        base_url = llm_cfg.get("base_url", "https://api.openai.com/v1")
        self.model = llm_cfg.get("model", "gpt-4o-mini")
        self.temperature = float(llm_cfg.get("temperature", 0.2))

        self.client = OpenAI(api_key=api_key or "sk-placeholder", base_url=base_url)

    @staticmethod
    def _resolve_env(value) -> str:
        """Resolve ${ENV_VAR} placeholders in config values."""
        if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            env_var = value[2:-1]
            resolved = os.getenv(env_var, "")
            if not resolved:
                logger.warning(f"[LLM] Environment variable '{env_var}' is not set.")
            return resolved
        return str(value) if value else ""

    def chat(self, system_prompt: str, user_message: str, json_mode: bool = False):
        """
        Send a chat completion request.
        If json_mode=True, instructs the model to return JSON and parses the response.
        Returns a dict (json_mode=True) or a string.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
        }

        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            response = self.client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content

            if json_mode:
                return json.loads(content)
            return content

        except json.JSONDecodeError as e:
            logger.error(f"[LLM] Failed to parse JSON response: {e}")
            return {}
        except Exception as e:
            logger.error(f"[LLM] API call failed: {e}")
            return {} if json_mode else ""
