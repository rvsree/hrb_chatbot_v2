"""One place that hands out every client the project uses.

Why this exists
---------------
Without it, every module that needed a model would create its own
OpenAIChatClient, its own TavilyClient, and so on. That means the same settings get read over and over, and
if you ever need to change how a client is built you have to find every copy.

How to use it
-------------
    from src.hrb_chatbot.common.clients.llm_client.client_gateway import get_client_gateway

    gateway = get_client_gateway()
    answer = gateway.openai_chat().ask("What is 2+2?")

Each client is created the first time you ask for it and then kept, so calling
gateway.openai_chat() a hundred times still only builds one client. Holding on to
an object like this instead of rebuilding it is called caching.
"""

from src.hrb_chatbot.common.clients.llm_client.anthropic_client import AnthropicChatClient
from src.hrb_chatbot.common.clients.llm_client.bedrock_client import BedrockChatClient
from src.hrb_chatbot.common.clients.llm_client.open_router_client import OpenRouterChatClient
from src.hrb_chatbot.common.clients.llm_client.openai_client import (
    OpenAIChatClient,
    OpenAIEmbeddingClient,
)
from src.hrb_chatbot.common.clients.web_client.tavily_client import TavilyClient


class ClientGateway:
    """Creates each client once, then returns that same client every time."""

    def __init__(self):
        """Start with no clients built yet.

        Each one stays None until somebody actually asks for it. This is called
        "lazy" creation, and it matters here: if we built all five up front, a
        project that only needs Tavily would still print warnings about missing
        OpenAI keys.
        """
        self.openai_chat_client = None
        self.openai_embedding_client = None
        self.anthropic_chat_client = None
        self.openrouter_chat_client = None
        self.bedrock_chat_client = None
        self.tavily_search_client = None

    def openai_chat(self) -> OpenAIChatClient:
        """Return the shared OpenAI chat client, building it on first use."""
        if self.openai_chat_client is None:
            self.openai_chat_client = OpenAIChatClient()
        return self.openai_chat_client

    def openai_embedding(self) -> OpenAIEmbeddingClient:
        """Return the shared OpenAI embedding client, building it on first use."""
        if self.openai_embedding_client is None:
            self.openai_embedding_client = OpenAIEmbeddingClient()
        return self.openai_embedding_client

    def anthropic_chat(self) -> AnthropicChatClient:
        """Return the shared Anthropic chat client, building it on first use."""
        if self.anthropic_chat_client is None:
            self.anthropic_chat_client = AnthropicChatClient()
        return self.anthropic_chat_client

    def openrouter_chat(self) -> OpenRouterChatClient:
        """Return the shared OpenRouter chat client, building it on first use."""
        if self.openrouter_chat_client is None:
            self.openrouter_chat_client = OpenRouterChatClient()
        return self.openrouter_chat_client

    def bedrock_chat(self) -> BedrockChatClient:
        """Return the shared Bedrock client, building it on first use."""
        if self.bedrock_chat_client is None:
            self.bedrock_chat_client = BedrockChatClient()
        return self.bedrock_chat_client

    def tavily(self) -> TavilyClient:
        """Return the shared Tavily search client, building it on first use."""
        if self.tavily_search_client is None:
            self.tavily_search_client = TavilyClient()
        return self.tavily_search_client


# The single gateway shared by the whole program.
# It starts as None and is built the first time get_client_gateway() is called.
# The leading underscore is a Python convention meaning "this belongs to this
# file - please use the function below instead of touching it directly".
_shared_gateway = None


def get_client_gateway() -> ClientGateway:
    """Return the one shared ClientGateway, creating it on the first call."""
    global _shared_gateway

    if _shared_gateway is None:
        _shared_gateway = ClientGateway()

    return _shared_gateway


def reset_client_gateway():
    """Throw away the shared gateway so the next call builds a fresh one.

    Only needed in tests: the clients read their settings once, when they are
    built, so a test that changes an environment variable must clear the cache
    for the change to have any effect.
    """
    global _shared_gateway
    _shared_gateway = None
