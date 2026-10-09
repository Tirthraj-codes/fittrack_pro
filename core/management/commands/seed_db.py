from .seed_demo import Command as SeedDemoCommand


class Command(SeedDemoCommand):
    help = 'Same as seed_demo: fills the database with demo data.'