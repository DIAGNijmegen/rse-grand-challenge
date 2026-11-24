from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError

from grandchallenge.components.models import ComponentInterface
from grandchallenge.reader_studies.models import Answer, Question
from grandchallenge.reader_studies.tasks import (
    answers_from_ground_truth,
    create_display_sets_for_upload_session,
    update_reader_studies_credits_consumed,
    update_reader_study_credits_consumed,
)
from tests.factories import ImageFactory, UserFactory
from tests.reader_studies_tests.factories import (
    AnswerFactory,
    DisplaySetFactory,
    QuestionFactory,
    ReaderStudyFactory,
)
from tests.utilization_tests.factories import SessionUtilizationFactory


@pytest.mark.django_db
def test_create_display_sets_for_upload_session():
    rs = ReaderStudyFactory()
    image = ImageFactory()
    ci = ComponentInterface.objects.get(slug="generic-medical-image")

    assert rs.display_sets.count() == 0

    create_display_sets_for_upload_session(
        upload_session_pk=image.origin.pk,
        reader_study_pk=rs.pk,
        interface_pk=ci.pk,
    )

    assert rs.display_sets.count() == 1
    assert rs.display_sets.first().values.first().image == image

    create_display_sets_for_upload_session(
        upload_session_pk=image.origin.pk,
        reader_study_pk=rs.pk,
        interface_pk=ci.pk,
    )

    assert rs.display_sets.count() == 1
    assert rs.display_sets.first().values.first().image == image


@pytest.mark.django_db
def test_answers_from_ground_truth_with_existing_answers():
    rs = ReaderStudyFactory()
    ds = DisplaySetFactory(reader_study=rs)
    q = QuestionFactory(
        reader_study=rs,
        answer_type=Question.AnswerType.BOOL,
    )

    user = UserFactory()
    rs.add_editor(user)

    answers_from_ground_truth(
        reader_study_pk=rs.pk, target_user_pk=user.pk
    )  # NOOP

    AnswerFactory(
        creator=user,
        question=q,
        display_set=ds,
        is_ground_truth=True,
        answer=False,
    )

    answers_from_ground_truth(reader_study_pk=rs.pk, target_user_pk=user.pk)

    assert Answer.objects.filter(
        question=q, display_set=ds, creator=user, is_ground_truth=False
    ).exists(), "Sanity: user answer got created"

    # With an existing answer it should block a new attempt
    with pytest.raises(ValidationError):
        answers_from_ground_truth(
            reader_study_pk=rs.pk, target_user_pk=user.pk
        )


@pytest.mark.django_db
def test_update_single_reader_study_credits_consumed():
    reader_study = ReaderStudyFactory(max_credits=10000)
    other_reader_study = ReaderStudyFactory(max_credits=10000)

    session_utilization = SessionUtilizationFactory(
        duration=timedelta(
            hours=2
        )  # 2 hours * 500 credits/hour = 1000 credits
    )
    session_utilization.reader_studies.set([reader_study, other_reader_study])

    reader_study.refresh_from_db()
    assert reader_study.credits_consumed is None

    update_reader_study_credits_consumed(pk=reader_study.pk)

    reader_study.refresh_from_db()
    other_reader_study.refresh_from_db()
    assert (
        reader_study.credits_consumed == 500
    )  # half of the session utilization is attributed to this reader study

    # The other one should not be updated (yet)
    assert other_reader_study.credits_consumed is None


@pytest.mark.django_db
def test_update_multiple_reader_studies_credits_consumed(
    settings, django_capture_on_commit_callbacks
):
    settings.LAMBDA_TASKS_EAGER = True

    reader_studies = ReaderStudyFactory.create_batch(3, max_credits=10000)

    session_utilization = SessionUtilizationFactory(
        duration=timedelta(
            hours=3
        )  # 3 hours * 500 credits/hour = 1500 credits
    )
    session_utilization.reader_studies.set(reader_studies)

    with django_capture_on_commit_callbacks(execute=True):
        update_reader_studies_credits_consumed()

    for reader_study in reader_studies:
        reader_study.refresh_from_db()
        assert reader_study.credits_consumed == 500


@pytest.mark.django_db
def test_update_reader_studies_credits_consumed_skips_null_max_credits(
    settings, django_capture_on_commit_callbacks
):
    settings.LAMBDA_TASKS_EAGER = True

    reader_study_with_max_credits = ReaderStudyFactory(max_credits=1000)
    reader_study_without_max_credits = ReaderStudyFactory(max_credits=None)

    session_utilization = SessionUtilizationFactory(
        duration=timedelta(
            hours=2
        )  # 2 hours * 500 credits/hour = 1000 credits
    )
    session_utilization.reader_studies.set(
        [reader_study_with_max_credits, reader_study_without_max_credits]
    )

    with django_capture_on_commit_callbacks(execute=True):
        update_reader_studies_credits_consumed()

    reader_study_with_max_credits.refresh_from_db()
    reader_study_without_max_credits.refresh_from_db()

    # Sanity: the task ran for the reader study with a max_credits set
    assert reader_study_with_max_credits.credits_consumed == 500

    # No max_credits means no budget to enforce, so it is not updated
    assert reader_study_without_max_credits.credits_consumed is None
