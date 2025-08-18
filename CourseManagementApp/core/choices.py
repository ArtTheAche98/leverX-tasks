from django.db import models

class UserRole(models.TextChoices):
    TEACHER = "TEACHER", "Teacher"
    STUDENT = "STUDENT", "Student"

class MemberRole(models.TextChoices):
    TEACHER = "TEACHER", "Teacher"
    STUDENT = "STUDENT", "Student"

class SubmissionState(models.TextChoices):
    SUBMITTED = "SUBMITTED", "Submitted"
    RESUBMITTED = "RESUBMITTED", "Resubmitted"
    GRADED = "GRADED", "Graded"
