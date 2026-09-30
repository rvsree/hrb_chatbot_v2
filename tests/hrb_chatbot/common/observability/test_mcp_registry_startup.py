"""Tests for Phase 50's startup registry orchestration (control flow only -
McpRegistryClient/the real MCP call are both faked, no real Postgres or
network call, matching every other client test in this project)."""

from src.hrb_chatbot.common.observability import mcp_registry_startup


class FakeRegistry:
    def __init__(self):
        self.registered_server = None
        self.registered_tools = None
        self.connection_attempts = []

    async def register_server(self, **kwargs):
        self.registered_server = kwargs

    async def register_tools(self, server_id, tools):
        self.registered_tools = (server_id, tools)

    async def record_connection_attempt(self, server_id, success, result, error_message=None):
        self.connection_attempts.append((server_id, success, result, error_message))


async def test_reachable_server_registers_tools_and_a_successful_attempt(monkeypatch):
    fake_registry = FakeRegistry()
    monkeypatch.setattr(mcp_registry_startup, "McpRegistryClient", lambda: fake_registry)

    async def _fake_list_tools_live(mcp_url):
        return [{"name": "get_leave_balance", "description": "..."}]

    monkeypatch.setattr(mcp_registry_startup, "_list_tools_live", _fake_list_tools_live)

    await mcp_registry_startup.register_configured_mcp_servers()

    assert fake_registry.registered_server["server_id"] == "hrb_lms_mcp"
    assert fake_registry.registered_tools[0] == "hrb_lms_mcp"
    assert len(fake_registry.registered_tools[1]) == 1
    server_id, success, result, error_message = fake_registry.connection_attempts[0]
    assert (server_id, success, error_message) == ("hrb_lms_mcp", True, None)
    assert result["tool_count"] == 1


async def test_unreachable_mcp_server_still_registers_and_records_failure(monkeypatch):
    fake_registry = FakeRegistry()
    monkeypatch.setattr(mcp_registry_startup, "McpRegistryClient", lambda: fake_registry)

    async def _fake_list_tools_live_raising(mcp_url):
        raise ConnectionError("hrb_lms_mcp unreachable")

    monkeypatch.setattr(mcp_registry_startup, "_list_tools_live", _fake_list_tools_live_raising)

    await mcp_registry_startup.register_configured_mcp_servers()

    assert fake_registry.registered_server is not None  # server row still written first
    assert fake_registry.registered_tools is None  # tools/list never succeeded
    assert fake_registry.connection_attempts[0][0] == "hrb_lms_mcp"
    assert fake_registry.connection_attempts[0][1] is False
    assert "unreachable" in fake_registry.connection_attempts[0][3]


async def test_registry_database_unreachable_skips_everything_without_raising(monkeypatch):
    class RaisingRegistry:
        async def register_server(self, **kwargs):
            raise ConnectionError("hr_chatbot database unreachable")

    monkeypatch.setattr(mcp_registry_startup, "McpRegistryClient", lambda: RaisingRegistry())

    # Should not raise - startup must never crash on registry bookkeeping.
    await mcp_registry_startup.register_configured_mcp_servers()
