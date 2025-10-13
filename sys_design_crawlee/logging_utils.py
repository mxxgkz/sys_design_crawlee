"""
Shared logging utilities for the crawler project.
Consolidates common logging functions used across multiple modules.
"""

import logging

def log_with_emoji(emoji: str, message: str, details: str = "", context=None):
    """
    Unified logging helper with emoji prefix.
    
    Args:
        emoji: Emoji to prefix the message
        message: Main log message
        details: Additional details to append
        context: Optional context object with log attribute
    """
    full_message = f"{emoji} {message}"
    if details:
        full_message += f" - {details}"
    
    if context and hasattr(context, 'log'):
        context.log.info(full_message)
    else:
        logger = logging.getLogger(__name__)
        logger.info(full_message)


def log_debug(context, message):
    """Debug logging helper"""
    if hasattr(context, 'log'):
        context.log.info(f"🔍 {message}")
    else:
        logger = logging.getLogger(__name__)
        logger.info(f"🔍 {message}")


def log_attempt(context, message, attempt_num):
    """Attempt logging helper"""
    if hasattr(context, 'log'):
        context.log.info(f"🔄 {message} (attempt {attempt_num})")
    else:
        logger = logging.getLogger(__name__)
        logger.info(f"🔄 {message} (attempt {attempt_num})")


def log_warning(context, message):
    """Warning logging helper"""
    if hasattr(context, 'log'):
        context.log.warning(f"⚠️ {message}")
    else:
        logger = logging.getLogger(__name__)
        logger.warning(f"⚠️ {message}")
