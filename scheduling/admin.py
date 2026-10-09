from django.contrib import admin

from .models import Session, TrainerAssignment, TrainerAvailability


@admin.register(TrainerAvailability)
class TrainerAvailabilityAdmin(admin.ModelAdmin):
    list_display = ('trainer', 'weekday', 'start_time', 'end_time')
    list_filter = ('weekday', 'trainer')


@admin.register(TrainerAssignment)
class TrainerAssignmentAdmin(admin.ModelAdmin):
    list_display = ('member', 'trainer', 'assigned_on')


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ('kind', 'member', 'trainer', 'date', 'start_time', 'end_time', 'status')
    list_filter = ('status', 'kind', 'trainer')