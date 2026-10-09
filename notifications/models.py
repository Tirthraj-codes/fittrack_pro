from django.conf import settings
from django.db import models


class Notification(models.Model):
    """One reminder for one person. It is shown in the app and also emailed when possible."""

    class Kind(models.TextChoices):
        MEMBERSHIP_EXPIRING = 'membership_expiring', 'Membership expiring'
        MEMBERSHIP_EXPIRED = 'membership_expired', 'Membership expired'
        PAYMENT_DUE = 'payment_due', 'Payment due'
        PAYMENT_OVERDUE = 'payment_overdue', 'Payment overdue'
        SESSION = 'session', 'Session reminder'

    class EmailStatus(models.TextChoices):
        SENT = 'sent', 'Sent'
        FAILED = 'failed', 'Failed'
        SKIPPED = 'skipped', 'Not sent'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    kind = models.CharField(max_length=25, choices=Kind.choices)
    title = models.CharField(max_length=140)
    message = models.TextField()
    link = models.CharField(max_length=200, blank=True)      # a path inside the site, e.g. /payments/mine/
    key = models.CharField(max_length=100)                   # makes sure the same reminder is never created twice
    is_read = models.BooleanField(default=False)
    email_status = models.CharField(max_length=10, choices=EmailStatus.choices, default=EmailStatus.SKIPPED)
    email_error = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        constraints = [
            models.UniqueConstraint(fields=['user', 'key'], name='one_notification_per_user_per_key'),
        ]

    def __str__(self):
        return f"{self.user} - {self.title}"

    @property
    def icon(self):
        return {
            'membership_expiring': 'bi-hourglass-split',
            'membership_expired': 'bi-x-circle-fill',
            'payment_due': 'bi-credit-card-2-front-fill',
            'payment_overdue': 'bi-exclamation-triangle-fill',
            'session': 'bi-calendar-event-fill',
        }.get(self.kind, 'bi-bell-fill')

    @property
    def color(self):
        return {
            'membership_expiring': 'grad-orange',
            'membership_expired': 'grad-pink',
            'payment_due': 'grad-blue',
            'payment_overdue': 'grad-pink',
            'session': 'grad-purple',
        }.get(self.kind, 'grad-teal')