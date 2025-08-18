from rest_framework.permissions import BasePermission, SAFE_METHODS
from django.shortcuts import get_object_or_404

from CourseManagementApp.courses.models import Course, CourseMembership
from CourseManagementApp.learning.models import Lecture, Homework
from CourseManagementApp.core.choices import MemberRole

class IsCourseOwner(BasePermission):
    def has_object_permission(self, request, view, obj):
        course = obj if isinstance(obj, Course) else getattr(obj, "course", None)
        if course is None and hasattr(obj, "lecture"):
            course = obj.lecture.course
        return course and course.owner_id == request.user.id


class IsCourseTeacher(BasePermission):
    """
    Grants write access if the user is a teacher of the target course.
    Supports nested routes by resolving course from kwargs:
      - course_pk
      - lecture_pk
      - homework_pk
    Read (SAFE_METHODS) always allowed (object filtering handled separately).
    """
    def _course_from_view(self, view):
        if hasattr(view, "_resolved_course"):
            return view._resolved_course
        course = None
        kw = view.kwargs
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

    def _is_teacher(self, user, course):
        if not course:
            return False
        return CourseMembership.objects.filter(
            course=course, user=user, role=MemberRole.TEACHER
        ).exists()

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        # For create/update/destroy on nested endpoints resolve cours
        course = self._course_from_view(view)
        if course:
            return self._is_teacher(request.user, course)
        # If course not inferable (e.g. listing), defer to object checks
        return True

    def has_object_permission(self, request, view, obj):
        course = obj if isinstance(obj, Course) else getattr(obj, "course", None)
        if course is None and hasattr(obj, "lecture"):
            course = obj.lecture.course
        return self._is_teacher(request.user, course)

class IsCourseTeacherOrOwner(BasePermission):
    def has_object_permission(self, request, view, obj):
        course = obj if isinstance(obj, Course) else getattr(obj, "course", None)
        if course is None and hasattr(obj, "lecture"):
            course = obj.lecture.course
        if not course:
            return False
        if course.owner_id == request.user.id:
            return True
        return CourseMembership.objects.filter(
            course=course, user=request.user, role=MemberRole.TEACHER
        ).exists()


class IsCourseStudent(BasePermission):
    def has_object_permission(self, request, view, obj):
        course = obj if isinstance(obj, Course) else getattr(obj, "course", None)
        if course is None and hasattr(obj, "lecture"):
            course = obj.lecture.course
        return CourseMembership.objects.filter(
            course=course, user=request.user, role=MemberRole.STUDENT
        ).exists()


class IsSubmissionOwner(BasePermission):
    def has_object_permission(self, request, view, obj):
        return getattr(obj, "student_id", None) == request.user.id


class IsSubmissionParticipant(BasePermission):
    def has_object_permission(self, request, view, obj):
        # obj: Submission
        course = obj.homework.lecture.course
        if obj.student_id == request.user.id:
            return True
        return CourseMembership.objects.filter(
            course=course, user=request.user, role=MemberRole.TEACHER
        ).exists()


class IsGradeCommentParticipant(BasePermission):
    """
    Allows access (retrieve/destroy) if user is the comment author or a teacher of the course.
    """
    def has_object_permission(self, request, view, obj):
        # obj: GradeComment
        if obj.author_id == request.user.id:
            return True
        course = obj.grade.submission.homework.lecture.course
        return CourseMembership.objects.filter(
            course=course, user=request.user, role=MemberRole.TEACHER
        ).exists()

class IsGradeParticipant(BasePermission):
    """
    Allows access (retrieve/destroy) if user is the grade author or a teacher of the course.
    """
    def has_object_permission(self, request, view, obj):
        # obj: Grade
        if obj.graded_by_id == request.user.id:
            return True
        course = obj.submission.homework.lecture.course
        return CourseMembership.objects.filter(
            course=course, user=request.user, role=MemberRole.TEACHER
        ).exists()