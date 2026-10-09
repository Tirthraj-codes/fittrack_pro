from django.contrib.admin.models import LogEntry
from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.core.management.base import BaseCommand

from accounts.models import User

ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'Admin@12345'


class Command(BaseCommand):
    help = 'Gets the project ready to hand over: fresh demo data, a known admin login and no leftover sessions.'

    def handle(self, *args, **options):
        admin = User.objects.filter(username=ADMIN_USERNAME).first()
        if admin is None:
            admin = User(username=ADMIN_USERNAME)
        admin.is_staff = admin.is_superuser = admin.is_active = True
        admin.set_password(ADMIN_PASSWORD)
        admin.save()

        call_command('seed_demo', reset=True, yes=True)

        Session.objects.all().delete()          # nobody stays logged in
        LogEntry.objects.all().delete()         # empty admin-panel history

        self.stdout.write(self.style.SUCCESS('Ready to hand over.'))
        self.stdout.write(f'Admin login: {ADMIN_USERNAME} / {ADMIN_PASSWORD}')
        self.stdout.write('Demo trainers and members use the password: FitDemo@2026')