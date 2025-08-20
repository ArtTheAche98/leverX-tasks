"""Course domain models: Course, CourseMembership, CourseWaitlistEntry."""

from django.db import models
from django.conf import settings

from simple_history.models import HistoricalRecords

from CourseManagementApp.core.choices import MemberRole
from CourseManagementApp.courses.querysets import CourseQuerySet


User = settings.AUTH_USER_MODEL

class Course(models.Model):
    """A course owned by a user (owner) that can be public/published and has members.

    Fields:
        title: Human readable course title.
        description: Optional longer text.
        is_public: Whether non‑enrolled users may view (when published).
        is_published: Whether content is considered published.
        owner: FK to user who owns/administers the course.
        created_at / updated_at: Timestamps.
        history: Audit history (django-simple-history).
    """
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_public = models.BooleanField(default=False)
    is_published = models.BooleanField(default=False)
    owner = models.ForeignKey(User, on_delete=models.PROTECT, related_name="owned_courses")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()

    objects = CourseQuerySet.as_manager()

    def __str__(self) -> str:
        return f"{self.title} (#{self.pk})"

class CourseMembership(models.Model):
    """Enrollment of a user in a course with a role (teacher or student).

    Fields:
        course: Target course.
        user: Enrolled user.
        role: MemberRole value.
        added_by: User who created the membership (auditing).
        created_at: Timestamp.
        history: Historical records.
    Constraints:
        uq_course_user: Prevent duplicate membership rows.
    """
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="course_memberships")
    role = models.CharField(max_length=16, choices=MemberRole.choices)
    added_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="members_added")
    created_at = models.DateTimeField(auto_now_add=True)
    history = HistoricalRecords()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["course", "user"], name="uq_course_user"),
        ]

    def __str__(self) -> str:
        return f"{self.user} -> {self.course} ({self.role})"


class CourseWaitlistEntry(models.Model):
    """A student's request to join a course, pending approval.

    Fields:
        course: Target course.
        student: User requesting access.
        created_at: Timestamp.
        approved: True (accepted), False (rejected), None (pending).
    Unique:
        (course, student) pair enforced to avoid duplicates.
    """
    course = models.ForeignKey(Course, related_name="waitlist", on_delete=models.CASCADE)
    student = models.ForeignKey(User, related_name="course_waitlist", on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    approved = models.BooleanField(null=True)

    class Meta:
        unique_together = ('course', 'student')

    def __str__(self) -> str:
        status = "pending" if self.approved is None else ("approved" if self.approved else "rejected")
        return f"Waitlist({self.student} -> {self.course}, {status})"