"""Anthropic client: chat and tool calling with Claude models.

Base URL
--------
The correct base URL is https://api.anthropic.com - the host name ONLY, with no
"/v1" on the end. This is the opposite of OpenAI. The Anthropic library adds the
whole path itself ("/v1/messages"), so if you put "/v1" in the base URL the
request goes to "/v1/v1/messages" and returns 404.

Workspace
---------
A workspace is Anthropic's way of separating environments (dev, prod, and so on)
and tracking spend per environment.

* If your API key was created inside one workspace, you do not need to do
  anything - leave ANTHROPIC_WORKSPACE_ID blank in .env.
* If your API key is a multi-workspace key (the Console shows "All workspaces"),
  then EVERY request must include the workspace id or it fails. Put the id in
  ANTHROPIC_WORKSPACE_ID and this client sends it as the "anthropic-workspace-id"
  header.

Copy the id from the ID column in Console -> Settings -> Workspaces. It looks
like "wrkspc_01JwQvzr7rXLA5AGx3HKfFUJ" - it is not the workspace's name.

Temperature
-----------
Anthropic has deprecated the `temperature` setting: models released after Claude
Opus 4.6 reject any value other than 1.0, and version 1.2 of the anthropic
library removed the argument from messages.create() altogether. Passing it now
raises "unexpected keyword argument 'temperature'".

So the `temperature` argument on the methods below is accepted (because the
shared BaseLLMClient interface has it, and OpenAI still uses it) but is not sent
to Anthropic. The modern replacement is `output_config.effort`, which takes
"low", "medium", "high", "xhigh" or "max" instead of a number.
"""

import anthropic

from src.hrb_chatbot.common.clients.llm_client.base_llm_client import BaseLLMClient
from src.hrb_chatbot.common.config.settings import read_setting, read_url_setting
from src.hrb_chatbot.common.logging.call_logger import log_backend_call
from src.hrb_chatbot.common.logging.logger import get_logger

logger = get_logger("anthropic_client")


