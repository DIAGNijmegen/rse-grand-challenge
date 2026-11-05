"""OpenTelemetry tracing setup for the Django API workers.

The tracer-provider setup (SigV4-signed OTLP/HTTP exporter to the AWS X-Ray
endpoint, X-Ray id generator and propagator, opt-in on the OTLP endpoint
variables) is shared with the Lambda and Batch execution paths and lives in
``lambda_tasks.tracing`` (installed via the ``django-lambda-tasks`` ``otel``
extra). That shared setup also instruments the libraries the tasks use
(psycopg, botocore, requests, httpx, redis), so those are covered on every
runtime.

This module adds what is specific to the API worker:

* ``configure_tracing`` — the ``service.name`` (from ``SESSION_COOKIE_DOMAIN``)
  and the shared provider setup. Called at settings-import time.
* ``instrument_django_requests`` — the ``DjangoInstrumentor`` request tracing
  that replaces the old ``XRayMiddleware``. This **must** be called from an
  ``AppConfig.ready()``, not at settings-import time: ``DjangoInstrumentor``
  injects its middleware into ``settings.MIDDLEWARE``, and a mutation made
  while the settings module is still importing does not survive into the
  finalised ``LazySettings`` — so the request span would never be created and
  every DB/AWS/HTTP span would be orphaned into its own trace. Running it in
  ``ready()`` (after settings are configured, before the handler loads
  middleware) makes the injection stick.
"""

import logging
import os

from lambda_tasks import tracing as lambda_tasks_tracing
from opentelemetry.instrumentation.django import DjangoInstrumentor


class SuppressContextDetachError(logging.Filter):
    """Drop OpenTelemetry's benign "Failed to detach context" log records.

    Under ASGI (uvicorn worker), Django adapts the sync OTel request
    middleware with ``sync_to_async``, so the context ``attach`` and ``detach``
    can straddle two ``contextvars`` contexts. ``opentelemetry.context.detach``
    catches the resulting ``ValueError`` and logs it via ``logger.exception`` —
    the span is still recorded and exported; only the cleanup logs noise. This
    filter suppresses that one message.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        return "Failed to detach context" not in record.getMessage()


def configure_tracing(*, service_name: str) -> None:
    """Configure the tracer provider for the Django API worker.

    No-op unless an OTLP endpoint is set. Delegates the provider setup and the
    shared library instrumentation to ``lambda_tasks.tracing``. Does **not**
    install the Django request instrumentation — see
    ``instrument_django_requests``.

    :param service_name: Value for the ``service.name`` resource attribute.
        Passed to the shared setup via ``OTEL_SERVICE_NAME``; an explicitly
        configured value still wins.
    """
    os.environ.setdefault("OTEL_SERVICE_NAME", service_name)
    lambda_tasks_tracing.configure_tracing()


def instrument_django_requests() -> None:
    """Install Django request instrumentation. Call from ``AppConfig.ready()``.

    No-op unless tracing is enabled. Creates the per-request SERVER span that
    the DB / AWS / HTTP spans attach to; without it those spans are orphaned.
    """
    if not lambda_tasks_tracing.tracing_is_enabled():
        return
    else:
        DjangoInstrumentor().instrument()
