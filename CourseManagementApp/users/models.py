from django.contrib.auth.models import AbstractUser
from django.db import models

from CourseManagementApp.core.choices import UserRole

class User(AbstractUser):
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=16, choices=UserRole.choices)
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]
