import pytest
from allauth.socialaccount.models import SocialAccount
from django.core import mail
from django.core.management import call_command

from grandchallenge.subdomains.utils import reverse
from tests.factories import UserFactory


def create_gmail_user(*, password=None, is_active=True):
    user = UserFactory(is_active=is_active)
    if password is None:
        # Pure OAuth signups have an unusable password, as set by allauth
        user.set_unusable_password()
    else:
        user.set_password(password)
    user.save()
    SocialAccount.objects.create(user=user, provider="gmail", uid=user.email)
    return user


@pytest.mark.django_db
def test_email_sent_only_to_passwordless_active_gmail_users():
    target_user = create_gmail_user()
    user_with_password = create_gmail_user(password="a-password")
    inactive_user = create_gmail_user(is_active=False)
    # A regular user with no social account should be ignored
    UserFactory()

    call_command("send_gmail_users_password_reset")

    recipients = {address for message in mail.outbox for address in message.to}

    assert recipients == {target_user.email}
    assert user_with_password.email not in recipients
    assert inactive_user.email not in recipients


@pytest.mark.django_db
def test_email_contains_password_reset_link():
    create_gmail_user()

    call_command("send_gmail_users_password_reset")

    assert len(mail.outbox) == 1
    body = mail.outbox[0].body
    assert reverse("account_reset_password") in body
