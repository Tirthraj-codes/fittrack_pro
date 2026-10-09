from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import admin_required, staff_required, trainer_required
from accounts.models import User
from memberships.models import Membership

from .forms import AvailabilityForm, SessionForm, SessionLogForm
from .models import WEEKDAYS, Session, TrainerAssignment, TrainerAvailability


def _form_page(request, form, title, subtitle, submit_label, cancel_url,
               icon='bi-calendar-plus-fill', icon_class='grad-blue'):
    """Reuses the shared form page from the memberships templates."""
    return render(request, 'memberships/form.html', {
        'form': form, 'title': title, 'subtitle': subtitle,
        'submit_label': submit_label, 'cancel_url': cancel_url,
        'icon': icon, 'icon_class': icon_class,
    })


def _week_url(day):
    return f"{reverse('schedule_week')}?date={day.isoformat()}"


def _can_view(user, session):
    return user.is_admin_role or session.trainer_id == user.pk or session.member_id == user.pk


def _can_manage(user, session):
    return user.is_admin_role or session.trainer_id == user.pk


# ================= Weekly schedule (everyone) =================
@login_required
def schedule_week(request):
    user = request.user
    today = timezone.localdate()
    try:
        anchor = date.fromisoformat(request.GET.get('date', ''))
    except ValueError:
        anchor = today
    monday = anchor - timedelta(days=anchor.weekday())
    sunday = monday + timedelta(days=6)

    sessions = Session.objects.filter(date__range=(monday, sunday)).select_related('trainer', 'member')
    trainers, trainer_id = None, ''
    if user.is_trainer:
        sessions = sessions.filter(trainer=user)
    elif user.is_member:
        sessions = sessions.filter(member=user)
    else:                                            # admin: can filter by trainer
        trainers = User.objects.filter(role=User.Role.TRAINER, is_active=True).order_by('first_name', 'username')
        trainer_id = request.GET.get('trainer', '')
        if trainer_id.isdigit():
            sessions = sessions.filter(trainer_id=int(trainer_id))

    sessions = list(sessions)
    days = []
    for offset in range(7):
        day = monday + timedelta(days=offset)
        days.append({
            'date': day,
            'is_today': day == today,
            'sessions': [s for s in sessions if s.date == day],
        })

    context = {
        'days': days, 'monday': monday, 'sunday': sunday,
        'prev_week': monday - timedelta(days=7), 'next_week': monday + timedelta(days=7),
        'trainers': trainers, 'trainer_id': trainer_id,
    }
    return render(request, 'scheduling/week.html', context)


# ================= Sessions =================
@staff_required
def session_create(request):
    initial = {'date': timezone.localdate()}
    member_id = request.GET.get('member', '')
    if member_id.isdigit():
        initial['member'] = int(member_id)

    form = SessionForm(request.POST or None, user=request.user, initial=initial)
    if request.method == 'POST' and form.is_valid():
        session = form.save(commit=False)
        session.created_by = request.user
        session.save()
        messages.success(
            request,
            f'Session booked: {session.member.display_name} with {session.trainer.display_name} on {session.date:%a, %d %b}.'
        )
        return redirect(_week_url(session.date))
    return _form_page(request, form, 'Book a session',
                      'The system checks availability, clashes and the member\'s membership.',
                      'Book session', reverse('schedule_week'))


