import random
from datetime import datetime, time, timedelta, date
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.test import override_settings
from django.utils import timezone

from accounts.models import User
from attendance.models import Attendance
from memberships.models import Membership, MembershipPlan
from notifications.models import Notification
from notifications.reminders import run_reminders
from payments.models import Payment
from progress.models import FitnessGoal, ProgressEntry
from scheduling.models import Session, TrainerAssignment, TrainerAvailability
from scheduling.services import has_membership_on, member_clash, trainer_clash, within_availability

PASSWORD = 'FitDemo@2026'            # the password of every demo trainer and member

PLANS = [
    ('Basic', 30, 999, ['Gym floor access', 'Locker room', 'Free Wi-Fi']),
    ('Standard', 90, 2499, ['Gym floor access', 'Group classes', 'Locker room', 'One fitness assessment']),
    ('Premium', 365, 7999, ['Everything in Standard', 'Personal trainer sessions', 'Diet consultation', 'Steam room']),
]

TRAINERS = [('Arjun', 'Mehta', 'M'), ('Priya', 'Patel', 'F'), ('Rohan', 'Shah', 'M')]

# first name, last name, gender, height (cm), starting weight (kg)
MEMBERS = [
    ('Aarav', 'Sharma', 'M', 176, 86), ('Diya', 'Nair', 'F', 162, 68), ('Vivaan', 'Joshi', 'M', 172, 94),
    ('Ananya', 'Iyer', 'F', 158, 52), ('Kabir', 'Singh', 'M', 180, 72), ('Isha', 'Desai', 'F', 165, 78),
    ('Reyansh', 'Gupta', 'M', 170, 61), ('Meera', 'Kapoor', 'F', 160, 59), ('Arnav', 'Reddy', 'M', 178, 88),
    ('Saanvi', 'Pillai', 'F', 167, 70), ('Dev', 'Malhotra', 'M', 174, 80), ('Tara', 'Bose', 'F', 163, 64),
    ('Yash', 'Trivedi', 'M', 169, 74), ('Navya', 'Rao', 'F', 156, 49), ('Karan', 'Chauhan', 'M', 182, 97),
    ('Riya', 'Menon', 'F', 164, 66), ('Aditya', 'Verma', 'M', 173, 69), ('Pooja', 'Bhatt', 'F', 161, 73),
]

# What each member's latest membership looks like today (every other member is simply "active")
SCENARIOS = {
    3: 'upgraded', 5: 'cancelled', 7: 'lapsed', 8: 'lapsed',
    9: 'expiring', 10: 'expiring', 11: 'overdue', 12: 'due_soon',
}

LOG_NOTES = [
    'Squats 4 x 8 and leg press. Good depth, add weight next week.',
    'Upper body day: bench press and rows. Form is improving.',
    'Cardio intervals plus core. Heart rate recovered well.',
    'Deadlift technique review. Keep the back neutral.',
    'Full-body circuit. Energy was high, increased reps.',
    'Mobility and light weights. Focus on recovery this week.',
]


def dec(value):
    return Decimal(f'{value:.1f}')


