from django.contrib import admin
from django.contrib.admin import ModelAdmin
from django.forms import ModelForm

from grandchallenge.core.widgets import MarkdownEditorAdminWidget
from grandchallenge.policies.models import Policy


class PolicyAdminForm(ModelForm):
    class Meta:
        widgets = {"body": MarkdownEditorAdminWidget()}


@admin.register(Policy)
class PolicyAdmin(ModelAdmin):
    form = PolicyAdminForm
