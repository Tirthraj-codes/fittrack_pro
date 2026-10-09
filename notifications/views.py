import hmac

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from accounts.decorators import admin_required

from .models import Notification
from .reminders import run_reminders


@login_required
def notification_list(request):
    notifications = list(request.user.notifications.all()[:50])
    unread_ids = {n.pk for n in notifications if not n.is_read}
    request.user.notifications.filter(is_read=False).update(is_read=True)    # opening the page marks them read
    return render(request, 'notifications/list.html',
                  {'notifications': notifications, 'unread_ids': unread_ids})


@admin_required
def reminder_log(request):
    kind = request.GET.get('kind', '')
    email = request.GET.get('email', '')

    items = Notification.objects.select_related('user')
    if kind in Notification.Kind.values:
        items = items.filter(kind=kind)
    if email in Notification.EmailStatus.values:
        items = items.filter(email_status=email)

    context = {
        'items': items[:200],
        'kinds': Notification.Kind.choices,
        'email_statuses': Notification.EmailStatus.choices,
        'kind': kind, 'email': email,
        'total': Notification.objects.count(),
        'token_enabled': bool(getattr(settings, 'REMINDER_TOKEN', '')),
    }
    return render(request, 'notifications/log.html', context)


@admin_required
@require_POST
def run_now(request):
    dry_run = request.POST.get('mode') == 'preview'
    summary = run_reminders(dry_run=dry_run)
    details = ', '.join(f'{count} {name.lower()}' for name, count in summary['by_kind'].items()) or 'nothing new'

    if dry_run:
        messages.info(request, f"Preview: {summary['new']} reminder(s) would be created ({details}). Nothing was saved or sent.")
    else:
        messages.success(
            request,
            f"Reminders run: {summary['new']} new ({details}). Emails sent: {summary['emails_sent']}, "
            f"failed: {summary['emails_failed']}, not emailed: {summary['not_emailed']}."
        )
    return redirect('reminder_log')


@csrf_exempt
def run_by_token(request, token):
    """Lets a free external timer trigger the reminders once a day. Disabled unless REMINDER_TOKEN is set."""
    expected = getattr(settings, 'REMINDER_TOKEN', '')
    if not expected or not hmac.compare_digest(token.encode(), expected.encode()):
        raise Http404
    return JsonResponse(run_reminders())