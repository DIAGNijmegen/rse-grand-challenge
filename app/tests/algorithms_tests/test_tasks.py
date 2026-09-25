from datetime import timedelta
from pathlib import Path

import pytest
from actstream.models import Follow
from django.core import mail
from django.core.exceptions import ObjectDoesNotExist
from django.utils.timezone import now
from guardian.shortcuts import assign_perm

from grandchallenge.algorithms.models import AlgorithmImage, Job
from grandchallenge.algorithms.tasks import (
    deactivate_old_algorithm_images,
    execute_algorithm_job_for_inputs,
    send_failed_job_notification,
)
from grandchallenge.components.models import (
    APIMethodChoices,
    ComponentInterface,
    ComponentInterfaceValue,
    ImportStatusChoices,
    InterfaceKindChoices,
)
from grandchallenge.components.tasks import (
    upload_to_registry_and_sagemaker,
    validate_container_image,
)
from grandchallenge.notifications.models import Notification
from tests.algorithms_tests.factories import (
    AlgorithmFactory,
    AlgorithmImageFactory,
    AlgorithmInterfaceFactory,
    AlgorithmJobFactory,
    ReaderStudyAlgorithmImplementationFactory,
)
from tests.components_tests.factories import (
    ComponentInterfaceFactory,
    ComponentInterfaceValueFactory,
)
from tests.conftest import get_interface_form_data
from tests.factories import (
    ImageFileFactory,
    UserFactory,
)
from tests.utils import get_view_for_user, recurse_callbacks
from tests.verification_tests.factories import VerificationFactory


@pytest.mark.django_db
def test_algorithm(client, settings, django_capture_on_commit_callbacks):
    settings.LAMBDA_TASKS_EAGER = True

    assert Job.objects.count() == 0

    # Create the algorithm image
    ai = AlgorithmImageFactory(
        is_manifest_valid=True, is_in_registry=True, is_desired_version=True
    )

    user = UserFactory()
    ai.algorithm.add_editor(user)
    VerificationFactory(user=user, is_verified=True)

    # Run the algorithm, it will create a results.json and an output.tif
    image_file = ImageFileFactory(
        file__from_path=Path(__file__).parent / "resources" / "input_file.tif"
    )
    assign_perm("cases.view_image", user, image_file.image)

    input_interface = ComponentInterface.objects.get(
        slug="generic-medical-image"
    )
    json_result_interface = ComponentInterface.objects.get(
        slug="results-json-file"
    )
    heatmap_interface = ComponentInterface.objects.get(slug="generic-overlay")
    interface = AlgorithmInterfaceFactory(
        inputs=[input_interface, heatmap_interface],
        outputs=[json_result_interface, heatmap_interface],
    )
    ai.algorithm.interfaces.add(interface)

    with django_capture_on_commit_callbacks() as callbacks:
        get_view_for_user(
            viewname="algorithms:job-create",
            client=client,
            method=client.post,
            user=user,
            reverse_kwargs={
                "slug": ai.algorithm.slug,
                "interface_pk": interface.pk,
            },
            follow=True,
            data={
                **get_interface_form_data(
                    interface_slug=input_interface.slug,
                    data=image_file.image.pk,
                    existing_data=True,
                ),
                **get_interface_form_data(
                    interface_slug=heatmap_interface.slug,
                    data=image_file.image.pk,
                    existing_data=True,
                ),
            },
        )

    recurse_callbacks(
        callbacks=callbacks,
        django_capture_on_commit_callbacks=django_capture_on_commit_callbacks,
    )

    # There should be a single, successful job
    job = Job.objects.filter(algorithm_image=ai).get()

    assert job.error_message == ""
    assert job.status == job.SUCCESS
    assert job.exec_duration == timedelta(seconds=1337)
    assert job.invoke_duration == timedelta(seconds=1874)
    assert job.utilization.duration.total_seconds() > 0

    # The job should have two ComponentInterfaceValues,
    # one for the results.json and one for output.tif
    assert len(job.outputs.all()) == 2

    json_result_civ = job.outputs.get(interface=json_result_interface)
    assert json_result_civ.value

    heatmap_civ = job.outputs.get(interface=heatmap_interface)
    assert heatmap_civ.image.name == "input_file.tif"

    # We add another ComponentInterface with file value and run the algorithm again
    metrics_file = ComponentInterface.objects.get(slug="metrics-json-file")
    interface2 = AlgorithmInterfaceFactory(
        inputs=[input_interface, heatmap_interface],
        outputs=[
            json_result_interface,
            heatmap_interface,
            metrics_file,
        ],
    )
    ai.algorithm.interfaces.add(interface2)
    image_file = ImageFileFactory(
        file__from_path=Path(__file__).parent / "resources" / "input_file.tif"
    )
    assign_perm("cases.view_image", user, image_file.image)

    with django_capture_on_commit_callbacks() as callbacks:
        get_view_for_user(
            viewname="algorithms:job-create",
            client=client,
            method=client.post,
            user=user,
            reverse_kwargs={
                "slug": ai.algorithm.slug,
                "interface_pk": interface2.pk,
            },
            follow=True,
            data={
                **get_interface_form_data(
                    interface_slug=input_interface.slug,
                    data=image_file.image.pk,
                    existing_data=True,
                ),
                **get_interface_form_data(
                    interface_slug=heatmap_interface.slug,
                    data=image_file.image.pk,
                    existing_data=True,
                ),
            },
        )

    recurse_callbacks(
        callbacks=callbacks,
        django_capture_on_commit_callbacks=django_capture_on_commit_callbacks,
    )

    jobs = Job.objects.filter(
        algorithm_image=ai, inputs__image=image_file.image
    ).distinct()
    # There should be a single, successful job
    assert len(jobs) == 1

    # The job should have three ComponentInterfaceValues
    assert len(jobs[0].outputs.all()) == 3
    metrics_civ = jobs[0].outputs.get(interface=metrics_file)
    assert metrics_civ.value


