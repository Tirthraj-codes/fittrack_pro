from django.conf import settings
from django.db import models
from django.utils import timezone

WEEKDAYS = [
    (0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'), (3, 'Thursday'),
    (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday'),
]


class TrainerAvailability(models.Model):
    """A weekly time window in which a trainer can take sessions."""
    trainer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='availability', limit_choices_to={'role': 'trainer'},
    )
    weekday = models.PositiveSmallIntegerField(choices=WEEKDAYS)
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        ordering = ['weekday', 'start_time']
        verbose_name_plural = 'trainer availability'

    def __str__(self):
        return f"{self.trainer} - {self.get_weekday_display()} {self.start_time:%H:%M}-{self.end_time:%H:%M}"


class TrainerAssignment(models.Model):
    """Each member has at most one assigned trainer."""
    member = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='trainer_assignment', limit_choices_to={'role': 'member'},
    )
    trainer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='assigned_members', limit_choices_to={'role': 'trainer'},
    )
    assigned_on = models.DateField(default=timezone.localdate)

    def __str__(self):
        return f"{self.member} -> {self.trainer}"


class Session(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = 'scheduled', 'Scheduled'
        COMPLETED = 'completed', 'Completed'
        NO_SHOW = 'no_show', 'No-show'
        CANCELLED = 'cancelled', 'Cancelled'

    class Kind(models.TextChoices):
        PERSONAL = 'personal_training', 'Personal training'
        ASSESSMENT = 'assessment', 'Fitness assessment'
        DIET = 'diet', 'Diet consultation'
        OTHER = 'other', 'Other'

    trainer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='trainer_sessions', limit_choices_to={'role': 'trainer'},
    )
    member = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='member_sessions', limit_choices_to={'role': 'member'},
    )
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.PERSONAL)
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.SCHEDULED)
    notes = models.TextField(blank=True)          # the trainer's session log
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['date', 'start_time']

    def __str__(self):
        return f"{self.get_kind_display()}: {self.member} with {self.trainer} on {self.date}"