class AnthropicChatClient(BaseLLMClient):
    """Talks to Anthropic's Claude models."""

    PROVIDER_NAME = "anthropic"
    ENV_KEY = "ANTHROPIC_API_KEY"

    # Host name only - see the note at the top of this file.
    DEFAULT_BASE_URL = "https://api.anthropic.com"
    DEFAULT_MODEL = "claude-haiku-4-5"

    # Real workspace ids always start with this. Used to spot a pasted name.
    WORKSPACE_ID_PREFIX = "wrkspc_"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        workspace_id: str | None = None,
        base_url: str | None = None,
    ):
        """Create the client, reading anything not passed in from the .env file."""
        self.api_key = read_setting(api_key, "ANTHROPIC_API_KEY")
        self.model = read_setting(model, "ANTHROPIC_CHAT_MODEL", self.DEFAULT_MODEL)
        self.base_url = read_url_setting(base_url, "ANTHROPIC_BASE_URL", self.DEFAULT_BASE_URL)
        self.workspace_id = read_setting(workspace_id, "ANTHROPIC_WORKSPACE_ID")

        if not self.api_key:
            logger.warning("[ANTHROPIC] ANTHROPIC_API_KEY not set")

        self.warn_if_workspace_id_looks_wrong()

        # Only send the workspace header when we actually have an id.
        headers = {}
        if self.workspace_id:
            headers["anthropic-workspace-id"] = self.workspace_id

        # Only build the Anthropic object when we have a key. Without a key the
        # library raises an error here, which would crash the health endpoints.
        if self.api_key:
            self.client = anthropic.Anthropic(
                api_key=self.api_key,
                base_url=self.base_url,
                default_headers=headers,
            )
        else:
            self.client = None

    def warn_if_workspace_id_looks_wrong(self):
        """Print a warning if ANTHROPIC_WORKSPACE_ID looks like a name, not an id.

        Pasting the workspace's name instead of its id is an easy mistake, and the
        only clue you get from the API is an unhelpful 400 error. Catching it here
        saves a lot of guessing.
        """
        if not self.workspace_id:
            return

        if not self.workspace_id.startswith(self.WORKSPACE_ID_PREFIX):
            logger.warning(
                "[ANTHROPIC] ANTHROPIC_WORKSPACE_ID=%r does not start with %r - the "
                "Console shows the ID (not the name) in the ID column of "
                "Settings -> Workspaces",
                self.workspace_id,
                self.WORKSPACE_ID_PREFIX,
            )

    def get_client(self):
        """Return the Anthropic object, or raise a clear error if there is no key."""
        if self.client is None:
            raise RuntimeError(f"{self.ENV_KEY} is not configured")
        return self.client

    def get_configuration(self) -> dict:
        """Return the settings this client is using, with no secrets in it."""
        return {
            "base_url": self.base_url,
            "model": self.model,
            "workspace_id": self.workspace_id,
            "workspace_id_set": bool(self.workspace_id),
        }

    def ask(self, question, context=None, temperature=0.0, max_tokens=None):
        """Ask one question and return the answer text.

        `temperature` is accepted but ignored - Anthropic has deprecated it.
        See the note at the top of this file.
        """
        if context:
            message_text = f"Context:\n{context}\n\nQuestion:\n{question}"
        else:
            message_text = question

        # temperature is deliberately not passed - see the note at the top of
        # this file. The anthropic library would reject it outright.
        with log_backend_call(logger, "anthropic", "messages.ask", model=self.model):
            response = self.get_client().messages.create(
                model=self.model,
                max_tokens=max_tokens or 1024,
                messages=[{"role": "user", "content": message_text}],
            )

        # Claude replies with a list of "blocks". Join the text ones together.
        answer = ""
        for block in response.content:
            if block.type == "text":
                answer = answer + block.text
        return answer

    def ask_with_tools(self, messages, tools, temperature=0.0, max_tokens=None, tool_choice="auto"):
        """Ask a question and let Claude call tools.

        This method takes OpenAI-shaped messages and tools and returns an
        OpenAI-shaped reply, so the rest of the project can treat every provider
        the same way. The two conversions happen in the helper methods below.
        """
        claude_tools = self.convert_tools_to_claude_format(tools)
        system_text, chat_messages = self.split_out_system_message(messages)

        # Claude takes the system prompt as its own argument, not as a message.
        extra_arguments = {}
        if system_text:
            extra_arguments["system"] = system_text

        # temperature is deliberately not passed - see the note at the top of file.
        with log_backend_call(
            logger, "anthropic", "messages.ask_with_tools", model=self.model, tool_count=len(tools)
        ):
            response = self.get_client().messages.create(
                model=self.model,
                max_tokens=max_tokens or 1024,
                messages=chat_messages,
                tools=claude_tools,
                **extra_arguments,
            )
        return self.convert_response_to_openai_format(response)

    @staticmethod
    def convert_tools_to_claude_format(tools: list[dict]) -> list[dict]:
        """Rewrite OpenAI-style tool definitions into the shape Claude expects.

        OpenAI nests everything under a "function" key; Claude wants the name,
        description and schema at the top level, and calls the schema
        "input_schema" instead of "parameters".
        """
        claude_tools = []
        for tool in tools:
            if tool.get("type") != "function":
                continue

            function = tool["function"]
            claude_tools.append(
                {
                    "name": function["name"],
                    "description": function.get("description", ""),
                    "input_schema": function.get("parameters", {}),
                }
            )
        return claude_tools

    @staticmethod
    def split_out_system_message(messages: list[dict]) -> tuple[str | None, list[dict]]:
        """Separate the system message from the rest of the conversation.

        Returns two things: the system text (or None), and the remaining messages.
        """
        system_text = None
        chat_messages = []

        for message in messages:
            if message.get("role") == "system":
                system_text = message.get("content")
            else:
                chat_messages.append(message)

        return system_text, chat_messages

    @staticmethod
    def convert_response_to_openai_format(response) -> dict:
        """Rewrite Claude's reply into the shape OpenAI uses.

        Doing this here means calling code only ever has to understand one reply
        format, no matter which provider answered.
        """
        answer_text = ""
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                answer_text = answer_text + block.text
            elif block.type == "tool_use":
                tool_calls.append(
                    {
                        "id": block.id,
                        "type": "function",
                        "function": {"name": block.name, "arguments": str(block.input)},
                    }
                )

        # OpenAI uses None rather than an empty list when no tools were called.
        if not tool_calls:
            tool_calls = None

        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": answer_text,
                        "tool_calls": tool_calls,
                    }
                }
            ],
            "usage": {
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
            },
        }

    def health_check(self, deep: bool = False) -> dict:
        """Report whether this client is usable.

        deep=False: only checks that the API key is present. No network call.
        deep=True: calls GET {base_url}/v1/models. That call is free (it uses no
        tokens) and it checks three things at once: the base URL is right, the key
        works, and the workspace header (if needed) is accepted.
        """
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
            available_model_names = []
            for model in self.get_client().models.list():
                available_model_names.append(model.id)

            # Model ids carry a date on the end (claude-haiku-4-5-20251001), so
            # compare with startswith rather than looking for an exact match.
            model_is_available = False
            for name in available_model_names:
                if name.startswith(self.model):
                    model_is_available = True

            result["status"] = "healthy"
            result["models_visible"] = len(available_model_names)
            result["chat_model_available"] = model_is_available
        except Exception as error:
            # A health check must never crash - report the problem instead.
            result["status"] = "unhealthy"
            result["message"] = str(error)

        return result
