from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """One user table for Admin, Trainer and Member. The 'role' field decides which."""

    class Role(models.TextChoices):
        ADMIN = 'admin', 'Admin'
        TRAINER = 'trainer', 'Trainer'
        MEMBER = 'member', 'Member'

    class Gender(models.TextChoices):
        MALE = 'M', 'Male'
        FEMALE = 'F', 'Female'
        OTHER = 'O', 'Other'

    role = models.CharField(max_length=10, choices=Role.choices, default=Role.MEMBER)
    phone = models.CharField(max_length=15, blank=True)
    gender = models.CharField(max_length=1, choices=Gender.choices, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    address = models.TextField(blank=True)
    photo = models.ImageField(upload_to='profiles/', blank=True, null=True)

    def save(self, *args, **kwargs):
        # A Django superuser is always an Admin in our system
        if self.is_superuser:
            self.role = self.Role.ADMIN
        super().save(*args, **kwargs)

    # Handy shortcuts, used later in views and templates
    @property
    def is_admin_role(self):
        return self.role == self.Role.ADMIN

    @property
    def is_trainer(self):
        return self.role == self.Role.TRAINER

    @property
    def is_member(self):
        return self.role == self.Role.MEMBER

    @property
    def display_name(self):
        return self.get_full_name() or self.username

    def __str__(self):
        return f"{self.display_name} ({self.get_role_display()})"