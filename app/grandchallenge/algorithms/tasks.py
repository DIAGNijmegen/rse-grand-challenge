from typing import NamedTuple
from uuid import UUID

from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.core.cache import cache
from django.db.models import F, Max
from django.utils import timezone
from lambda_tasks.decorators import lambda_task
from lambda_tasks.logging import task_logger

from grandchallenge.algorithms.exceptions import TooManyJobsScheduled
from grandchallenge.components.tasks import (
    provision_invocation_input_data,
    remove_container_image_from_registry,
)
from grandchallenge.core.exceptions import LockNotAcquiredException
from grandchallenge.core.utils.query import check_lock_acquired
from grandchallenge.notifications.models import (
    Notification,
    NotificationTypeChoices,
)
from grandchallenge.subdomains.utils import reverse


@lambda_task(
    retry_on=(LockNotAcquiredException, TooManyJobsScheduled),
    retry_delay=60,
)
def execute_algorithm_job_for_inputs(*, job_pk: str | UUID):
    from grandchallenge.algorithms.models import Job

    with check_lock_acquired():
        job = Job.objects.select_for_update(nowait=True).get(pk=job_pk)

    if not job.inputs_complete:
        task_logger.info("Nothing to do, inputs are still being validated")
        return

    if not job.status == job.VALIDATING_INPUTS:
        # this task can be called multiple times with complete inputs,
        # and might have been queued for execution already, so ignore
        task_logger.info("Job has already been scheduled for execution")
        return

    if Job.objects.active().count() >= settings.ALGORITHMS_MAX_ACTIVE_JOBS:
        task_logger.info("Too many jobs scheduled")
        raise TooManyJobsScheduled

    task_logger.info("Job is ready, creating execution task")

    # Notify the job creator on failure
    job.task_on_failure = send_failed_job_notification.serialize(job_pk=job.pk)
    job.status = job.PENDING
    job.save()

    job.execute()


def filter_archive_items_for_algorithm(
    *,
    valid_archive_items_per_interface,
    scheduled_input_sets_per_interface,
):
    """
    Archive items that still need a job, grouped by interface.

    Both arguments are grouped by interface. From the valid archive items
    (those that have values for all of an interface's inputs), this excludes
    any whose value set has already been scheduled.

    Parameters
    ----------
    valid_archive_items_per_interface
        Candidate archive items grouped by interface (see
        ``get_archive_items_for_interfaces``).
    scheduled_input_sets_per_interface
        The input value sets that have already been scheduled, grouped by
        interface (each a set of frozensets of ComponentInterfaceValues).
        Archive items matching one of these are excluded.

    Returns
    -------
    Dictionary of ArchiveItems that still need a job, grouped by interface.
    """
    return {
        interface: [
            archive_item
            for archive_item in items
            if frozenset(archive_item.values.all())
            not in scheduled_input_sets_per_interface[interface]
        ]
        for interface, items in valid_archive_items_per_interface.items()
    }


@lambda_task
def send_failed_job_notification(*, job_pk: str | UUID):
    from grandchallenge.algorithms.models import Job

    job = Job.objects.get(pk=job_pk)

    if job.status == Job.FAILURE and job.creator is not None:
        algorithm = job.algorithm_image.algorithm
        url = reverse("algorithms:job-list", kwargs={"slug": algorithm.slug})
        Notification.send(
            kind=NotificationTypeChoices.JOB_STATUS,
            actor=job.creator,
            message=f"Unfortunately one of the jobs for algorithm {algorithm.title} "
            f"failed with an error",
            target=algorithm,
            description=url,
        )


class ChallengeNameAndUrl(NamedTuple):
    short_name: str
    get_absolute_url: str


@lambda_task
def update_associated_challenges():
    from grandchallenge.algorithms.models import Algorithm
    from grandchallenge.challenges.models import Challenge

    challenge_list = {}
    for algorithm in Algorithm.objects.iterator(chunk_size=1000):
        challenge_list[algorithm.pk] = [
            ChallengeNameAndUrl(
                short_name=challenge.short_name,
                get_absolute_url=challenge.get_absolute_url(),
            )
            for challenge in Challenge.objects.filter(
                phase__submission__algorithm_image__algorithm=algorithm
            ).distinct()
        ]

    cache.set("challenges_for_algorithms", challenge_list, timeout=None)


@lambda_task(retry_on=(LockNotAcquiredException,))
def update_algorithm_average_duration(*, algorithm_pk: str | UUID):
    from grandchallenge.algorithms.models import Algorithm, Job
    from grandchallenge.utilization.models import JobUtilization

    with check_lock_acquired():
        algorithm = Algorithm.objects.select_for_update(nowait=True).get(
            pk=algorithm_pk
        )

    algorithm.average_duration = JobUtilization.objects.filter(
        algorithm=algorithm, job__status=Job.SUCCESS
    ).average_duration()
    algorithm.save(update_fields=("average_duration",))


@lambda_task
def deactivate_old_algorithm_images():
    from grandchallenge.algorithms.models import AlgorithmImage

    images_to_remove = AlgorithmImage.objects.annotate(
        most_recent_job=Max("job__created", default=F("created"))
    ).filter(
        most_recent_job__lt=timezone.now() - relativedelta(years=1),
        algorithm__public=False,
        is_in_registry=True,
        algorithm__reader_study_algorithm_implementations__isnull=True,
    )

    for image in images_to_remove:
        remove_container_image_from_registry.execute_on_commit(
            pk=image.pk,
            app_label=AlgorithmImage._meta.app_label,
            model_name=AlgorithmImage._meta.model_name,
        )


@lambda_task(retry_on=(LockNotAcquiredException,))
def execute_invocation_for_inputs(*, invocation_pk: str | UUID):
    from grandchallenge.algorithms.models import Invocation

    with check_lock_acquired():
        invocation = Invocation.objects.select_for_update(nowait=True).get(
            pk=invocation_pk
        )

    if not invocation.inputs_complete:
        # Nothing to do
        return

    if invocation.status != Invocation.StatusChoices.VALIDATING_INPUTS:
        # this task can be called multiple times with complete inputs,
        # and might have been queued for execution already, so ignore
        return

    invocation.update_status(status=Invocation.StatusChoices.QUEUED)

    provision_invocation_input_data.execute_on_commit(**invocation.task_kwargs)
