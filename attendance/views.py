import calendar
from collections import Counter
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import admin_required, member_required, staff_required
from accounts.models import User

from .forms import ManualAttendanceForm
from .models import Attendance, format_minutes
from .services import AttendanceError, check_in, check_out, close_record, scan_member
from .utils import clock, member_code, member_from_code, parse_month, qr_png


# ================= Front desk (admin + trainer) =================
@staff_required
def desk(request):
    today = timezone.localdate()
    todays = Attendance.objects.filter(date=today).select_related('member')
    context = {
        'form': ManualAttendanceForm(),
        'todays': todays,
        'visits_today': todays.count(),
        'inside_now': todays.filter(check_out__isnull=True).count(),
        'today': today,
    }
    return render(request, 'attendance/desk.html', context)


@staff_required
@require_POST
def scan(request):
    member = member_from_code(request.POST.get('code', ''))
    if member is None:
        messages.error(request, 'That code is not valid. Please scan the member QR code again.')
        return redirect('attendance_desk')

    try:
        record, direction = scan_member(member, request.user)
    except AttendanceError as error:
        messages.error(request, str(error))
    else:
        if direction == 'in':
            messages.success(request, f'{member.display_name} checked IN at {clock(record.check_in)} (QR).')
        else:
            messages.success(
                request,
                f'{member.display_name} checked OUT at {clock(record.check_out)} ({record.duration_label}).'
            )
    return redirect('attendance_desk')


@staff_required
@require_POST
def manual(request):
    form = ManualAttendanceForm(request.POST)
    action = request.POST.get('action')
    if not form.is_valid() or action not in ('in', 'out'):
        messages.error(request, 'Please choose a member first.')
        return redirect('attendance_desk')

    member = form.cleaned_data['member']
    try:
        if action == 'in':
            record = check_in(member, request.user)
            messages.success(request, f'{member.display_name} checked IN at {clock(record.check_in)}.')
        else:
            record = check_out(member)
            messages.success(
                request,
                f'{member.display_name} checked OUT at {clock(record.check_out)} ({record.duration_label}).'
            )
    except AttendanceError as error:
        messages.error(request, str(error))
    return redirect('attendance_desk')


@staff_required
@require_POST
def record_checkout(request, pk):
    record = get_object_or_404(Attendance.objects.select_related('member'), pk=pk)
    if record.check_out is None:
        close_record(record)
        messages.success(
            request,
            f'{record.member.display_name} checked OUT at {clock(record.check_out)} ({record.duration_label}).'
        )
    else:
        messages.error(request, f'{record.member.display_name} is already checked out.')
    return redirect('attendance_desk')


# ================= History (admin + trainer) =================
@staff_required
def history(request):
    year, month = parse_month(request.GET.get('month'))
    member_id = request.GET.get('member', '')

    records = Attendance.objects.filter(date__year=year, date__month=month).select_related('member', 'recorded_by')
    if member_id.isdigit():
        records = records.filter(member_id=int(member_id))

    context = {
        'records': records,
        'members': User.objects.filter(role=User.Role.MEMBER).order_by('first_name', 'username'),
        'member_id': member_id,
        'month_value': f'{year}-{month:02d}',
        'month_label': date(year, month, 1),
        'today': timezone.localdate(),
    }
    return render(request, 'attendance/history.html', context)


# ================= Monthly report (admin only) =================
@admin_required
def monthly_report(request):
    year, month = parse_month(request.GET.get('month'))
    today = timezone.localdate()
    days_in_month = calendar.monthrange(year, month)[1]

    records = list(
        Attendance.objects.filter(date__year=year, date__month=month).select_related('member')
    )

    per_day = Counter()
    per_member = {}
    for r in records:
        per_day[r.date.day] += 1
        row = per_member.setdefault(
            r.member_id, {'member': r.member, 'days': 0, 'minutes': 0, 'last_visit': r.date}
        )
        row['days'] += 1
        row['minutes'] += r.duration_minutes or 0
        if r.date > row['last_visit']:
            row['last_visit'] = r.date

    rows = sorted(per_member.values(), key=lambda row: (-row['days'], row['member'].display_name))
    for row in rows:
        row['time_label'] = format_minutes(row['minutes'])

    # Average over the days that have happened so far
    if (year, month) == (today.year, today.month):
        counted_days = today.day
    elif (year, month) > (today.year, today.month):
        counted_days = 1
    else:
        counted_days = days_in_month

    busiest = per_day.most_common(1)
    context = {
        'month_value': f'{year}-{month:02d}',
        'month_label': date(year, month, 1),
        'total_visits': len(records),
        'members_visited': len(rows),
        'avg_per_day': round(len(records) / counted_days, 1),
        'busiest_day': date(year, month, busiest[0][0]) if busiest else None,
        'busiest_count': busiest[0][1] if busiest else 0,
        'rows': rows,
        'chart_labels': list(range(1, days_in_month + 1)),
        'chart_data': [per_day.get(day, 0) for day in range(1, days_in_month + 1)],
    }
    return render(request, 'attendance/report.html', context)


# ================= Member: my attendance =================
@member_required
def my_attendance(request):
    today = timezone.localdate()
    records = request.user.attendance_records.all()
    month_records = list(records.filter(date__year=today.year, date__month=today.month))
    month_minutes = sum(r.duration_minutes or 0 for r in month_records)

    context = {
        'qr_code': member_code(request.user),
        'today_record': records.filter(date=today).first(),
        'month_days': len(month_records),
        'month_time': format_minutes(month_minutes),
        'total_visits': records.count(),
        'recent': records[:60],
        'today': today,
    }
    return render(request, 'attendance/my_attendance.html', context)


# ================= QR image =================
@login_required
def qr_image(request, pk):
    """Members can see their own QR code. Admins and trainers can see anyone's."""
    if request.user.pk != pk and not (request.user.is_admin_role or request.user.is_trainer):
        raise PermissionDenied
    member = get_object_or_404(User, pk=pk, role=User.Role.MEMBER)
    return HttpResponse(qr_png(member_code(member)), content_type='image/png')