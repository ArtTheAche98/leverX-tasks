from django.db import models
from django.conf import settings

from simple_history.models import HistoricalRecords

from CourseManagementApp.core.choices import MemberRole
from CourseManagementApp.courses.querysets import CourseQuerySet


User = settings.AUTH_USER_MODEL

class Course(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_public = models.BooleanField(default=False)
    is_published = models.BooleanField(default=False)
    owner = models.ForeignKey(User, on_delete=models.PROTECT, related_name="owned_courses")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()

    objects = CourseQuerySet.as_manager()

class CourseMembership(models.Model):
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
