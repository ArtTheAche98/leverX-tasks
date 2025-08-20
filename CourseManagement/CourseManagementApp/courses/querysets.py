"""Custom querysets encapsulating visibility and role-based filtering for courses and learning objects."""

from django.db.models import QuerySet, Q
from typing import Self


from CourseManagementApp.core.choices import MemberRole

class CourseQuerySet(QuerySet):
    """QuerySet with helpers for course visibility and ownership."""

    def public_published(self) -> Self:
        """Courses that are both public and published."""
        return self.filter(is_public=True, is_published=True)

    def for_owner(self, user) -> Self:
        """Courses owned by the given user."""
        return self.filter(owner=user)

    def where_user_member(self, user) -> Self:
        """Courses where the user has any membership."""
        return self.filter(memberships__user=user).distinct()

    def visible_to(self, user) -> Self:
        """Courses visible to user:
        - Anonymous: public & published
        - Authenticated: union of (public & published) OR owned OR member
        """
        if not user or not user.is_authenticated:
            return self.public_published()
        return self.filter(
            Q(is_public=True, is_published=True) |
            Q(owner=user) |
            Q(memberships__user=user)
        ).distinct()


class LectureQuerySet(QuerySet):
    """QuerySet helpers for lecture visibility."""
    def published_for_student(self, user) -> Self:
        """Published lectures in courses where user is enrolled as student."""
        return self.filter(
            is_published=True,
            course__memberships__user=user,
            course__memberships__role=MemberRole.STUDENT
        )

    def visible_to(self, user) -> Self:
        """Lectures visible to user:
        - Owner/teacher: all in their courses
        - Student: published lectures of enrolled courses
        - Anonymous: published lectures of public & published courses
        """
        if not user or not user.is_authenticated:
            return self.filter(
                is_published=True,
                course__is_public=True,
                course__is_published=True,
            )
        return self.filter(
            Q(course__owner=user) |
            Q(course__memberships__user=user,
              course__memberships__role=MemberRole.TEACHER) |
            Q(is_published=True,
              course__memberships__user=user,
              course__memberships__role=MemberRole.STUDENT) |
            Q(is_published=True,
              course__is_public=True,
              course__is_published=True)
        ).distinct()


class HomeworkQuerySet(QuerySet):
    """QuerySet helpers for homework visibility."""

    def visible_to(self, user) -> Self:
        """Homework visible to user:
        - Anonymous: active homework of published public courses / published lecture
        - Teacher/Owner: all
        - Student: active homework of published lectures in enrolled courses
        """
        if not user or not user.is_authenticated:
            return self.filter(
                lecture__is_published=True,
                lecture__course__is_public=True,
                lecture__course__is_published=True,
                is_active=True,
            )
        return self.filter(
            Q(lecture__course__owner=user) |
            Q(lecture__course__memberships__user=user,
              lecture__course__memberships__role=MemberRole.TEACHER) |
            Q(lecture__is_published=True, is_active=True,
              lecture__course__memberships__user=user,
              lecture__course__memberships__role=MemberRole.STUDENT) |
            Q(lecture__is_published=True, is_active=True,
              lecture__course__is_public=True,
              lecture__course__is_published=True)
        ).distinct()

class SubmissionQuerySet(QuerySet):
    """QuerySet helpers for filtering submissions by role."""

    def for_teacher(self, user):
        """Submissions in courses where user is a teacher."""
        return self.filter(
            homework__lecture__course__memberships__user=user,
            homework__lecture__course__memberships__role=MemberRole.TEACHER
        )

    def for_student(self, user):
        """Submissions belonging to the student."""
        return self.filter(student=user)