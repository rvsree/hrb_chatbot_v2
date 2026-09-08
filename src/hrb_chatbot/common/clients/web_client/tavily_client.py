"""Tavily client: web search built for AI agents.

Tavily has no official-library dependency here - we call it with plain HTTP
using the `requests` library, which makes every part of the request easy to see.

Base URL
--------
The correct base URL is https://api.tavily.com - the host name ONLY, no "/v1".
The two endpoints we use are:
    POST /search   run a web search (costs credits)
    GET  /usage    report how many credits are left (free)

Authentication
--------------
Tavily expects the key in a header: `Authorization: Bearer tvly-...`.
An older style put the key in the JSON body instead. This client uses the header,
which is what Tavily's current API reference documents.

Project
-------
TAVILY_PROJECT_ID is Tavily's version of a workspace. It is sent as the
"X-Project-ID" header and is used purely to group usage when one key is shared by
several apps. It does not restrict what the key can do.
"""

import time

import requests

from src.hrb_chatbot.common.config.settings import read_setting, read_url_setting
from src.hrb_chatbot.common.logging.logger import get_logger

logger = get_logger("tavily_client")


class TavilyClient:
    """Runs web searches through Tavily.

    This class does not inherit from BaseLLMClient because Tavily is not an LLM -
    it has no `ask` method and no models. It only searches.
    """

    PROVIDER_NAME = "tavily"
    ENV_KEY = "TAVILY_API_KEY"

    # Host name only - see the note at the top of this file.
    DEFAULT_BASE_URL = "https://api.tavily.com"

    DEFAULT_TIMEOUT_SECONDS = 30
    # How many seconds to wait for the free GET /usage health check.
    HEALTH_CHECK_TIMEOUT_SECONDS = 10
    # Never wait longer than this between retries, however many have failed.
    MAX_SECONDS_BETWEEN_RETRIES = 10

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        project_id: str | None = None,
        timeout: int | None = None,
    ):
        """Create the client, reading anything not passed in from the .env file."""
        self.api_key = read_setting(api_key, "TAVILY_API_KEY")
        self.base_url = read_url_setting(base_url, "TAVILY_BASE_URL", self.DEFAULT_BASE_URL)
        self.project_id = read_setting(project_id, "TAVILY_PROJECT_ID")

        timeout_value = read_setting(timeout, "TAVILY_TIMEOUT", self.DEFAULT_TIMEOUT_SECONDS)
        # The value from .env arrives as text like "30", so convert it to a number.
        self.timeout = int(timeout_value)

        if not self.api_key:
            logger.warning("[TAVILY] TAVILY_API_KEY not set")

    def build_headers(self) -> dict:
        """Build the headers sent with every Tavily request."""
        headers = {
            "Authorization": "Bearer " + str(self.api_key),
            "Content-Type": "application/json",
        }

        # Only send the project header when a project id was configured.
        if self.project_id:
            headers["X-Project-ID"] = self.project_id

        return headers

    def get_configuration(self) -> dict:
        """Return the settings this client is using, with no secrets in it."""
        return {
            "base_url": self.base_url,
            "project_id": self.project_id,
            "timeout": self.timeout,
        }

    def search(
        self,
        query: str,
        max_results: int = 5,
        search_depth: str = "basic",
        include_answer: bool = True,
        max_retries: int = 3,
    ) -> dict:
        """Search the web and return the results.

        This method never raises. It always returns a dictionary containing
        "results", "answer" and "query". If something went wrong, the dictionary
        also contains an "error" key - so check for that before using the results.

        If the request fails it is retried, waiting longer after each failure
        (2 seconds, then 4, then 8). This is called "exponential backoff", and it
        gives a busy or briefly offline server time to recover.
        """
        if not self.api_key:
            return self.build_empty_result(query, "TAVILY_API_KEY not configured")

        if not query or not query.strip():
            return self.build_empty_result(query, "Query cannot be empty")

        request_body = {
            "query": query,
            "max_results": max_results,
            "search_depth": search_depth,
            "include_answer": include_answer,
        }

        last_error = None

        for attempt_number in range(1, max_retries + 1):
            try:
                response = requests.post(
                    self.base_url + "/search",
                    json=request_body,
                    headers=self.build_headers(),
                    timeout=self.timeout,
                )
                # Turns a 401 or 404 reply into an error we can catch below.
                response.raise_for_status()

                data = response.json()
                return {
                    "results": data.get("results", []),
                    "answer": data.get("answer", ""),
                    "query": query,
                }
            except Exception as error:
                last_error = error
                logger.warning(
                    "[TAVILY] Attempt %d of %d failed: %s",
                    attempt_number,
                    max_retries,
                    error,
                )

                # Wait before trying again, but not after the final attempt.
                if attempt_number < max_retries:
                    seconds_to_wait = min(2**attempt_number, self.MAX_SECONDS_BETWEEN_RETRIES)
                    time.sleep(seconds_to_wait)

        return self.build_empty_result(query, str(last_error))

    @staticmethod
    def build_empty_result(query: str, error_message: str) -> dict:
        """Build the "nothing found" reply used whenever a search fails.

        Returning the same shape on success and on failure means calling code
        never has to guess which keys exist.
        """
        return {
            "results": [],
            "answer": "",
            "query": query,
            "error": error_message,
        }

    def health_check(self, deep: bool = False) -> dict:
        """Report whether this client is usable.

        deep=False: only checks that the API key is present. No network call.
        deep=True: calls GET {base_url}/usage. That call spends no search credits,
        and it also tells you how many credits are left - a problem an ordinary
        test search would not reveal until it suddenly started failing.
        """
        result = {"provider": self.PROVIDER_NAME}
        result.update(self.get_configuration())

        if not self.api_key:
            result["status"] = "unhealthy"
            result["message"] = "API key not configured"
            return result

        if not deep:
            result["status"] = "configured"
            return result

        try:
            headers = self.build_headers()
            headers["Accept"] = "application/json"

            response = requests.get(
                self.base_url + "/usage",
                headers=headers,
                timeout=self.HEALTH_CHECK_TIMEOUT_SECONDS,
            )
            response.raise_for_status()

            data = response.json()
            key_usage = data.get("key", {})
            account = data.get("account", {})

            result["status"] = "healthy"
            result["key_usage"] = key_usage.get("usage")
            result["key_limit"] = key_usage.get("limit")
            result["plan"] = account.get("current_plan")
        except Exception as error:
            # A health check must never crash - report the problem instead.
            result["status"] = "unhealthy"
            result["message"] = str(error)

        return result
