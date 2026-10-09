from datetime import timedelta
from progress.models import FitnessGoal
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import redirect, render
from django.utils import timezone

from accounts.decorators import admin_required, member_required, trainer_required
from attendance.models import Attendance
from memberships.models import Membership
from payments.models import Payment
from scheduling.models import Session, TrainerAssignment

User = get_user_model()


def _total(queryset):
    return queryset.aggregate(total=Sum('amount'))['total'] or 0


def home(request):
    return render(request, 'core/home.html')


@login_required
def dashboard(request):
    """Sends each user to the dashboard that matches their role."""
    if request.user.is_admin_role:
        return redirect('admin_dashboard')
    if request.user.is_trainer:
        return redirect('trainer_dashboard')
    return redirect('member_dashboard')


@admin_required
def admin_dashboard(request):
    today = timezone.localdate()
    collected = _total(Payment.objects.paid().filter(paid_on__year=today.year, paid_on__month=today.month))
    context = {
        'total_members': User.objects.filter(role=User.Role.MEMBER).count(),
        'total_trainers': User.objects.filter(role=User.Role.TRAINER).count(),
        'running_memberships': Membership.objects.running().count(),
        'expiring_count': Membership.objects.expiring().count(),
        'expired_count': Membership.objects.expired().count(),
        'expiring_list': Membership.objects.expiring().select_related('member', 'plan').order_by('end_date')[:5],
        'visits_today': Attendance.objects.filter(date=today).count(),
        'collected_this_month': collected,
        'pending_total': _total(Payment.objects.filter(status=Payment.Status.PENDING)),
        'overdue_count': Payment.objects.overdue().count(),
    }
    return render(request, 'core/admin_dashboard.html', context)


@trainer_required
def trainer_dashboard(request):
    today = timezone.localdate()
    my_sessions = Session.objects.filter(trainer=request.user).exclude(
        status=Session.Status.CANCELLED
    ).select_related('member')
    context = {
        'assigned_count': request.user.assigned_members.count(),
        'today_sessions': my_sessions.filter(date=today),
        'upcoming_count': my_sessions.filter(
            date__gt=today, date__lte=today + timedelta(days=7), status=Session.Status.SCHEDULED
        ).count(),
    }
    return render(request, 'core/trainer_dashboard.html', context)
@member_required
def member_dashboard(request):
       today = timezone.localdate()
       memberships = request.user.memberships.select_related('plan')
       current = memberships.running().order_by('end_date').first()
       unpaid = request.user.payments.filter(status=Payment.Status.PENDING)
       assignment = TrainerAssignment.objects.filter(member=request.user).select_related('trainer').first()
       next_session = Session.objects.filter(
           member=request.user, date__gte=today, status=Session.Status.SCHEDULED
       ).select_related('trainer').order_by('date', 'start_time').first()

       context = {
           'membership': current or memberships.first(),
           'unpaid_count': unpaid.count(),
           'unpaid_total': _total(unpaid),
           'trainer': assignment.trainer if assignment else None,
           'next_session': next_session,
           'latest_entry': request.user.progress_entries.first(),
           'goal': FitnessGoal.objects.filter(member=request.user, is_active=True).first(),
       }
       return render(request, 'core/member_dashboard.html', context)