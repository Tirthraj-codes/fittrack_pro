from datetime import timedelta

from django.utils import timezone

from memberships.models import Membership

from .models import Attendance
from .utils import clock


class AttendanceError(Exception):
    """A friendly message that can be shown straight to staff."""


def open_record_for(member):
    """The member's current visit: checked in within the last 12 hours and not yet out."""
    since = timezone.now() - timedelta(hours=12)
    return (
        Attendance.objects.filter(member=member, check_out__isnull=True, check_in__gte=since)
        .order_by('-check_in')
        .first()
    )


def check_in(member, by, method=Attendance.Method.MANUAL):
    if not Membership.objects.running().filter(member=member).exists():
        raise AttendanceError(
            f'{member.display_name} has no active membership, so the check-in was not recorded.'
        )
    record, created = Attendance.objects.get_or_create(
        member=member,
        date=timezone.localdate(),
        defaults={'check_in': timezone.now(), 'method': method, 'recorded_by': by},
    )
    if not created:
        if record.check_out is None:
            raise AttendanceError(f'{member.display_name} is already checked in (since {clock(record.check_in)}).')
        raise AttendanceError(f'{member.display_name} has already completed attendance for today.')
    return record


def close_record(record):
    record.check_out = timezone.now()
    record.save(update_fields=['check_out'])
    return record


def check_out(member):
    record = open_record_for(member)
    if record is None:
        raise AttendanceError(f'{member.display_name} is not checked in right now.')
    return close_record(record)


def scan_member(member, by):
    """QR/barcode scan: the first scan checks in, the next scan checks out."""
    if open_record_for(member):
        return check_out(member), 'out'
    return check_in(member, by, Attendance.Method.QR), 'in'