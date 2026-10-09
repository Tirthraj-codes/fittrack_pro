from datetime import timedelta

from django.utils import timezone

from attendance.models import Attendance

from .utils import goal_progress

WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

GOAL_LABELS = {'weight_loss': 'Weight loss', 'muscle_gain': 'Muscle gain', 'maintenance': 'Maintenance'}
LEVEL_LABELS = {'low': 'Getting started', 'moderate': 'Regular', 'high': 'Very consistent'}

DISCLAIMER = (
    'These suggestions are general fitness guidance based on your goal, measurements and attendance. '
    'They are not medical advice. If you have a medical condition, are pregnant or feel unwell, '
    'please check with a doctor or a qualified dietitian before changing your training or diet.'
)

# ---------------------------------------------------------------------------
# Workout templates: five training days per goal. Attendance decides how many are used.
# ---------------------------------------------------------------------------
WORKOUTS = {
    'weight_loss': [
        ('Full-body strength A', ['Goblet squat 3 x 10', 'Dumbbell bench press 3 x 10', 'Seated cable row 3 x 12', 'Plank 3 x 30 sec']),
        ('Interval cardio', ['5 min easy warm-up', '8 rounds: 1 min fast, 1 min easy', '5 min cool-down']),
        ('Full-body strength B', ['Romanian deadlift 3 x 10', 'Overhead press 3 x 10', 'Lat pulldown 3 x 12', 'Walking lunges 3 x 10 each leg']),
        ('Steady cardio + core', ['35-40 min steady cardio (cycle, treadmill or cross-trainer)', 'Core circuit 3 rounds: dead bug, side plank, bicycle crunch']),
        ('Full-body strength C + mobility', ['Leg press 3 x 12', 'Push-ups 3 x as many as you can', 'Cable row 3 x 12', '10 min hip and shoulder mobility']),
    ],
    'muscle_gain': [
        ('Push: chest, shoulders, triceps', ['Bench press 4 x 8', 'Overhead press 3 x 10', 'Incline dumbbell press 3 x 10', 'Triceps pushdown 3 x 12']),
        ('Pull: back and biceps', ['Deadlift 3 x 6', 'Lat pulldown 4 x 10', 'Seated row 3 x 10', 'Biceps curl 3 x 12']),
        ('Legs', ['Squat 4 x 8', 'Leg press 3 x 12', 'Romanian deadlift 3 x 10', 'Calf raise 4 x 15']),
        ('Upper body', ['Pull-ups or assisted pull-ups 3 x 8', 'Dumbbell press 3 x 10', 'Lateral raise 3 x 15', 'Face pull 3 x 15']),
        ('Lower body + core', ['Walking lunges 3 x 10 each leg', 'Hip thrust 3 x 10', 'Leg curl 3 x 12', 'Plank 3 x 45 sec']),
    ],
    'maintenance': [
        ('Full-body strength A', ['Squat 3 x 8', 'Bench press 3 x 8', 'Seated row 3 x 10', 'Plank 3 x 30 sec']),
        ('Moderate cardio', ['30 min run, cycle or swim at a comfortable pace']),
        ('Full-body strength B', ['Deadlift 3 x 6', 'Overhead press 3 x 8', 'Lat pulldown 3 x 10', 'Core circuit 2 rounds']),
        ('Active recovery', ['30-45 min walk', 'Stretching or yoga 15 min']),
        ('Fun session', ['Group class or a sport you enjoy, 45 min']),
    ],
}

SLOTS = {3: (0, 2, 4), 4: (0, 1, 3, 4), 5: (0, 1, 2, 4, 5)}      # which weekdays are training days
DAYS_BY_LEVEL = {
    'weight_loss': {'low': 3, 'moderate': 4, 'high': 5},
    'muscle_gain': {'low': 3, 'moderate': 4, 'high': 5},
    'maintenance': {'low': 3, 'moderate': 4, 'high': 4},
}

WORKOUT_TIPS = [
    'Warm up for 5-10 minutes before lifting, and stretch afterwards.',
    'Add a little weight or one extra rep when a set feels easy (progressive overload).',
    'Ask your trainer to check your form on the big lifts.',
    'Sleep 7-9 hours. Muscle and fat loss both depend on recovery.',
    'Rest days are part of the plan. Do not skip them.',
]

