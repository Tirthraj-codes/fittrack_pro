from django import forms
from django.core.files.uploadedfile import UploadedFile  # noqa: F401  (not used, kept out of the way)
from django.utils import timezone

from accounts.models import User
from core.forms import BootstrapFormMixin

from .models import FitnessGoal, ProgressEntry


class ProgressEntryForm(BootstrapFormMixin, forms.ModelForm):
    """Members log their own measurements. Staff choose a member first."""

    class Meta:
        model = ProgressEntry
        fields = ('member', 'date', 'weight_kg', 'height_cm', 'body_fat_percent',
                  'chest_cm', 'waist_cm', 'hips_cm', 'arms_cm', 'thighs_cm', 'notes')
        labels = {
            'weight_kg': 'Weight (kg)',
            'height_cm': 'Height (cm)',
            'body_fat_percent': 'Body fat (%)',
            'chest_cm': 'Chest (cm)',
            'waist_cm': 'Waist (cm)',
            'hips_cm': 'Hips (cm)',
            'arms_cm': 'Arms (cm)',
            'thighs_cm': 'Thighs (cm)',
            'notes': 'Notes (optional)',
        }
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fixed_member = None

        if self.instance.pk:                         # editing: the member cannot change
            self.fixed_member = self.instance.member
        elif user.is_member:                         # a member always logs for themselves
            self.fixed_member = user
            self.instance.member = user

        if self.fixed_member:
            del self.fields['member']
        else:
            members = User.objects.filter(role=User.Role.MEMBER, is_active=True)
            if not user.is_admin_role:               # trainers: only their assigned members
                members = members.filter(trainer_assignment__trainer=user)
            self.fields['member'].queryset = members.order_by('first_name', 'username')
            self.fields['member'].label_from_instance = lambda u: f"{u.display_name} (@{u.username})"
            self.fields['member'].empty_label = 'Choose a member'

    def clean(self):
        cleaned = super().clean()
        member = self.fixed_member or cleaned.get('member')
        day = cleaned.get('date')

        if day and day > timezone.localdate():
            self.add_error('date', 'The date cannot be in the future.')
        elif member and day:
            duplicate = ProgressEntry.objects.filter(member=member, date=day).exclude(pk=self.instance.pk)
            if duplicate.exists():
                raise forms.ValidationError(
                    f'An entry for {day:%d %b %Y} already exists. Edit that entry instead.'
                )
        return cleaned


class GoalForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = FitnessGoal
        fields = ('goal_type', 'target_weight_kg', 'target_date', 'notes')
        labels = {
            'goal_type': 'Goal',
            'target_weight_kg': 'Target weight (kg)',
            'target_date': 'Target date (optional)',
            'notes': 'Notes (optional)',
        }
        widgets = {
            'target_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        }

    def __init__(self, *args, member, by, **kwargs):
        super().__init__(*args, **kwargs)
        self.member = member
        self.by = by
        latest = member.progress_entries.order_by('-date', '-id').first()
        self.latest_weight = latest.weight_kg if latest else None
        self.latest_height = latest.height_cm if latest else None
        self.fields['target_weight_kg'].help_text = 'Leave empty for a maintenance goal.'

    def clean(self):
        cleaned = super().clean()
        goal_type = cleaned.get('goal_type')
        target = cleaned.get('target_weight_kg')
        target_date = cleaned.get('target_date')
        current = self.latest_weight

        if current is None:
            raise forms.ValidationError('Log a first measurement before setting a goal.')

        if goal_type == FitnessGoal.GoalType.WEIGHT_LOSS:
            if target is None:
                self.add_error('target_weight_kg', 'Enter a target weight for this goal.')
            elif target >= current:
                self.add_error('target_weight_kg', f'A weight-loss target must be lower than the current weight ({current} kg).')
            else:
                target_bmi = float(target) / ((float(self.latest_height) / 100) ** 2)
                if target_bmi < 18.5:
                    self.add_error(
                        'target_weight_kg',
                        f'That target would give a BMI of {target_bmi:.1f}, which is in the underweight range '
                        '(below 18.5). Please choose a healthier target.'
                    )
        elif goal_type == FitnessGoal.GoalType.MUSCLE_GAIN:
            if target is None:
                self.add_error('target_weight_kg', 'Enter a target weight for this goal.')
            elif target <= current:
                self.add_error('target_weight_kg', f'A muscle-gain target must be higher than the current weight ({current} kg).')
        elif goal_type == FitnessGoal.GoalType.MAINTENANCE:
            cleaned['target_weight_kg'] = None       # maintenance has no target weight

        if target_date and target_date <= timezone.localdate():
            self.add_error('target_date', 'The target date must be in the future.')
        return cleaned

    def save(self, commit=True):
        goal = super().save(commit=False)
        goal.member = self.member
        goal.start_weight_kg = self.latest_weight
        goal.created_by = self.by
        if commit:
            # Only one goal is active at a time: the new one replaces the old one
            FitnessGoal.objects.filter(member=self.member, is_active=True).update(is_active=False)
            goal.save()
        return goal