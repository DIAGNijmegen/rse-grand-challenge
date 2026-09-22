import pytest
from django.core import mail

from tests.utils import get_view_for_user


@pytest.mark.django_db
def test_valid_submission_sends_email(client, settings):
    settings.MANAGERS = [("Manager", "manager@example.org")]

    response = get_view_for_user(
        client=client,
        viewname="contact:contact",
        user=None,
        method=client.post,
        data={
            "email": "jane@example.org",
            "message": "I have a question about your platform.",
        },
    )

    # Post/Redirect/Get
    assert response.status_code == 302

    assert len(mail.outbox) == 1
    email = mail.outbox[0]
    assert email.subject == "[testserver] New contact message"
    assert email.to == ["manager@example.org"]
    assert email.reply_to == ["jane@example.org"]

    body = email.body
    assert "I have a question about your platform." in body
    assert "jane@example.org" in body


@pytest.mark.django_db
def test_valid_submission_shows_success_message(client, settings):
    settings.MANAGERS = [("Manager", "manager@example.org")]

    response = get_view_for_user(
        client=client,
        viewname="contact:contact",
        user=None,
        method=client.post,
        data={
            "email": "jane@example.org",
            "message": "I have a question about your platform.",
        },
        follow=True,
    )
    assert response.status_code == 200
    messages = [str(m) for m in response.context["messages"]]
    assert any("sent" in m.lower() for m in messages)
