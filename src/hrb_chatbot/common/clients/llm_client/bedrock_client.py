"""Bedrock client: talks to any model hosted on AWS Bedrock via the unified
Converse API (one request/response shape per call, unlike the older
InvokeModel API's per-model-family JSON shapes).

Untested against a real AWS account - ask_with_tools()'s OpenAI<->Bedrock
conversion has not been exercised against a live endpoint; treat as reviewed, not verified.
"""

import boto3

from src.hrb_chatbot.common.clients.llm_client.base_llm_client import BaseLLMClient
from src.hrb_chatbot.common.config.settings import read_setting
from src.hrb_chatbot.common.logging.call_logger import log_backend_call
from src.hrb_chatbot.common.logging.logger import get_logger

logger = get_logger("bedrock_client")


class BedrockChatClient(BaseLLMClient):
    """Talks to AWS Bedrock's Converse API."""

    PROVIDER_NAME = "bedrock"
    ENV_KEY = "AWS_REGION"

    DEFAULT_REGION = "us-east-1"
    # Amazon's own model, not Anthropic's - Bedrock is more useful here as
    # access to a different model family than as an indirect path to Claude.
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

        # Building a boto3 client makes no network call by itself, so this is
        # safe to do eagerly; only a real call proves credentials are valid.
        self.client = boto3.client("bedrock-runtime", **self._client_kwargs)

    def get_configuration(self) -> dict:
        """Return the settings this client is using - no secret values in it."""
        if self._credentials_explicit:
            credentials_source = "explicit .env values"
        else:
            credentials_source = "boto3 default chain"

        return {
            "region": self.region,
            "model": self.model,
            "credentials_source": credentials_source,
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

        with log_backend_call(logger, "bedrock", "converse.ask", model=self.model, temperature=temperature):
            response = self.client.converse(
                modelId=self.model,
                messages=[{"role": "user", "content": [{"text": message_text}]}],
                inferenceConfig=inference_config,
            )

        # Converse can return several content blocks (e.g. text plus a citation
        # block); join their text into one string, matching every other provider's ask().
        blocks = response["output"]["message"]["content"]
        answer_text = ""
        for block in blocks:
            answer_text += block.get("text", "")
        return answer_text

    def ask_with_tools(self, messages, tools, temperature=0.0, max_tokens=None, tool_choice="auto"):
        """Ask a question and let the model call tools. Takes OpenAI-shaped messages/tools,
        returns an OpenAI-shaped reply - same conversion pattern anthropic_client.py uses."""
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

        with log_backend_call(
            logger, "bedrock", "converse.ask_with_tools", model=self.model, tool_count=len(tools)
        ):
            response = self.client.converse(**request)
        return self._convert_response_to_openai_format(response)

    @staticmethod
    def _convert_tools_to_bedrock_format(tools: list[dict]) -> list[dict]:
        """Rewrite OpenAI-style tool defs into Bedrock's toolSpec shape: name,
        description, and schema nested under "toolSpec", schema key "inputSchema": {"json": ...}."""
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
        """Rewrite OpenAI-shaped messages into Bedrock's Converse shape: splits out
        the system message, and groups tool results into "user" turns since Bedrock has no "tool" role."""
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

    def health_check(self) -> dict:
        """Report whether this client is usable: calls ListFoundationModels to
        confirm. AWS creds may come from an IAM role rather than .env, so there's
        no cheap "is a key present" check to do first - this is the only way to know."""
        result = {"provider": self.PROVIDER_NAME}
        result.update(self.get_configuration())

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
