"""Structured logs with trace correlation and credentials removed before export."""
from __future__ import annotations

import logging
import re
from collections.abc import Mapping

import structlog

_SECRET = re.compile(r"(?i)([?&](?:key|api[_-]?key|token|access_token|secret|password)=)[^&\s\"']+")
_USERINFO = re.compile(r"(\w+://)[^/@\s]+:[^/@\s]+@")


def redact(value):
    if isinstance(value, Mapping):
        return {k: '[REDACTED]' if any(s in k.lower() for s in
                ('password', 'secret', 'token', 'authorization', 'api_key')) else redact(v)
                for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    if isinstance(value, str):
        return _USERINFO.sub(r'\1[REDACTED]@', _SECRET.sub(r'\1[REDACTED]', value))
    return value


def enrich(_, __, event):
    try:
        from opentelemetry import trace
    except ImportError:
        return redact(event)
    ctx = trace.get_current_span().get_span_context()
    if ctx.is_valid:
        event.update(trace_id=f'{ctx.trace_id:032x}', span_id=f'{ctx.span_id:016x}')
    return redact(event)


class RedactionFilter(logging.Filter):
    def filter(self, record):
        record.msg = redact(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(redact(item) for item in record.args)
        elif isinstance(record.args, dict):
            record.args = redact(record.args)
        return True


def configure_logging():
    logging.basicConfig(format='%(message)s', level=logging.INFO)
    # HTTP client INFO messages include full URLs; credentials must never reach handlers.
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpx2').setLevel(logging.WARNING)
    # Uvicorn config may replace handlers later; a logger filter survives that setup.
    logging.getLogger('uvicorn.access').addFilter(RedactionFilter())
    structlog.configure(processors=[structlog.processors.TimeStamper(fmt='iso'), enrich,
                                   structlog.processors.JSONRenderer()])
