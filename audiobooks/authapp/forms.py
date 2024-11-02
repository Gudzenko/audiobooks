from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import Group
from .models import CustomUser


class CustomUserCreationForm(UserCreationForm):
    USER_TYPE_CHOICES = (
        ('user', 'User'),
        ('manager', 'Manager'),
    )

    user_type = forms.ChoiceField(choices=USER_TYPE_CHOICES, label="User Type")

    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'password1', 'password2', 'user_type')

    def save(self, commit=True):
        user = super().save(commit=False)
        user_type = self.cleaned_data['user_type']

        if commit:
            user.save()
            group = None
            if user_type == 'user':
                group = Group.objects.get(name='User')
            elif user_type == 'manager':
                group = Group.objects.get(name='Manager')
            if group is not None:
                user.groups.add(group)
        return user


class CustomLoginForm(AuthenticationForm):
    username = forms.CharField(label='Email or Username', max_length=254)
    password = forms.CharField(widget=forms.PasswordInput)
