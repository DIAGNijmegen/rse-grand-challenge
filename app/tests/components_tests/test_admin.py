from datetime import timedelta

import pytest
from django.contrib.admin import AdminSite

from grandchallenge.algorithms.admin import JobAdmin
from grandchallenge.algorithms.models import Job
from grandchallenge.components.admin import requeue_jobs
from grandchallenge.evaluation.admin import BatchJobAdmin, EvaluationAdmin
from grandchallenge.evaluation.models import BatchJob, Evaluation
from tests.algorithms_tests.factories import AlgorithmJobFactory
from tests.evaluation_tests.factories import (
    BatchJobFactory,
    EvaluationFactory,
)


@pytest.mark.parametrize("factory", (AlgorithmJobFactory, EvaluationFactory))
@pytest.mark.django_db
def test_job_reset_after_admin_requeue(factory):
    job = factory(
        time_limit=60,
        status=Job.FAILURE,
        exec_duration=timedelta(seconds=1337),
        invoke_duration=timedelta(seconds=1874),
        use_warm_pool=True,
    )
    job.utilization.duration = timedelta(minutes=1)
    job.utilization.save()

    jobs = factory._meta.model.objects.all()

    assert len(jobs) == 1
    assert job.utilization.duration is not None
    assert job.exec_duration == timedelta(seconds=1337)
    assert job.invoke_duration == timedelta(seconds=1874)
    assert job.use_warm_pool is True

    requeue_jobs(None, None, jobs)

    job.refresh_from_db()

    assert job.status == Job.RETRY
    assert job.utilization.duration is None
    assert job.exec_duration is None
    assert job.invoke_duration is None
    assert job.use_warm_pool is False


@pytest.mark.parametrize(
    "factory,model,admin_class",
    (
        (AlgorithmJobFactory, Job, JobAdmin),
        (EvaluationFactory, Evaluation, EvaluationAdmin),
        (BatchJobFactory, BatchJob, BatchJobAdmin),
    ),
)
@pytest.mark.django_db
def test_external_admin_link(factory, model, admin_class, settings, mocker):
    settings.COMPONENTS_DEFAULT_BACKEND = "grandchallenge.components.backends.amazon_sagemaker_training.AmazonSageMakerTrainingExecutor"

    job = factory(time_limit=60)

    # The admin link must not build the (expensive) inference task definitions.
    task_definitions = mocker.patch(
        f"{model.__module__}.{model.__name__}.inference_task_definitions",
        new_callable=mocker.PropertyMock,
    )

    model_admin = admin_class(model, AdminSite())
    link = model_admin.external_admin(job)

    task_definitions.assert_not_called()

    expected_url = job.get_executor(
        backend=settings.COMPONENTS_DEFAULT_BACKEND
    ).external_admin_url
    assert expected_url in link
