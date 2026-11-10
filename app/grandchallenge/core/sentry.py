import logging

from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from lambda_tasks.decorators import lambda_task

from config.lambda_tasks import LambdaTaskQueueChoices

logger = logging.getLogger(__name__)


def _sentry_soft_error():
    try:
        _sentry_hard_error()
    except RuntimeError as error:
        logger.error(str(error), exc_info=True)


def _sentry_hard_error():
    raise RuntimeError("Error raised to test sentry, ignore")


@lambda_task
def sentry_soft_error_task():
    _sentry_soft_error()


@lambda_task
def sentry_hard_error_task():
    _sentry_hard_error()


@lambda_task(queue=LambdaTaskQueueChoices.BATCH_MEM8G)
def sentry_soft_error_batch_task():
    _sentry_soft_error()


@lambda_task(queue=LambdaTaskQueueChoices.BATCH_MEM8G)
def sentry_hard_error_batch_task():
    _sentry_hard_error()


def sentry_soft_error_view(request):
    if not request.user.is_staff:
        raise PermissionDenied

    _sentry_soft_error()

    return HttpResponse("Error logged")


def sentry_hard_error_view(request):
    if not request.user.is_staff:
        raise PermissionDenied

    _sentry_hard_error()

    return HttpResponse("Error logged")


def sentry_soft_error_lamba_task_view(request):
    if not request.user.is_staff:
        raise PermissionDenied

    sentry_soft_error_task.execute_on_commit()

    return HttpResponse("Task scheduled")


def sentry_hard_error_lamba_task_view(request):
    if not request.user.is_staff:
        raise PermissionDenied

    sentry_hard_error_task.execute_on_commit()

    return HttpResponse("Task scheduled")


def sentry_soft_error_lamba_batch_task_view(request):
    if not request.user.is_staff:
        raise PermissionDenied

    sentry_soft_error_batch_task.execute_on_commit()

    return HttpResponse("Batch task scheduled")


def sentry_hard_error_lamba_batch_task_view(request):
    if not request.user.is_staff:
        raise PermissionDenied

    sentry_hard_error_batch_task.execute_on_commit()

    return HttpResponse("Batch task scheduled")
