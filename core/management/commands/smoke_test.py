import logging

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.test import Client, override_settings

from memberships.models import Membership, MembershipPlan
from payments.models import Payment
from progress.models import ProgressEntry
from scheduling.models import Session, TrainerAssignment

User = get_user_model()
PNG, PDF, CSV = 'image/png', 'application/pdf', 'text/csv'


def page(url, statuses=(200,), kind=None):
    return (url, statuses, kind)


class Command(BaseCommand):
    help = 'Opens the important pages as each role and reports any that fail.'

    def open_page(self, client, url, statuses, kind):
        try:
            response = client.get(url)
        except Exception as error:
            return f'{type(error).__name__}: {str(error)[:150]}'
        if response.status_code not in statuses:
            return f'status {response.status_code}, expected {" or ".join(map(str, statuses))}'
        if kind and kind not in response.get('Content-Type', ''):
            return f'wrong file type: {response.get("Content-Type", "")}'
        return None

    def handle(self, *args, **options):
        admin = User.objects.filter(is_superuser=True).first()
        assignment = TrainerAssignment.objects.select_related('trainer', 'member').first()
        if admin is None or assignment is None:
            raise CommandError('Demo data is missing. Run: python manage.py prepare_handover')

        trainer, member = assignment.trainer, assignment.member
        paid = Payment.objects.filter(member=member, status='paid').first()
        pending = Payment.objects.filter(member=member, status='pending').first()
        session = Session.objects.filter(member=member, trainer=trainer).first()
        membership = Membership.objects.filter(member=member).first()
        plan = MembershipPlan.objects.first()
        entry = ProgressEntry.objects.filter(member=member).first()

        visitor = [
            page('/'), page('/accounts/login/'), page('/accounts/register/'), page('/accounts/password/reset/'),
            page('/manifest.webmanifest', kind='manifest+json'), page('/service-worker.js', kind='javascript'),
            page('/offline/'), page('/no-such-page/', (404,)),
            page('/dashboard/', (302,)), page('/payments/mine/', (302,)), page('/reports/', (302,)),
        ]

        admin_pages = [
            page('/dashboard/admin/'), page('/accounts/profile/'), page('/accounts/manage/users/'),
            page('/accounts/manage/users/add/'), page('/memberships/'), page('/memberships/?status=expiring'),
            page('/memberships/plans/'), page('/memberships/plans/add/'), page('/memberships/assign/'),
            page('/attendance/'), page('/attendance/history/'), page('/attendance/report/'),
            page('/payments/'), page('/payments/?status=overdue'), page('/payments/add/'),
            page('/scheduling/'), page('/scheduling/sessions/add/'), page('/scheduling/availability/'),
            page('/scheduling/assignments/'), page('/progress/'),
            page(f'/progress/member/{member.pk}/'), page(f'/progress/member/{member.pk}/plan/'),
            page(f'/attendance/qr/{member.pk}/', kind=PNG),
            page('/reports/'), page('/reports/export/summary.pdf', kind=PDF),
            page('/reports/export/payments.csv', kind=CSV), page('/reports/export/dues.csv', kind=CSV),
            page('/reports/export/memberships.csv', kind=CSV), page('/reports/export/attendance.csv', kind=CSV),
            page('/notifications/'), page('/notifications/log/'),
            page('/dashboard/member/', (403,)), page('/payments/mine/', (403,)),
        ]
        if plan:
            admin_pages.append(page(f'/memberships/plans/{plan.pk}/edit/'))
        if membership:
            admin_pages += [page(f'/memberships/{membership.pk}/renew/', (200, 302)),
                            page(f'/memberships/{membership.pk}/upgrade/', (200, 302))]
        if paid:
            admin_pages += [page(f'/payments/{paid.pk}/receipt/', kind=PDF), page(f'/payments/{paid.pk}/success/')]
        if session:
            admin_pages += [page(f'/scheduling/sessions/{session.pk}/'),
                            page(f'/scheduling/sessions/{session.pk}/edit/', (200, 302))]
        if entry:
            admin_pages.append(page(f'/progress/entries/{entry.pk}/edit/'))

        trainer_pages = [
            page('/dashboard/trainer/'), page('/accounts/profile/'), page('/attendance/'),
            page('/attendance/history/'), page('/scheduling/'), page('/scheduling/sessions/add/'),
            page('/scheduling/availability/'), page('/scheduling/my-members/'), page('/progress/'),
            page(f'/progress/member/{member.pk}/'), page(f'/progress/member/{member.pk}/plan/'),
            page(f'/attendance/qr/{member.pk}/', kind=PNG),
            page('/reports/', (403,)), page('/payments/', (403,)), page('/memberships/', (403,)),
            page('/accounts/manage/users/', (403,)), page('/attendance/report/', (403,)),
            page('/scheduling/assignments/', (403,)),
        ]
        if session:
            trainer_pages.append(page(f'/scheduling/sessions/{session.pk}/'))

        member_pages = [
            page('/dashboard/member/'), page('/accounts/profile/'), page('/accounts/password/change/'),
            page('/memberships/mine/'), page('/attendance/mine/'), page(f'/attendance/qr/{member.pk}/', kind=PNG),
            page('/payments/mine/'), page('/scheduling/'), page('/progress/mine/'), page('/progress/plan/'),
            page('/progress/add/'), page('/progress/goal/', (200, 302)),
            page('/accounts/manage/users/', (403,)), page('/reports/', (403,)), page('/attendance/', (403,)),
            page('/payments/', (403,)), page('/memberships/', (403,)), page('/progress/', (403,)),
            page('/scheduling/assignments/', (403,)), page('/dashboard/admin/', (403,)),
        ]
        if pending:
            member_pages.append(page(f'/payments/{pending.pk}/pay/'))
        if paid:
            member_pages += [page(f'/payments/{paid.pk}/receipt/', kind=PDF), page(f'/payments/{paid.pk}/success/')]
        if session:
            member_pages.append(page(f'/scheduling/sessions/{session.pk}/'))
        if entry:
            member_pages.append(page(f'/progress/entries/{entry.pk}/edit/'))

        groups = [('visitor', None, visitor), ('admin', admin, admin_pages),
                  ('trainer', trainer, trainer_pages), ('member', member, member_pages)]
        total = failed = 0

        logging.disable(logging.CRITICAL)             # hide the expected 403/404 log noise
        try:
            with override_settings(SESSION_ENGINE='django.contrib.sessions.backends.signed_cookies',
                                   ALLOWED_HOSTS=['*']):
                for label, user, pages in groups:
                    client = Client(HTTP_HOST='127.0.0.1')
                    if user is not None:
                        client.force_login(user)
                    problems = []
                    for url, statuses, kind in pages:
                        total += 1
                        error = self.open_page(client, url, statuses, kind)
                        if error:
                            failed += 1
                            problems.append(f'  FAIL  {url}   ({error})')
                    good = len(pages) - len(problems)
                    line = f'{label}: {good} of {len(pages)} OK'
                    self.stdout.write(self.style.SUCCESS(line) if not problems else self.style.ERROR(line))
                    for problem in problems:
                        self.stdout.write(self.style.ERROR(problem))
        finally:
            logging.disable(logging.NOTSET)

        if failed:
            raise CommandError(f'{failed} of {total} checks failed. Copy the lines above and send them to me.')
        self.stdout.write(self.style.SUCCESS(f'All {total} checks passed.'))