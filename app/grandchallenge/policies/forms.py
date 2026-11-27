from django.forms import ModelForm

from grandchallenge.core.forms import SaveFormInitMixin
from grandchallenge.core.widgets import MarkdownEditorFullPageWidget
from grandchallenge.policies.models import Policy


class PolicyForm(SaveFormInitMixin, ModelForm):
    class Meta:
        model = Policy
        fields = ("title", "body")
        widgets = {"body": MarkdownEditorFullPageWidget}
