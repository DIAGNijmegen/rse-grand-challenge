import pytest

from grandchallenge.components.models import InterfaceKindChoices
from grandchallenge.core.error_handlers import SubmissionCIVErrorHandler
from grandchallenge.evaluation.models import SubmissionStatusChoices
from tests.components_tests.factories import ComponentInterfaceFactory
from tests.evaluation_tests.factories import SubmissionFactory


@pytest.mark.django_db
def test_submission_civ_error_handler_messages():
    interface = ComponentInterfaceFactory(kind=InterfaceKindChoices.STRING)

    s1 = SubmissionFactory(status=SubmissionStatusChoices.VALIDATING_INPUTS)
    SubmissionCIVErrorHandler(submission=s1).handle_error(
        error_message="Some message for interface validation",
        interface=interface,
    )
    s1.refresh_from_db()
    assert s1.status == SubmissionStatusChoices.FAILED
    assert s1.status_message == "One or more of the inputs failed validation."

    s2 = SubmissionFactory(status=SubmissionStatusChoices.VALIDATING_INPUTS)
    SubmissionCIVErrorHandler(submission=s2).handle_error(
        error_message="Some error message"
    )
    s2.refresh_from_db()
    assert s2.status == SubmissionStatusChoices.FAILED
    assert s2.status_message == "Some error message"
