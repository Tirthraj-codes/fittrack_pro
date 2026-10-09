from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .forms import StyledPasswordResetForm, StyledSetPasswordForm

urlpatterns = [
    # Sign up / in / out
    path('register/', views.register, name='register'),
    path(
        'login/',
        auth_views.LoginView.as_view(
            template_name='accounts/login.html',
            redirect_authenticated_user=True,
        ),
        name='login',
    ),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    # Profile and password change
    path('profile/', views.profile, name='profile'),
    path('password/change/', views.StyledPasswordChangeView.as_view(), name='password_change'),

    # Forgot password (4 built-in steps)
    path(
        'password/reset/',
        auth_views.PasswordResetView.as_view(
            template_name='accounts/password_reset_form.html',
            email_template_name='accounts/password_reset_email.txt',
            subject_template_name='accounts/password_reset_subject.txt',
            form_class=StyledPasswordResetForm,
        ),
        name='password_reset',
    ),
    path(
        'password/reset/sent/',
        auth_views.PasswordResetDoneView.as_view(template_name='accounts/password_reset_done.html'),
        name='password_reset_done',
    ),
    path(
        'reset/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='accounts/password_reset_confirm.html',
            form_class=StyledSetPasswordForm,
        ),
        name='password_reset_confirm',
    ),
    path(
        'reset/done/',
        auth_views.PasswordResetCompleteView.as_view(template_name='accounts/password_reset_complete.html'),
        name='password_reset_complete',
    ),

    # Admin: manage users
    path('manage/users/', views.user_list, name='user_list'),
    path('manage/users/add/', views.user_create, name='user_create'),
    path('manage/users/<int:pk>/toggle/', views.user_toggle_active, name='user_toggle_active'),
]