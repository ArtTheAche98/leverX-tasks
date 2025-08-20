"""Learning domain models: Lecture, Homework, Submission, Grade, GradeComment."""

from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator

from CourseManagementApp.courses.models import Course
from CourseManagementApp.core.choices import SubmissionState
from CourseManagementApp.core.validators import validate_file_size, validate_presentation_mime, validate_attachment_mime
from CourseManagementApp.courses.querysets import LectureQuerySet, HomeworkQuerySet, SubmissionQuerySet

from simple_history.models import HistoricalRecords

User = settings.AUTH_USER_MODEL

class Lecture(models.Model):
    """A teaching unit within a course (optionally published) with an optional presentation file or URL."""
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="lectures")
    topic = models.CharField(max_length=255)
    presentation = models.FileField(
        upload_to="presentations/", blank=True, null=True,
        validators=[validate_file_size, validate_presentation_mime]
    )
    presentation_url = models.URLField(blank=True, null=True)
    is_published = models.BooleanField(default=False)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="created_lectures")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()

    objects = LectureQuerySet.as_manager()


class Homework(models.Model):
    """An assignment linked to a lecture with optional due date and active flag."""
    lecture = models.ForeignKey(Lecture, on_delete=models.CASCADE, related_name="homeworks")
    text = models.TextField()
    due_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()

    objects = HomeworkQuerySet.as_manager()


class Submission(models.Model):
    """A student's (or teacher's) submission for a homework (unique per homework+student)."""
    homework = models.ForeignKey(Homework, on_delete=models.CASCADE, related_name="submissions")
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="submissions")
    content_text = models.TextField(blank=True)
    attachment = models.FileField(
        upload_to="submissions/", blank=True, null=True,
        validators=[validate_file_size, validate_attachment_mime]
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_late = models.BooleanField(default=False)
    state = models.CharField(max_length=16, choices=SubmissionState.choices, default=SubmissionState.SUBMITTED)
    history = HistoricalRecords()

    objects = SubmissionQuerySet.as_manager()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["homework", "student"], name="uq_homework_student"),
        ]


class Grade(models.Model):
    """A teacher's evaluation (0–100) of a submission."""
    submission = models.OneToOneField(Submission, on_delete=models.CASCADE, related_name="grade")
    graded_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="assigned_grades")
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    value = models.PositiveSmallIntegerField(validators=[MinValueValidator(0), MaxValueValidator(100)])
    history = HistoricalRecords()


class GradeComment(models.Model):
    """A comment thread entry attached to a grade (author can be student or teacher)."""
    grade = models.ForeignKey(Grade, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="grade_comments")
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    history = HistoricalRecords()