@pytest.mark.django_db
def test_algorithm_with_invalid_output(
    client, settings, django_capture_on_commit_callbacks
):
    settings.LAMBDA_TASKS_EAGER = True

    assert Job.objects.count() == 0

    ai = AlgorithmImageFactory(
        image=None,
        is_manifest_valid=True,
        is_in_registry=True,
        is_desired_version=True,
    )

    user = UserFactory()
    ai.algorithm.add_editor(user)
    VerificationFactory(user=user, is_verified=True)

    # Make sure the job fails when trying to upload an invalid file
    input_interface = ComponentInterface.objects.get(
        slug="generic-medical-image"
    )
    detection_interface = ComponentInterfaceFactory(
        store_in_database=False,
        relative_path="some_text.txt",
        slug="detection-json-file",
        kind=ComponentInterface.Kind.ANY,
    )
    interface = AlgorithmInterfaceFactory(
        inputs=[input_interface], outputs=[detection_interface]
    )
    ai.algorithm.interfaces.add(interface)

    image_file = ImageFileFactory(
        file__from_path=Path(__file__).parent / "resources" / "input_file.tif"
    )
    assign_perm("cases.view_image", user, image_file.image)

    with django_capture_on_commit_callbacks() as callbacks:
        get_view_for_user(
            viewname="algorithms:job-create",
            client=client,
            method=client.post,
            user=user,
            reverse_kwargs={
                "slug": ai.algorithm.slug,
                "interface_pk": interface.pk,
            },
            follow=True,
            data={
                **get_interface_form_data(
                    interface_slug=input_interface.slug,
                    data=image_file.image.pk,
                    existing_data=True,
                ),
            },
        )

    recurse_callbacks(
        callbacks=callbacks,
        django_capture_on_commit_callbacks=django_capture_on_commit_callbacks,
    )

    jobs = Job.objects.filter(
        algorithm_image=ai, inputs__image=image_file.image, status=Job.FAILURE
    ).all()
    assert len(jobs) == 1
    assert (
        jobs.first().error_message
        == "The output file 'some_text.txt' is not valid json"
    )
    assert len(jobs[0].outputs.all()) == 0


@pytest.mark.django_db
def test_execute_algorithm_job_for_missing_inputs():
    creator = UserFactory()

    # Create the algorithm image
    alg = AlgorithmImageFactory()
    alg.algorithm.add_editor(creator)

    # create the job without value for the ComponentInterfaceValues
    ci = ComponentInterface.objects.get(slug="generic-medical-image")
    ComponentInterfaceValue.objects.create(interface=ci)
    interface = AlgorithmInterfaceFactory(
        inputs=[ci], outputs=[ComponentInterfaceFactory()]
    )
    alg.algorithm.interfaces.add(interface)
    job = AlgorithmJobFactory(
        creator=creator,
        algorithm_image=alg,
        time_limit=alg.algorithm.time_limit,
        algorithm_interface=interface,
    )
    execute_algorithm_job_for_inputs(job_pk=job.pk)

    # nothing happens since the input is missing
    job.refresh_from_db()
    assert job.status == Job.PENDING
    assert job.error_message == ""


