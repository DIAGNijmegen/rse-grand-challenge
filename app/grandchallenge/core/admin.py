from django.contrib import admin


class UserObjectPermissionAdmin(admin.ModelAdmin):
    readonly_fields = ("user", "permission", "content_object")
    search_fields = ("user__username", "content_object__pk")
    list_display = ("user", "permission", "content_object")


class GroupObjectPermissionAdmin(admin.ModelAdmin):
    readonly_fields = ("group", "permission", "content_object")
    search_fields = ("group__name", "content_object__pk")
    list_display = ("group", "permission", "content_object")
