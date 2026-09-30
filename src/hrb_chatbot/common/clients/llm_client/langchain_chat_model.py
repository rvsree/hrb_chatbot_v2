"""LangChain-native chat model wrapping this project's own ask() clients (real version conflict rules out langchain-anthropic/aws)."""

from typing import Any

from langchain_core.callbacks.manager import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.messages.ai import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from src.hrb_chatbot.common.clients.llm_client.client_gateway import get_client_gateway
from src.hrb_chatbot.common.clients.llm_client.openai_client import OpenAIChatClient
from src.hrb_chatbot.common.enums import LlmProvider

# Dispatch dict, matching CHUNKING_STRATEGIES/SEARCH_STRATEGIES - a bound
# call on the gateway passed in, not ClientGateway's method pulled off the class.
_PROVIDER_CLIENTS = {
    LlmProvider.OPENAI: lambda gateway: gateway.openai_chat(),
    LlmProvider.ANTHROPIC: lambda gateway: gateway.anthropic_chat(),
    LlmProvider.OPENROUTER: lambda gateway: gateway.openrouter_chat(),
    LlmProvider.BEDROCK: lambda gateway: gateway.bedrock_chat(),
}


def _label_for_context(message: BaseMessage) -> str:
    # Role-labeled so the model can tell who said what in the flattened context string ask() builds.
    if isinstance(message, HumanMessage):
        return f"User: {message.content}"
    if isinstance(message, AIMessage):
        return f"Assistant: {message.content}"
    return str(message.content)


def _split_messages(messages: list[BaseMessage]) -> tuple[str, str | None, str | None]:
    """Last message is the question; earlier SystemMessage -> system_prompt, everything else -> context."""
    if not messages:
        return "", None, None

    *earlier, last = messages
    question = str(last.content)
    if not earlier:
        return question, None, None

    system_parts = [str(message.content) for message in earlier if isinstance(message, SystemMessage)]
    context_parts = [
        _label_for_context(message)
        for message in earlier
        if not isinstance(message, SystemMessage) and message.content
    ]
    system_prompt = "\n\n".join(system_parts) if system_parts else None
    context = "\n\n".join(context_parts) if context_parts else None
    return question, context, system_prompt


class GatewayChatModel(BaseChatModel):
    """Adapts one of this project's own LLM clients to LangChain's BaseChatModel."""

    provider: LlmProvider = LlmProvider.OPENAI
    temperature: float = 0.0
    model_name_override: str | None = None
    max_tokens: int | None = None

    @property
    def _llm_type(self) -> str:
        return f"hrb-gateway-{self.provider}"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        question, context, system_prompt = _split_messages(messages)

        # A model override only means something for OpenAI today - a fresh client, not the shared gateway's cached one.
        if self.model_name_override and self.provider == LlmProvider.OPENAI:
            chat_client = OpenAIChatClient(model=self.model_name_override)
        else:
            chat_client = _PROVIDER_CLIENTS[self.provider](get_client_gateway())

        answer = chat_client.ask(
            question,
            context=context,
            system_prompt=system_prompt,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        # response_metadata carries which model actually answered - a
        # chain ending in StrOutputParser() alone would discard this.
        generation = ChatGeneration(
            message=AIMessage(content=answer, response_metadata={"model": chat_client.model})
        )
        return ChatResult(generations=[generation])