@pytest.mark.django_db
def test_execute_algorithm_job_sets_on_failed_jobs(
    django_capture_on_commit_callbacks,
):
    creator = UserFactory()

    # Create the algorithm image
    alg = AlgorithmImageFactory()
    alg.algorithm.add_editor(creator)

    ci = ComponentInterfaceFactory(kind=InterfaceKindChoices.STRING)
    civ = ComponentInterfaceValueFactory(interface=ci, value="foo")
    interface = AlgorithmInterfaceFactory(
        inputs=[ci], outputs=[ComponentInterfaceFactory()]
    )
    alg.algorithm.interfaces.add(interface)
    job = AlgorithmJobFactory(
        creator=creator,
        algorithm_image=alg,
        time_limit=alg.algorithm.time_limit,
        algorithm_interface=interface,
        status=Job.VALIDATING_INPUTS,
    )
    job.inputs.set([civ])

    with django_capture_on_commit_callbacks() as callbacks:
        execute_algorithm_job_for_inputs(job_pk=job.pk)

    # Sanity: task should run till execution
    assert len(callbacks) == 1
    assert "grandchallenge.components.tasks.provision_job" in str(callbacks[0])

    job.refresh_from_db()
    assert job.status == Job.PENDING
    assert (
        job.task_on_failure["message"]["task_name"]
        == "grandchallenge.algorithms.tasks.send_failed_job_notification"
    )  # Full task is tested somewhere else


@pytest.mark.django_db
def test_failed_job_notifications(client, django_capture_on_commit_callbacks):
    creator = UserFactory()
    editor = UserFactory()

    algorithm_interface = AlgorithmInterfaceFactory()

    # Create the algorithm image
    ai = AlgorithmImageFactory()
    ai.algorithm.add_editor(editor)

    job = Job.objects.create(
        creator=creator,
        algorithm_image=ai,
        algorithm_interface=algorithm_interface,
        input_civ_set=[],
        time_limit=ai.algorithm.time_limit,
        requires_gpu_type=ai.algorithm.job_requires_gpu_type,
        requires_memory_gb=ai.algorithm.job_requires_memory_gb,
    )

    # mark job as failed
    job.status = Job.FAILURE
    job.save()

    with django_capture_on_commit_callbacks(execute=True):
        send_failed_job_notification(job_pk=job.pk)

    # 1 notification for the job creator
    notification = Notification.objects.get()
    assert notification.user == creator
    assert (
        f"Unfortunately one of the jobs for algorithm {ai.algorithm.title} failed with an error"
        in notification.print_notification(user=creator.username)
    )

    # delete notifications for easier testing below
    Notification.objects.all().delete()
    # unsubscribe creator from job notifications
    _ = get_view_for_user(
        viewname="api:follow-detail",
        client=client,
        method=client.patch,
        reverse_kwargs={
            "pk": Follow.objects.filter(user=creator, flag="job-active")
            .get()
            .pk
        },
        content_type="application/json",
        data={"flag": "job-inactive"},
        user=creator,
    )

    job = Job.objects.create(
        creator=creator,
        algorithm_image=ai,
        algorithm_interface=algorithm_interface,
        input_civ_set=[],
        time_limit=ai.algorithm.time_limit,
        requires_gpu_type=ai.algorithm.job_requires_gpu_type,
        requires_memory_gb=ai.algorithm.job_requires_memory_gb,
    )

    # mark job as failed
    job.status = Job.FAILURE
    job.save()

    with django_capture_on_commit_callbacks(execute=True):
        send_failed_job_notification(job_pk=job.pk)

    with pytest.raises(ObjectDoesNotExist):
        Notification.objects.get()


