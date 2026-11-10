"""OpenTelemetry tracing setup for the Django API workers.

The tracer-provider setup (SigV4-signed OTLP/HTTP exporter to the AWS X-Ray
endpoint, X-Ray id generator and propagator, opt-in on the OTLP endpoint
variables) is shared with the Lambda and Batch execution paths and lives in
``lambda_tasks.tracing`` (installed via the ``django-lambda-tasks`` ``otel``
extra). That shared setup also instruments the libraries the tasks use
(psycopg, botocore, requests, httpx, redis), so those are covered on every
runtime.

This module only adds what is specific to the API worker: the ``service.name``
(from ``SESSION_COOKIE_DOMAIN``) and the ``DjangoInstrumentor`` request tracing
that replaces the old ``XRayMiddleware``.
"""

import os

from lambda_tasks import tracing as lambda_tasks_tracing
from opentelemetry.instrumentation.django import DjangoInstrumentor


def configure_tracing(*, service_name: str) -> None:
    """Configure tracing for the Django API worker.

    No-op unless an OTLP endpoint is set. Delegates the tracer-provider setup
    and the shared library instrumentation to ``lambda_tasks.tracing`` (which
    returns ``None`` when tracing is disabled or already configured), then adds
    the Django request instrumentation.

    :param service_name: Value for the ``service.name`` resource attribute,
        shown as the service name in the X-Ray service map. Passed to the
        shared setup via ``OTEL_SERVICE_NAME``; an explicitly configured value
        still wins.
    """
    os.environ.setdefault("OTEL_SERVICE_NAME", service_name)

    if lambda_tasks_tracing.configure_tracing() is None:
        return
    else:
        DjangoInstrumentor().instrument()