@staff_required
def session_edit(request, pk):
    session = get_object_or_404(Session.objects.select_related('trainer', 'member'), pk=pk)
    if not _can_manage(request.user, session):
        raise PermissionDenied
    if session.status != Session.Status.SCHEDULED:
        messages.error(request, 'Only scheduled sessions can be rescheduled.')
        return redirect('session_detail', pk=pk)

    form = SessionForm(request.POST or None, instance=session, user=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Session rescheduled.')
        return redirect('session_detail', pk=pk)
    return _form_page(request, form, 'Reschedule session',
                      f'{session.member.display_name} with {session.trainer.display_name}',
                      'Save changes', reverse('session_detail', args=[pk]),
                      'bi-calendar2-week-fill', 'grad-orange')


@login_required
def session_detail(request, pk):
    session = get_object_or_404(Session.objects.select_related('trainer', 'member'), pk=pk)
    if not _can_view(request.user, session):
        raise PermissionDenied

    can_manage = _can_manage(request.user, session)
    form = None
    if can_manage and session.status != Session.Status.CANCELLED:
        form = SessionLogForm(request.POST or None, instance=session)
        if request.method == 'POST' and form.is_valid():
            form.save()
            messages.success(request, 'Session log saved.')
            return redirect('session_detail', pk=pk)

    return render(request, 'scheduling/session_detail.html',
                  {'session': session, 'form': form, 'can_manage': can_manage})


@staff_required
@require_POST
def session_cancel(request, pk):
    session = get_object_or_404(Session, pk=pk)
    if not _can_manage(request.user, session):
        raise PermissionDenied
    if session.status == Session.Status.SCHEDULED:
        session.status = Session.Status.CANCELLED
        session.save(update_fields=['status'])
        messages.success(request, 'Session cancelled.')
    else:
        messages.error(request, 'Only a scheduled session can be cancelled.')
    return redirect(_week_url(session.date))


# ================= Trainer availability =================
@staff_required
def availability(request):
    user = request.user
    trainers = User.objects.filter(role=User.Role.TRAINER, is_active=True).order_by('first_name', 'username')

    if user.is_admin_role:
        picked = request.GET.get('trainer', '')
        trainer = trainers.filter(pk=int(picked)).first() if picked.isdigit() else trainers.first()
        if trainer is None:
            messages.warning(request, 'Create a trainer account first.')
            return redirect('user_list')
    else:
        trainer = user

    form = AvailabilityForm(request.POST or None, trainer=trainer)
    if request.method == 'POST' and form.is_valid():
        count = form.save()
        messages.success(request, f'Availability added for {count} day{"s" if count != 1 else ""}.')
        return redirect(f"{reverse('availability')}?trainer={trainer.pk}")

    slots = list(trainer.availability.all())
    by_day = [
        {'name': name, 'slots': [s for s in slots if s.weekday == value]}
        for value, name in WEEKDAYS
    ]
    context = {
        'form': form, 'trainer': trainer, 'by_day': by_day,
        'trainers': trainers if user.is_admin_role else None,
    }
    return render(request, 'scheduling/availability.html', context)


@staff_required
@require_POST
def availability_delete(request, pk):
    slot = get_object_or_404(TrainerAvailability, pk=pk)
    if not (request.user.is_admin_role or slot.trainer_id == request.user.pk):
        raise PermissionDenied
    slot.delete()
    messages.success(request, 'Availability slot removed.')
    return redirect(f"{reverse('availability')}?trainer={slot.trainer_id}")


# ================= Trainer: my members =================
@trainer_required
def my_members(request):
    today = timezone.localdate()
    assignments = request.user.assigned_members.select_related('member').order_by('member__first_name')

    rows = []
    for assignment in assignments:
        member = assignment.member
        memberships = Membership.objects.filter(member=member)
        rows.append({
            'member': member,
            'membership': memberships.running().first() or memberships.first(),
            'next_session': Session.objects.filter(
                trainer=request.user, member=member, date__gte=today, status=Session.Status.SCHEDULED
            ).order_by('date', 'start_time').first(),
        })
    return render(request, 'scheduling/my_members.html', {'rows': rows})


# ================= Admin: trainer assignments =================
@admin_required
def assignment_list(request):
    q = request.GET.get('q', '').strip()
    show = request.GET.get('show', '')

    members = User.objects.filter(role=User.Role.MEMBER, is_active=True).select_related(
        'trainer_assignment__trainer'
    ).order_by('first_name', 'username')
    if show == 'unassigned':
        members = members.filter(trainer_assignment__isnull=True)
    if q:
        members = members.filter(
            Q(username__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q)
        )

    trainers = User.objects.filter(role=User.Role.TRAINER, is_active=True).annotate(
        member_count=Count('assigned_members')
    ).order_by('first_name', 'username')

    context = {'members': members, 'trainers': trainers, 'q': q, 'show': show}
    return render(request, 'scheduling/assignments.html', context)


@admin_required
@require_POST
def assignment_set(request, member_id):
    member = get_object_or_404(User, pk=member_id, role=User.Role.MEMBER)
    trainer_id = request.POST.get('trainer', '')

    if trainer_id == '':
        TrainerAssignment.objects.filter(member=member).delete()
        messages.success(request, f'Trainer removed from {member.display_name}.')
    elif trainer_id.isdigit():
        trainer = get_object_or_404(User, pk=int(trainer_id), role=User.Role.TRAINER, is_active=True)
        TrainerAssignment.objects.update_or_create(
            member=member, defaults={'trainer': trainer, 'assigned_on': timezone.localdate()}
        )
        messages.success(request, f'{member.display_name} is now assigned to {trainer.display_name}.')
    else:
        raise Http404
    return redirect(request.META.get('HTTP_REFERER') or 'assignment_list')