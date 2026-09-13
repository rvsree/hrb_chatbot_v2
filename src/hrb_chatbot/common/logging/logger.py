"""Sets up logging so every file in the project prints messages the same way.

get_logger(name) factory used throughout the project. Distinct from
log_helper.py, which formats a tag onto an existing logger's message rather
than creating one.
"""

import logging
import sys

# How each line is laid out. The odd-looking %(levelname)-8s means "pad the level
# to 8 characters", which keeps the columns lined up between INFO and WARNING.
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
TIME_FORMAT = "%H:%M:%S"


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Return a logger with the given name, setting it up on first use.

    Safe to call repeatedly with the same name - the handlers check below stops a second call from attaching a duplicate printer.
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
