from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordChangeView
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST

from .decorators import admin_required
from .forms import (
    MemberRegistrationForm,
    ProfileForm,
    StaffCreateForm,
    StyledPasswordChangeForm,
)
from .models import User


# ---------- Registration ----------
def register(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = MemberRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'Welcome to FitTrack Pro, {user.display_name}! Your account is ready.')
            return redirect('dashboard')
    else:
        form = MemberRegistrationForm()

    return render(request, 'accounts/register.html', {'form': form})


# ---------- Profile ----------
@login_required
def profile(request):
    # Use a fresh copy so a failed form never changes the name shown in the navbar
    profile_user = User.objects.get(pk=request.user.pk)

    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance=profile_user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your profile was updated.')
            return redirect('profile')
    else:
        form = ProfileForm(instance=profile_user)

    return render(request, 'accounts/profile.html', {'form': form, 'profile_user': profile_user})


class StyledPasswordChangeView(SuccessMessageMixin, PasswordChangeView):
    template_name = 'accounts/password_change.html'
    form_class = StyledPasswordChangeForm
    success_url = reverse_lazy('profile')
    success_message = 'Your password was changed successfully.'


# ---------- Admin: user management ----------
@admin_required
def user_list(request):
    users = User.objects.all().order_by('-date_joined')
    role = request.GET.get('role', '')
    q = request.GET.get('q', '').strip()

    if role in User.Role.values:
        users = users.filter(role=role)
    if q:
        users = users.filter(
            Q(username__icontains=q) | Q(first_name__icontains=q)
            | Q(last_name__icontains=q) | Q(email__icontains=q)
        )

    context = {'users': users, 'role': role, 'q': q, 'roles': User.Role.choices}
    return render(request, 'accounts/user_list.html', context)


@admin_required
def user_create(request):
    if request.method == 'POST':
        form = StaffCreateForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f'{user.get_role_display()} account created for {user.display_name}.')
            return redirect('user_list')
    else:
        form = StaffCreateForm()

    return render(request, 'accounts/user_form.html', {'form': form})


@admin_required
@require_POST
def user_toggle_active(request, pk):
    target = get_object_or_404(User, pk=pk)
    if target == request.user:
        messages.error(request, "You can't deactivate your own account.")
    else:
        target.is_active = not target.is_active
        target.save(update_fields=['is_active'])
        state = 'activated' if target.is_active else 'deactivated'
        messages.success(request, f'{target.display_name} was {state}.')
    return redirect('user_list')