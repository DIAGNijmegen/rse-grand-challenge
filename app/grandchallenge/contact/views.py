from django.contrib import messages
from django.views.generic import FormView

from grandchallenge.contact.emails import send_contact_email
from grandchallenge.contact.forms import ContactForm
from grandchallenge.subdomains.utils import reverse


class ContactView(FormView):
    template_name = "contact/contact_form.html"
    form_class = ContactForm

    def get_initial(self):
        initial = super().get_initial()
        for field in ["message", "referer"]:
            value = self.request.GET.get(field)
            if value is not None:
                initial[field] = value
        return initial

    def get_success_url(self):
        return reverse("home")

    def form_valid(self, form):
        if form.honeypot_tripped or not form.challenge_passed:
            # Silently drop the submission (both honeypot or unsolved JS
            # challenge) without revealing why, but politely point genuine
            # users (false positives) to support.
            return self.render_to_response(
                self.get_context_data(form=form, honeypot_tripped=True)
            )

        send_contact_email(
            cleaned_data=form.cleaned_data, request=self.request
        )
        messages.success(
            self.request,
            "Your message has been sent!",
        )
        return super().form_valid(form)
