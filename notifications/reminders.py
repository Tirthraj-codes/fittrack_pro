from collections import Counter
from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from memberships.models import Membership
from payments.models import Payment
from scheduling.models import Session

from .models import Notification
from .services import notify

K = Notification.Kind


def _has_queued_renewal(membership):
    """True if the member already has a later membership lined up (so no need to remind)."""
    return Membership.objects.filter(
        member=membership.member, closed_reason='', start_date__gt=membership.end_date
    ).exists()


def _when(days):
    if days <= 0:
        return 'today'
    if days == 1:
        return 'tomorrow'
    return f'in {days} days'


def run_reminders(dry_run=False):
    """Checks every rule and creates the reminders that are due. Safe to run as often as you like."""
    today = timezone.localdate()
    created = []

    def add(notification):
        if notification:
            created.append(notification)

    # 1. Memberships ending within 7 days
    for m in Membership.objects.expiring().select_related('member', 'plan'):
        if _has_queued_renewal(m):
            continue
        days = m.days_left
        stage = 2 if days <= 2 else 7                  # one reminder at 7 days, another at 2 days
        add(notify(
            m.member, K.MEMBERSHIP_EXPIRING,
            f'Your {m.plan.name} membership ends {_when(days)}',
            f'Your membership ends on {m.end_date:%d %b %Y}. Please renew at the front desk to keep training without a break.',
            key=f'membership-expiring-{m.pk}-{stage}', link=reverse('my_membership'), dry_run=dry_run,
        ))

    # 2. Memberships that ended in the last 7 days
    recently_expired = Membership.objects.expired().filter(end_date__gte=today - timedelta(days=7))
    for m in recently_expired.select_related('member', 'plan'):
        if _has_queued_renewal(m):
            continue
        add(notify(
            m.member, K.MEMBERSHIP_EXPIRED,
            f'Your {m.plan.name} membership has expired',
            f'It ended on {m.end_date:%d %b %Y}. Please renew at the front desk to continue training.',
            key=f'membership-expired-{m.pk}', link=reverse('my_membership'), dry_run=dry_run,
        ))

    # 3. Payments due in the next 3 days
    due_soon = Payment.objects.filter(
        status=Payment.Status.PENDING, due_date__gte=today, due_date__lte=today + timedelta(days=3)
    )
    for p in due_soon.select_related('member'):
        add(notify(
            p.member, K.PAYMENT_DUE,
            f'Payment due {_when((p.due_date - today).days)}',
            f'{p.description}: Rs. {p.amount:,.2f} is due on {p.due_date:%d %b %Y}. You can pay online from the My Payments page.',
            key=f'payment-due-{p.pk}', link=reverse('my_payments'), dry_run=dry_run,
        ))

    # 4. Overdue payments (first reminder at once, then once a week)
    for p in Payment.objects.overdue().select_related('member'):
        days_over = (today - p.due_date).days
        add(notify(
            p.member, K.PAYMENT_OVERDUE,
            'Payment overdue',
            f'{p.description}: Rs. {p.amount:,.2f} was due on {p.due_date:%d %b %Y} ({days_over} day{"s" if days_over != 1 else ""} ago). '
            'Please pay as soon as you can.',
            key=f'payment-overdue-{p.pk}-{days_over // 7}', link=reverse('my_payments'), dry_run=dry_run,
        ))

    # 5. Sessions tomorrow: remind the member and the trainer
    tomorrow = Session.objects.filter(date=today + timedelta(days=1), status=Session.Status.SCHEDULED)
    for s in tomorrow.select_related('member', 'trainer'):
        when = f'{s.date:%A, %d %b} at {s.start_time:%I:%M %p}'
        link = reverse('session_detail', args=[s.pk])
        add(notify(
            s.member, K.SESSION, f'Session tomorrow: {s.get_kind_display()}',
            f'{s.get_kind_display()} with {s.trainer.display_name} on {when}.',
            key=f'session-{s.pk}-member', link=link, dry_run=dry_run,
        ))
        add(notify(
            s.trainer, K.SESSION, f'Session tomorrow: {s.get_kind_display()}',
            f'{s.get_kind_display()} with {s.member.display_name} on {when}.',
            key=f'session-{s.pk}-trainer', link=link, dry_run=dry_run,
        ))

    return {
        'dry_run': dry_run,
        'new': len(created),
        'emails_sent': sum(1 for n in created if n.email_status == Notification.EmailStatus.SENT),
        'emails_failed': sum(1 for n in created if n.email_status == Notification.EmailStatus.FAILED),
        'not_emailed': sum(1 for n in created if n.email_status == Notification.EmailStatus.SKIPPED),
        'by_kind': dict(Counter(n.get_kind_display() for n in created)),
    }