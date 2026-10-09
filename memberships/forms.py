from django import forms
from django.utils import timezone

from accounts.models import User
from core.forms import BootstrapFormMixin

from .models import Membership, MembershipPlan


def plan_label(plan):
    return f"{plan.name} - {plan.duration_label} - ₹{plan.price:,.0f}"


class MembershipPlanForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = MembershipPlan
        fields = ('name', 'duration_days', 'price', 'features', 'is_active')
        labels = {
            'duration_days': 'Duration (days)',
            'price': 'Price (₹)',
            'is_active': 'Available for sale',
        }
        widgets = {
            'features': forms.Textarea(attrs={'rows': 5, 'placeholder': 'Gym floor access\nLocker room\nFree Wi-Fi'}),
        }


class AssignMembershipForm(BootstrapFormMixin, forms.Form):
    member = forms.ModelChoiceField(queryset=User.objects.none(), empty_label='Choose a member')
    plan = forms.ModelChoiceField(queryset=MembershipPlan.objects.none(), empty_label='Choose a plan')
    start_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['member'].queryset = User.objects.filter(
            role=User.Role.MEMBER, is_active=True
        ).order_by('first_name', 'username')
        self.fields['member'].label_from_instance = lambda u: f"{u.display_name} (@{u.username})"
        self.fields['plan'].queryset = MembershipPlan.objects.filter(is_active=True)
        self.fields['plan'].label_from_instance = plan_label
        self.fields['start_date'].initial = timezone.localdate()

    def clean(self):
        cleaned = super().clean()
        member = cleaned.get('member')
        if member and Membership.objects.unfinished().filter(member=member).exists():
            raise forms.ValidationError(
                f'{member.display_name} already has an active or upcoming membership. '
                'Use Renew or Upgrade instead.'
            )
        return cleaned


class PlanChoiceForm(BootstrapFormMixin, forms.Form):
    """Pick one plan from a given list. Used for renew and upgrade."""
    plan = forms.ModelChoiceField(queryset=MembershipPlan.objects.none(), empty_label=None)

    def __init__(self, *args, plans, initial_plan=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['plan'].queryset = plans
        self.fields['plan'].label_from_instance = plan_label
        if initial_plan is not None:
            self.fields['plan'].initial = initial_plan.pk