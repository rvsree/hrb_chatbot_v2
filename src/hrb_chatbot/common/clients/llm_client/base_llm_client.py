"""Shared interface every LLM provider client implements (ask/ask_with_tools/
health_check) - ABC enforces every subclass implements all three."""

from abc import ABC, abstractmethod


class BaseLLMClient(ABC):
    """Every provider client (OpenAI, Anthropic, OpenRouter) inherits from this."""

    # Each subclass overrides these two with its own values.
    PROVIDER_NAME = "base"
    ENV_KEY = ""

    @abstractmethod
    def ask(
        self,
        question: str,
        context: str | None = None,
        system_prompt: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> str:
        """Ask one question and return the answer as plain text.
        system_prompt is sent via each provider's own native mechanism, not folded into the question."""
        raise NotImplementedError

    @abstractmethod
    def ask_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        temperature: float = 0.0,
        max_tokens: int | None = None,
        tool_choice: str = "auto",
    ) -> dict:
        """Ask a question and let the model call tools ("functions"). Every provider
        returns this in the OpenAI response shape (response["choices"][0]["message"]["tool_calls"])."""
        raise NotImplementedError

    @abstractmethod
    def health_check(self) -> dict:
        """Report whether this client is usable - one real, free call, never
        raises (see CODING-STANDARDS.md's "Errors: where they live")."""
        raise NotImplementedError
