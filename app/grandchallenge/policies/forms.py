from django.core.exceptions import ValidationError
from django.forms import ModelForm
from django.utils.text import slugify

from grandchallenge.core.forms import SaveFormInitMixin
from grandchallenge.core.widgets import MarkdownEditorFullPageWidget
from grandchallenge.policies.models import Policy


class PolicyForm(SaveFormInitMixin, ModelForm):
    class Meta:
        model = Policy
        fields = ("title", "body")
        widgets = {"body": MarkdownEditorFullPageWidget}

    def clean_title(self):
        title = self.cleaned_data["title"]

        if slugify(title) == "create":
            raise ValidationError(
                "This title is not allowed, please choose another one."
            )

        return title
