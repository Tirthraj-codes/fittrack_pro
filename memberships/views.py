from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import admin_required, member_required

from .forms import AssignMembershipForm, MembershipPlanForm, PlanChoiceForm
from .models import STATUS_LABELS, Membership, MembershipPlan
from .services import cancel_membership, create_membership, renew_membership, upgrade_membership


def _form_page(request, form, title, subtitle, submit_label, cancel_url_name,
               icon='bi-pencil-fill', icon_class='grad-purple'):
    """Renders the shared form page used by every create/edit screen below."""
    return render(request, 'memberships/form.html', {
        'form': form, 'title': title, 'subtitle': subtitle,
        'submit_label': submit_label, 'cancel_url': reverse(cancel_url_name),
        'icon': icon, 'icon_class': icon_class,
    })


# ================= Plans (admin) =================
@admin_required
def plan_list(request):
    return render(request, 'memberships/plan_list.html', {'plans': MembershipPlan.objects.all()})


@admin_required
def plan_create(request):
    form = MembershipPlanForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        plan = form.save()
        messages.success(request, f'Plan "{plan.name}" was created.')
        return redirect('plan_list')
    return _form_page(request, form, 'Add membership plan', 'Set the duration, price and features.',
                      'Create plan', 'plan_list', 'bi-card-checklist', 'grad-orange')


@admin_required
def plan_edit(request, pk):
    plan = get_object_or_404(MembershipPlan, pk=pk)
    form = MembershipPlanForm(request.POST or None, instance=plan)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'Plan "{plan.name}" was updated.')
        return redirect('plan_list')
    return _form_page(request, form, f'Edit plan: {plan.name}',
                      'Changing a price does not affect memberships already sold.',
                      'Save changes', 'plan_list', 'bi-pencil-fill', 'grad-orange')


@admin_required
@require_POST
def plan_toggle(request, pk):
    plan = get_object_or_404(MembershipPlan, pk=pk)
    plan.is_active = not plan.is_active
    plan.save(update_fields=['is_active'])
    state = 'activated' if plan.is_active else 'deactivated'
    messages.success(request, f'Plan "{plan.name}" was {state}.')
    return redirect('plan_list')


# ================= Memberships (admin) =================
@admin_required
def membership_list(request):
    status = request.GET.get('status', '')
    q = request.GET.get('q', '').strip()

    memberships = Membership.objects.select_related('member', 'plan')
    if status in STATUS_LABELS:
        memberships = getattr(memberships, status)()      # e.g. memberships.expiring()
    if q:
        memberships = memberships.filter(
            Q(member__username__icontains=q)
            | Q(member__first_name__icontains=q)
            | Q(member__last_name__icontains=q)
        )

    chips = [
        {'key': key, 'label': label, 'count': getattr(Membership.objects, key)().count()}
        for key, label in STATUS_LABELS.items()
    ]
    context = {
        'memberships': memberships, 'status': status, 'q': q,
        'chips': chips, 'total': Membership.objects.count(),
    }
    return render(request, 'memberships/membership_list.html', context)


@admin_required
def membership_assign(request):
    form = AssignMembershipForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        member = form.cleaned_data['member']
        plan = form.cleaned_data['plan']
        membership = create_membership(member, plan, form.cleaned_data['start_date'])
        messages.success(
            request,
            f'{plan.name} assigned to {member.display_name} until {membership.end_date:%d %b %Y}.'
        )
        return redirect('membership_list')
    return _form_page(request, form, 'Assign a plan', 'Give a member a new membership.',
                      'Assign plan', 'membership_list', 'bi-person-check-fill', 'grad-teal')


@admin_required
def membership_renew(request, pk):
    membership = get_object_or_404(Membership.objects.select_related('member', 'plan'), pk=pk)

    if not membership.can_renew:
        messages.error(request, 'This membership cannot be renewed.')
        return redirect('membership_list')
    already_queued = Membership.objects.filter(
        member=membership.member, closed_reason='', start_date__gt=membership.end_date
    ).exists()
    if already_queued:
        messages.error(request, f'A renewal is already queued for {membership.member.display_name}.')
        return redirect('membership_list')

    form = PlanChoiceForm(request.POST or None, plans=MembershipPlan.objects.filter(is_active=True),
                          initial_plan=membership.plan)
    if request.method == 'POST' and form.is_valid():
        plan = form.cleaned_data['plan']
        new = renew_membership(membership, plan)
        messages.success(
            request,
            f'{membership.member.display_name} renewed on {plan.name}, valid until {new.end_date:%d %b %Y}.'
        )
        return redirect('membership_list')

    subtitle = f'{membership.member.display_name}: {membership.plan.name}, ends {membership.end_date:%d %b %Y}'
    return _form_page(request, form, 'Renew membership', subtitle, 'Renew', 'membership_list',
                      'bi-arrow-repeat', 'grad-teal')


@admin_required
def membership_upgrade(request, pk):
    membership = get_object_or_404(Membership.objects.select_related('member', 'plan'), pk=pk)

    if not membership.can_upgrade:
        messages.error(request, 'Only a running membership can be upgraded.')
        return redirect('membership_list')
    higher_plans = MembershipPlan.objects.filter(is_active=True, price__gt=membership.plan.price)
    if not higher_plans.exists():
        messages.warning(request, f'There is no higher plan than {membership.plan.name} to upgrade to.')
        return redirect('membership_list')

    form = PlanChoiceForm(request.POST or None, plans=higher_plans)
    if request.method == 'POST' and form.is_valid():
        plan = form.cleaned_data['plan']
        new = upgrade_membership(membership, plan)
        messages.success(
            request,
            f'{membership.member.display_name} upgraded to {plan.name}, valid until {new.end_date:%d %b %Y}.'
        )
        return redirect('membership_list')

    subtitle = (f'{membership.member.display_name} is on {membership.plan.name}. '
                'The current membership ends today and the new plan starts today.')
    return _form_page(request, form, 'Upgrade membership', subtitle, 'Upgrade', 'membership_list',
                      'bi-rocket-takeoff-fill', 'grad-pink')


@admin_required
@require_POST
def membership_cancel(request, pk):
    membership = get_object_or_404(Membership.objects.select_related('member'), pk=pk)
    if membership.can_cancel:
        cancel_membership(membership)
        messages.success(request, f"{membership.member.display_name}'s membership was cancelled.")
    else:
        messages.error(request, 'This membership cannot be cancelled.')
    return redirect('membership_list')


# ================= Member: my membership =================
@member_required
def my_membership(request):
    history = request.user.memberships.select_related('plan')
    current = (history.running().order_by('end_date').first()
               or history.upcoming().order_by('start_date').first())
    context = {'current': current, 'latest': history.first(), 'history': history}
    return render(request, 'memberships/my_membership.html', context)