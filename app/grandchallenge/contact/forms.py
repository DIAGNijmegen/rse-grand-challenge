import secrets

from django import forms
from django.utils.functional import lazy
from django.utils.html import format_html

from grandchallenge.core.forms import SaveFormInitMixin
from grandchallenge.subdomains.utils import reverse


def _privacy_policy_consent_label():
    return format_html(
        "I agree that the information I provide (including my name, "
        "email address and message) may be stored and processed so that "
        "we can respond to my enquiry, as described in the "
        '<a href="{privacy_policy_url}">privacy policy</a>.',
        privacy_policy_url=reverse(
            "policies:detail", kwargs={"slug": "privacy-policy"}
        ),
    )


class ContactForm(SaveFormInitMixin, forms.Form):
    save_button_text = "Send message"

    name = forms.CharField(
        max_length=255,
        label="Your name",
        widget=forms.TextInput(attrs={"placeholder": "Your name"}),
    )
    email = forms.EmailField(
        label="Your email",
        widget=forms.TextInput(attrs={"placeholder": "Your email"})
    )
    message = forms.CharField(
        widget=forms.Textarea(attrs={"placeholder": "Your Message"})
    )
    accept_privacy_policy = forms.BooleanField(
        required=True,
        # The label links to the privacy policy and is evaluated lazily so
        # that reversing the policy URL (which needs the current Site) only
        # happens at render time, not at form construction/import time.
        label=lazy(lambda: format_html(
            "I agree with the "
            '<a href="{privacy_policy_url}">privacy policy</a>.',
            privacy_policy_url=reverse(
                "policies:detail", kwargs={"slug": "privacy"}
            )), str)(),
    )

    # Honeypot field: hidden from real users, but likely to be filled in by
    # bots. It is deliberately named "subject" to look like a plausible field
    # and is never used anywhere (not included in the email).
    subject = forms.CharField(
        required=False,
        label="Subject",
        widget=forms.HiddenInput,
    )

    # Hidden reference field, allows us to know where the user reached the
    # form from. Can be prefilled via a URL argument.
    ref = forms.CharField(
        required=False,
        widget=forms.HiddenInput,
    )

    # JavaScript bot challenge fields. c0 and c1 are prefilled server-side
    # with random tokens; c2 is empty and must be filled in by client-side
    # JavaScript to equal c1 + c0. Real browsers run the script and
    # solve it; bots that submit the raw form do not.
    c0 = forms.CharField(required=False, widget=forms.HiddenInput)
    c1 = forms.CharField(required=False, widget=forms.HiddenInput)
    c2 = forms.CharField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Seed fresh challenge tokens for the intial form that is rendered
        # to the user, not the POST returning it.
        if not self.is_bound:
            self.fields["c0"].initial = secrets.token_urlsafe(8)
            self.fields["c1"].initial = secrets.token_urlsafe(8)

    @property
    def honeypot_tripped(self):
        return bool(self.cleaned_data.get("subject"))

    @property
    def challenge_passed(self):
        c0 = self.cleaned_data.get("c0", "")
        c1 = self.cleaned_data.get("c1", "")
        c2 = self.cleaned_data.get("c2", "")

        if not c0 or not c1:
            return False
        else:
            return c2 == c1 + c0
