"""The shared interface that every LLM provider client implements.

Why this file exists
--------------------
OpenAI, Anthropic and OpenRouter all have different Python libraries with
different method names. This class defines the three methods our own code cares
about, so the rest of the project can call `client.ask(...)` without knowing or
caring which provider is behind it.

`ABC` means "Abstract Base Class". A class that inherits from it and does not
write all the `@abstractmethod` methods cannot be created - Python raises an
error straight away. That is a helpful safety net: if you add a new provider and
forget `health_check`, you find out immediately.
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
        """Ask a question and let the model call tools (also called "functions").

        Every provider returns this in the OpenAI response shape, so calling code
        can always read `response["choices"][0]["message"]["tool_calls"]`.
        """
        raise NotImplementedError

    @abstractmethod
    def health_check(self, deep: bool = False) -> dict:
        """Report whether this client is usable.

        deep=False: only check that the API key is present. No network call.
        deep=True: make one real (but free) call to confirm the key works.
        """
        raise NotImplementedError
