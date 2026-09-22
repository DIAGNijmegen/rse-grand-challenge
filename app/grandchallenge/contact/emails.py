from django.conf import settings
from django.contrib.sites.models import Site
from django.core.mail import EmailMessage
from django.utils.html import format_html


def send_contact_email(*, email, message):
    """Send a contact form submission to the site managers."""
    site = Site.objects.get_current()
    domain = site.domain.lower()

    subject = f"[{domain}] New contact message"
    body = format_html(
        "Email: {email}\n\nMessage:\n{message}\n",
        email=email,
        message=message,
    )

    # this check is taken from Django 5.2' mail_managers implementation; the format of the manager emails is
    # changed in Django 6.0. We use EmailMessage directly so we can set a reply_to.
    if not all(
        isinstance(a, (list, tuple)) and len(a) == 2 for a in settings.MANAGERS
    ):
        raise ValueError("The MANAGERS setting must be a list of 2-tuples.")

    EmailMessage(
        subject=subject,
        body=body,
        to=[a[1] for a in settings.MANAGERS],
        reply_to=[email],
    ).send()
