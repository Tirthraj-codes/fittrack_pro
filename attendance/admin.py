from django.contrib import admin

from .models import Attendance


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('member', 'date', 'check_in', 'check_out', 'method')
    list_filter = ('method', 'date')
    search_fields = ('member__username', 'member__first_name', 'member__last_name')