from django.db import transaction
from rest_framework.exceptions import PermissionDenied

from CourseManagementApp.courses.models import Course, CourseMembership
from CourseManagementApp.core.choices import MemberRole

@transaction.atomic
def create_course(owner, data):
    course = Course.objects.create(owner=owner, **data)
    CourseMembership.objects.create(course=course, user=owner, role=MemberRole.TEACHER, added_by=owner)
    return course

def _ensure_course_teacher(user, course):
    if not CourseMembership.objects.filter(course=course, user=user, role=MemberRole.TEACHER).exists():
        raise PermissionDenied("Teacher role required")

@transaction.atomic
def add_teacher(actor, course, teacher_user):
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
def add_student(actor, course, student_user):
    _ensure_course_teacher(actor, course)
    membership, created = CourseMembership.objects.get_or_create(
        course=course,
        user=student_user,
        defaults={"role": MemberRole.STUDENT, "added_by": actor},
    )
    return membership

@transaction.atomic
def remove_member(actor, course, member_user):
    _ensure_course_teacher(actor, course)
    CourseMembership.objects.filter(course=course, user=member_user).delete()