import re
from datetime import timedelta

from django import forms
from django.utils import timezone

from accounts.models import User
from core.forms import BootstrapFormMixin

from .models import Payment

DECLINED_TEST_CARD = '4000000000000002'     # demo card that is always declined

BANKS = [
    ('', 'Choose your bank'),
    ('sbi', 'State Bank of India'),
    ('hdfc', 'HDFC Bank'),
    ('icici', 'ICICI Bank'),
    ('axis', 'Axis Bank'),
    ('kotak', 'Kotak Mahindra Bank'),
    ('pnb', 'Punjab National Bank'),
]


class CheckoutForm(BootstrapFormMixin, forms.Form):
    """Fake payment form. It only checks the format of the details, no real payment happens."""

    method = forms.ChoiceField(
        choices=[('card', 'Card'), ('upi', 'UPI'), ('netbanking', 'Net Banking')],
        initial='card',
    )
    card_number = forms.CharField(label='Card number', required=False, max_length=23)
    card_name = forms.CharField(label='Name on card', required=False, max_length=60)
    expiry = forms.CharField(label='Expiry (MM/YY)', required=False, max_length=5)
    cvv = forms.CharField(label='CVV', required=False, max_length=4,
                          widget=forms.PasswordInput(render_value=False))
    upi_id = forms.CharField(label='UPI ID', required=False, max_length=60)
    bank = forms.ChoiceField(label='Bank', choices=BANKS, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['card_number'].widget.attrs['placeholder'] = '4242 4242 4242 4242'
        self.fields['card_name'].widget.attrs['placeholder'] = 'Name on card'
        self.fields['expiry'].widget.attrs['placeholder'] = 'MM/YY'
        self.fields['cvv'].widget.attrs['placeholder'] = '123'
        self.fields['upi_id'].widget.attrs['placeholder'] = 'yourname@bank'

    def clean(self):
        cleaned = super().clean()
        method = cleaned.get('method')

        if method == 'card':
            number = re.sub(r'[\s-]', '', cleaned.get('card_number', ''))
            if not (number.isdigit() and 12 <= len(number) <= 19):
                self.add_error('card_number', 'Enter a valid card number (12 to 19 digits).')
            elif number == DECLINED_TEST_CARD:
                self.add_error(None, 'The bank declined this card (demo test card). Please try another card.')
            if not cleaned.get('card_name', '').strip():
                self.add_error('card_name', 'Enter the name on the card.')
            self._check_expiry(cleaned.get('expiry', ''))
            if not re.fullmatch(r'\d{3,4}', cleaned.get('cvv', '')):
                self.add_error('cvv', 'Enter the 3 or 4 digit CVV.')

        elif method == 'upi':
            if not re.fullmatch(r'[\w.\-]{2,}@[A-Za-z]{2,}', cleaned.get('upi_id', '').strip()):
                self.add_error('upi_id', 'Enter a valid UPI ID, like name@bank.')

        elif method == 'netbanking':
            if not cleaned.get('bank'):
                self.add_error('bank', 'Choose your bank.')

        return cleaned

    def _check_expiry(self, value):
        match = re.fullmatch(r'(0[1-9]|1[0-2])/(\d{2})', value)
        if not match:
            self.add_error('expiry', 'Use the format MM/YY.')
            return
        month, year = int(match.group(1)), 2000 + int(match.group(2))
        today = timezone.localdate()
        if (year, month) < (today.year, today.month):
            self.add_error('expiry', 'This card has expired.')


class MarkPaidForm(BootstrapFormMixin, forms.Form):
    method = forms.ChoiceField(choices=Payment.Method.choices, label='Payment received by')
    note = forms.CharField(label='Note (optional)', required=False, max_length=200)


class ManualPaymentForm(BootstrapFormMixin, forms.Form):
    """Admin adds an extra charge for a member (locker fee, personal training, etc.)."""

    member = forms.ModelChoiceField(queryset=User.objects.none(), empty_label='Choose a member')
    description = forms.CharField(max_length=120, help_text='For example: Locker fee, Personal training session')
    amount = forms.DecimalField(max_digits=8, decimal_places=2, min_value=1, label='Amount (₹)')
    due_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'))
    already_paid = forms.BooleanField(required=False, label='Already paid')
    method = forms.ChoiceField(
        choices=[('', 'Choose a method')] + Payment.Method.choices,
        required=False, label='Payment method (only if already paid)',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['member'].queryset = User.objects.filter(
            role=User.Role.MEMBER, is_active=True
        ).order_by('first_name', 'username')
        self.fields['member'].label_from_instance = lambda u: f"{u.display_name} (@{u.username})"
        self.fields['due_date'].initial = timezone.localdate() + timedelta(days=7)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('already_paid') and not cleaned.get('method'):
            self.add_error('method', 'Choose how it was paid.')
        return cleaned