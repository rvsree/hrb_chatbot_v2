"""OAuth2 client-credentials - acquires and caches a Bearer token for calling hrb_lms_mcp."""

import time

import httpx

from src.hrb_chatbot.common.config.settings import read_setting
from src.hrb_chatbot.common.logging.logger import get_logger

logger = get_logger("oauth_client")

# Cached in module state - one client identity, one token, refreshed near expiry (not per-request).
_cached_token: str | None = None
_cached_token_expires_at: float = 0.0


async def get_access_token() -> str:
    """Returns a valid Bearer token, fetching a new one if missing or near expiry."""
    global _cached_token, _cached_token_expires_at

    if _cached_token and time.monotonic() < _cached_token_expires_at - 30:
        return _cached_token

    token_url = read_setting(None, "HRB_LMS_MCP_OAUTH_TOKEN_URL", "http://127.0.0.1:8190/oauth/token")
    client_id = read_setting(None, "HRB_LMS_MCP_OAUTH_CLIENT_ID", "")
    client_secret = read_setting(None, "HRB_LMS_MCP_OAUTH_CLIENT_SECRET", "")

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(token_url, json={"client_id": client_id, "client_secret": client_secret})
        response.raise_for_status()
        body = response.json()

    _cached_token = body["access_token"]
    _cached_token_expires_at = time.monotonic() + body["expires_in"]
    logger.info("Acquired new OAuth2 access token for hrb_lms_mcp, expires_in=%ss", body["expires_in"])
    return _cached_token
