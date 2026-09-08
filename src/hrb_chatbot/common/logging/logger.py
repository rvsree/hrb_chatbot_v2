"""Sets up logging so every file in the project prints messages the same way.

This is the get_logger(name) factory every client imports. It is deliberately
separate from log_helper.py, which does something different: log_helper.py
formats an agent-type tag onto a message you hand it, using a logger you already
have - it does not create one. This module is what creates that logger.

How to use it
-------------
    from src.hrb_chatbot.common.logging.logger import get_logger

    logger = get_logger("my_module")
    logger.info("Starting up")
    logger.warning("OPENAI_API_KEY not set")

Output looks like:
    21:00:43 | WARNING  | openai_client | OPENAI_API_KEY not set
"""

import logging
import sys

# How each line is laid out. The odd-looking %(levelname)-8s means "pad the level
# to 8 characters", which keeps the columns lined up between INFO and WARNING.
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
TIME_FORMAT = "%H:%M:%S"


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Return a logger with the given name, setting it up on first use.

    It is safe to call this as many times as you like with the same name: Python
    keeps one logger per name, and the `if not logger.handlers` check below stops
    us attaching a second printer to it. Without that check, calling this twice
    would make every message appear twice.
    """
    logger = logging.getLogger(name)

    # Already set up by an earlier call - just hand it back.
    if logger.handlers:
        return logger

    # A handler decides where messages go. This one sends them to the terminal.
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=TIME_FORMAT))

    logger.addHandler(handler)
    logger.setLevel(level)

    # Stop messages also travelling up to Python's root logger, which would
    # print them a second time in some setups.
    logger.propagate = False

    return logger
