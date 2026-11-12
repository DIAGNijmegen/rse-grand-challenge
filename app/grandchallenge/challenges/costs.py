from datetime import timedelta

from django.contrib.auth.models import Permission
from django.db.models import Avg, Sum

from grandchallenge.algorithms.models import (
    AlgorithmImage,
    AlgorithmModel,
    Job,
)
from grandchallenge.cases.models import ImageFile
from grandchallenge.components.models import ComponentInterfaceValue
from grandchallenge.evaluation.models import (
    BatchJob,
    Evaluation,
    EvaluationGroundTruth,
    Method,
)
from grandchallenge.utilization.models import (
    BatchJobUtilization,
    EvaluationUtilization,
    JobUtilization,
    JobWarmPoolUtilization,
)


def _sum_compute_cost_by_key(*, queryset, key):
    """Sum compute cost grouped by ``key``, returning a {key_value: sum} map."""
    return {
        row[key]: row["compute_cost_euro_millicents__sum"] or 0
        for row in queryset.values(key)
        .order_by()
        .annotate(Sum("compute_cost_euro_millicents"))
    }


def _average_duration_by_key(*, queryset, key):
    """Average duration of completed jobs grouped by ``key``.

    Mirrors ``ComponentJobUtilizationManager.average_duration`` by only
    considering utilizations with a duration greater than zero. Returns a
    {key_value: average_duration} map.
    """
    return {
        row[key]: row["duration__avg"]
        for row in queryset.filter(duration__gt=timedelta(seconds=0))
        .values(key)
        .order_by()
        .annotate(Avg("duration"))
    }


def annotate_invoice_compute_costs(*, invoices):
    invoice_ids = [invoice.pk for invoice in invoices]

    algorithm_job_costs = _sum_compute_cost_by_key(
        queryset=JobUtilization.objects.filter(invoice_id__in=invoice_ids),
        key="invoice_id",
    )
    job_warm_pool_costs = _sum_compute_cost_by_key(
        queryset=JobWarmPoolUtilization.objects.filter(
            invoice_id__in=invoice_ids
        ),
        key="invoice_id",
    )
    evaluation_costs = _sum_compute_cost_by_key(
        queryset=EvaluationUtilization.objects.filter(
            invoice_id__in=invoice_ids
        ),
        key="invoice_id",
    )
    batch_job_costs = _sum_compute_cost_by_key(
        queryset=BatchJobUtilization.objects.filter(
            invoice_id__in=invoice_ids
        ),
        key="invoice_id",
    )

    for invoice in invoices:
        invoice.compute_cost_euro_millicents = (
            algorithm_job_costs.get(invoice.pk, 0)
            + job_warm_pool_costs.get(invoice.pk, 0)
            + evaluation_costs.get(invoice.pk, 0)
            + batch_job_costs.get(invoice.pk, 0)
        )


def annotate_job_duration_and_compute_costs(*, phases):
    phase_ids = [phase.pk for phase in phases]

    algorithm_job_costs = _sum_compute_cost_by_key(
        queryset=JobUtilization.objects.filter(phase_id__in=phase_ids),
        key="phase_id",
    )
    job_warm_pool_costs = _sum_compute_cost_by_key(
        queryset=JobWarmPoolUtilization.objects.filter(phase_id__in=phase_ids),
        key="phase_id",
    )
    evaluation_costs = _sum_compute_cost_by_key(
        queryset=EvaluationUtilization.objects.filter(
            phase_id__in=phase_ids, external_evaluation=False
        ),
        key="phase_id",
    )
    batch_job_costs = _sum_compute_cost_by_key(
        queryset=BatchJobUtilization.objects.filter(phase_id__in=phase_ids),
        key="phase_id",
    )

    average_algorithm_job_durations = _average_duration_by_key(
        queryset=JobUtilization.objects.filter(
            phase_id__in=phase_ids, job__status=Job.SUCCESS
        ),
        key="phase_id",
    )
    average_batch_job_durations = _average_duration_by_key(
        queryset=BatchJobUtilization.objects.filter(
            phase_id__in=phase_ids, batch_job__status=BatchJob.SUCCESS
        ),
        key="phase_id",
    )

    for phase in phases:
        phase.average_algorithm_job_duration = (
            average_algorithm_job_durations.get(phase.pk)
        )
        phase.average_batch_job_duration = average_batch_job_durations.get(
            phase.pk
        )
        phase.compute_cost_euro_millicents = (
            algorithm_job_costs.get(phase.pk, 0)
            + job_warm_pool_costs.get(phase.pk, 0)
            + evaluation_costs.get(phase.pk, 0)
            + batch_job_costs.get(phase.pk, 0)
        )


