"""The shared interface that every LLM provider client implements.

OpenAI, Anthropic and OpenRouter each have different client libraries; this
defines the three methods the rest of the project relies on (`ask`,
`ask_with_tools`, `health_check`) so calling code doesn't need to know which
provider is behind it. ABC enforces that a subclass implements all of them.
"""

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
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> str:
        """Ask one question and return the answer as plain text."""
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
        """Report whether this client is usable: makes one real, free call to the
        provider and reports the outcome - never raises, see BaseLLMClient's own
        module docstring and CODING-STANDARDS.md's "Errors: where they live" section."""
        raise NotImplementedError
