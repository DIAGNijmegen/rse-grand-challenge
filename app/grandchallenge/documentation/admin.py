from django.contrib import admin
from django.contrib.admin import ModelAdmin

from grandchallenge.documentation.models import DocPage


@admin.register(DocPage)
class DocPageAdmin(ModelAdmin):
    list_display = ("pk", "title", "order")
