from django.contrib.messages.views import SuccessMessageMixin
from django.views.generic import FormView

from grandchallenge.contact.emails import send_contact_email
from grandchallenge.contact.forms import ContactForm
from grandchallenge.subdomains.utils import reverse


class ContactView(SuccessMessageMixin, FormView):
    form_class = ContactForm
    template_name = "contact/contact_form.html"
    success_message = "Your message has been sent!"

    def get_initial(self):
        initial = super().get_initial()
        value = self.request.GET.get("message")
        if value is not None:
            initial["message"] = value
        return initial

    def get_success_url(self):
        return reverse("home")

    def form_valid(self, form):
        send_contact_email(
            email=form.cleaned_data["email"],
            message=form.cleaned_data["message"],
        )
        return super().form_valid(form)
