"""Role & object access helpers."""

from typing import Any
from CourseManagementApp.courses.models import Course, CourseMembership
from CourseManagementApp.learning.models import (
    Lecture, Homework, Submission, Grade, GradeComment
)
from CourseManagementApp.core.choices import MemberRole


def course_from(obj: Any) -> Course | None:
    if obj is None:
        return None
    if isinstance(obj, Course):
        return obj
    if isinstance(obj, Lecture):
        return obj.course
    if isinstance(obj, Homework):
        return obj.lecture.course
    if isinstance(obj, Submission):
        return obj.homework.lecture.course
    if isinstance(obj, Grade):
        return obj.submission.homework.lecture.course
    if isinstance(obj, GradeComment):
        return obj.grade.submission.homework.lecture.course
    return getattr(obj, "course", None)


def is_owner(user, course: Course | None) -> bool:
    return bool(user and course and course.owner_id == user.id)


def is_teacher(user, course: Course | None) -> bool:
    if not (user and course):
        return False
    return CourseMembership.objects.filter(
        course=course, user=user, role=MemberRole.TEACHER
    ).exists()


def is_student(user, course: Course | None) -> bool:
    if not (user and course):
        return False
    return CourseMembership.objects.filter(
        course=course, user=user, role=MemberRole.STUDENT
    ).exists()


def is_member(user, course: Course | None) -> bool:
    if not (user and course):
        return False
    return CourseMembership.objects.filter(course=course, user=user).exists()


def is_submission_participant(user, obj: Any) -> bool:
    """User is involved with submission / grade / grade comment or teacher/owner."""
    course = course_from(obj)
    if not course:
        return False
    # Direct submission
    if isinstance(obj, Submission) and obj.student_id == user.id:
        return True
    # Grade
    if isinstance(obj, Grade):
        if obj.submission.student_id == user.id or obj.graded_by_id == user.id:
            return True
    # GradeComment
    if isinstance(obj, GradeComment):
        if obj.author_id == user.id or obj.grade.submission.student_id == user.id:
            return True
    return is_teacher(user, course) or is_owner(user, course)