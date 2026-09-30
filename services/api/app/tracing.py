from __future__ import annotations

from functools import wraps
from functools import lru_cache
import os
from typing import Callable, TypeVar

from app.settings import settings

F = TypeVar("F", bound=Callable)


@lru_cache(maxsize=1)
def _otel_tracer():
    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    provider = TracerProvider(resource=Resource.create({"service.name": "halfspace-api"}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)
    return trace.get_tracer("halfspace.search")


def traced(name: str):
    """Use Langfuse when configured, with OpenTelemetry spans as a fallback."""
    def decorate(fn: F) -> F:
        if settings.langfuse_public_key and settings.langfuse_secret_key:
            try:
                from langfuse import Langfuse, observe
                Langfuse(public_key=settings.langfuse_public_key, secret_key=settings.langfuse_secret_key, host=settings.langfuse_host)
                return observe(name=name, capture_input=False, capture_output=False)(fn)
            except (ImportError, AttributeError, RuntimeError):
                pass
        if settings.otel_enabled or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
            try:
                tracer = _otel_tracer()
                @wraps(fn)
                def wrapped(*args, **kwargs):
                    with tracer.start_as_current_span(name):
                        return fn(*args, **kwargs)
                return wrapped  # type: ignore[return-value]
            except ImportError:
                pass
        return fn
    return decorate
