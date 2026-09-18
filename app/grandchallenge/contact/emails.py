from django.core.mail import mail_managers
from django.utils.html import format_html

CONTACT_SUBJECT_PREFIX = "[CONTACT-US] "


def send_contact_email(*, cleaned_data, request):
    """Send a contact form submission to the site managers.

    The email contains all the form fields, the ``ref`` and some metadata
    about the request (client IP, user agent and referer) to help triage.
    """

    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "<none>")
    user_agent = request.META.get("HTTP_USER_AGENT", "<none>")
    host = request.get_host()

    subject = f"{CONTACT_SUBJECT_PREFIX}{cleaned_data['name']}"

    message = format_html(
        "Name: {name}\n"
        "Email: {email}\n"
        "Referer: {referer}\n"
        "\n"
        "Message:\n"
        "{message}\n"
        "\n"
        "---\n"
        "Request metadata:\n"
        "IP Address (Forwarded-For): {forwarded_for}\n"
        "User agent: {user_agent}\n"
        "Host: {host}\n",
        name=cleaned_data["name"],
        email=cleaned_data["email"],
        referer=cleaned_data.get("referer") or "<none>",
        message=cleaned_data["message"],
        user_agent=user_agent,
        forwarded_for=forwarded_for,
        host=host,
    )

    mail_managers(
        subject=subject,
        message=message,
    )
