from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.core.management import BaseCommand
from django.db import transaction
from django.utils.html import format_html
from django.utils.timezone import now

from grandchallenge.emails.emails import send_standard_email_batch
from grandchallenge.profiles.models import EmailSubscriptionTypes
from grandchallenge.subdomains.utils import reverse

GMAIL_PROVIDER_ID = "gmail"
LAST_LOGIN_CUTOFF_DAYS = 365


class Command(BaseCommand):
    help = (
        "Emails users who signed up with Google social login, have no "
        "usable password, are still active, and have logged in within the "
        "past year, prompting them to reset their password now that Google "
        "login has been removed."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        users = [
            user
            for user in get_user_model()
            .objects.filter(
                is_active=True,
                socialaccount__provider=GMAIL_PROVIDER_ID,
                last_login__gte=now() - timedelta(days=LAST_LOGIN_CUTOFF_DAYS),
            )
            .distinct()
            if not user.has_usable_password()
        ]

        if not users:
            self.stdout.write("No users to email.")
            return

        password_reset_url = reverse("account_reset_password")

        markdown_message = format_html(
            "Google login is no longer available on the platform. To "
            "continue signing in, please set a password for your account "
            "using the password reset page:\n\n{password_reset_url}\n\n"
            "Enter the email address associated with your account and "
            "follow the instructions in the email you receive.",
            password_reset_url=password_reset_url,
        )

        send_standard_email_batch(
            site=Site.objects.get_current(),
            subject="Action required: set a password for your account",
            markdown_message=markdown_message,
            recipients=users,
            subscription_type=EmailSubscriptionTypes.SYSTEM,
        )

        self.stdout.write(f"Emailed {len(users)} user(s).")
