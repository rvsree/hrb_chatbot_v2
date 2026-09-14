# The HRB chatbot, as a container image.
#
# Build it from the REPOSITORY ROOT, not from anywhere else:
#
#     docker build -t hrb-chatbot:local .
#
# The build context has to be the repository root, because that is where
# requirements.txt and src/ live.
#
# Two stages
# ----------
# The builder stage installs the dependencies; the runtime stage copies the
# finished virtual environment across and nothing else. The compilers and
# build headers some wheels need never reach the final image, which keeps it
# smaller and removes tooling an attacker could otherwise use.

# ---------------------------------------------------------------------------
# Stage 1 - build the virtual environment
# ---------------------------------------------------------------------------
# 3.12, not 3.13+: chromadb depends on Pydantic v1 internals that Python 3.13
# removed - see the workshop README this project's RAG approach is modeled on.
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /srv

# Requirements are copied on their own, before the source, so an ordinary code
# edit reuses Docker's cached install layer instead of reinstalling everything.
COPY requirements.txt ./
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip && \
    /opt/venv/bin/pip install -r requirements.txt

# ---------------------------------------------------------------------------
# Stage 2 - the image that actually runs
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PORT=8093

# curl is for the HEALTHCHECK below - without it the health check can never
# pass. libmagic1 is what python-magic actually loads at import time (it's a
# ctypes wrapper, not a compiled extension, so pip install needs nothing
# extra - only the runtime import does) - confirmed by the build failing
# without it when python-magic-bin (Windows-only) was swapped out.
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl libmagic1 && \
    rm -rf /var/lib/apt/lists/*

# Run as a normal user. Nothing here needs root, and a container that starts
# as root stays root if somebody finds a way to execute code in it.
RUN useradd --create-home --uid 10001 hrbchat

COPY --from=builder /opt/venv /opt/venv

# /srv holds src/ so imports written as `from src.hrb_chatbot...` resolve the
# same way they do when running locally from the repository root - see
# docs/RAG-ROADMAP.md's note on the src.hrb_chatbot.* import convention.
# No .env is copied in: a container is configured through environment
# variables at run time (see README.md's Docker section), not a file baked
# into the image.
WORKDIR /srv
COPY --chown=hrbchat:hrbchat src ./src

# ChromaDB's persistent store, the SQLite metadata file, and uploaded PDFs
# all write under data/ (relative to /srv). /srv itself is root-owned and
# not writable by hrbchat, so without this, the app fails at startup with a
# confusing "unable to open database file" / "could not connect to tenant" -
# it's actually a permission error, not a missing-database error. Only data/
# gets hrbchat ownership - the code under src/ stays read-only to the
# process that runs it.
RUN mkdir -p data && chown hrbchat:hrbchat data

USER hrbchat

EXPOSE 8093

# GET /ping only confirms the process is up - no provider is called, no
# tokens spent. A probe running every 30 seconds forever must never be able
# to cost money or fail because a backend (not this container) is down -
# that's what GET /health is for, checked deliberately by hand, not by this probe.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl --fail --silent http://127.0.0.1:8093/ping || exit 1

# No --reload here - reload runs the app in a child process, which breaks
# both container signal handling and any attached debugger.
CMD ["uvicorn", "src.hrb_chatbot.main:app", "--host", "0.0.0.0", "--port", "8093"]
