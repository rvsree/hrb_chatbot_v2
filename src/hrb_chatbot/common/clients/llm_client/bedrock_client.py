"""Bedrock client: talks to any model hosted on AWS Bedrock, via the Converse API.

Why Converse, not the older per-model InvokeModel API
----------------------------------------------------------
Bedrock originally required a different JSON request/response body per model
family (Anthropic's shape, Amazon's shape, Meta's shape, all different). The
Converse API is Bedrock's newer, unified interface - one request/response
shape regardless of which model answers - which is exactly this project's
own reason for BaseLLMClient existing at all. Converse is what makes this
client roughly a third the size a per-model implementation would be.

Two different boto3 clients, on purpose
-------------------------------------------
"bedrock-runtime" (self.client) is the data plane - Converse and
InvokeModel, the calls that actually run a model. "bedrock" (built lazily,
only for the deep health check) is the control plane - ListFoundationModels,
which does not exist on bedrock-runtime. This is a real AWS API split, not
a design choice made here.

Credentials
-----------
If AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are both set in .env, they are
passed explicitly. If either is missing, boto3's own default credential chain
is used instead (environment variables it reads itself, ~/.aws/credentials,
an EC2/ECS/Lambda IAM role) - this client does not require .env to be the
only source of credentials, unlike the API-key-based providers, because AWS
credentials legitimately come from many places boto3 already knows how to
check.

UNTESTED against a real account as of the commit that added this file
---------------------------------------------------------------------------
No AWS credentials were available in this project's .env or on the machine
building this client. ask() and health_check() are straightforward enough
that they are very likely correct; ask_with_tools()'s message/tool format
conversion (OpenAI shape <-> Bedrock Converse shape) is the more intricate
part and has not been exercised against a real Bedrock endpoint. Treat it
as reviewed, not verified, until it's actually run against a real account.
"""

import boto3

from src.hrb_chatbot.common.clients.llm_client.base_llm_client import BaseLLMClient
from src.hrb_chatbot.common.config.settings import read_setting
from src.hrb_chatbot.common.logging.logger import get_logger

logger = get_logger("bedrock_client")


