from django.core.management.base import BaseCommand

from memberships.models import Membership
from payments.services import create_pending_payment


class Command(BaseCommand):
    help = 'Creates a pending payment for every open membership that has no payment yet.'

    def handle(self, *args, **options):
        created = 0
        memberships = Membership.objects.filter(closed_reason='', payments__isnull=True).select_related('member', 'plan')
        for membership in memberships:
            create_pending_payment(membership)
            created += 1
        self.stdout.write(self.style.SUCCESS(f'Created {created} pending payment(s).'))