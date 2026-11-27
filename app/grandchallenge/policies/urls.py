from django.urls import path

from grandchallenge.policies.views import (
    PolicyCreate,
    PolicyDetail,
    PolicyUpdate,
)

app_name = "policies"

urlpatterns = [
    path("create/", PolicyCreate.as_view(), name="create"),
    path("<slug>/", PolicyDetail.as_view(), name="detail"),
    path("<slug>/update/", PolicyUpdate.as_view(), name="update"),
]