class BedrockChatClient(BaseLLMClient):
    """Talks to AWS Bedrock's Converse API."""

    PROVIDER_NAME = "bedrock"
    ENV_KEY = "AWS_REGION"

    DEFAULT_REGION = "us-east-1"
    # Amazon's own model, not Anthropic's - this project already has a direct
    # Anthropic client, so Bedrock is more useful as access to a genuinely
    # different model family than as a second, indirect path to Claude.
    DEFAULT_MODEL = "amazon.nova-pro-v1:0"

    def __init__(
        self,
        region: str | None = None,
        model: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
    ):
        """Create the client, reading anything not passed in from the .env file."""
        self.region = read_setting(region, "AWS_REGION", self.DEFAULT_REGION)
        self.model = read_setting(model, "BEDROCK_MODEL_ID", self.DEFAULT_MODEL)
        self.access_key_id = read_setting(access_key_id, "AWS_ACCESS_KEY_ID")
        self.secret_access_key = read_setting(secret_access_key, "AWS_SECRET_ACCESS_KEY")

        self._credentials_explicit = bool(self.access_key_id and self.secret_access_key)

        self._client_kwargs = {"region_name": self.region}
        if self._credentials_explicit:
            self._client_kwargs["aws_access_key_id"] = self.access_key_id
            self._client_kwargs["aws_secret_access_key"] = self.secret_access_key

        # Building a boto3 client makes no network call by itself - safe to
        # do here rather than lazily, the same as OpenAI()'s constructor.
        # Actual credential validity is only proven by a real call (deep
        # health check, or a genuine ask()).
        self.client = boto3.client("bedrock-runtime", **self._client_kwargs)

    def get_configuration(self) -> dict:
        """Return the settings this client is using - no secret values in it."""
        return {
            "region": self.region,
            "model": self.model,
            "credentials_source": "explicit .env values" if self._credentials_explicit else "boto3 default chain",
        }

    def ask(self, question, context=None, temperature=0.0, max_tokens=None):
        """Ask one question and return the answer text."""
        if context:
            message_text = f"Context:\n{context}\n\nQuestion:\n{question}"
        else:
            message_text = question

        inference_config = {"temperature": temperature}
        if max_tokens:
            inference_config["maxTokens"] = max_tokens

        response = self.client.converse(
            modelId=self.model,
            messages=[{"role": "user", "content": [{"text": message_text}]}],
            inferenceConfig=inference_config,
        )

        blocks = response["output"]["message"]["content"]
        return "".join(block.get("text", "") for block in blocks)

    def ask_with_tools(self, messages, tools, temperature=0.0, max_tokens=None, tool_choice="auto"):
        """Ask a question and let the model call tools.

        Takes OpenAI-shaped messages and tools, returns an OpenAI-shaped
        reply, so the rest of the project can treat every provider the
        same way - the two conversions happen in the helper methods below,
        the same pattern anthropic_client.py uses for the same reason.
        """
        bedrock_tools = self._convert_tools_to_bedrock_format(tools)
        system_text, bedrock_messages = self._convert_messages_to_bedrock_format(messages)

        inference_config = {"temperature": temperature}
        if max_tokens:
            inference_config["maxTokens"] = max_tokens

        request = {
            "modelId": self.model,
            "messages": bedrock_messages,
            "inferenceConfig": inference_config,
        }
        if bedrock_tools:
            request["toolConfig"] = {"tools": bedrock_tools}
        if system_text:
            request["system"] = [{"text": system_text}]

        response = self.client.converse(**request)
        return self._convert_response_to_openai_format(response)

    @staticmethod
    def _convert_tools_to_bedrock_format(tools: list[dict]) -> list[dict]:
        """Rewrite OpenAI-style tool definitions into Bedrock's toolSpec shape.

        OpenAI nests everything under a "function" key; Bedrock wants name,
        description, and schema under "toolSpec", and calls the schema
        "inputSchema": {"json": ...} instead of "parameters".
        """
        bedrock_tools = []
        for tool in tools:
            if tool.get("type") != "function":
                continue

            function = tool["function"]
            bedrock_tools.append(
                {
                    "toolSpec": {
                        "name": function["name"],
                        "description": function.get("description", ""),
                        "inputSchema": {"json": function.get("parameters", {})},
                    }
                }
            )
        return bedrock_tools

    @staticmethod
    def _convert_messages_to_bedrock_format(
        messages: list[dict],
    ) -> tuple[str | None, list[dict]]:
        """Rewrite an OpenAI-shaped conversation into Bedrock's Converse shape.

        Three shape differences to reconcile:
        - Bedrock takes the system prompt as its own top-level argument, not
          a message - so it's split out here, same as anthropic_client.py.
        - An assistant message's tool_calls become toolUse content blocks.
        - OpenAI gives each tool result its own "tool"-role message; Bedrock
          has no such role - every tool result for one assistant turn is
          grouped into content blocks on a single following "user" turn.
        """
        system_text = None
        bedrock_messages: list[dict] = []
        pending_tool_results: list[dict] = []

        def flush_pending_tool_results():
            if pending_tool_results:
                bedrock_messages.append({"role": "user", "content": list(pending_tool_results)})
                pending_tool_results.clear()

        for message in messages:
            role = message.get("role")

            if role == "system":
                system_text = message.get("content")
                continue

            if role == "tool":
                pending_tool_results.append(
                    {
                        "toolResult": {
                            "toolUseId": message.get("tool_call_id"),
                            "content": [{"text": message.get("content") or ""}],
                        }
                    }
                )
                continue

            # Any non-tool message ends the run of tool results that came
            # before it - they belong to the turn that precedes this one.
            flush_pending_tool_results()

            content_blocks = []
            if message.get("content"):
                content_blocks.append({"text": message["content"]})
            for tool_call in message.get("tool_calls") or []:
                function = tool_call.get("function", {})
                content_blocks.append(
                    {
                        "toolUse": {
                            "toolUseId": tool_call.get("id"),
                            "name": function.get("name"),
                            "input": function.get("arguments"),
                        }
                    }
                )

            bedrock_messages.append({"role": role, "content": content_blocks})

        flush_pending_tool_results()

        return system_text, bedrock_messages

    @staticmethod
    def _convert_response_to_openai_format(response: dict) -> dict:
        """Rewrite a Converse reply into the shape OpenAI uses, so calling
        code only ever has to understand one reply format."""
        answer_text = ""
        tool_calls = []

        for block in response["output"]["message"]["content"]:
            if "text" in block:
                answer_text += block["text"]
            elif "toolUse" in block:
                tool_use = block["toolUse"]
                tool_calls.append(
                    {
                        "id": tool_use.get("toolUseId"),
                        "type": "function",
                        "function": {
                            "name": tool_use.get("name"),
                            "arguments": tool_use.get("input"),
                        },
                    }
                )

        if not tool_calls:
            tool_calls = None

        usage = response.get("usage", {})

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
                "prompt_tokens": usage.get("inputTokens"),
                "completion_tokens": usage.get("outputTokens"),
            },
        }

    def health_check(self, deep: bool = False) -> dict:
        """Report whether this client is usable.

        deep=False: reports configured region/model/credential-source only -
        no network call. Unlike the API-key providers, "configured" here
        cannot mean "a key is present" (AWS credentials may legitimately
        come from an IAM role this code never sees) - only deep=True
        actually proves anything works.
        deep=True: calls the separate "bedrock" control-plane client's
        ListFoundationModels - free, no tokens spent, and it's the only way
        to genuinely confirm credentials + region + model all work together.
        """
        result = {"provider": self.PROVIDER_NAME}
        result.update(self.get_configuration())

        if not deep:
            result["status"] = "configured"
            return result

        try:
            control_client = boto3.client("bedrock", **self._client_kwargs)
            models = control_client.list_foundation_models()
            model_ids = [entry["modelId"] for entry in models.get("modelSummaries", [])]

            result["status"] = "healthy"
            result["models_visible"] = len(model_ids)
            result["configured_model_available"] = self.model in model_ids
        except Exception as error:
            # A health check must never crash - report the problem instead.
            result["status"] = "unhealthy"
            result["message"] = str(error)

        return result
