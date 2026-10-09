from collections import Counter, defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone

from attendance.models import Attendance
from memberships.models import STATUS_LABELS, Membership
from payments.models import Payment

User = get_user_model()
WEEKDAY_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']


# ---------- date helpers ----------
def add_months(day, months):
    """First day of the month that is `months` away from `day`'s month."""
    index = day.year * 12 + (day.month - 1) + months
    return date(index // 12, index % 12 + 1, 1)


def parse_range(request):
    """Reads ?from=YYYY-MM-DD&to=YYYY-MM-DD. Defaults to the last 6 months."""
    today = timezone.localdate()

    def read(name, default):
        try:
            return date.fromisoformat(request.GET.get(name, ''))
        except ValueError:
            return default

    start = read('from', add_months(today, -5))
    end = read('to', today)
    if start > end:
        start, end = end, start
    if (end - start).days > 730:                    # two years at most
        start = end - timedelta(days=730)
    return start, end


def presets(today):
    return [
        ('Last 30 days', today - timedelta(days=29), today),
        ('Last 90 days', today - timedelta(days=89), today),
        ('This month', today.replace(day=1), today),
        ('Last 6 months', add_months(today, -5), today),
        ('Last 12 months', add_months(today, -11), today),
        ('This year', date(today.year, 1, 1), today),
    ]


def month_keys(start, end):
    keys, current = [], date(start.year, start.month, 1)
    while current <= end:
        keys.append((current.year, current.month))
        current = add_months(current, 1)
    return keys


def month_label(key):
    return date(key[0], key[1], 1).strftime('%b %Y')


def _local(moment):
    return timezone.localtime(moment)


def _ranked(groups):
    """{'UPI': [3, Decimal]} -> list sorted by money, biggest first."""
    rows = [{'name': name, 'count': values[0], 'total': values[1]} for name, values in groups.items()]
    return sorted(rows, key=lambda row: row['total'], reverse=True)


# ---------- the three reports ----------
def revenue_report(start, end):
    payments = list(
        Payment.objects.paid()
        .filter(paid_on__date__range=(start, end))
        .select_related('membership__plan')
    )
    keys = month_keys(start, end)
    monthly = {key: Decimal('0') for key in keys}
    by_method = defaultdict(lambda: [0, Decimal('0')])
    by_plan = defaultdict(lambda: [0, Decimal('0')])
    total = Decimal('0')

    for p in payments:
        local = _local(p.paid_on)
        monthly[(local.year, local.month)] += p.amount
        method = p.get_method_display() or 'Unknown'
        plan = p.membership.plan.name if p.membership else 'Other charges'
        for group, name in ((by_method, method), (by_plan, plan)):
            group[name][0] += 1
            group[name][1] += p.amount
        total += p.amount

    unpaid = Payment.objects.filter(status=Payment.Status.PENDING)
    overdue = Payment.objects.overdue()
    return {
        'total': total,
        'count': len(payments),
        'monthly': [{'label': month_label(key), 'total': monthly[key]} for key in keys],
        'by_method': _ranked(by_method),
        'by_plan': _ranked(by_plan),
        'outstanding': {
            'total': sum((p.amount for p in unpaid), Decimal('0')),
            'count': unpaid.count(),
            'overdue_total': sum((p.amount for p in overdue), Decimal('0')),
            'overdue_count': overdue.count(),
        },
    }


def membership_report(start, end):
    keys = month_keys(start, end)
    rows = {key: {'new': 0, 'renewal': 0, 'upgrade': 0, 'signups': 0} for key in keys}

    sold = list(Membership.objects.filter(created_at__date__range=(start, end)))
    for m in sold:
        local = _local(m.created_at)
        rows[(local.year, local.month)][m.kind] += 1

    joined = User.objects.filter(
        role=User.Role.MEMBER, date_joined__date__range=(start, end)
    ).values_list('date_joined', flat=True)
    signups_total = 0
    for moment in joined:
        local = _local(moment)
        rows[(local.year, local.month)]['signups'] += 1
        signups_total += 1

    return {
        'sold': len(sold),
        'signups_total': signups_total,
        'monthly': [{'label': month_label(key), **rows[key]} for key in keys],
        'status_counts': [
            {'label': label, 'count': getattr(Membership.objects, key)().count()}
            for key, label in STATUS_LABELS.items()
        ],
        'active_members': Membership.objects.running().values('member').distinct().count(),
    }


def attendance_report(start, end):
    today = timezone.localdate()
    records = list(Attendance.objects.filter(date__range=(start, end)).select_related('member'))

    # visits per week (weeks start on Monday)
    per_week = Counter(r.date - timedelta(days=r.date.weekday()) for r in records)
    weekly, week = [], start - timedelta(days=start.weekday())
    while week <= end:
        weekly.append({'label': week.strftime('%d %b'), 'visits': per_week.get(week, 0)})
        week += timedelta(days=7)

    per_weekday = Counter(r.date.weekday() for r in records)
    per_hour = Counter(_local(r.check_in).hour for r in records)
    low, high = min([5] + list(per_hour)), max([22] + list(per_hour))
    by_hour = [
        {'label': f'{hour % 12 or 12} {"AM" if hour < 12 else "PM"}', 'visits': per_hour.get(hour, 0)}
        for hour in range(low, high + 1)
    ]

    names, days_attended = {}, Counter()
    for r in records:
        names[r.member_id] = r.member.display_name
        days_attended[r.member_id] += 1

    counted_days = max((min(end, today) - start).days + 1, 1)
    return {
        'total_visits': len(records),
        'unique_members': len(days_attended),
        'avg_per_day': round(len(records) / counted_days, 1),
        'weekly': weekly,
        'by_weekday': [{'label': WEEKDAY_NAMES[i], 'visits': per_weekday.get(i, 0)} for i in range(7)],
        'by_hour': by_hour,
        'top_members': [{'name': names[pk], 'days': count} for pk, count in days_attended.most_common(5)],
    }


def build_report(start, end):
    revenue = revenue_report(start, end)
    memberships = membership_report(start, end)
    attendance = attendance_report(start, end)
    summary = {
        'revenue_total': revenue['total'],
        'outstanding_total': revenue['outstanding']['total'],
        'sold': memberships['sold'],
        'active_members': memberships['active_members'],
        'signups': memberships['signups_total'],
        'visits': attendance['total_visits'],
    }
    return {'revenue': revenue, 'memberships': memberships, 'attendance': attendance, 'summary': summary}


def build_charts(data):
    """The numbers the Chart.js charts need, as plain lists."""
    revenue, memberships, attendance = data['revenue'], data['memberships'], data['attendance']
    months = [row['label'] for row in memberships['monthly']]
    return {
        'revenue': {'labels': [r['label'] for r in revenue['monthly']],
                    'values': [float(r['total']) for r in revenue['monthly']]},
        'method': {'labels': [r['name'] for r in revenue['by_method']],
                   'values': [float(r['total']) for r in revenue['by_method']]},
        'plan': {'labels': [r['name'] for r in revenue['by_plan']],
                 'values': [float(r['total']) for r in revenue['by_plan']]},
        'sold': {'labels': months,
                 'new': [r['new'] for r in memberships['monthly']],
                 'renewal': [r['renewal'] for r in memberships['monthly']],
                 'upgrade': [r['upgrade'] for r in memberships['monthly']]},
        'signups': {'labels': months, 'values': [r['signups'] for r in memberships['monthly']]},
        'status': {'labels': [r['label'] for r in memberships['status_counts']],
                   'values': [r['count'] for r in memberships['status_counts']]},
        'weekly': {'labels': [r['label'] for r in attendance['weekly']],
                   'values': [r['visits'] for r in attendance['weekly']]},
        'weekday': {'labels': [r['label'] for r in attendance['by_weekday']],
                    'values': [r['visits'] for r in attendance['by_weekday']]},
        'hour': {'labels': [r['label'] for r in attendance['by_hour']],
                 'values': [r['visits'] for r in attendance['by_hour']]},
    }