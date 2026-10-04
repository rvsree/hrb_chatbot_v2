"""Vector KB Agent is a thin wrapper - confirms it forwards to the real tool unchanged."""

from src.hrb_chatbot.ai.agents.domain_agents import vector_kb_agent


async def test_run_forwards_focus_to_search_knowledge_base(monkeypatch):
    captured = {}

    async def _fake_search(query, search_strategy=None):
        captured["query"] = query
        return "fake KB result"

    monkeypatch.setattr(vector_kb_agent, "search_knowledge_base", _fake_search)

    result = await vector_kb_agent.run("what is the 401k match?")

    assert result == "fake KB result"
    assert captured["query"] == "what is the 401k match?"