# ---------------------------------------------------------------------------
# Nutrition content
# ---------------------------------------------------------------------------
PROTEIN_PER_KG = {'weight_loss': (1.6, 2.2), 'muscle_gain': (1.6, 2.2), 'maintenance': (1.2, 1.6)}

PRINCIPLES = {
    'weight_loss': [
        'Aim for a small, steady calorie deficit. Crash diets cost muscle and are hard to keep up.',
        'Build every meal around protein and vegetables so you stay full.',
        'Keep carbohydrates, but use slightly smaller portions of rice and roti.',
        'Limit fried snacks, sweets and sugary drinks.',
    ],
    'muscle_gain': [
        'Eat a small calorie surplus. Bigger surpluses mostly add fat.',
        'Spread protein across 3-4 meals, including one within a few hours after training.',
        'Do not skip carbohydrates. They fuel hard sessions.',
        'Add healthy calories: nuts, milk, curd, peanut butter and olive or groundnut oil.',
    ],
    'maintenance': [
        'Eat around your maintenance calories and keep your weight within about 2 kg.',
        'Keep a balanced plate: protein, vegetables, whole grains and some healthy fats.',
        'Enjoy treats in moderation. Consistency matters more than perfection.',
    ],
}

PORTION_NOTES = {
    'weight_loss': 'Keep rice and roti portions on the smaller side and fill half the plate with vegetables.',
    'muscle_gain': 'Add an extra roti or a bigger portion of rice, a handful of nuts, and a milk or protein shake after training.',
    'maintenance': 'Keep portions moderate and balanced.',
}

SAMPLE_DAY = [
    ('Breakfast',
     'Moong dal chilla (2) with curd and a fruit',
     '3-egg omelette with 2 multigrain toast and a fruit'),
    ('Mid-morning',
     'Curd or buttermilk with a handful of nuts',
     'Curd or buttermilk with a handful of nuts'),
    ('Lunch',
     '2 rotis, dal, mixed sabzi, salad and 100 g paneer',
     '2 rotis, dal, sabzi, salad and 120 g grilled chicken'),
    ('Evening / pre-workout',
     'Banana with peanut butter, or sprouts chaat',
     'Banana with peanut butter, or boiled eggs (2)'),
    ('Dinner',
     'Khichdi or brown rice with vegetables and tofu, paneer or soya chunks',
     'Rice or roti with egg or fish curry and vegetables'),
]


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def attendance_level(visits):
    """Visits in the last 30 days -> low / moderate / high."""
    if visits < 4:
        return 'low'
    if visits < 12:
        return 'moderate'
    return 'high'


def age_from(birth_date, today):
    if birth_date is None:
        return None
    years = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
    return years if 5 <= years <= 100 else None


def weekly_rate(entries, today):
    """Weight change in kg per week over roughly the last 4 weeks (negative = losing).
    Returns (rate, days_covered), or (None, None) when there is not enough data."""
    if len(entries) < 2:
        return None, None
    latest = entries[-1]
    recent = [e for e in entries if (today - e.date).days <= 28]
    start = recent[0] if len(recent) >= 2 else entries[-2]
    days = (latest.date - start.date).days
    if days < 7:
        start = entries[0]
        days = (latest.date - start.date).days
        if days < 7:
            return None, None
    rate = (float(latest.weight_kg) - float(start.weight_kg)) / (days / 7)
    return round(rate, 2), days


def estimate_calories(weight, height, age, gender, visits_30d, goal_type, bmi):
    """Mifflin-St Jeor estimate. Returns None when it should not be shown."""
    if age is None or age < 18 or gender not in ('M', 'F'):
        return None

    bmr = 10 * weight + 6.25 * height - 5 * age + (5 if gender == 'M' else -161)
    per_week = visits_30d / 4.3
    if per_week < 1.5:
        factor = 1.2
    elif per_week < 3:
        factor = 1.375
    elif per_week < 5:
        factor = 1.55
    else:
        factor = 1.725
    maintenance = bmr * factor

    adjustment = 0
    if goal_type == 'weight_loss':
        if bmi >= 30:
            adjustment = -500
        elif bmi >= 25:
            adjustment = -400
        elif bmi >= 18.5:
            adjustment = -250          # underweight members never get a deficit
    elif goal_type == 'muscle_gain':
        adjustment = 250

    target = maintenance + adjustment
    floor = 1500 if gender == 'M' else 1200
    floor_applied = target < floor
    target = max(target, floor)
    return {
        'maintenance': int(round(maintenance / 10) * 10),
        'target': int(round(target / 10) * 10),
        'adjustment': int(round((target - maintenance) / 10) * 10),
        'floor_applied': floor_applied,
    }


