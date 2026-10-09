from datetime import timedelta

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

EXPIRING_SOON_DAYS = 7

STATUS_LABELS = {
    'active': 'Active',
    'expiring': 'Expiring soon',
    'upcoming': 'Upcoming',
    'expired': 'Expired',
    'cancelled': 'Cancelled',
    'upgraded': 'Upgraded',
}


class MembershipPlan(models.Model):
    name = models.CharField(max_length=60, unique=True)
    duration_days = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text='30 = 1 month, 90 = 3 months, 365 = 1 year',
    )
    price = models.DecimalField(
        max_digits=8, decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text='Price in rupees',
    )
    features = models.TextField(blank=True, help_text='One feature per line')
    is_active = models.BooleanField(default=True, help_text='Inactive plans cannot be sold to members')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['price']

    def __str__(self):
        return self.name

    @property
    def feature_list(self):
        return [line.strip() for line in self.features.splitlines() if line.strip()]

    @property
    def duration_label(self):
        days = self.duration_days
        if days % 365 == 0:
            n, unit = days // 365, 'year'
        elif days % 30 == 0:
            n, unit = days // 30, 'month'
        else:
            n, unit = days, 'day'
        return f"{n} {unit}{'s' if n != 1 else ''}"


class MembershipQuerySet(models.QuerySet):
    """Ready-made filters, e.g. Membership.objects.expiring()"""

    def running(self):
        """Valid today (includes the 'expiring soon' ones)."""
        today = timezone.localdate()
        return self.filter(closed_reason='', start_date__lte=today, end_date__gte=today)

    def active(self):
        limit = timezone.localdate() + timedelta(days=EXPIRING_SOON_DAYS)
        return self.running().filter(end_date__gt=limit)

    def expiring(self):
        limit = timezone.localdate() + timedelta(days=EXPIRING_SOON_DAYS)
        return self.running().filter(end_date__lte=limit)

    def upcoming(self):
        return self.filter(closed_reason='', start_date__gt=timezone.localdate())

    def expired(self):
        return self.filter(closed_reason='', end_date__lt=timezone.localdate())

    def cancelled(self):
        return self.filter(closed_reason='cancelled')

    def upgraded(self):
        return self.filter(closed_reason='upgraded')

    def unfinished(self):
        """Not closed and not yet ended: running or upcoming."""
        return self.filter(closed_reason='', end_date__gte=timezone.localdate())


class Membership(models.Model):
    class Kind(models.TextChoices):
        NEW = 'new', 'New'
        RENEWAL = 'renewal', 'Renewal'
        UPGRADE = 'upgrade', 'Upgrade'

    class ClosedReason(models.TextChoices):
        CANCELLED = 'cancelled', 'Cancelled'
        UPGRADED = 'upgraded', 'Upgraded'

    member = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='memberships', limit_choices_to={'role': 'member'},
    )
    plan = models.ForeignKey(MembershipPlan, on_delete=models.PROTECT, related_name='memberships')
    start_date = models.DateField()
    end_date = models.DateField()
    amount = models.DecimalField(max_digits=8, decimal_places=2)   # price at the time of purchase
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.NEW)
    closed_reason = models.CharField(max_length=10, choices=ClosedReason.choices, blank=True)
    closed_on = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = MembershipQuerySet.as_manager()

    class Meta:
        ordering = ['-start_date', '-id']

    def __str__(self):
        return f"{self.member} - {self.plan}"

    # ----- automatic status flagging -----
    @property
    def status(self):
        today = timezone.localdate()
        if self.closed_reason:
            return self.closed_reason            # 'cancelled' or 'upgraded'
        if self.end_date < today:
            return 'expired'
        if self.start_date > today:
            return 'upcoming'
        if (self.end_date - today).days <= EXPIRING_SOON_DAYS:
            return 'expiring'
        return 'active'

    @property
    def status_label(self):
        return STATUS_LABELS[self.status]

    @property
    def days_left(self):
        return (self.end_date - timezone.localdate()).days

    @property
    def progress_percent(self):
        total = (self.end_date - self.start_date).days or 1
        elapsed = (timezone.localdate() - self.start_date).days
        return max(0, min(100, round(elapsed / total * 100)))

    # ----- which actions are allowed -----
    @property
    def can_renew(self):
        return self.status in ('active', 'expiring', 'expired')

    @property
    def can_upgrade(self):
        return self.status in ('active', 'expiring')

    @property
    def can_cancel(self):
        return self.status in ('active', 'expiring', 'upcoming')