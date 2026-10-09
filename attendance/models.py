from django.conf import settings
from django.db import models
from django.utils import timezone


def format_minutes(minutes):
    hours, mins = divmod(int(minutes), 60)
    return f"{hours}h {mins}m" if hours else f"{mins}m"


class Attendance(models.Model):
    class Method(models.TextChoices):
        MANUAL = 'manual', 'Manual'
        QR = 'qr', 'QR code'

    member = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='attendance_records', limit_choices_to={'role': 'member'},
    )
    date = models.DateField(default=timezone.localdate)
    check_in = models.DateTimeField(default=timezone.now)
    check_out = models.DateTimeField(null=True, blank=True)
    method = models.CharField(max_length=10, choices=Method.choices, default=Method.MANUAL)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
    )

    class Meta:
        ordering = ['-date', '-check_in']
        constraints = [
            models.UniqueConstraint(fields=['member', 'date'], name='one_attendance_per_member_per_day'),
        ]

    def __str__(self):
        return f"{self.member} - {self.date}"

    @property
    def duration_minutes(self):
        if not self.check_out:
            return None
        return int((self.check_out - self.check_in).total_seconds() // 60)

    @property
    def duration_label(self):
        minutes = self.duration_minutes
        return '-' if minutes is None else format_minutes(minutes)