def _flag(level, title, text):
    return {'level': level, 'title': title, 'text': text}


LEVEL_ORDER = {'danger': 0, 'warning': 1, 'info': 2, 'success': 3}


def build_flags(latest, goal, rate, span_days, visits, age, today):
    """The 'smart' part: simple rules that turn the numbers into advice."""
    flags = []
    goal_type = goal.goal_type if goal else None

    if (today - latest.date).days > 14:
        flags.append(_flag('info', 'Update your measurements',
                           f'Your last entry is from {latest.date:%d %b %Y}. Log a new one for better suggestions.'))

    if latest.bmi_category == 'Underweight':
        if goal_type == 'weight_loss':
            flags.append(_flag('danger', 'Weight loss is not advised',
                               f'Your BMI ({latest.bmi}) is in the underweight range. Please talk to your trainer '
                               'about a maintenance or muscle-gain goal instead.'))
        else:
            flags.append(_flag('warning', 'BMI in the underweight range',
                               f'Your BMI is {latest.bmi}. Focus on eating enough and building strength, and speak '
                               'to your trainer or a doctor if you are unsure.'))

    if age is not None and age < 18:
        flags.append(_flag('info', 'Calorie targets are not shown',
                           'For members under 18 we only give general training advice. Please talk to your '
                           'trainer about food.'))

    if goal is None:
        flags.append(_flag('info', 'Set a goal',
                           'Set a goal on your progress page and the plan will match it. For now you are seeing a '
                           'balanced maintenance plan.'))
    else:
        progress = goal_progress(goal, latest.weight_kg)
        if progress and not progress.get('is_maintenance') and progress.get('done'):
            flags.append(_flag('success', 'Goal reached!',
                               'You hit your target weight. Set a new goal or switch to maintenance.'))

        if rate is not None:
            if goal_type == 'weight_loss':
                if rate <= -1.0:
                    flags.append(_flag('warning', 'Losing weight quickly',
                                       f'You are losing about {abs(rate)} kg per week. A pace of 0.25-0.75 kg a week '
                                       'is easier to keep and protects your muscle. Consider eating a little more.'))
                elif rate >= 0.2:
                    flags.append(_flag('warning', 'Weight is going up',
                                       f'Your weight rose about {rate} kg per week recently. Review your portions and '
                                       'keep up your cardio, or ask your trainer to check your plan.'))
                elif abs(rate) < 0.1 and span_days >= 21:
                    flags.append(_flag('info', 'Progress has levelled off',
                                       'Your weight has been flat for about three weeks. Try a few extra steps a day, '
                                       'add one cardio session, or ask your trainer to adjust your plan.'))
                elif -0.75 <= rate <= -0.25:
                    flags.append(_flag('success', 'Good, steady pace',
                                       f'You are losing about {abs(rate)} kg per week. Keep going!'))
            elif goal_type == 'muscle_gain':
                if rate >= 0.6:
                    flags.append(_flag('warning', 'Gaining quickly',
                                       f'You are gaining about {rate} kg per week. Faster gain is usually extra fat. '
                                       'Try slightly smaller portions.'))
                elif rate <= -0.1:
                    flags.append(_flag('warning', 'Weight is going down',
                                       'You want to gain but your weight is dropping. Add more calories, especially '
                                       'protein and carbohydrates.'))
                elif abs(rate) < 0.1 and span_days >= 21:
                    flags.append(_flag('info', 'Progress has levelled off',
                                       'Your weight has been flat for about three weeks. Add a little more food '
                                       'and try to increase the weights you lift.'))
                elif 0.1 <= rate < 0.6:
                    flags.append(_flag('success', 'Steady gain',
                                       f'You are gaining about {rate} kg per week. Keep training hard.'))
            elif goal_type == 'maintenance' and abs(rate) > 0.5:
                flags.append(_flag('warning', 'Weight is drifting',
                                   f'Your weight is changing by about {abs(rate)} kg per week. Adjust your food '
                                   'or activity to stay stable.'))

        # Is the target date realistic?
        if goal.target_date and goal.target_weight_kg is not None and goal_type in ('weight_loss', 'muscle_gain'):
            weeks_left = (goal.target_date - today).days / 7
            if weeks_left > 0:
                remaining = abs(float(latest.weight_kg) - float(goal.target_weight_kg))
                needed = remaining / weeks_left
                limit = 1.0 if goal_type == 'weight_loss' else 0.5
                if needed > limit:
                    flags.append(_flag('warning', 'Your target date is very tight',
                                       f'You would need to change by about {needed:.1f} kg per week to reach the target '
                                       f'by {goal.target_date:%d %b %Y}. Consider a later date.'))

    if visits < 4:
        flags.append(_flag('info', 'Build the habit',
                           f'You visited {visits} time{"s" if visits != 1 else ""} in the last 30 days. '
                           'Aim for 3 sessions a week before adding more.'))
    elif visits >= 20:
        flags.append(_flag('success', 'Great consistency',
                           f'{visits} visits in the last 30 days. Remember to take rest days too.'))

    flags.sort(key=lambda f: LEVEL_ORDER[f['level']])
    return flags


