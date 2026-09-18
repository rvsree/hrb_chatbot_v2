"""LangChain-native chat model wrapping this project's own ask() clients
(Phase 20) - not langchain-anthropic/langchain-aws, which can't install
here at all (real version conflict - see RAG-ROADMAP.md's Phase 20 entry)."""

from typing import Any

from langchain_core.callbacks.manager import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.messages.ai import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from src.hrb_chatbot.common.clients.llm_client.client_gateway import ClientGateway, get_client_gateway
from src.hrb_chatbot.common.enums import LlmProvider

# Dispatch dict, matching CHUNKING_STRATEGIES/SEARCH_STRATEGIES - provider
# name -> the ClientGateway method returning that provider's client.
_PROVIDER_CLIENTS = {
    LlmProvider.OPENAI: ClientGateway.openai_chat,
    LlmProvider.ANTHROPIC: ClientGateway.anthropic_chat,
    LlmProvider.OPENROUTER: ClientGateway.openrouter_chat,
    LlmProvider.BEDROCK: ClientGateway.bedrock_chat,
}


def _messages_to_question_and_context(messages: list[BaseMessage]) -> tuple[str, str | None]:
    """ask() takes one question string (+ optional context), not a message
    list - the last message is the real question, everything before it
    becomes context."""
    if not messages:
        return "", None

    *earlier, last = messages
    question = str(last.content)
    if not earlier:
        return question, None

    context = "\n\n".join(str(message.content) for message in earlier if message.content)
    return question, context or None


class GatewayChatModel(BaseChatModel):
    """Adapts one of this project's own LLM clients to LangChain's
    BaseChatModel - `provider` picks which one, via client_gateway.py."""

    provider: LlmProvider = LlmProvider.OPENAI
    temperature: float = 0.0

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
        question, context = _messages_to_question_and_context(messages)
        chat_client = _PROVIDER_CLIENTS[self.provider](get_client_gateway())
        answer = chat_client.ask(question, context=context, temperature=self.temperature)
        generation = ChatGeneration(message=AIMessage(content=answer))
        return ChatResult(generations=[generation])
