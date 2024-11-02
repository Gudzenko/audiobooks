from django.shortcuts import redirect
from django.contrib.auth.views import LoginView
from django.contrib.auth.decorators import login_required, user_passes_test
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView, ListView, CreateView
from .models import CustomUser
from .forms import CustomLoginForm, CustomUserCreationForm
from .mixins import AddUserGroupContextMixin


class CustomLoginView(AddUserGroupContextMixin, LoginView):
    template_name = 'authapp/login.html'
    form_class = CustomLoginForm


@method_decorator(login_required, name='dispatch')
class ProfileView(AddUserGroupContextMixin, TemplateView):
    template_name = 'authapp/profile.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user'] = self.request.user
        return context


@method_decorator(login_required, name='dispatch')
@method_decorator(user_passes_test(lambda u: u.groups.filter(name='Manager').exists()), name='dispatch')
class ManageUsersView(AddUserGroupContextMixin, ListView):
    template_name = 'authapp/manage_users.html'
    context_object_name = 'users'

    def get_queryset(self):
        return CustomUser.objects.filter(manager=self.request.user)


@method_decorator(login_required, name='dispatch')
class AdminManageUsersView(AddUserGroupContextMixin, ListView):
    template_name = 'authapp/admin_manage_users.html'
    context_object_name = 'users'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            return redirect('profile')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return CustomUser.objects.all()


class UserRegistrationView(CreateView):
    template_name = 'authapp/register.html'
    form_class = CustomUserCreationForm
    success_url = reverse_lazy('login')

    def form_valid(self, form):
        return super().form_valid(form)