def build_workout(goal_type, level):
    days = DAYS_BY_LEVEL[goal_type][level]
    blueprints = WORKOUTS[goal_type]
    slots = SLOTS[days]
    week = []
    for weekday in range(7):
        if weekday in slots:
            title, exercises = blueprints[slots.index(weekday)]
            week.append({'day': WEEKDAYS[weekday], 'title': title, 'exercises': exercises, 'rest': False})
        else:
            week.append({'day': WEEKDAYS[weekday], 'title': 'Rest day',
                         'exercises': ['Easy walk, stretching or mobility work'], 'rest': True})
    return days, week


def _round5(value):
    return int(round(value / 5.0) * 5)


# ---------------------------------------------------------------------------
# The main function used by the page
# ---------------------------------------------------------------------------
def generate(member):
    today = timezone.localdate()
    entries = list(member.progress_entries.order_by('date', 'id'))
    if not entries:
        return {'ready': False, 'reason': 'Log your first measurements to get a personal plan.'}

    latest = entries[-1]
    goal = member.goals.filter(is_active=True).first()
    goal_type = goal.goal_type if goal else 'maintenance'

    rate, span_days = weekly_rate(entries, today)
    visits = Attendance.objects.filter(member=member, date__gte=today - timedelta(days=30)).count()
    level = attendance_level(visits)
    age = age_from(member.date_of_birth, today)
    weight, height = float(latest.weight_kg), float(latest.height_cm)

    days, week = build_workout(goal_type, level)
    low, high = PROTEIN_PER_KG[goal_type]
    calories = estimate_calories(weight, height, age, member.gender, visits, goal_type, latest.bmi)

    if calories is not None:
        calories_note = ''
    elif age is not None and age < 18:
        calories_note = 'Calorie targets are not shown for members under 18.'
    else:
        calories_note = 'Add your date of birth and gender in your profile to see calorie estimates.'

    return {
        'ready': True,
        'flags': build_flags(latest, goal, rate, span_days, visits, age, today),
        'snapshot': {
            'weight': latest.weight_kg, 'bmi': latest.bmi, 'category': latest.bmi_category,
            'badge': latest.bmi_badge, 'goal_label': GOAL_LABELS[goal_type] if goal else 'No goal set',
            'visits': visits, 'level_label': LEVEL_LABELS[level], 'rate': rate, 'last_date': latest.date,
        },
        'workout': {
            'days': days, 'week': week, 'tips': WORKOUT_TIPS,
            'intro': (f'You visited {visits} time{"s" if visits != 1 else ""} in the last 30 days, so this plan uses '
                      f'{days} training days a week. As your attendance grows, the plan adds more days.'),
        },
        'nutrition': {
            'calories': calories, 'calories_note': calories_note,
            'protein_low': _round5(weight * low), 'protein_high': _round5(weight * high),
            'water': round(min(4.0, max(2.0, weight * 0.035)), 1),
            'principles': PRINCIPLES[goal_type], 'portion_note': PORTION_NOTES[goal_type],
            'sample_day': SAMPLE_DAY,
        },
        'disclaimer': DISCLAIMER,
    }