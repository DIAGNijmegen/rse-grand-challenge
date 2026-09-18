from django import forms

from grandchallenge.core.forms import SaveFormInitMixin


class ContactForm(SaveFormInitMixin, forms.Form):
    save_button_text = "Send message"

    email = forms.EmailField(
        label="Your email",
        widget=forms.TextInput(attrs={"placeholder": "Your email"}),
    )
    message = forms.CharField(
        label="Your message",
        widget=forms.Textarea(attrs={"placeholder": "Your message"}),
    )
