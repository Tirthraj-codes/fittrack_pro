import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db import IntegrityError

from .models import Notification

logger = logging.getLogger(__name__)


def _send_email(notification):
    """Tries to email the notification. Returns (status, error text). Never raises."""
    if not getattr(settings, 'SEND_REMINDER_EMAILS', True):
        return Notification.EmailStatus.SKIPPED, 'Emails are switched off.'
    user = notification.user
    if not user.email:
        return Notification.EmailStatus.SKIPPED, 'No email address on file.'

    body = f"Hello {user.display_name},\n\n{notification.message}"
    if notification.link:
        body += f"\n\nOpen: {settings.SITE_URL.rstrip('/')}{notification.link}"
    body += "\n\n- FitTrack Pro"

    try:
        send_mail(
            subject=f"FitTrack Pro: {notification.title}",
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
    except Exception as error:               # e.g. the host blocks outgoing email
        logger.warning('Reminder email to %s failed: %s', user.email, error)
        return Notification.EmailStatus.FAILED, str(error)[:200]
    return Notification.EmailStatus.SENT, ''


def notify(user, kind, title, message, key, link='', dry_run=False):
    """Creates one notification (and emails it) unless this user already has one with the same key.
    Returns the notification, or None if it already existed."""
    if Notification.objects.filter(user=user, key=key).exists():
        return None

    fields = dict(user=user, kind=kind, title=title, message=message, link=link, key=key)
    if dry_run:
        return Notification(**fields)        # not saved: only used for counting

    try:
        notification = Notification.objects.create(**fields)
    except IntegrityError:                    # two runs at the same moment
        return None

    status, error = _send_email(notification)
    notification.email_status = status
    notification.email_error = error
    notification.save(update_fields=['email_status', 'email_error'])
    return notification