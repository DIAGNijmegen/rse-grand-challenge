"""OpenTelemetry tracing setup.

Replaces the former AWS X-Ray SDK integration (``aws_xray_sdk.ext.django``
middleware + ``XRAY_RECORDER``). See the AWS migration guide:
https://docs.aws.amazon.com/xray/latest/devguide/migrate-xray-to-opentelemetry-python.html

Design
------
* Tracing is *opt-in*. Nothing is configured unless the standard
  ``OTEL_EXPORTER_OTLP_ENDPOINT`` environment variable is set. This mirrors the
  previous behaviour where X-Ray was disabled by default, and keeps local
  development and the test suite free of exporters.
* Spans are exported over OTLP/HTTP to a local collector (the ADOT Collector
  sidecar on ECS/Batch, or the ADOT Lambda layer's collector), which forwards
  them to AWS X-Ray.
* Trace IDs are generated in the AWS X-Ray format (``AwsXRayIdGenerator``)

The three runtimes that call ``configure_tracing``:

* Django API workers (ECS Fargate, long-lived uvicorn/gunicorn process).
* ``lambda_tasks`` handler on AWS Lambda.
* ``lambda_tasks`` entry point on AWS Batch (ECS Fargate, one-shot process).

On Lambda, prefer the managed ADOT Lambda layer (zero-code). When the layer is
in use it configures the SDK itself and sets ``OTEL_EXPORTER_OTLP_ENDPOINT`` to
the layer's collector, so this function detects the Lambda runtime and installs
the ``AwsXRayLambdaPropagator`` (which also reads the ``_X_AMZN_TRACE_ID``
environment variable AWS Lambda injects).
"""

import os

from opentelemetry import propagate, trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter,
)
from opentelemetry.propagators.aws import (
    AwsXRayLambdaPropagator,
    AwsXRayPropagator,
)
from opentelemetry.sdk.extension.aws.trace import AwsXRayIdGenerator
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def tracing_is_enabled() -> bool:
    """Whether an OTLP endpoint has been configured.

    Tracing is only set up when an endpoint is present, so that local
    development and the test suite do not attempt to export spans.
    """
    return bool(os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip())


def _running_on_lambda() -> bool:
    """Whether the current process is an AWS Lambda invocation."""
    return bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))


def configure_tracing(*, service_name: str) -> None:
    """Configure the global OpenTelemetry tracer provider.

    No-op unless ``OTEL_EXPORTER_OTLP_ENDPOINT`` is set. Safe to call more than
    once: once a non-default ``TracerProvider`` is installed, subsequent calls
    return early so the Django API worker and the Lambda/Batch entry points can
    all call it without clobbering each other.

    :param service_name: Value for the ``service.name`` resource attribute,
        used as the service name shown in the X-Ray service map.
    """
    if not tracing_is_enabled():
        return

    if isinstance(trace.get_tracer_provider(), TracerProvider):
        # Already configured by an earlier call in this process.
        return

    resource = Resource.create(attributes={"service.name": service_name})

    tracer_provider = TracerProvider(
        resource=resource,
        id_generator=AwsXRayIdGenerator(),
    )
    tracer_provider.add_span_processor(
        BatchSpanProcessor(span_exporter=OTLPSpanExporter())
    )

    trace.set_tracer_provider(tracer_provider)

    # Keep X-Ray trace-header format so traces correlate across services.
    propagate.set_global_textmap(
        AwsXRayLambdaPropagator()
        if _running_on_lambda()
        else AwsXRayPropagator()
    )
