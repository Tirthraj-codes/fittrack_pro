from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from .recommendations import generate
from accounts.decorators import member_required, staff_required
from accounts.models import User

from .forms import GoalForm, ProgressEntryForm
from .models import ProgressEntry
from .utils import build_summary, can_access_member


def _back_url(user, member):
    """Where to go after saving: members to their own page, staff to the member's page."""
    if user.is_member:
        return reverse('my_progress')
    return reverse('member_progress', args=[member.pk])


def _progress_page(request, member):
    is_self = member.pk == request.user.pk
    suffix = '' if is_self else f'?member={member.pk}'
    context = build_summary(member)
    context.update({
        'plan_url': reverse('my_plan') if is_self else reverse('member_plan', args=[member.pk]),
        'target': member,
        'is_self': is_self,
        'add_url': reverse('entry_create') + suffix,
        'goal_url': reverse('goal_create') + suffix,
    })
    return render(request, 'progress/progress.html', context)


# ================= Progress pages =================
@member_required
def my_progress(request):
    return _progress_page(request, request.user)


@staff_required
def member_progress(request, member_id):
    member = get_object_or_404(User, pk=member_id, role=User.Role.MEMBER)
    if not can_access_member(request.user, member):
        raise PermissionDenied
    return _progress_page(request, member)


@staff_required
def progress_overview(request):
    q = request.GET.get('q', '').strip()
    members = User.objects.filter(role=User.Role.MEMBER, is_active=True)
    if request.user.is_trainer:
        members = members.filter(trainer_assignment__trainer=request.user)
    if q:
        members = members.filter(
            Q(username__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q)
        )

    rows = []
    for member in members.order_by('first_name', 'username'):
        entries = list(member.progress_entries.order_by('date', 'id'))
        latest = entries[-1] if entries else None
        first = entries[0] if entries else None
        change = None
        if latest and first and latest is not first:
            change = round(float(latest.weight_kg) - float(first.weight_kg), 1)
        rows.append({
            'member': member, 'latest': latest, 'change': change,
            'count': len(entries), 'goal': member.goals.filter(is_active=True).first(),
        })
    return render(request, 'progress/overview.html', {'rows': rows, 'q': q})


# ================= Entries =================
@login_required
def entry_create(request):
    user = request.user
    initial = {'date': timezone.localdate()}
    target = user if user.is_member else None

    member_param = request.GET.get('member', '')
    if not user.is_member and member_param.isdigit():
        picked = User.objects.filter(pk=int(member_param), role=User.Role.MEMBER).first()
        if picked and can_access_member(user, picked):
            target = picked
            initial['member'] = picked.pk

    if target:                                       # height rarely changes, so pre-fill it
        last = target.progress_entries.first()
        if last:
            initial['height_cm'] = last.height_cm

    form = ProgressEntryForm(request.POST or None, user=user, initial=initial)
    if request.method == 'POST' and form.is_valid():
        entry = form.save(commit=False)
        entry.recorded_by = user
        entry.save()
        messages.success(request, f'Measurements saved. BMI {entry.bmi} ({entry.bmi_category}).')
        return redirect(_back_url(user, entry.member))

    if user.is_member:
        cancel_url = reverse('my_progress')
    elif target:
        cancel_url = reverse('member_progress', args=[target.pk])
    else:
        cancel_url = reverse('progress_overview')
    return render(request, 'progress/entry_form.html', {
        'form': form, 'title': 'Log measurements',
        'subtitle': f'For {target.display_name}' if target and not user.is_member else 'Record how you are doing today.',
        'cancel_url': cancel_url,
    })


@login_required
def entry_edit(request, pk):
    entry = get_object_or_404(ProgressEntry.objects.select_related('member'), pk=pk)
    if not can_access_member(request.user, entry.member):
        raise PermissionDenied

    form = ProgressEntryForm(request.POST or None, instance=entry, user=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Entry updated.')
        return redirect(_back_url(request.user, entry.member))
    return render(request, 'progress/entry_form.html', {
        'form': form, 'title': f'Edit entry: {entry.date:%d %b %Y}',
        'subtitle': f'For {entry.member.display_name}',
        'cancel_url': _back_url(request.user, entry.member),
    })


@login_required
@require_POST
def entry_delete(request, pk):
    entry = get_object_or_404(ProgressEntry.objects.select_related('member'), pk=pk)
    if not can_access_member(request.user, entry.member):
        raise PermissionDenied
    member = entry.member
    entry.delete()
    messages.success(request, 'Entry deleted.')
    return redirect(_back_url(request.user, member))


# ================= Goals =================
@login_required
def goal_create(request):
    user = request.user
    if user.is_member:
        member = user
    else:
        member_param = request.GET.get('member', '')
        member = None
        if member_param.isdigit():
            member = User.objects.filter(pk=int(member_param), role=User.Role.MEMBER).first()
        if member is None:
            messages.warning(request, 'Choose a member first.')
            return redirect('progress_overview')
        if not can_access_member(user, member):
            raise PermissionDenied

    if not member.progress_entries.exists():
        messages.warning(request, 'Log a first measurement before setting a goal.')
        suffix = '' if user.is_member else f'?member={member.pk}'
        return redirect(reverse('entry_create') + suffix)

    form = GoalForm(request.POST or None, member=member, by=user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Goal saved. It replaces any previous goal.')
        return redirect(_back_url(user, member))

    latest = member.progress_entries.first()
    return render(request, 'memberships/form.html', {
        'form': form, 'title': 'Set a goal',
        'subtitle': f'{member.display_name}: current weight {latest.weight_kg} kg',
        'submit_label': 'Save goal', 'cancel_url': _back_url(user, member),
        'icon': 'bi-bullseye', 'icon_class': 'grad-pink',
    })
   # ================= Workout and diet plan =================
def _plan_page(request, member):
       return render(request, 'progress/plan.html', {
           'target': member,
           'is_self': member.pk == request.user.pk,
           'plan': generate(member),
       })
@member_required
def my_plan(request):
       return _plan_page(request, request.user)


@staff_required
def member_plan(request, member_id):
       member = get_object_or_404(User, pk=member_id, role=User.Role.MEMBER)
       if not can_access_member(request.user, member):
           raise PermissionDenied
       return _plan_page(request, member)