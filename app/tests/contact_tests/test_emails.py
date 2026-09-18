import pytest
from django.core import mail
from django.test import override_settings

from tests.utils import get_view_for_user


@pytest.mark.django_db
@override_settings(
    MANAGERS=[("Manager", "manager@example.org")],
    EMAIL_SUBJECT_PREFIX="",
)
def test_valid_submission_sends_email(client):
    response = get_view_for_user(
        client=client,
        viewname="contact:contact",
        user=None,
        method=client.post,
        data={
            "name": "Jane Doe",
            "email": "jane@example.org",
            "message": "I have a question about your platform.",
            "accept_privacy_policy": True,
            "subject": "",
            "referer": "homepage-footer",
            "c0": "AAA",
            "c1": "BBB",
            "c2": "BBBAAA",
        },
        HTTP_USER_AGENT="Mozilla/5.0 (TestAgent)",
        HTTP_X_FORWARDED_FOR="203.0.113.7",
    )

    # Post/Redirect/Get
    assert response.status_code == 302

    assert len(mail.outbox) == 1
    email = mail.outbox[0]
    assert email.subject.startswith("[CONTACT-US] ")
    assert "Jane Doe" in email.subject
    assert email.to == ["manager@example.org"]

    body = email.body
    assert "I have a question about your platform." in body
    assert "homepage-footer" in body
    assert "203.0.113.7" in body
    assert "Mozilla/5.0 (TestAgent)" in body
    assert "jane@example.org" in body
    assert "Jane Doe" in body


@pytest.mark.django_db
@override_settings(
    MANAGERS=[("Manager", "manager@example.org")],
    EMAIL_SUBJECT_PREFIX="",
)
def test_valid_submission_shows_success_message(client):
    response = get_view_for_user(
        client=client,
        viewname="contact:contact",
        user=None,
        method=client.post,
        data={
            "name": "Jane Doe",
            "email": "jane@example.org",
            "message": "I have a question about your platform.",
            "accept_privacy_policy": True,
            "subject": "",
            "referer": "homepage-footer",
            "c0": "AAA",
            "c1": "BBB",
            "c2": "BBBAAA",
        },
        follow=True,
    )
    assert response.status_code == 200
    messages = [str(m) for m in response.context["messages"]]
    assert any("sent" in m.lower() for m in messages)
