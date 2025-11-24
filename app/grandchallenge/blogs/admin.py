from django.contrib import admin
from django.contrib.admin import ModelAdmin
from django.forms import ModelForm

from grandchallenge.blogs.models import (
    Post,
    PostGroupObjectPermission,
    PostUserObjectPermission,
    Tag,
)
from grandchallenge.core.admin import (
    GroupObjectPermissionAdmin,
    UserObjectPermissionAdmin,
)
from grandchallenge.core.widgets import MarkdownEditorAdminWidget


class AdminPostForm(ModelForm):
    class Meta:
        widgets = {"content": MarkdownEditorAdminWidget}


@admin.register(Post)
class PostAdmin(ModelAdmin):
    form = AdminPostForm
    list_display = ("pk", "slug", "title", "published", "highlight")
    list_filter = ("tags", "highlight")
    readonly_fields = ("authors",)

    def has_add_permission(self, *args, **kwargs):
        return False


@admin.register(Tag)
class TagAdmin(ModelAdmin):
    list_display = ("__str__", "slug")


admin.site.register(PostUserObjectPermission, UserObjectPermissionAdmin)
admin.site.register(PostGroupObjectPermission, GroupObjectPermissionAdmin)
