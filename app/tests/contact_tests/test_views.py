import html

import pytest
from django.core import mail
from django.test import override_settings

from grandchallenge.subdomains.utils import reverse
from tests.utils import get_view_for_user

TEST_SUPPORT_EMAIL = "test-support@example.test"


@pytest.mark.django_db
def test_contact_page_renders(client):
    response = get_view_for_user(
        client=client,
        viewname="contact:contact",
        user=None,
    )
    assert response.status_code == 200
    assert "Send us a message" in response.rendered_content


@pytest.mark.django_db
def test_contact_form_is_rendered(client):
    response = get_view_for_user(
        client=client,
        viewname="contact:contact",
        user=None,
    )
    content = response.rendered_content
    for field in [
        "name",
        "email",
        "message",
        "accept_privacy_policy",
        "subject",
        "referer",
        "c0",
        "c1",
        "c2",
    ]:
        assert f'name="{field}"' in content


@pytest.mark.django_db
def test_contact_form_prefill_from_url(client):
    response = get_view_for_user(
        client=client,
        url="/contact-us/?message=Prefilled+Message&referer=homepage-footer",
        user=None,
    )
    form = response.context["form"]
    assert form.initial["message"] == "Prefilled Message"
    assert form.initial["referer"] == "homepage-footer"

    content = response.rendered_content
    assert "Prefilled Message" in content
    assert "homepage-footer" in content


@pytest.mark.django_db
@override_settings(SUPPORT_EMAIL=TEST_SUPPORT_EMAIL)
def test_valid_submission_redirects_to_homepage(client):
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
            "referer": "",
            "c0": "AAA",
            "c1": "BBB",
            "c2": "BBBAAA",
        },
    )
    assert response.status_code == 302
    assert response.url == reverse("home")


@pytest.mark.django_db
@override_settings(SUPPORT_EMAIL=TEST_SUPPORT_EMAIL)
def test_honeypot_trip_shows_polite_notice_and_sends_no_email(client):
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
            "subject": "Buy cheap things",
            "referer": "",
            "c0": "AAA",
            "c1": "BBB",
            "c2": "BBBAAA",
        },
    )
    # Regular page, no redirect.
    assert response.status_code == 200
    # No email is sent.
    assert len(mail.outbox) == 0

    content = html.unescape(response.rendered_content)
    # Polite notice pointing to support.
    assert TEST_SUPPORT_EMAIL in content
    # The honeypot is not revealed.
    assert "honeypot" not in content.lower()
    form = response.context["form"]
    assert "subject" not in form.errors


@pytest.mark.django_db
def test_challenge_script_is_included(client):
    response = get_view_for_user(
        client=client,
        viewname="contact:contact",
        user=None,
    )
    assert "contact_challenge.mjs" in response.rendered_content


@pytest.mark.django_db
@override_settings(SUPPORT_EMAIL=TEST_SUPPORT_EMAIL)
def test_unsolved_challenge_shows_polite_notice_and_sends_no_email(client):
    # A bot submits the raw form without running the JS, so c2 is empty.
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
            "referer": "",
            "c0": "AAA",
            "c1": "BBB",
            "c2": "",
        },
    )
    # Regular page, no redirect.
    assert response.status_code == 200
    # No email is sent.
    assert len(mail.outbox) == 0

    content = html.unescape(response.rendered_content)
    # Polite notice pointing to support.
    assert TEST_SUPPORT_EMAIL in content
    form = response.context["form"]
    assert form.challenge_passed is False
