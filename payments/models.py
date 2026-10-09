from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

STATUS_LABELS = {
    'paid': 'Paid',
    'pending': 'Pending',
    'overdue': 'Overdue',
    'cancelled': 'Cancelled',
}


class PaymentQuerySet(models.QuerySet):
    def paid(self):
        return self.filter(status='paid')

    def pending(self):
        """Waiting for payment and not late yet."""
        return self.filter(status='pending', due_date__gte=timezone.localdate())

    def overdue(self):
        """Waiting for payment and past the due date."""
        return self.filter(status='pending', due_date__lt=timezone.localdate())

    def cancelled(self):
        return self.filter(status='cancelled')


class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PAID = 'paid', 'Paid'
        CANCELLED = 'cancelled', 'Cancelled'

    class Method(models.TextChoices):
        CARD = 'card', 'Card'
        UPI = 'upi', 'UPI'
        NETBANKING = 'netbanking', 'Net Banking'
        CASH = 'cash', 'Cash'

    member = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='payments', limit_choices_to={'role': 'member'},
    )
    # Empty for extra charges (locker fee etc.) that are not tied to a membership
    membership = models.ForeignKey(
        'memberships.Membership', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='payments',
    )
    description = models.CharField(max_length=120)
    amount = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(0)])
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    method = models.CharField(max_length=12, choices=Method.choices, blank=True)
    due_date = models.DateField()
    paid_on = models.DateTimeField(null=True, blank=True)
    transaction_id = models.CharField(max_length=30, blank=True)
    receipt_no = models.CharField(max_length=30, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
    )
    note = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = PaymentQuerySet.as_manager()

    class Meta:
        ordering = ['-created_at', '-id']

    def __str__(self):
        return f"{self.member} - {self.description} - Rs.{self.amount}"

    # 'overdue' is not stored: it is worked out from the due date each time
    @property
    def display_status(self):
        if self.status == self.Status.PENDING and self.due_date < timezone.localdate():
            return 'overdue'
        return self.status

    @property
    def display_status_label(self):
        return STATUS_LABELS[self.display_status]