# Checks all backend services are wired up and working correctly?

from src.hrb_chatbot.common.clients.db_client.db_gateway import get_db_gateway
from src.hrb_chatbot.common.clients.llm_client.client_gateway import get_client_gateway
from src.hrb_chatbot.common.config.settings import SETTINGS_TAKEN_FROM_ENV_FILE

WORKING_STATUSES = ["configured", "healthy"]

# TODO(next feature - tools): add a "tools" check here once a tool/schema

def check_vector_database(provider: str = "chromadb", deep: bool = False) -> dict:
    # Check the vector store the RAG pipeline reads and writes chunks in.
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
    # Check the store holding one row per uploaded document.
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
    deep=False only checks that a key is configured but deep=True makes real call."""
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


def check_all_backend_services(
    provider: str = "openai",
    deep: bool = False,
    metadata_provider: str = "sqlite",
    vector_provider: str = "chromadb",
) -> dict:

    checks = {
        "llm": check_llm(provider=provider, deep=deep),
        "vector_database": check_vector_database(provider=vector_provider, deep=deep),
        "metadata_database": check_metadata_database(provider=metadata_provider),
        # TODO(next feature - tools): "tools": check_tools()
    }

    all_backend_services_health = True
    for result in checks.values():
        if not is_working(result):
            all_backend_services_health = False
            break

    if all_backend_services_health:
        overall_status = "healthy"
    else:
        overall_status = "unhealthy"

    return {
        "status": overall_status,
        "app": "HRB Chatbot",
        "deep": deep,
        "settings_taken_from_env_file": SETTINGS_TAKEN_FROM_ENV_FILE,
        "checks": checks,
    }
