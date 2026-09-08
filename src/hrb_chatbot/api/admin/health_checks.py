"""Is the backend wired up correctly?

Scope right now: the LLM client, the vector store - ChromaDB (the active
choice) and Pinecone (a fully working alternative, tested on its own, not
yet the active one - pass vector_provider=pinecone to check it) - and the
document-metadata store - SQLite (active) and Postgres (working
alternative, pass metadata_provider=postgres).

Any tool/schema-drift check lands here later too, as its own feature.
`check_everything` combines whatever checks exist into one report, so a
single broken piece is impossible to miss once more checks are added.

Like every health check in this project, none of this costs money unless you ask
for deep=true - and even then, only a free provider call is made (GET /models,
GET /key, and so on - never a chat completion).
"""

from src.hrb_chatbot.common.clients.db_client.db_gateway import get_db_gateway
from src.hrb_chatbot.common.clients.llm_client.client_gateway import get_client_gateway
from src.hrb_chatbot.common.config.settings import SETTINGS_TAKEN_FROM_ENV_FILE

# Statuses that mean a client is usable, matching what the clients report:
# "configured" = the key is present, "healthy" = we called the API and it worked.
WORKING_STATUSES = ["configured", "healthy"]

# TODO(next feature - tools): add a "tools" check here once a tool/schema
# system exists, then fold it into check_everything() below.


def check_vector_database(provider: str = "chromadb", deep: bool = False) -> dict:
    """Check the vector store the RAG pipeline reads and writes chunks in.

    ChromaDB (embedded, local disk) always runs its "deep" check regardless
    of the `deep` argument here - it costs nothing and there is no separate
    free "prove the connection" call the way GET /models does for an LLM
    provider, so listing collections *is* the real operation.

    Pinecone is a real external service, so it respects `deep` properly:
    deep=False only reports configured settings, no network call. deep=True
    calls out to Pinecone, and - on the very first call for a fresh account -
    creates the configured index, which is not instant (see
    pinecone_client.py). Never make this call from a health probe that
    expects an instant answer; use the shallow check for that.
    """
    gateway = get_db_gateway()

    try:
        if provider == "pinecone":
            client = gateway.pinecone()
            return client.health_check(deep=deep)

        client = gateway.chroma()
        return client.health_check(deep=True)
    except Exception as error:
        return {"status": "unhealthy", "provider": provider, "message": str(error)}


def check_metadata_database(provider: str = "sqlite") -> dict:
    """Check the store holding one row per uploaded document.

    'sqlite' is the store documents_service.py actually uses today.
    'postgres' is a fully working alternative, checked the same way but not
    yet wired into documents_service.py - see docs/RAG-ROADMAP.md.

    deep=True opens the database (file or connection) and confirms the
    documents table is queryable.
    """
    gateway = get_db_gateway()

    try:
        if provider == "postgres":
            client = gateway.postgres()
        else:
            client = gateway.sqlite()

        return client.health_check(deep=True)
    except Exception as error:
        return {"status": "unhealthy", "provider": provider, "message": str(error)}


def check_llm(provider: str = "openai", deep: bool = False) -> dict:
    """Check the chat client the agent will use.

    deep=False only checks that a key is configured. deep=True makes one real but
    free call to prove the key and base URL actually work.

    This never raises: a health endpoint that returns a stack trace tells you far
    less than one that returns the reason.
    """
    gateway = get_client_gateway()

    try:
        if provider == "anthropic":
            client = gateway.anthropic_chat()
        elif provider == "openrouter":
            client = gateway.openrouter_chat()
        elif provider == "bedrock":
            client = gateway.bedrock_chat()
        else:
            client = gateway.openai_chat()

        return client.health_check(deep=deep)
    except Exception as error:
        return {"status": "unhealthy", "provider": provider, "message": str(error)}


def is_working(check_result: dict) -> bool:
    """Return True if one check result means that part is usable."""
    return check_result.get("status") in WORKING_STATUSES


def check_everything(
    provider: str = "openai",
    deep: bool = False,
    metadata_provider: str = "sqlite",
    vector_provider: str = "chromadb",
) -> dict:
    """Run every check that currently exists and combine them into one report.

    The overall status is "healthy" only if every part is working, so a single
    broken piece is impossible to miss.
    """
    checks = {
        "llm": check_llm(provider=provider, deep=deep),
        "vector_database": check_vector_database(provider=vector_provider, deep=deep),
        "metadata_database": check_metadata_database(provider=metadata_provider),
        # TODO(next feature - tools): "tools": check_tools()
    }

    # True only if every single check passed - written as an explicit loop
    # rather than Python's all(... for ...) idiom (a generator expression
    # passed straight into a function call), which has no direct Java
    # equivalent and reads oddly the first several times you see it.
    everything_works = True
    for result in checks.values():
        if not is_working(result):
            everything_works = False
            break

    if everything_works:
        overall_status = "healthy"
    else:
        overall_status = "unhealthy"

    return {
        "status": overall_status,
        "app": "HRB Chatbot",
        "deep": deep,
        # Which settings .env replaced on the way in. Usually an empty list. Only
        # the NAMES appear here - never the values, which are secrets.
        "settings_taken_from_env_file": SETTINGS_TAKEN_FROM_ENV_FILE,
        "checks": checks,
    }
