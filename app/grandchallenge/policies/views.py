from django.contrib.auth.mixins import PermissionRequiredMixin
from django.views.generic import CreateView, DetailView, UpdateView
from guardian.mixins import LoginRequiredMixin

from grandchallenge.policies.forms import PolicyForm
from grandchallenge.policies.models import Policy
from grandchallenge.subdomains.utils import reverse_lazy


class PolicyCreate(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Policy
    form_class = PolicyForm
    permission_required = "policies.add_policy"
    raise_exception = True
    login_url = reverse_lazy("account_login")


class PolicyDetail(DetailView):
    model = Policy


class PolicyUpdate(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Policy
    form_class = PolicyForm
    permission_required = "policies.change_policy"
    raise_exception = True
    login_url = reverse_lazy("account_login")
