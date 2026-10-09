from django import forms
from django.utils import timezone

from accounts.models import User
from core.forms import BootstrapFormMixin

from .models import WEEKDAYS, Session, TrainerAvailability
from .services import (
    has_membership_on, member_clash, t12, trainer_clash, within_availability,
)


class AvailabilityForm(BootstrapFormMixin, forms.Form):
    """Adds the same hours to one or more weekdays for a trainer."""
    weekdays = forms.MultipleChoiceField(
        choices=[(str(value), name) for value, name in WEEKDAYS],
        error_messages={'required': 'Choose at least one day.'},
    )
    start_time = forms.TimeField(widget=forms.TimeInput(attrs={'type': 'time'}, format='%H:%M'))
    end_time = forms.TimeField(widget=forms.TimeInput(attrs={'type': 'time'}, format='%H:%M'))

    def __init__(self, *args, trainer, **kwargs):
        super().__init__(*args, **kwargs)
        self.trainer = trainer

    def clean(self):
        cleaned = super().clean()
        days = cleaned.get('weekdays')
        start, end = cleaned.get('start_time'), cleaned.get('end_time')
        if not (days and start and end):
            return cleaned
        if end <= start:
            self.add_error('end_time', 'The end time must be after the start time.')
            return cleaned

        names = dict(WEEKDAYS)
        clashing = [
            names[int(day)] for day in days
            if TrainerAvailability.objects.filter(
                trainer=self.trainer, weekday=int(day), start_time__lt=end, end_time__gt=start
            ).exists()
        ]
        if clashing:
            raise forms.ValidationError(
                f'These hours overlap with existing availability on: {", ".join(clashing)}.'
            )
        return cleaned

    def save(self):
        slots = [
            TrainerAvailability(
                trainer=self.trainer, weekday=int(day),
                start_time=self.cleaned_data['start_time'], end_time=self.cleaned_data['end_time'],
            )
            for day in self.cleaned_data['weekdays']
        ]
        TrainerAvailability.objects.bulk_create(slots)
        return len(slots)


class SessionForm(BootstrapFormMixin, forms.ModelForm):
    """Book or reschedule a session. Admins pick the trainer, trainers book for themselves."""

    class Meta:
        model = Session
        fields = ('trainer', 'member', 'kind', 'date', 'start_time', 'end_time')
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'start_time': forms.TimeInput(attrs={'type': 'time'}, format='%H:%M'),
            'end_time': forms.TimeInput(attrs={'type': 'time'}, format='%H:%M'),
        }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fixed_trainer = user if user.is_trainer else None

        self.fields['trainer'].queryset = User.objects.filter(
            role=User.Role.TRAINER, is_active=True
        ).order_by('first_name', 'username')
        self.fields['trainer'].label_from_instance = lambda u: f"{u.display_name} (@{u.username})"
        self.fields['member'].queryset = User.objects.filter(
            role=User.Role.MEMBER, is_active=True
        ).order_by('first_name', 'username')
        self.fields['member'].label_from_instance = lambda u: f"{u.display_name} (@{u.username})"

        if self.fixed_trainer:                       # a trainer always books for themselves
            del self.fields['trainer']
            self.instance.trainer = self.fixed_trainer

    def clean(self):
        cleaned = super().clean()
        trainer = self.fixed_trainer or cleaned.get('trainer')
        member = cleaned.get('member')
        day = cleaned.get('date')
        start, end = cleaned.get('start_time'), cleaned.get('end_time')
        if not (trainer and member and day and start and end):
            return cleaned                           # field errors are already shown

        if end <= start:
            self.add_error('end_time', 'The end time must be after the start time.')
            return cleaned
        if day < timezone.localdate():
            self.add_error('date', 'Sessions cannot be booked in the past.')
            return cleaned

        exclude_pk = self.instance.pk
        if not has_membership_on(member, day):
            raise forms.ValidationError(f'{member.display_name} has no active membership on {day:%d %b %Y}.')
        if not within_availability(trainer, day, start, end):
            raise forms.ValidationError(
                f'{trainer.display_name} is not available on {day:%A} from {t12(start)} to {t12(end)}. '
                'Check the trainer\'s availability.'
            )
        clash = trainer_clash(trainer, day, start, end, exclude_pk)
        if clash:
            raise forms.ValidationError(
                f'Time clash: {trainer.display_name} already has a session from '
                f'{t12(clash.start_time)} to {t12(clash.end_time)} with {clash.member.display_name}.'
            )
        clash = member_clash(member, day, start, end, exclude_pk)
        if clash:
            raise forms.ValidationError(
                f'Time clash: {member.display_name} already has a session from '
                f'{t12(clash.start_time)} to {t12(clash.end_time)} with {clash.trainer.display_name}.'
            )
        return cleaned


class SessionLogForm(BootstrapFormMixin, forms.ModelForm):
    """The trainer's log: outcome and notes."""

    class Meta:
        model = Session
        fields = ('status', 'notes')
        labels = {'notes': 'Session log / notes'}
        widgets = {
            'notes': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'What did you work on? Exercises, weights, feedback, next steps...',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['status'].choices = [
            (Session.Status.SCHEDULED, 'Scheduled'),
            (Session.Status.COMPLETED, 'Completed'),
            (Session.Status.NO_SHOW, 'No-show'),
        ]

    def clean_status(self):
        status = self.cleaned_data['status']
        finished = status in (Session.Status.COMPLETED, Session.Status.NO_SHOW)
        if finished and self.instance.date > timezone.localdate():
            raise forms.ValidationError('A future session cannot be marked as completed or no-show yet.')
        return status