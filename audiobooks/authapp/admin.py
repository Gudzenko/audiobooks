
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser
from django.contrib.auth.models import Group


class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ('email', 'username', 'is_staff', 'is_active', 'manager')
    list_filter = ('is_staff', 'is_active', 'groups')
    search_fields = ('email', 'username')
    ordering = ('email',)
    readonly_fields = ('date_joined',)
    fieldsets = (
        (None, {'fields': ('email', 'username', 'password', 'manager')}),
        ('Permissions', {'fields': ('is_staff', 'is_active', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )


admin.site.register(CustomUser, CustomUserAdmin)
admin.site.unregister(Group)
admin.site.register(Group)