class Command(BaseCommand):
    help = 'Fills the database with realistic demo data (trainers, members, memberships, payments, attendance, sessions, progress).'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true',
                            help='Delete every member, trainer and their data first (admin accounts are kept).')
        parser.add_argument('--yes', action='store_true', help='Do not ask for confirmation.')

    def handle(self, *args, **options):
        admin = User.objects.filter(is_superuser=True).first() or User.objects.filter(role=User.Role.ADMIN).first()
        if admin is None:
            raise CommandError('Create an admin first: python manage.py createsuperuser')

        has_data = (User.objects.filter(role__in=[User.Role.MEMBER, User.Role.TRAINER]).exists()
                    or MembershipPlan.objects.exists())
        if has_data and not options['reset']:
            raise CommandError('The database already has data. Run with --reset to wipe it first (admins are kept).')

        if options['reset'] and not options['yes']:
            answer = input('This deletes ALL members, trainers, plans, memberships, payments, attendance, sessions '
                           'and progress. Type YES to continue: ')
            if answer.strip() != 'YES':
                self.stdout.write('Cancelled. Nothing was changed.')
                return

        with transaction.atomic():
            if options['reset']:
                self.wipe()
            self.seed(admin)

        with override_settings(SEND_REMINDER_EMAILS=False):          # do not print dozens of emails
            reminders = run_reminders()

        self.stdout.write(self.style.SUCCESS('Demo data created.'))
        for label, count in [
            ('Trainers', User.objects.filter(role=User.Role.TRAINER).count()),
            ('Members', User.objects.filter(role=User.Role.MEMBER).count()),
            ('Memberships', Membership.objects.count()),
            ('Payments', Payment.objects.count()),
            ('Attendance records', Attendance.objects.count()),
            ('Sessions', Session.objects.count()),
            ('Progress entries', ProgressEntry.objects.count()),
            ('Reminders', reminders['new']),
        ]:
            self.stdout.write(f'  {label}: {count}')
        self.stdout.write(f'Every demo trainer and member logs in with the password: {PASSWORD}')

    # ------------------------------------------------------------------
    def wipe(self):
        Notification.objects.all().delete()
        ProgressEntry.objects.all().delete()
        FitnessGoal.objects.all().delete()
        Session.objects.all().delete()
        TrainerAvailability.objects.all().delete()
        TrainerAssignment.objects.all().delete()
        Attendance.objects.all().delete()
        Payment.objects.all().delete()
        Membership.objects.all().delete()
        MembershipPlan.objects.all().delete()
        User.objects.filter(role__in=[User.Role.MEMBER, User.Role.TRAINER]).delete()

    # ------------------------------------------------------------------
    def periods_for(self, scenario, plans, today, rng):
        """The memberships a member has had, oldest first, shaped so today's status is the one we want."""
        basic, standard, premium = plans['Basic'], plans['Standard'], plans['Premium']

        def chain(plan, last_end, max_periods):
            periods, end = [], last_end
            for _ in range(max_periods):
                start = end - timedelta(days=plan.duration_days)
                periods.append({'plan': plan, 'start': start, 'end': end})
                end = start - timedelta(days=1)
                if start < today - timedelta(days=170):
                    break
            periods.reverse()
            return periods

        if scenario == 'upgraded':
            upgrade_day = today - timedelta(days=10)
            basic_start = upgrade_day - timedelta(days=22)
            periods = chain(basic, basic_start - timedelta(days=1), 2)
            periods.append({'plan': basic, 'start': basic_start, 'end': basic_start + timedelta(days=30),
                            'closed_reason': 'upgraded', 'closed_on': upgrade_day})
            periods.append({'plan': standard, 'start': upgrade_day, 'end': upgrade_day + timedelta(days=90),
                            'kind': 'upgrade'})
        elif scenario == 'cancelled':
            start = today - timedelta(days=35)
            periods = [{'plan': standard, 'start': start, 'end': start + timedelta(days=90),
                        'closed_reason': 'cancelled', 'closed_on': today - timedelta(days=20)}]
        elif scenario == 'lapsed':
            periods = chain(basic, today - timedelta(days=rng.randint(3, 18)), 3)
        elif scenario == 'expiring':
            plan = rng.choice([basic, standard])
            periods = chain(plan, today + timedelta(days=rng.randint(1, 6)), 3 if plan is basic else 2)
        elif scenario in ('overdue', 'due_soon'):
            start = today - timedelta(days=12 if scenario == 'overdue' else 2)
            periods = chain(basic, start - timedelta(days=1), 2)
            periods.append({'plan': basic, 'start': start, 'end': start + timedelta(days=30), 'payment': 'pending'})
        else:                                                         # active
            plan = rng.choices([basic, standard, premium], weights=[45, 40, 15])[0]
            if plan is premium:
                periods = chain(premium, today + timedelta(days=rng.randint(120, 300)), 1)
            elif plan is standard:
                periods = chain(standard, today + timedelta(days=rng.randint(10, 85)), 2)
            else:
                periods = chain(basic, today + timedelta(days=rng.randint(3, 28)), 4)

        for number, period in enumerate(periods):
            period.setdefault('kind', 'new' if number == 0 else 'renewal')
            period.setdefault('closed_reason', '')
            period.setdefault('closed_on', None)
            period.setdefault('payment', 'paid')
        return periods

    def pay(self, payment, paid_at, rng, admin):
        method = rng.choices(['card', 'upi', 'netbanking', 'cash'], weights=[3, 5, 2, 2])[0]
        local = timezone.localtime(paid_at)
        payment.status = 'paid'
        payment.method = method
        payment.paid_on = paid_at
        payment.transaction_id = f"{'CSH' if method == 'cash' else 'TXN'}{local:%Y%m%d%H%M%S}{rng.randint(100, 999)}"
        payment.receipt_no = f'FT-{local:%Y%m}-{payment.pk:05d}'
        payment.recorded_by = admin if method == 'cash' else None
        payment.save()

    # ------------------------------------------------------------------
    def seed(self, admin):
        rng = random.Random(2026)                     # same data every time
        today = timezone.localdate()
        now = timezone.now()

        def at(day, hour=10, minute=0):
            return timezone.make_aware(datetime.combine(day, time(hour, minute)))

        # ----- plans -----
        plans = {}
        for name, days, price, features in PLANS:
            plans[name] = MembershipPlan.objects.create(
                name=name, duration_days=days, price=price, features='\n'.join(features))

        # ----- trainers and their weekly hours (Mon-Sat, morning and evening) -----
        trainers, hours = [], []
        for first, last, gender in TRAINERS:
            username = f'{first}.{last}'.lower()
            trainer = User.objects.create_user(
                username=username, email=f'{username}@example.com', password=PASSWORD,
                first_name=first, last_name=last, role=User.Role.TRAINER, gender=gender,
                phone=f'9{rng.randint(100000000, 999999999)}')
            trainers.append(trainer)
            for weekday in range(6):
                hours.append(TrainerAvailability(trainer=trainer, weekday=weekday, start_time=time(6), end_time=time(10)))
                hours.append(TrainerAvailability(trainer=trainer, weekday=weekday, start_time=time(17), end_time=time(21)))
        TrainerAvailability.objects.bulk_create(hours)

        # ----- members, memberships and payments -----
        members, join_days, all_memberships = [], {}, []
        for index, (first, last, gender, height, weight) in enumerate(MEMBERS):
            periods = self.periods_for(SCENARIOS.get(index, 'active'), plans, today, rng)
            join_day = periods[0]['start'] - timedelta(days=rng.randint(0, 2))
            username = f'{first}.{last}'.lower()
            member = User.objects.create_user(
                username=username, email=f'{username}@example.com', password=PASSWORD,
                first_name=first, last_name=last, role=User.Role.MEMBER, gender=gender,
                phone=f'9{rng.randint(100000000, 999999999)}',
                date_of_birth=date(rng.randint(1980, 2005), rng.randint(1, 12), rng.randint(1, 28)))
            User.objects.filter(pk=member.pk).update(date_joined=at(join_day, 11))
            members.append(member)
            join_days[member.pk] = join_day

            for period in periods:
                plan = period['plan']
                sold_on = max(period['start'] - timedelta(days=rng.randint(0, 2)), join_day)
                membership = Membership.objects.create(
                    member=member, plan=plan, start_date=period['start'], end_date=period['end'],
                    amount=plan.price, kind=period['kind'],
                    closed_reason=period['closed_reason'], closed_on=period['closed_on'])
                Membership.objects.filter(pk=membership.pk).update(created_at=at(sold_on, 10, 30))
                all_memberships.append(membership)

                payment = Payment.objects.create(
                    member=member, membership=membership,
                    description=f'{plan.name} plan ({plan.duration_label})',
                    amount=plan.price, due_date=period['start'] + timedelta(days=3))
                if period['payment'] == 'paid':
                    paid_day = min(period['start'] + timedelta(days=rng.randint(0, 2)), today)
                    self.pay(payment, min(at(paid_day, rng.randint(9, 19), rng.randint(0, 59)), now), rng, admin)
                Payment.objects.filter(pk=payment.pk).update(created_at=at(sold_on, 10, 30))

        # ----- a few extra charges (locker fee etc.) -----
        extras = [('Locker fee (monthly)', 300), ('Personal training session', 500), ('Protein shake bundle', 650)]
        for member in rng.sample(members, 8):
            description, amount = rng.choice(extras)
            day = max(today - timedelta(days=rng.randint(2, 100)), join_days[member.pk])
            extra = Payment.objects.create(member=member, description=description, amount=amount, due_date=day)
            self.pay(extra, min(at(day, rng.randint(9, 19), rng.randint(0, 59)), now), rng, admin)
            Payment.objects.filter(pk=extra.pk).update(created_at=at(day, 10))

        # ----- trainer assignments and training sessions -----
        assigned = {}
        for index, member in enumerate(members):
            trainer = trainers[index % len(trainers)]
            TrainerAssignment.objects.create(member=member, trainer=trainer, assigned_on=join_days[member.pk])
            assigned[member.pk] = trainer

        for member in members:
            trainer = assigned[member.pk]
            for _ in range(rng.randint(5, 9)):
                day = today + timedelta(days=rng.randint(-56, 14))
                if day.weekday() == 6 or day < join_days[member.pk]:
                    continue
                hour = rng.choice([6, 7, 8, 9, 17, 18, 19, 20])
                start, end = time(hour), time(hour + 1)
                if not (has_membership_on(member, day) and within_availability(trainer, day, start, end)):
                    continue
                if trainer_clash(trainer, day, start, end) or member_clash(member, day, start, end):
                    continue
                if day < today:
                    status = rng.choices(['completed', 'no_show', 'cancelled'], weights=[8, 1, 1])[0]
                else:
                    status = 'scheduled'
                Session.objects.create(
                    trainer=trainer, member=member, date=day, start_time=start, end_time=end, status=status,
                    kind=rng.choices(['personal_training', 'assessment', 'diet', 'other'], weights=[6, 2, 1, 1])[0],
                    notes=rng.choice(LOG_NOTES) if status == 'completed' else '', created_by=trainer)

        # ----- attendance over the last 120 days -----
        records, seen, coaches = [], set(), trainers + [admin]
        for member in members:
            frequency = rng.choice([0.25, 0.4, 0.55, 0.7])
            for membership in [m for m in all_memberships if m.member_id == member.pk]:
                last_day = min(membership.end_date, today)
                if membership.closed_on:
                    last_day = min(last_day, membership.closed_on - timedelta(days=1))
                day = max(membership.start_date, today - timedelta(days=120))
                while day <= last_day:
                    factor = 0.25 if day.weekday() == 6 else 1.0
                    if day != today and (member.pk, day) not in seen and rng.random() < frequency * factor:
                        seen.add((member.pk, day))
                        hour = rng.randint(6, 9) if rng.random() < 0.55 else rng.randint(17, 20)
                        check_in = at(day, hour, rng.randint(0, 59))
                        records.append(Attendance(
                            member=member, date=day, check_in=check_in,
                            check_out=check_in + timedelta(minutes=rng.randint(40, 110)),
                            method=rng.choices(['qr', 'manual'], weights=[6, 4])[0],
                            recorded_by=rng.choice(coaches)))
                    day += timedelta(days=1)
        Attendance.objects.bulk_create(records)

        # a few people in the gym right now
        running_now = list(Membership.objects.running().select_related('member'))
        rng.shuffle(running_now)
        for number, membership in enumerate(running_now[:7]):
            check_in = now - timedelta(minutes=rng.randint(35, 150))
            if timezone.localdate(check_in) != today:
                continue
            check_out = None if number < 2 else check_in + timedelta(minutes=rng.randint(40, 70))
            if check_out and check_out > now:
                check_out = None
            Attendance.objects.create(
                member=membership.member, date=today, check_in=check_in, check_out=check_out,
                method='qr', recorded_by=rng.choice(coaches))

        # ----- progress entries and goals -----
        rows = []
        for member, (first, last, gender, height, start_weight) in zip(members, MEMBERS):
            male = gender == 'M'
            bmi = start_weight / (height / 100) ** 2
            if bmi >= 25:
                goal_type, per_day = 'weight_loss', -0.05
            elif bmi < 20:
                goal_type, per_day = 'muscle_gain', 0.03
            else:
                goal_type, per_day = 'maintenance', 0.0

            join_day = join_days[member.pk]
            dates, day = [], today - timedelta(days=rng.randint(0, 5))
            while day >= join_day:
                dates.append(day)
                day -= timedelta(days=rng.randint(11, 17))
            if join_day not in dates and len(dates) < 2:
                dates.append(join_day)
            dates.sort()

            measured = rng.random() < 0.75
            offset = start_weight - (72 if male else 58)
            first_weight = None
            for day in dates:
                weight = round(start_weight + per_day * (day - dates[0]).days + rng.uniform(-0.4, 0.4), 1)
                if first_weight is None:
                    first_weight = weight
                change = weight - start_weight
                entry = ProgressEntry(member=member, date=day, weight_kg=dec(weight),
                                      height_cm=dec(height), recorded_by=member)
                if measured:
                    entry.body_fat_percent = dec((18 if male else 26) + offset * 0.15 + change * 0.4)
                    entry.chest_cm = dec((98 if male else 88) + offset * 0.35 + change * 0.4)
                    entry.waist_cm = dec((80 if male else 70) + offset * 0.6 + change * 0.9)
                    entry.hips_cm = dec((98 if male else 96) + offset * 0.4 + change * 0.5)
                    entry.arms_cm = dec((32 if male else 27) + offset * 0.12 + change * 0.2)
                    entry.thighs_cm = dec((56 if male else 55) + offset * 0.3 + change * 0.4)
                rows.append(entry)

            if rng.random() < 0.8:
                target = None
                if goal_type == 'weight_loss':
                    target = dec(first_weight - 6)
                elif goal_type == 'muscle_gain':
                    target = dec(first_weight + 4)
                goal = FitnessGoal.objects.create(
                    member=member, goal_type=goal_type, start_weight_kg=dec(first_weight), target_weight_kg=target,
                    target_date=today + timedelta(days=rng.randint(45, 120)), created_by=member)
                FitnessGoal.objects.filter(pk=goal.pk).update(created_at=at(dates[0], 12))
        ProgressEntry.objects.bulk_create(rows)

        # earlier, replaced goals for the first three members
        for member, (_, _, _, _, start_weight) in list(zip(members, MEMBERS))[:3]:
            old = FitnessGoal.objects.create(
                member=member, goal_type='maintenance', start_weight_kg=dec(start_weight), is_active=False)
            FitnessGoal.objects.filter(pk=old.pk).update(created_at=at(join_days[member.pk], 12))