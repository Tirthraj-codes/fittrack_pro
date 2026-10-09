import random
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import Payment

DUE_GRACE_DAYS = 3   # a membership payment is due this many days after the membership starts


def create_pending_payment(membership):
    """Called automatically whenever a membership is created."""
    payment = Payment.objects.create(
        member=membership.member,
        membership=membership,
        description=f'{membership.plan.name} plan ({membership.plan.duration_label})',
        amount=membership.amount,
        due_date=membership.start_date + timedelta(days=DUE_GRACE_DAYS),
    )
    if payment.amount <= 0:                      # a free plan needs no payment
        mark_paid(payment, Payment.Method.CASH, note='Free plan')
    return payment


@transaction.atomic
def mark_paid(payment, method, by=None, note=''):
    """Marks a payment as paid and creates its transaction ID and receipt number."""
    prefix = 'CSH' if method == Payment.Method.CASH else 'TXN'
    now = timezone.now()
    payment.status = Payment.Status.PAID
    payment.method = method
    payment.paid_on = now
    payment.transaction_id = f"{prefix}{timezone.localtime(now):%Y%m%d%H%M%S}{random.randint(100, 999)}"
    payment.receipt_no = f"FT-{timezone.localtime(now):%Y%m}-{payment.pk:05d}"
    payment.recorded_by = by                     # staff member who recorded it (empty for online payments)
    if note:
        payment.note = note
    payment.save()
    return payment


def cancel_pending_payments(membership):
    """When a membership is cancelled or upgraded, its unpaid payments are cancelled too."""
    membership.payments.filter(status=Payment.Status.PENDING).update(status=Payment.Status.CANCELLED)