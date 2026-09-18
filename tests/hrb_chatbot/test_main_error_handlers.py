"""Tests for main.py's http_exception_handler() - specifically that it
reshapes a raw HTTPException (rate_limiter.py's only real caller today)
into the project's standard {"error", "code"} envelope, and correctly
separates real HTTP headers (Retry-After) from the JSON body rather than
leaking them into it. Called directly as a unit test rather than through
100 real requests to actually trip the rate limiter - see
common/rate_limiting/test_rate_limiter.py for the limiter's own logic."""

import json

from fastapi import HTTPException

from src.hrb_chatbot.main import http_exception_handler


async def test_a_429_is_reshaped_into_the_standard_error_envelope():
    exc = HTTPException(status_code=429, detail="Rate limit exceeded: try again in 5s.")

    response = await http_exception_handler(request=None, exc=exc)

    assert response.status_code == 429
    body = json.loads(response.body)
    assert body["error"] == "Rate limit exceeded: try again in 5s."
    assert body["code"] == "RATE_LIMITED"


async def test_retry_after_becomes_a_real_header_not_a_body_field():
    exc = HTTPException(status_code=429, detail="Rate limited.", headers={"Retry-After": "7"})

    response = await http_exception_handler(request=None, exc=exc)

    assert response.headers["retry-after"] == "7"
    body = json.loads(response.body)
    assert "headers" not in body
    assert "Retry-After" not in body


async def test_a_401_is_reshaped_with_the_unauthenticated_code():
    exc = HTTPException(status_code=401, detail="Missing required identity header(s): X-Role.")

    response = await http_exception_handler(request=None, exc=exc)

    assert response.status_code == 401
    body = json.loads(response.body)
    assert body["code"] == "UNAUTHENTICATED"


async def test_a_403_is_reshaped_with_the_forbidden_code():
    exc = HTTPException(status_code=403, detail="Forbidden.")

    response = await http_exception_handler(request=None, exc=exc)

    assert response.status_code == 403
    body = json.loads(response.body)
    assert body["code"] == "FORBIDDEN"


async def test_an_http_exception_with_no_specific_mapping_gets_a_generic_code():
    exc = HTTPException(status_code=418, detail="I'm a teapot.")

    response = await http_exception_handler(request=None, exc=exc)

    assert response.status_code == 418
    body = json.loads(response.body)
    assert body["code"] == "INTERNAL_ERROR"
