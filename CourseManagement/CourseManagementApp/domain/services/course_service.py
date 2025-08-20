"""Domain service functions for course lifecycle and membership management.

These helpers encapsulate business rules (e.g., only teachers can manage membership)
and keep view/serializer layers thin. All mutating operations run inside atomic
transactions to ensure consistency of course and membership state.
"""
from typing import Any
from django.db import transaction
from rest_framework.exceptions import PermissionDenied

from CourseManagementApp.courses.models import Course, CourseMembership, User
from CourseManagementApp.core.choices import MemberRole

@transaction.atomic
def create_course(owner: User, data: dict[str, Any]) -> Course:
    """Create a course and auto‑enroll the owner as a teacher.

    Args:
        owner: User creating (and owning) the course.
        data: Validated payload for the Course model (title, description, etc.).

    Returns:
        The newly created Course instance.
    """
    course = Course.objects.create(owner=owner, **data)
    CourseMembership.objects.create(course=course, user=owner, role=MemberRole.TEACHER, added_by=owner)
    return course

def _ensure_course_teacher(user: User, course: Course) -> None:
    """Raise PermissionDenied if user is not a teacher of the course."""
    if not CourseMembership.objects.filter(course=course, user=user, role=MemberRole.TEACHER).exists():
        raise PermissionDenied("Teacher role required")

@transaction.atomic
def add_teacher(actor: User, course: Course, teacher_user: User) -> CourseMembership:
    """Add (or promote) a user as a teacher of the course.

    Args:
        actor: Initiating user (must already be a teacher).
        course: Target course.
        teacher_user: User to add or promote.

    Returns:
        The CourseMembership for the teacher.
    """
    _ensure_course_teacher(actor, course)
    membership, created = CourseMembership.objects.get_or_create(
        course=course,
        user=teacher_user,
        defaults={"role": MemberRole.TEACHER, "added_by": actor},
    )
    if not created and membership.role != MemberRole.TEACHER:
        membership.role = MemberRole.TEACHER
        membership.save(update_fields=["role"])
    return membership

@transaction.atomic
def add_student(actor: User, course: Course, student_user: User) -> CourseMembership:
    """Enroll a student in the course (idempotent).

    Args:
        actor: Must be a teacher of the course.
        course: Target course.
        student_user: User to enroll.

    Returns:
        The (possibly existing) CourseMembership.
    """
    _ensure_course_teacher(actor, course)
    membership, created = CourseMembership.objects.get_or_create(
        course=course,
        user=student_user,
        defaults={"role": MemberRole.STUDENT, "added_by": actor},
    )
    return membership

@transaction.atomic
def remove_member(actor: User, course: Course, member_user: User) -> None:
    """Remove any membership record for the given user from the course.

    Args:
        actor: Must be a teacher of the course.
        course: Target course.
        member_user: User to remove (teacher or student).
    """
    _ensure_course_teacher(actor, course)
    CourseMembership.objects.filter(course=course, user=member_user).delete()