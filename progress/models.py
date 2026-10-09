from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


def _cm_field():
    """An optional body measurement in centimetres."""
    return models.DecimalField(
        max_digits=4, decimal_places=1, null=True, blank=True,
        validators=[MinValueValidator(10), MaxValueValidator(250)],
    )


class ProgressEntry(models.Model):
    """One set of measurements taken on one day."""
    member = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='progress_entries', limit_choices_to={'role': 'member'},
    )
    date = models.DateField(default=timezone.localdate)
    weight_kg = models.DecimalField(
        max_digits=5, decimal_places=1,
        validators=[MinValueValidator(20), MaxValueValidator(300)],
    )
    height_cm = models.DecimalField(
        max_digits=4, decimal_places=1,
        validators=[MinValueValidator(100), MaxValueValidator(250)],
    )
    body_fat_percent = models.DecimalField(
        max_digits=4, decimal_places=1, null=True, blank=True,
        validators=[MinValueValidator(2), MaxValueValidator(60)],
    )
    chest_cm = _cm_field()
    waist_cm = _cm_field()
    hips_cm = _cm_field()
    arms_cm = _cm_field()
    thighs_cm = _cm_field()
    notes = models.CharField(max_length=200, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-id']
        verbose_name_plural = 'progress entries'
        constraints = [
            models.UniqueConstraint(fields=['member', 'date'], name='one_progress_entry_per_member_per_day'),
        ]

    def __str__(self):
        return f"{self.member} - {self.date} - {self.weight_kg} kg"

    # BMI is worked out each time, never stored
    @property
    def bmi(self):
        height_m = float(self.height_cm) / 100
        return round(float(self.weight_kg) / (height_m * height_m), 1)

    @property
    def bmi_category(self):
        bmi = self.bmi
        if bmi < 18.5:
            return 'Underweight'
        if bmi < 25:
            return 'Normal'
        if bmi < 30:
            return 'Overweight'
        return 'Obese'

    @property
    def bmi_badge(self):
        return {
            'Underweight': 'badge-soft-blue',
            'Normal': 'badge-soft-success',
            'Overweight': 'badge-soft-orange',
            'Obese': 'badge-soft-danger',
        }[self.bmi_category]


class FitnessGoal(models.Model):
    class GoalType(models.TextChoices):
        WEIGHT_LOSS = 'weight_loss', 'Weight loss'
        MUSCLE_GAIN = 'muscle_gain', 'Muscle gain'
        MAINTENANCE = 'maintenance', 'Maintenance'

    member = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='goals', limit_choices_to={'role': 'member'},
    )
    goal_type = models.CharField(max_length=15, choices=GoalType.choices)
    start_weight_kg = models.DecimalField(max_digits=5, decimal_places=1)   # weight when the goal was set
    target_weight_kg = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    target_date = models.DateField(null=True, blank=True)
    notes = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)                           # only one active goal per member
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.member} - {self.get_goal_type_display()}"