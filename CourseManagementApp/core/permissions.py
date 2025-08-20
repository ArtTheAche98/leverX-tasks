"""Custom DRF permission classes for course, submission, grade, and comment access control."""

from rest_framework.request import Request
from typing import Any

from rest_framework.permissions import BasePermission, SAFE_METHODS
from django.shortcuts import get_object_or_404

from CourseManagementApp.courses.models import Course, CourseMembership
from CourseManagementApp.learning.models import Lecture, Homework
from CourseManagementApp.core.choices import MemberRole
from CourseManagementApp.core.access import (
    course_from, is_teacher, is_owner, is_student, is_submission_participant
)


class IsCourseTeacher(BasePermission):
    """Write access limited to course teachers (GET always allowed)."""

    def _course_from_view(self, view: Any) -> Course | None:
        course = getattr(view, "_resolved_course", None)
        if course:
            return course
        kw = getattr(view, "kwargs", {})
        if "course_pk" in kw:
            course = get_object_or_404(Course, pk=kw["course_pk"])
        elif "lecture_pk" in kw:
            lecture = get_object_or_404(Lecture, pk=kw["lecture_pk"])
            course = lecture.course
        elif "homework_pk" in kw:
            hw = get_object_or_404(Homework, pk=kw["homework_pk"])
            course = hw.lecture.course
        if course:
            view._resolved_course = course
        return course

    def has_permission(self, request: Request, view: Any) -> bool:
        if request.method in SAFE_METHODS:
            return True
        course = self._course_from_view(view)
        return True if not course else is_teacher(request.user, course)

    def has_object_permission(self, request: Request, view: Any, obj: Any) -> bool:
        return is_teacher(request.user, course_from(obj))


class IsCourseTeacherOrOwner(BasePermission):
    """Allow access if user is course owner or a teacher."""

    def has_object_permission(self, request: Request, view: Any, obj: Any) -> bool:
        course = course_from(obj)
        return bool(course and (is_owner(request.user, course) or is_teacher(request.user, course)))

class IsCourseOwner(BasePermission):
    """Allow access only if the requesting user owns the course."""
    def has_object_permission(self, request: Request, view: Any, obj: Any) -> bool:
        """Object-level check: compare resolved course owner with user."""
        course = obj if isinstance(obj, Course) else getattr(obj, "course", None)
        if course is None and hasattr(obj, "lecture"):
            course = obj.lecture.course
        return course and course.owner_id == request.user.id

class IsCourseStudent(BasePermission):
    """Allow access if user is a student member of the course."""

    def has_object_permission(self, request: Request, view: Any, obj: Any) -> bool:
        return is_student(request.user, course_from(obj))


class IsSubmissionOwner(BasePermission):
    """Allow access only to the submission's student owner."""

    def has_object_permission(self, request: Request, view: Any, obj: Any) -> bool:
        return getattr(obj, "student_id", None) == request.user.id


class ParticipantPermission(BasePermission):
    """Unified participant permission for Submission, Grade, GradeComment."""

    def has_object_permission(self, request: Request, view: Any, obj: Any) -> bool:
        return is_submission_participant(request.user, obj)


class IsSubmissionAccess(BasePermission):
    """
    Permission for submission endpoints.
    has_permission: require enrollment in the homework's course (nested routes).
    has_object_permission: allow if submission owner or course teacher.
    """
    def _course_from_homework(self, homework_id: int | str) -> Any:
        from CourseManagementApp.learning.models import Homework
        try:
            hw = Homework.objects.select_related("lecture__course").get(pk=homework_id)
        except Homework.DoesNotExist:
            return None
        return hw.lecture.course

    def has_permission(self, request: Request, view: Any) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False
        hw_id = view.kwargs.get("homework_pk")
        if not hw_id:
            return True
        course = self._course_from_homework(hw_id)
        return bool(course and CourseMembership.objects.filter(course=course, user=request.user).exists())

    def has_object_permission(self, request: Request, view: Any, obj: Any) -> bool:
        return is_submission_participant(request.user, obj)


class IsGradeCommentParticipant(BasePermission):
    """Allow access if user authored the comment or is a teacher of the related course."""

    def has_object_permission(self, request: Request, view: Any, obj: Any) -> bool:
        # obj: GradeComment
        if obj.author_id == request.user.id:
            return True
        course = obj.grade.submission.homework.lecture.course
        return CourseMembership.objects.filter(
            course=course, user=request.user, role=MemberRole.TEACHER
        ).exists()

class IsGradeParticipant(BasePermission):
    """Allow access if user graded it or is a teacher of the course."""

    def has_object_permission(self, request: Request, view: Any, obj: Any) -> bool:
        # obj: Grade
        if obj.graded_by_id == request.user.id:
            return True
        course = obj.submission.homework.lecture.course
        return CourseMembership.objects.filter(
            course=course, user=request.user, role=MemberRole.TEACHER
        ).exists()