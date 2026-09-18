from django.core.mail import mail_managers
from django.utils.html import format_html


def send_contact_email(*, email, message):
    """Send a contact form submission to the site managers."""

    subject = f"[CONTACT-US] {email}"

    body = format_html(
        "Email: {email}\n\nMessage:\n{message}\n",
        email=email,
        message=message,
    )

    mail_managers(
        subject=subject,
        message=body,
    )
