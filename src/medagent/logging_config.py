"""Structured logging configuration using structlog.

All agent runs emit JSON-structured logs keyed by session_id so that
individual reasoning chains can be replayed from logs alone.
"""

import logging
import sys
from typing import Any, cast

import structlog
from structlog.types import EventDict, WrappedLogger


def _add_log_level(
    logger: WrappedLogger,
    method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """Inject the log level name into every event dict."""
    event_dict["level"] = method_name.upper()
    return event_dict


def configure_logging(log_level: str = "INFO") -> None:
    """Configure structlog with JSON rendering for production and pretty for dev.

    Args:
        log_level: Standard Python logging level string (INFO, DEBUG, etc.).
    """
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        _add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    is_tty = sys.stderr.isatty()

    if is_tty:
        renderer: Any = structlog.dev.ConsoleRenderer(colors=True)
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[*shared_processors, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level.upper())

    # Silence noisy libraries
    for noisy_lib in ("httpx", "httpcore", "openai", "anthropic"):
        logging.getLogger(noisy_lib).setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger for the given module name.

    Args:
        name: Module name, typically ``__name__``.

    Returns:
        A configured bound logger instance.
    """
    return cast(structlog.stdlib.BoundLogger, structlog.get_logger(name))
