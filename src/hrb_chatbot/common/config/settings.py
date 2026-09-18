"""Loads .env with override=True - beats a stale shell/Windows env value
(python-dotenv's default does NOT replace it, a real "wrong key" bug)."""

import os

from dotenv import dotenv_values, find_dotenv, load_dotenv


def load_env_file_and_report_overrides() -> list[str]:
    """Load .env so its values win, returning the names of any it replaced -
    health-report only, values are secrets and never stored/logged."""
    env_file_path = find_dotenv(usecwd=True)

    if not env_file_path:
        # No .env file at all. Fall back to whatever the environment provides.
        load_dotenv()
        return []

    # Work out what we are about to replace, before we replace it.
    replaced_settings = []
    for setting_name, value_in_file in dotenv_values(env_file_path).items():
        value_on_machine = os.environ.get(setting_name)

        both_have_a_value = value_in_file and value_on_machine
        if both_have_a_value and value_on_machine != value_in_file:
            replaced_settings.append(setting_name)

    replaced_settings.sort()

    # override=True is the important part - see the note at the top of this file.
    load_dotenv(env_file_path, override=True)

    return replaced_settings


# The names of settings where .env replaced a different value already set on this
# computer. Usually empty. A health check can read this to explain what happened.
SETTINGS_TAKEN_FROM_ENV_FILE = load_env_file_and_report_overrides()


def read_setting(passed_in_value: str | None, env_variable_name: str, default_value=None):
    """Work out which value to use: passed-in value, then .env/environment,
    then default - `if value:` treats an empty-string .env line as unset."""
    if passed_in_value:
        return passed_in_value

    value_from_env_file = os.getenv(env_variable_name)
    if value_from_env_file:
        return value_from_env_file

    return default_value


def read_url_setting(
    passed_in_value: str | None, env_variable_name: str, default_value: str
) -> str:
    """Same as read_setting, but also strips a trailing "/" - avoids a
    doubled "//" when callers build urls as base_url + "/search"."""
    url = read_setting(passed_in_value, env_variable_name, default_value)
    return url.rstrip("/")


def get_active_vector_db(override: str | None = None) -> str:
    """Which vector store to use - override wins, else .env's
    ACTIVE_VECTOR_DB, else chromadb. One place, not repeated per call site."""
    return read_setting(override, "ACTIVE_VECTOR_DB", "chromadb")


def get_active_llm_provider(override: str | None = None) -> str:
    """Which LLM provider powers embedding/retrieval-time reasoning -
    override wins, else .env's ACTIVE_LLM_PROVIDER, else openai. Not the
    final answer's model, which stays a separate per-call override."""
    return read_setting(override, "ACTIVE_LLM_PROVIDER", "openai")
