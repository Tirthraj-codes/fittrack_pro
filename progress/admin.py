from django.contrib import admin

from .models import FitnessGoal, ProgressEntry


@admin.register(ProgressEntry)
class ProgressEntryAdmin(admin.ModelAdmin):
    list_display = ('member', 'date', 'weight_kg', 'height_cm')
    list_filter = ('date',)
    search_fields = ('member__username', 'member__first_name', 'member__last_name')


@admin.register(FitnessGoal)
class FitnessGoalAdmin(admin.ModelAdmin):
    list_display = ('member', 'goal_type', 'start_weight_kg', 'target_weight_kg', 'is_active')
    list_filter = ('goal_type', 'is_active')