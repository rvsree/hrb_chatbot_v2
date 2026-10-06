"""Phase 97 regression: Postgres TEXT columns reject any embedded NUL byte -
a PDF-ligature extraction artifact (e.g. "offers" -> "o\x00ers") that can
ride into a saved LLM answer verbatim. Direct against ConversationStore -
no real Postgres, _connect() faked, matching this project's zero-network-
call test guarantee."""

from src.hrb_chatbot.common.clients.db_client.conversation_store import ConversationStore


class _FakeConnection:
    """Records every (sql, params) pair passed to execute() - enough to
    assert what would have reached Postgres, without a real connection."""

    def __init__(self, recorded_calls):
        self._recorded_calls = recorded_calls

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def execute(self, sql, params=None):
        self._recorded_calls.append((sql, params))

    def commit(self):
        pass


def _store_with_fake_connection(monkeypatch):
    store = ConversationStore(host="fake-host", port="5432", db_name="fake_db", user="fake_user", password="fake_pw")
    store._table_ready = True  # skip _ensure_table's own CREATE TABLE/INDEX calls
    recorded_calls = []
    monkeypatch.setattr(store, "_connect", lambda: _FakeConnection(recorded_calls))
    return store, recorded_calls


async def test_a_nul_byte_in_content_is_stripped_before_the_insert(monkeypatch):
    store, recorded_calls = _store_with_fake_connection(monkeypatch)

    # Stripping only removes the NUL byte - it can't recover the "ff" the
    # ligature-decoding artifact actually lost, so "o\x00ers" becomes
    # "oers", not "offers". The point is Postgres-safety, not text repair.
    await store.save_turn("conv-1", "EMP052", "ai", "JPMorgan Chase o\x00ers two dental plan options")

    assert len(recorded_calls) == 1
    _sql, params = recorded_calls[0]
    saved_content = params[3]
    assert "\x00" not in saved_content
    assert saved_content == "JPMorgan Chase oers two dental plan options"


async def test_content_with_no_nul_byte_is_unchanged(monkeypatch):
    store, recorded_calls = _store_with_fake_connection(monkeypatch)

    await store.save_turn("conv-1", "EMP052", "human", "What dental plans are offered?")

    _sql, params = recorded_calls[0]
    assert params[3] == "What dental plans are offered?"