def annotate_storage_size(*, challenge):
    permission = Permission.objects.get(
        codename="view_job",
        content_type__app_label="algorithms",
        content_type__model="job",
    )

    algorithm_jobs = Job.objects.filter(
        jobgroupobjectpermission__group=challenge.admins_group,
        jobgroupobjectpermission__permission=permission,
    ).distinct()

    evaluation_jobs = Evaluation.objects.filter(
        submission__phase__challenge=challenge,
        submission__phase__external_evaluation=False,
    ).distinct()

    update_size_in_storage_and_registry(
        challenge=challenge,
        algorithm_jobs=algorithm_jobs,
        evaluation_jobs=evaluation_jobs,
    )


def update_size_in_storage_and_registry(
    *, challenge, algorithm_jobs, evaluation_jobs
):
    archive_image_storage = (
        ImageFile.objects.filter(
            image__componentinterfacevalue__archive_items__archive__phase__challenge=challenge
        )
        .distinct()
        .aggregate(Sum("size_in_storage"))
    )
    archive_file_storage = (
        ComponentInterfaceValue.objects.filter(
            archive_items__archive__phase__challenge=challenge
        )
        .distinct()
        .aggregate(Sum("size_in_storage"))
    )

    non_archive_input_image_storage = (
        ImageFile.objects.filter(
            image__componentinterfacevalue__algorithms_jobs_as_input__in=algorithm_jobs
        )
        .exclude(
            image__componentinterfacevalue__archive_items__archive__phase__challenge=challenge
        )
        .distinct()
        .aggregate(Sum("size_in_storage"))
    )
    non_archive_input_file_storage = (
        ComponentInterfaceValue.objects.filter(
            algorithms_jobs_as_input__in=algorithm_jobs
        )
        .exclude(archive_items__archive__phase__challenge=challenge)
        .distinct()
        .aggregate(Sum("size_in_storage"))
    )

    output_image_storage = (
        ImageFile.objects.filter(
            image__componentinterfacevalue__evaluation_evaluations_as_input__in=evaluation_jobs
        )
        .distinct()
        .aggregate(Sum("size_in_storage"))
    )
    output_file_storage = (
        ComponentInterfaceValue.objects.filter(
            evaluation_evaluations_as_input__in=evaluation_jobs
        )
        .distinct()
        .aggregate(Sum("size_in_storage"))
    )

    algorithm_storage = (
        AlgorithmImage.objects.filter(job__in=algorithm_jobs)
        .distinct()
        .aggregate(Sum("size_in_storage"), Sum("size_in_registry"))
    )

    algorithm_model_storage = (
        AlgorithmModel.objects.filter(job__in=algorithm_jobs)
        .distinct()
        .aggregate(Sum("size_in_storage"))
    )

    method_storage = (
        Method.objects.filter(phase__challenge=challenge)
        .distinct()
        .aggregate(Sum("size_in_storage"), Sum("size_in_registry"))
    )

    ground_truth_storage = (
        EvaluationGroundTruth.objects.filter(phase__challenge=challenge)
        .distinct()
        .aggregate(Sum("size_in_storage"))
    )

    items = [
        archive_image_storage,
        archive_file_storage,
        non_archive_input_image_storage,
        non_archive_input_file_storage,
        output_image_storage,
        output_file_storage,
        algorithm_storage,
        algorithm_model_storage,
        method_storage,
        ground_truth_storage,
    ]

    challenge.size_in_storage = sum(
        item["size_in_storage__sum"] or 0 for item in items
    )
    challenge.size_in_registry = sum(
        item.get("size_in_registry__sum") or 0 for item in items
    )
