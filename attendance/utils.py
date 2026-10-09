import io
from datetime import datetime

import qrcode
from django.core.signing import BadSignature, Signer
from django.utils import timezone

from accounts.models import User

# Codes are signed with the project's secret key, so they cannot be forged.
_signer = Signer(salt='fittrack-member-qr')


def member_code(member):
    """The text stored inside a member's QR code."""
    return _signer.sign(f'FTP{member.pk}')


def member_from_code(code):
    """Returns the member for a scanned code, or None if the code is not valid."""
    try:
        value = _signer.unsign((code or '').strip())
    except BadSignature:
        return None
    if not value.startswith('FTP') or not value[3:].isdigit():
        return None
    return User.objects.filter(pk=int(value[3:]), role=User.Role.MEMBER, is_active=True).first()


def qr_png(text):
    """Draws the QR code as PNG bytes (in the theme's purple)."""
    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(text)
    qr.make(fit=True)
    image = qr.make_image(fill_color='#5B21B6', back_color='white')
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    return buffer.getvalue()


def parse_month(value):
    """'2026-10' -> (2026, 10). Falls back to the current month."""
    try:
        parsed = datetime.strptime(value or '', '%Y-%m')
        return parsed.year, parsed.month
    except ValueError:
        today = timezone.localdate()
        return today.year, today.month


def clock(moment):
    """Formats a datetime as local time, e.g. '09:05 AM'."""
    return timezone.localtime(moment).strftime('%I:%M %p')