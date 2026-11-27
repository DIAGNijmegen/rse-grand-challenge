import pytest
from guardian.shortcuts import assign_perm

from grandchallenge.policies.models import Policy
from grandchallenge.subdomains.utils import reverse
from tests.factories import PolicyFactory, UserFactory
from tests.utils import get_view_for_user


@pytest.mark.django_db
def test_terms_of_service(client):
    PolicyFactory(body="foo", title="terms")
    response = client.get(reverse("policies:detail", kwargs={"slug": "terms"}))
    assert response.status_code == 200
    assert "foo" in response.rendered_content


@pytest.mark.django_db
def test_policy_create_requires_login(client):
    response = get_view_for_user(
        viewname="policies:create",
        client=client,
        method=client.post,
        data={"title": "New policy", "body": "some body"},
        user=None,
    )

    assert response.status_code == 302
    assert "/accounts/login/" in response.url
    assert not Policy.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("is_staff", (False, True))
def test_policy_create_permission_denied(client, is_staff):
    # Staff status alone must not grant permission to create policies
    user = UserFactory(is_staff=is_staff)

    response = get_view_for_user(
        viewname="policies:create",
        client=client,
        method=client.post,
        data={"title": "New policy", "body": "some body"},
        user=user,
    )

    assert response.status_code == 403
    assert not Policy.objects.exists()


@pytest.mark.django_db
def test_policy_create_with_permission(client):
    user = UserFactory()
    assign_perm("policies.add_policy", user)

    response = get_view_for_user(
        viewname="policies:create",
        client=client,
        method=client.post,
        data={"title": "New policy", "body": "some body"},
        user=user,
    )

    assert response.status_code == 302

    policy = Policy.objects.get()
    assert policy.title == "New policy"
    assert policy.body == "some body"
    assert policy.slug == "new-policy"
    assert response.url == policy.get_absolute_url()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "title", ("Create", "create", "Create!", "Create.", '"Create"', "Créate")
)
def test_policy_create_reserved_title(client, title):
    user = UserFactory()
    assign_perm("policies.add_policy", user)

    response = get_view_for_user(
        viewname="policies:create",
        client=client,
        method=client.post,
        data={"title": title, "body": "some body"},
        user=user,
    )

    assert response.status_code == 200
    assert "title" in response.context["form"].errors
    assert not Policy.objects.exists()


@pytest.mark.django_db
def test_policy_update_requires_login(client):
    policy = PolicyFactory(title="terms", body="old body")

    response = get_view_for_user(
        viewname="policies:update",
        client=client,
        method=client.post,
        reverse_kwargs={"slug": policy.slug},
        data={"title": "terms", "body": "new body"},
        user=None,
    )

    assert response.status_code == 302
    assert "/accounts/login/" in response.url
    policy.refresh_from_db()
    assert policy.body == "old body"


@pytest.mark.django_db
@pytest.mark.parametrize("is_staff", (False, True))
def test_policy_update_permission_denied(client, is_staff):
    # Staff status alone must not grant permission to change policies
    policy = PolicyFactory(title="terms", body="old body")
    user = UserFactory(is_staff=is_staff)

    response = get_view_for_user(
        viewname="policies:update",
        client=client,
        method=client.post,
        reverse_kwargs={"slug": policy.slug},
        data={"title": "terms", "body": "new body"},
        user=user,
    )

    assert response.status_code == 403
    policy.refresh_from_db()
    assert policy.body == "old body"


@pytest.mark.django_db
def test_policy_update_add_permission_is_not_enough(client):
    policy = PolicyFactory(title="terms", body="old body")
    user = UserFactory()
    assign_perm("policies.add_policy", user)

    response = get_view_for_user(
        viewname="policies:update",
        client=client,
        method=client.post,
        reverse_kwargs={"slug": policy.slug},
        data={"title": "terms", "body": "new body"},
        user=user,
    )

    assert response.status_code == 403
    policy.refresh_from_db()
    assert policy.body == "old body"


@pytest.mark.django_db
def test_policy_update_with_permission(client):
    policy = PolicyFactory(title="terms", body="old body")
    user = UserFactory()
    assign_perm("policies.change_policy", user)

    response = get_view_for_user(
        viewname="policies:update",
        client=client,
        method=client.post,
        reverse_kwargs={"slug": policy.slug},
        data={"title": "Terms of Service", "body": "new body"},
        user=user,
    )

    assert response.status_code == 302

    policy.refresh_from_db()
    assert policy.title == "Terms of Service"
    assert policy.body == "new body"
    assert policy.slug == "terms", "The slug must not change"
    assert response.url == policy.get_absolute_url()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "perm,button_text",
    (
        ("policies.add_policy", "Create policy"),
        ("policies.change_policy", "Update policy"),
    ),
)
def test_policy_detail_buttons(client, perm, button_text):
    policy = PolicyFactory(title="terms", body="foo")
    user = UserFactory()

    response = get_view_for_user(
        viewname="policies:detail",
        client=client,
        reverse_kwargs={"slug": policy.slug},
        user=user,
    )

    assert response.status_code == 200
    assert button_text not in response.rendered_content

    assign_perm(perm, user)

    response = get_view_for_user(
        viewname="policies:detail",
        client=client,
        reverse_kwargs={"slug": policy.slug},
        user=user,
    )

    assert response.status_code == 200
    assert button_text in response.rendered_content
