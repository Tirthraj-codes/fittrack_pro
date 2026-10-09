import re
from datetime import date

from django import forms
from django.contrib.auth.forms import (
    PasswordChangeForm,
    PasswordResetForm,
    SetPasswordForm,
    UserCreationForm,
)
from django.core.files.uploadedfile import UploadedFile

from core.forms import BootstrapFormMixin

from .models import User


class UserFieldsCleanMixin:
    """Shared validation for email, phone and date of birth."""

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        others = User.objects.filter(email__iexact=email)
        if self.instance and self.instance.pk:
            others = others.exclude(pk=self.instance.pk)   # ignore the user themself
        if others.exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email

    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '').replace(' ', '')
        if phone and not re.fullmatch(r'\+?\d{10,13}', phone):
            raise forms.ValidationError('Enter a valid phone number (10 to 13 digits).')
        return phone

    def clean_date_of_birth(self):
        dob = self.cleaned_data.get('date_of_birth')
        if dob and dob >= date.today():
            raise forms.ValidationError('Date of birth must be in the past.')
        return dob


class MemberRegistrationForm(UserFieldsCleanMixin, BootstrapFormMixin, UserCreationForm):
    """Public sign-up form. It always creates a Member."""

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('first_name', 'last_name', 'username', 'email',
                  'phone', 'gender', 'date_of_birth')
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['first_name'].required = True
        self.fields['last_name'].required = True
        self.fields['email'].required = True
        self.fields['password1'].help_text = 'At least 8 characters, not too common, not only numbers.'
        self.fields['password2'].help_text = ''

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.MEMBER      # public sign-up = Member only
        if commit:
            user.save()
        return user


class StaffCreateForm(UserFieldsCleanMixin, BootstrapFormMixin, UserCreationForm):
    """Used by an admin to create Trainer or Admin accounts."""

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('first_name', 'last_name', 'username', 'email', 'phone', 'role')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ('first_name', 'last_name', 'email'):
            self.fields[name].required = True
        # Only these two roles can be created here
        self.fields['role'].choices = [
            (User.Role.TRAINER, 'Trainer'),
            (User.Role.ADMIN, 'Admin'),
        ]
        self.initial['role'] = User.Role.TRAINER
        self.fields['password1'].help_text = 'At least 8 characters, not too common, not only numbers.'
        self.fields['password2'].help_text = ''


class ProfileForm(UserFieldsCleanMixin, BootstrapFormMixin, forms.ModelForm):
    """Lets any logged-in user edit their own details and photo."""

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'phone',
                  'gender', 'date_of_birth', 'address', 'photo')
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'address': forms.Textarea(attrs={'rows': 3}),
            'photo': forms.FileInput(attrs={'accept': 'image/*'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ('first_name', 'last_name', 'email'):
            self.fields[name].required = True

    def clean_photo(self):
        photo = self.cleaned_data.get('photo')
        # Only check size for a newly uploaded file
        if isinstance(photo, UploadedFile) and photo.size > 2 * 1024 * 1024:
            raise forms.ValidationError('Photo must be smaller than 2 MB.')
        return photo


# Django's built-in password forms, restyled with Bootstrap
class StyledPasswordChangeForm(BootstrapFormMixin, PasswordChangeForm):
    pass


class StyledPasswordResetForm(BootstrapFormMixin, PasswordResetForm):
    pass


class StyledSetPasswordForm(BootstrapFormMixin, SetPasswordForm):
    pass