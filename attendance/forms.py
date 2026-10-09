from django import forms

from accounts.models import User
from core.forms import BootstrapFormMixin


class ManualAttendanceForm(BootstrapFormMixin, forms.Form):
    member = forms.ModelChoiceField(queryset=User.objects.none(), empty_label='Choose a member')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['member'].queryset = User.objects.filter(
            role=User.Role.MEMBER, is_active=True
        ).order_by('first_name', 'username')
        self.fields['member'].label_from_instance = lambda u: f"{u.display_name} (@{u.username})"