from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_active')
    list_filter = ('role', 'is_active')

    # Show our extra fields on the edit page and the "add user" page
    fieldsets = UserAdmin.fieldsets + (
        ('FitTrack Profile', {'fields': ('role', 'phone', 'gender', 'date_of_birth', 'address', 'photo')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('FitTrack Profile', {'fields': ('role', 'phone')}),
    )