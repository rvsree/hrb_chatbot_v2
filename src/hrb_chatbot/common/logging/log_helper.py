"""
Log Helper - Convenience functions for agent-tagged logging.

This module provides helper functions to easily add agent type tags to log messages.
"""

from typing import Optional
from src.app.common.config.agent_log_tags import format_log_tag, format_log_message


def log_with_agent_tag(
    logger,
    level: str,
    base_tag: str,
    message: str,
    agent_name: Optional[str] = None,
    agent_type: Optional[str] = None,
    **kwargs
):
    """
    Log message with agent type tag.
    
    Args:
        logger: Logger instance
        level: Log level ('info', 'warning', 'error', 'debug')
        base_tag: Base log tag (e.g., "[ORCHESTRATOR]")
        message: Log message
        agent_name: Agent name/identifier
        agent_type: Agent type string
        **kwargs: Additional arguments to pass to logger method
    """
    tagged_message = format_log_message(message, base_tag, agent_name, agent_type)
    
    if level == "info":
        logger.info(tagged_message, **kwargs)
    elif level == "warning":
        logger.warning(tagged_message, **kwargs)
    elif level == "error":
        logger.error(tagged_message, **kwargs)
    elif level == "debug":
        logger.debug(tagged_message, **kwargs)
    else:
        logger.info(tagged_message, **kwargs)


# Convenience functions for common agent types
def log_wa(logger, level: str, base_tag: str, message: str, **kwargs):
    """Log with Workflow Agent (WA) tag."""
    log_with_agent_tag(logger, level, base_tag, message, agent_type="workflow", **kwargs)


def log_da(logger, level: str, base_tag: str, message: str, agent_name: Optional[str] = None, **kwargs):
    """Log with Domain Agent (DA) tag."""
    log_with_agent_tag(logger, level, base_tag, message, agent_name=agent_name, agent_type="domain", **kwargs)


def log_sa(logger, level: str, base_tag: str, message: str, agent_name: Optional[str] = None, **kwargs):
    """Log with System Agent (SA) tag."""
    log_with_agent_tag(logger, level, base_tag, message, agent_name=agent_name, agent_type="system", **kwargs)


def log_ta(logger, level: str, base_tag: str, message: str, agent_name: Optional[str] = None, **kwargs):
    """Log with Task Agent (TA) tag."""
    log_with_agent_tag(logger, level, base_tag, message, agent_name=agent_name, agent_type="task", **kwargs)


def log_aa(logger, level: str, base_tag: str, message: str, agent_name: Optional[str] = None, **kwargs):
    """Log with Autonomous Agent (AA) tag."""
    log_with_agent_tag(logger, level, base_tag, message, agent_name=agent_name, agent_type="autonomous", **kwargs)
