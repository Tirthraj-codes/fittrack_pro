from memberships.models import Membership

from .models import Session, TrainerAvailability


def t12(value):
    """06:30 -> '06:30 AM'"""
    return value.strftime('%I:%M %p')


def _overlapping(queryset, day, start, end, exclude_pk):
    """First non-cancelled session that overlaps the given time window."""
    queryset = queryset.filter(date=day, start_time__lt=end, end_time__gt=start)
    queryset = queryset.exclude(status=Session.Status.CANCELLED)
    if exclude_pk:
        queryset = queryset.exclude(pk=exclude_pk)
    return queryset.select_related('trainer', 'member').first()


def trainer_clash(trainer, day, start, end, exclude_pk=None):
    return _overlapping(Session.objects.filter(trainer=trainer), day, start, end, exclude_pk)


def member_clash(member, day, start, end, exclude_pk=None):
    return _overlapping(Session.objects.filter(member=member), day, start, end, exclude_pk)


def within_availability(trainer, day, start, end):
    """True if the whole session fits inside one of the trainer's weekly windows."""
    return TrainerAvailability.objects.filter(
        trainer=trainer, weekday=day.weekday(),
        start_time__lte=start, end_time__gte=end,
    ).exists()


def has_membership_on(member, day):
    """True if the member has a running (not closed) membership on that date."""
    return Membership.objects.filter(
        member=member, closed_reason='', start_date__lte=day, end_date__gte=day
    ).exists()