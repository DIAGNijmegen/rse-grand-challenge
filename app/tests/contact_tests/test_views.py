import pytest

from grandchallenge.subdomains.utils import reverse
from tests.utils import get_view_for_user


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
        "email",
        "message",
    ]:
        assert f'name="{field}"' in content


@pytest.mark.django_db
def test_contact_form_prefill_from_url(client):
    response = get_view_for_user(
        client=client,
        url="/contact-us/?message=Prefilled+Message",
        user=None,
    )
    form = response.context["form"]
    assert form.initial["message"] == "Prefilled Message"

    content = response.rendered_content
    assert "Prefilled Message" in content


@pytest.mark.django_db
def test_valid_submission_redirects_to_homepage(client):
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
    assert response.status_code == 302
    assert response.url == reverse("home")
