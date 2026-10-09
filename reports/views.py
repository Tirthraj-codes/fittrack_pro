import csv

from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from accounts.decorators import admin_required
from attendance.models import Attendance
from memberships.models import Membership
from payments.models import Payment

from .pdf import build_summary_pdf
from .utils import build_charts, build_report, parse_range, presets


def _local(moment):
    return timezone.localtime(moment)


def _safe(value):
    """Stops spreadsheets from running text such as '=1+1' as a formula."""
    if isinstance(value, str) and value.startswith(('=', '+', '-', '@', '\t', '\r')):
        return "'" + value
    return value


def _csv_response(filename, header, rows):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response.write('\ufeff')                       # lets Excel read the file as UTF-8
    writer = csv.writer(response)
    writer.writerow(header)
    for row in rows:
        writer.writerow([_safe(value) for value in row])
    return response


def _range_name(start, end):
    return f'{start.isoformat()}_to_{end.isoformat()}'


# ================= The report page =================
@admin_required
def report_dashboard(request):
    start, end = parse_range(request)
    data = build_report(start, end)
    today = timezone.localdate()

    context = dict(data)
    context.update({
        'start': start, 'end': end,
        'query': f'from={start.isoformat()}&to={end.isoformat()}',
        'presets': [
            {'label': label, 'from': s.isoformat(), 'to': e.isoformat(), 'active': (s, e) == (start, end)}
            for label, s, e in presets(today)
        ],
        'chart': build_charts(data),
    })
    return render(request, 'reports/dashboard.html', context)


# ================= Exports =================
@admin_required
def export_payments(request):
    start, end = parse_range(request)
    payments = (Payment.objects.paid().filter(paid_on__date__range=(start, end))
                .select_related('member', 'recorded_by').order_by('paid_on'))
    rows = [
        [p.receipt_no, _local(p.paid_on).strftime('%Y-%m-%d %H:%M'), p.member.display_name, p.member.username,
         p.description, p.get_method_display(), p.amount, p.transaction_id,
         p.recorded_by.display_name if p.recorded_by else 'Online']
        for p in payments
    ]
    header = ['Receipt no', 'Paid on', 'Member', 'Username', 'Description', 'Method',
              'Amount (INR)', 'Transaction ID', 'Recorded by']
    return _csv_response(f'payments_{_range_name(start, end)}.csv', header, rows)


@admin_required
def export_dues(request):
    today = timezone.localdate()
    dues = Payment.objects.filter(status=Payment.Status.PENDING).select_related('member').order_by('due_date')
    rows = [
        [p.member.display_name, p.member.username, p.member.phone, p.member.email, p.description,
         p.amount, p.due_date, max((today - p.due_date).days, 0), p.display_status_label]
        for p in dues
    ]
    header = ['Member', 'Username', 'Phone', 'Email', 'Description', 'Amount (INR)',
              'Due date', 'Days overdue', 'Status']
    return _csv_response(f'unpaid-dues_{today.isoformat()}.csv', header, rows)


@admin_required
def export_memberships(request):
    start, end = parse_range(request)
    memberships = (Membership.objects.filter(created_at__date__range=(start, end))
                   .select_related('member', 'plan').order_by('created_at'))
    rows = [
        [m.member.display_name, m.member.username, m.plan.name, m.get_kind_display(), m.start_date, m.end_date,
         m.amount, m.status_label, _local(m.created_at).strftime('%Y-%m-%d')]
        for m in memberships
    ]
    header = ['Member', 'Username', 'Plan', 'Type', 'Starts', 'Ends', 'Amount (INR)', 'Status today', 'Sold on']
    return _csv_response(f'memberships_{_range_name(start, end)}.csv', header, rows)


@admin_required
def export_attendance(request):
    start, end = parse_range(request)
    records = (Attendance.objects.filter(date__range=(start, end))
               .select_related('member').order_by('date', 'check_in'))
    rows = [
        [r.date, r.member.display_name, r.member.username, _local(r.check_in).strftime('%H:%M'),
         _local(r.check_out).strftime('%H:%M') if r.check_out else '',
         r.duration_minutes if r.duration_minutes is not None else '', r.get_method_display()]
        for r in records
    ]
    header = ['Date', 'Member', 'Username', 'Check-in', 'Check-out', 'Minutes', 'Method']
    return _csv_response(f'attendance_{_range_name(start, end)}.csv', header, rows)


@admin_required
def export_summary(request):
    start, end = parse_range(request)
    pdf = build_summary_pdf(start, end, build_report(start, end))
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="club-report_{_range_name(start, end)}.pdf"'
    return response