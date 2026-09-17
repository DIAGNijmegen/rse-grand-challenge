from allauth.core.internal.httpkit import get_client_ip
from django.core.mail import mail_managers
from django.utils.html import format_html

CONTACT_SUBJECT_PREFIX = "[CONTACT-US] "


def send_contact_email(*, cleaned_data, request):
    """Send a contact form submission to the site managers.

    The email contains all the form fields, the ``ref`` and some metadata
    about the request (client IP, user agent and referer) to help triage.
    """
    ip_address = get_client_ip(request=request)
    user_agent = request.META.get("HTTP_USER_AGENT", "<none>")
    referer = request.META.get("HTTP_REFERER", "<none>")
    host = request.get_host()

    subject = f"{CONTACT_SUBJECT_PREFIX}{cleaned_data['name']}"

    message = format_html(
        "Name: {name}\n"
        "Email: {email}\n"
        "Ref: {ref}\n"
        "\n"
        "Message:\n"
        "{message}\n"
        "\n"
        "---\n"
        "Request metadata:\n"
        "IP address: {ip_address}\n"
        "User agent: {user_agent}\n"
        "Referer: {referer}\n"
        "Host: {host}\n",
        name=cleaned_data["name"],
        email=cleaned_data["email"],
        ref=cleaned_data.get("ref") or "<none>",
        message=cleaned_data["message"],
        ip_address=ip_address,
        user_agent=user_agent,
        referer=referer,
        host=host,
    )

    mail_managers(
        subject=subject,
        message=message,
    )
