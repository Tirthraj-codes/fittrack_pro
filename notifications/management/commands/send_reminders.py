from django.core.management.base import BaseCommand

from notifications.reminders import run_reminders


class Command(BaseCommand):
    help = 'Creates reminders (and emails them) for expiring memberships, due payments and tomorrow\'s sessions.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Show what would be created without saving or emailing anything.')

    def handle(self, *args, **options):
        summary = run_reminders(dry_run=options['dry_run'])

        label = 'Would create' if summary['dry_run'] else 'Created'
        self.stdout.write(self.style.SUCCESS(f"{label} {summary['new']} reminder(s)."))
        for name, count in summary['by_kind'].items():
            self.stdout.write(f'  {name}: {count}')
        if not summary['dry_run']:
            self.stdout.write(
                f"Emails sent: {summary['emails_sent']}, failed: {summary['emails_failed']}, "
                f"not emailed (no address): {summary['not_emailed']}"
            )