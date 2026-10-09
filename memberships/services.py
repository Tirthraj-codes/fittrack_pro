from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from payments.services import cancel_pending_payments, create_pending_payment

from .models import Membership


@transaction.atomic
def create_membership(member, plan, start_date=None, kind=Membership.Kind.NEW):
    """Create a membership and its pending payment. The end date is start date + the plan's days."""
    start = start_date or timezone.localdate()
    membership = Membership.objects.create(
        member=member,
        plan=plan,
        start_date=start,
        end_date=start + timedelta(days=plan.duration_days),
        amount=plan.price,          # remember the price, even if the plan price changes later
        kind=kind,
    )
    create_pending_payment(membership)
    return membership


@transaction.atomic
def renew_membership(membership, plan):
    """New membership starting right after the current one ends (or today if it already ended)."""
    today = timezone.localdate()
    if membership.end_date >= today:
        start = membership.end_date + timedelta(days=1)
    else:
        start = today
    return create_membership(membership.member, plan, start, Membership.Kind.RENEWAL)


@transaction.atomic
def upgrade_membership(membership, new_plan):
    """Close the current membership today and start the higher plan today."""
    today = timezone.localdate()
    membership.closed_reason = Membership.ClosedReason.UPGRADED
    membership.closed_on = today
    membership.save(update_fields=['closed_reason', 'closed_on'])
    cancel_pending_payments(membership)
    return create_membership(membership.member, new_plan, today, Membership.Kind.UPGRADE)


@transaction.atomic
def cancel_membership(membership):
    membership.closed_reason = Membership.ClosedReason.CANCELLED
    membership.closed_on = timezone.localdate()
    membership.save(update_fields=['closed_reason', 'closed_on'])
    cancel_pending_payments(membership)
    return membership