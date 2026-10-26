"""OTLP is optional at runtime; network export happens on bounded background queues."""
from __future__ import annotations

import os

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

_initialized = False


def configure_tracing(service='traffic-api'):
    global _initialized
    if _initialized:
        return
    _initialized = True
    resource = Resource.create({'service.name': service})
    provider = TracerProvider(resource=resource)
    endpoint = os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT')
    if endpoint:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        provider.add_span_processor(BatchSpanProcessor(
            OTLPSpanExporter(endpoint=endpoint.rstrip('/') + '/v1/traces', timeout=2),
            max_queue_size=512, max_export_batch_size=64))
        import logging

        from opentelemetry._logs import set_logger_provider
        from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
        from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
        from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
        logs = LoggerProvider(resource=resource)
        logs.add_log_record_processor(BatchLogRecordProcessor(
            OTLPLogExporter(endpoint=endpoint.rstrip('/') + '/v1/logs', timeout=2),
            max_queue_size=512, max_export_batch_size=64))
        set_logger_provider(logs)
        # Only sanitized structlog events use this named logger.
        logging.getLogger('traffic-api').addHandler(LoggingHandler(logger_provider=logs))
    trace.set_tracer_provider(provider)


def exemplar():
    ctx = trace.get_current_span().get_span_context()
    return {'trace_id': f'{ctx.trace_id:032x}'} if ctx.is_valid else None
