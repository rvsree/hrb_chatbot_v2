"""At startup, calls each MCP server's tools/list and records it in app_tracking - bookkeeping, not a hard dependency."""

import time

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from src.hrb_chatbot.common.clients.auth_client.oauth_client import get_access_token
from src.hrb_chatbot.common.clients.db_client.mcp_registry_client import McpRegistryClient
from src.hrb_chatbot.common.config.settings import read_setting
from src.hrb_chatbot.common.logging.logger import get_logger

logger = get_logger("mcp_registry_startup")


async def _list_tools_live(mcp_url: str) -> list[dict]:
    # Real OAuth2 Bearer token - hrb_lms_mcp enforces this, unlike the dead X-API-Key header it used to accept.
    access_token = await get_access_token()
    headers = {"Authorization": f"Bearer {access_token}"}
    async with streamablehttp_client(mcp_url, headers=headers) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.list_tools()
            return [{"name": tool.name, "description": tool.description, "inputSchema": tool.inputSchema} for tool in result.tools]


async def register_configured_mcp_servers() -> None:
    """One server today, loop shape ready for more - registers the server row first (FK dependency)."""
    registry = McpRegistryClient()
    mcp_url = read_setting(None, "HRB_LMS_MCP_URL", "http://127.0.0.1:8190/mcp")

    try:
        # CHECK-constrained by the existing table - 'http'/'active' are the closest real fits, found live.
        await registry.register_server(
            server_id="hrb_lms_mcp", server_name="HRB Leave Management System MCP Server",
            server_type="leave_management", connection_type="http",
            base_url=mcp_url.rsplit("/", 1)[0], endpoint_path="/mcp", status="active",
        )
    except Exception as error:
        logger.warning("MCP registry: hr_chatbot database unreachable, skipping registry entirely: %s", error)
        return

    started_at = time.monotonic()
    try:
        tools = await _list_tools_live(mcp_url)
        latency_ms = int((time.monotonic() - started_at) * 1000)
        await registry.register_tools("hrb_lms_mcp", tools)
        await registry.record_connection_attempt(
            "hrb_lms_mcp", success=True, result={"tool_count": len(tools), "latency_ms": latency_ms}
        )
        logger.info("MCP registry: hrb_lms_mcp registered, %d tool(s), %dms", len(tools), latency_ms)
    except Exception as error:
        logger.warning("MCP registry: hrb_lms_mcp unreachable at startup, app starting anyway: %s", error)
        await registry.record_connection_attempt("hrb_lms_mcp", success=False, result={}, error_message=str(error))
