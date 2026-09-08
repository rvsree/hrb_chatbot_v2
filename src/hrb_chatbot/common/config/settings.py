"""Loads the .env file and provides the helper every client uses to read it.

Why .env wins over your computer's environment
----------------------------------------------
By default, python-dotenv does NOT replace a variable that is already set in
your shell or in your Windows user environment - the existing one quietly wins.

That causes a genuinely baffling bug. If an old OPENAI_API_KEY is sitting in your
Windows user environment, it beats the new key you just typed into .env, and the
only symptom is a 401 error that makes it look as though the new key is bad. You
can stare at a perfectly correct .env file for a long time before suspecting it
is not the file being used.

So this project loads the file with override=True: .env is the single source of
truth. Put a value in .env and that value is what runs, whatever else is set on
the machine. Nothing outside this project is changed - other tools on your
computer carry on using the machine-level variable as before.

We also record which settings were replaced, so a health endpoint can tell you
it happened rather than leaving it invisible.
"""

import os

from dotenv import dotenv_values, find_dotenv, load_dotenv


def load_env_file_and_report_overrides() -> list[str]:
    """Load .env so its values win, and return the names of any it replaced.

    Runs once, when this module is first imported. The returned names are only
    for showing in a health report - the values themselves are secrets and are
    compared here but never stored or logged.
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
    """Work out which value to use for one setting, checking three places in order.

    1. The value passed in when the client was created (highest priority).
    2. The matching variable in the .env file / environment.
    3. The default value (lowest priority).

    We deliberately use `if value:` checks instead of `os.getenv(name, default)`.
    If a line in .env reads "OPENAI_BASE_URL=" with nothing after the "=", then
    os.getenv returns an empty string "" rather than None. An empty string would
    beat the default, and we would end up sending requests to a URL with no
    address in it. Treating "" the same as "not set" is what we want.

    Example:
        self.model = read_setting(model, "OPENAI_CHAT_MODEL", "gpt-4.1-mini")
    """
    if passed_in_value:
        return passed_in_value

    value_from_env_file = os.getenv(env_variable_name)
    if value_from_env_file:
        return value_from_env_file

    return default_value


def read_url_setting(
    passed_in_value: str | None, env_variable_name: str, default_value: str
) -> str:
    """Same as read_setting, but also removes any "/" from the end of the URL.

    We build full URLs by writing base_url + "/search". If the base URL already
    ended with a slash we would produce "https://api.tavily.com//search", so the
    trailing slash is stripped here rather than in four different places.
    """
    url = read_setting(passed_in_value, env_variable_name, default_value)
    return url.rstrip("/")
