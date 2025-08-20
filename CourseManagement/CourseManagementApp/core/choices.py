"""Typed enumerations (TextChoices) for user roles, member roles, and submission states."""
from django.db import models

class UserRole(models.TextChoices):
    """System-level role assigned to a user account."""
    TEACHER = "TEACHER", "Teacher"
    STUDENT = "STUDENT", "Student"

class MemberRole(models.TextChoices):
    """Role of a user within a specific course context."""
    TEACHER = "TEACHER", "Teacher"
    STUDENT = "STUDENT", "Student"

class SubmissionState(models.TextChoices):
    """Lifecycle states for a homework submission."""
    SUBMITTED = "SUBMITTED", "Submitted"
    RESUBMITTED = "RESUBMITTED", "Resubmitted"
    GRADED = "GRADED", "Graded"
