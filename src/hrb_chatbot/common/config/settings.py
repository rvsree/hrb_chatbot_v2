"""Loads the .env file and provides the helper every client uses to read it.

Loads with override=True so .env always wins over a stale value already set
in the shell/Windows environment (python-dotenv's default does NOT replace
it, which otherwise causes a baffling "why is my new key not working" bug).
"""

import os

from dotenv import dotenv_values, find_dotenv, load_dotenv


def load_env_file_and_report_overrides() -> list[str]:
    """Load .env so its values win, and return the names of any it replaced.

    Runs once on import. Returned for a health report only - values are secrets, never stored or logged.
    """
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
    """Work out which value to use for one setting, checking passed-in value,
    then .env/environment, then default - `if value:` treats an empty-string .env line as unset, not as a real value that beats the default."""
    if passed_in_value:
        return passed_in_value

    value_from_env_file = os.getenv(env_variable_name)
    if value_from_env_file:
        return value_from_env_file

    return default_value


def read_url_setting(
    passed_in_value: str | None, env_variable_name: str, default_value: str
) -> str:
    """Same as read_setting, but also strips any trailing "/" from the URL.

    Avoids a doubled "//" when callers build urls as base_url + "/search".
    """
    url = read_setting(passed_in_value, env_variable_name, default_value)
    return url.rstrip("/")
