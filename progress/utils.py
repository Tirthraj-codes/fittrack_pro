from scheduling.models import TrainerAssignment


def can_access_member(user, member):
    """Admins see everyone, trainers see their assigned members, members see only themselves."""
    if user.is_admin_role:
        return True
    if user.is_trainer:
        return TrainerAssignment.objects.filter(trainer=user, member=member).exists()
    return user.pk == member.pk


def goal_progress(goal, current_weight):
    """How far along a goal is, as a small dictionary (or None if it cannot be worked out)."""
    if goal is None or current_weight is None:
        return None

    current = float(current_weight)
    start = float(goal.start_weight_kg)

    if goal.goal_type == goal.GoalType.MAINTENANCE:
        gap = abs(current - start)
        on_track = gap <= 2
        return {
            'is_maintenance': True,
            'label': 'On track' if on_track else 'Off track',
            'on_track': on_track,
            'gap': round(gap, 1),
        }

    if goal.target_weight_kg is None:
        return None
    target = float(goal.target_weight_kg)
    total = start - target                      # positive for weight loss, negative for muscle gain
    if total == 0:
        return None

    percent = max(0, min(100, round((start - current) / total * 100)))
    remaining = round(abs(current - target), 1)
    reached = percent >= 100
    return {
        'is_maintenance': False,
        'percent': percent,
        'remaining': remaining,
        'done': reached,
        'label': 'Goal reached!' if reached else f'{remaining} kg to go',
    }


def build_summary(member):
    """Everything the progress page needs: numbers, goal progress and chart data."""
    entries = list(member.progress_entries.order_by('date', 'id'))        # oldest first
    latest = entries[-1] if entries else None
    first = entries[0] if entries else None
    previous = entries[-2] if len(entries) > 1 else None
    goal = member.goals.filter(is_active=True).first()

    change_total = change_last = None
    if latest and first and latest is not first:
        change_total = round(float(latest.weight_kg) - float(first.weight_kg), 1)
    if latest and previous:
        change_last = round(float(latest.weight_kg) - float(previous.weight_kg), 1)

    # Body measurement lines: only include the ones that have at least one value
    attributes = {'Chest': 'chest_cm', 'Waist': 'waist_cm', 'Hips': 'hips_cm', 'Arms': 'arms_cm', 'Thighs': 'thighs_cm'}
    measurements = {}
    for label, attribute in attributes.items():
        values = [
            float(getattr(e, attribute)) if getattr(e, attribute) is not None else None
            for e in entries
        ]
        if any(v is not None for v in values):
            measurements[label] = values

    target_line = None
    if goal and goal.target_weight_kg is not None:
        target_line = [float(goal.target_weight_kg)] * len(entries)

    chart = {
        'labels': [e.date.strftime('%d %b') for e in entries],
        'weight': [float(e.weight_kg) for e in entries],
        'bmi': [e.bmi for e in entries],
        'target': target_line,
        'measurements': measurements,
    }

    return {
        'latest': latest,
        'entries': list(reversed(entries)),                                # newest first for the table
        'change_total': change_total,
        'change_last': change_last,
        'goal': goal,
        'goal_progress': goal_progress(goal, latest.weight_kg if latest else None),
        'past_goals': member.goals.filter(is_active=False)[:5],
        'chart': chart,
        'has_measurements': bool(measurements),
    }