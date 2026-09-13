"""OpenRouter client: one key reaching models from many vendors, via OpenAI's
API shape (this reuses the openai library, just with a different base URL).

Model names need the vendor prefix (e.g. "anthropic/claude-haiku-4-5"); there's
no per-request workspace header, so the deep health check calls GET /key instead.
"""

import requests
from openai import OpenAI

from src.hrb_chatbot.common.clients.llm_client.base_llm_client import BaseLLMClient
from src.hrb_chatbot.common.config.settings import read_setting, read_url_setting
from src.hrb_chatbot.common.logging.call_logger import log_backend_call
from src.hrb_chatbot.common.logging.logger import get_logger

logger = get_logger("openrouter_client")


class OpenRouterChatClient(BaseLLMClient):
    """Talks to any model hosted by OpenRouter."""

    PROVIDER_NAME = "openrouter"
    ENV_KEY = "OPENROUTER_API_KEY"

    DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
    DEFAULT_MODEL = "openai/gpt-4.1-mini"

    # How many seconds to wait for the free GET /key health check.
    HEALTH_CHECK_TIMEOUT_SECONDS = 10

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        site_url: str | None = None,
        site_name: str | None = None,
    ):
        """Create the client, reading anything not passed in from the .env file."""
        self.api_key = read_setting(api_key, "OPENROUTER_API_KEY")
        self.model = read_setting(model, "OPENROUTER_MODEL", self.DEFAULT_MODEL)
        self.base_url = read_url_setting(base_url, "OPENROUTER_BASE_URL", self.DEFAULT_BASE_URL)
        self.site_url = read_setting(site_url, "OPENROUTER_SITE_URL")
        self.site_name = read_setting(site_name, "OPENROUTER_SITE_NAME")

        if not self.api_key:
            logger.warning("[OPENROUTER] OPENROUTER_API_KEY not set")

        self.extra_headers = self.build_attribution_headers()

        # Only build the OpenAI object when we have a key. Without a key the
        # library raises an error here, which would crash the health endpoints.
        if self.api_key:
            self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        else:
            self.client = None

    def build_attribution_headers(self) -> dict:
        """Build the optional headers that credit this app on OpenRouter's public
        leaderboard - left out entirely when the settings are blank."""
        headers = {}
        if self.site_url:
            headers["HTTP-Referer"] = self.site_url
        if self.site_name:
            headers["X-Title"] = self.site_name
        return headers

    def get_client(self):
        """Return the OpenAI object, or raise a clear error if there is no key."""
        if self.client is None:
            raise RuntimeError(f"{self.ENV_KEY} is not configured")
        return self.client

    def get_configuration(self) -> dict:
        """Return the settings this client is using, with no secrets in it."""
        return {
            "base_url": self.base_url,
            "model": self.model,
            "site_url": self.site_url,
            "site_name": self.site_name,
        }

    def ask(self, question, context=None, temperature=0.0, max_tokens=None):
        """Ask one question and return the answer text."""
        if context:
            message_text = f"Context:\n{context}\n\nQuestion:\n{question}"
        else:
            message_text = question

        with log_backend_call(logger, "openrouter", "chat.ask", model=self.model, temperature=temperature):
            response = self.get_client().chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": message_text}],
                temperature=temperature,
                max_tokens=max_tokens,
                extra_headers=self.extra_headers or None,
            )

        answer = response.choices[0].message.content
        if answer is None:
            return ""
        return answer

    def ask_with_tools(self, messages, tools, temperature=0.0, max_tokens=None, tool_choice="auto"):
        """Ask a question and let the model call tools. Returns the raw reply."""
        with log_backend_call(
            logger, "openrouter", "chat.ask_with_tools", model=self.model, tool_count=len(tools)
        ):
            response = self.get_client().chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                tool_choice=tool_choice,
                temperature=temperature,
                max_tokens=max_tokens,
                extra_headers=self.extra_headers or None,
            )
        return response.model_dump()

    def health_check(self, deep: bool = False) -> dict:
        """Report whether this client is usable. deep=False only checks the key is
        present; deep=True calls GET /key, since /models is public and would 200 for a made-up key."""
        result = {"provider": self.PROVIDER_NAME}
        result.update(self.get_configuration())

        if not self.api_key:
            result["status"] = "unhealthy"
            result["message"] = "API key not configured"
            return result

        if not deep:
            result["status"] = "configured"
            return result

        try:
            response = requests.get(
                self.base_url + "/key",
                headers={"Authorization": "Bearer " + self.api_key},
                timeout=self.HEALTH_CHECK_TIMEOUT_SECONDS,
            )
            # Turns a 401 or 404 reply into an error we can catch below.
            response.raise_for_status()

            key_information = response.json().get("data", {})
            result["status"] = "healthy"
            result["key_label"] = key_information.get("label")
            result["usage"] = key_information.get("usage")
            result["limit"] = key_information.get("limit")
            result["is_free_tier"] = key_information.get("is_free_tier")
        except Exception as error:
            # A health check must never crash - report the problem instead.
            result["status"] = "unhealthy"
            result["message"] = str(error)

        return result
