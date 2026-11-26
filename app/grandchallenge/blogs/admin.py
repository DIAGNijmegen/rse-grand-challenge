from django.contrib import admin
from django.contrib.admin import ModelAdmin

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


@admin.register(Post)
class PostAdmin(ModelAdmin):
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