@pytest.mark.django_db
def test_importing_same_sha_fails(
    settings, django_capture_on_commit_callbacks, invoke_container_image
):
    settings.LAMBDA_TASKS_EAGER = True

    alg = AlgorithmFactory()

    im1, im2 = AlgorithmImageFactory.create_batch(
        2, algorithm=alg, image__from_path=invoke_container_image
    )

    for im in [im1, im2]:
        with django_capture_on_commit_callbacks(execute=True):
            validate_container_image(
                pk=im.pk,
                app_label=im._meta.app_label,
                model_name=im._meta.model_name,
                mark_as_desired=False,
            )

    im1.refresh_from_db()
    im2.refresh_from_db()

    assert len(im1.image_sha256) == 71
    assert im1.image_sha256 == im2.image_sha256
    assert im1.is_manifest_valid is True
    assert im1.status == ""
    assert im2.is_manifest_valid is False
    assert im2.status == (
        "This container image has already been uploaded. "
        "Please re-activate the existing container image or upload a new version."
    )


@pytest.mark.django_db
def test_deactivate_old_algorithm_images(django_capture_on_commit_callbacks):
    old_unused_image = AlgorithmImageFactory(is_in_registry=True)
    AlgorithmImageFactory(is_in_registry=False)  # already removed
    AlgorithmImageFactory(
        is_in_registry=True, algorithm__public=True
    )  # is public so should still work
    algorithm_as_implementation = AlgorithmFactory()
    ReaderStudyAlgorithmImplementationFactory(
        algorithm=algorithm_as_implementation
    )
    AlgorithmImageFactory(
        is_in_registry=True,
        algorithm=algorithm_as_implementation,
    )  # linked to a reader study algorithm implementation
    old_with_recent_job = AlgorithmImageFactory(is_in_registry=True)
    old_with_old_job = AlgorithmImageFactory(is_in_registry=True)

    AlgorithmJobFactory(algorithm_image=old_with_old_job, time_limit=60)

    # Set old image and job dates
    old_created = now() - timedelta(days=400)
    AlgorithmImage.objects.update(created=old_created)
    Job.objects.update(created=old_created)

    # Create recent image and jobs
    AlgorithmImageFactory(is_in_registry=True)  # too new
    AlgorithmJobFactory(algorithm_image=old_with_recent_job, time_limit=60)

    with django_capture_on_commit_callbacks() as callbacks:
        deactivate_old_algorithm_images()

    expected_callbacks = {
        f"<bound method SQSLambdaTask._execute of SQSLambdaTask(message=SQSLambdaTaskMessage(task_name='grandchallenge.components.tasks.remove_container_image_from_registry', kwargs={{'pk': {image.pk!r}, 'app_label': 'algorithms', 'model_name': 'algorithmimage'}}, n_retries=0), delay=0, queue='default')>"
        # Private algorithm images not used for a long time, or ever, should be removed from the registry
        for image in {old_unused_image, old_with_old_job}
    }

    assert {str(callback) for callback in callbacks} == expected_callbacks


@pytest.mark.django_db
def test_non_invoke_api_method_image_not_marked_as_desired_version_after_import(
    settings, invoke_container_image, django_capture_on_commit_callbacks
):
    settings.LAMBDA_TASKS_EAGER = True

    with django_capture_on_commit_callbacks(execute=True):
        algorithm_image = AlgorithmImageFactory(
            image__from_path=invoke_container_image,
        )

    ReaderStudyAlgorithmImplementationFactory(
        algorithm=algorithm_image.algorithm
    )

    assert len(mail.outbox) == 0

    algorithm_image = AlgorithmImage.objects.get(pk=algorithm_image.pk)
    algorithm_image.import_status = ImportStatusChoices.STARTED
    algorithm_image.api_method = APIMethodChoices.EXEC
    algorithm_image.is_desired_version = False
    algorithm_image.save()

    with django_capture_on_commit_callbacks(execute=True):
        upload_to_registry_and_sagemaker(
            pk=algorithm_image.pk,
            app_label=algorithm_image._meta.app_label,
            model_name=algorithm_image._meta.model_name,
            mark_as_desired=True,
        )

    algorithm_image.refresh_from_db()
    assert not algorithm_image.is_desired_version

    assert len(mail.outbox) == 1
    email = mail.outbox[0]

    assert "Could not activate docker image" in email.subject
    assert (
        "Only algorithm images that implement the invoke API can be activated because this is an implementation of a reader study algorithm"
        in email.body
    )
