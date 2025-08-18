from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from CourseManagementApp.learning.models import Lecture, Homework, Submission, Grade
from CourseManagementApp.core.choices import SubmissionState, MemberRole
from CourseManagementApp.courses.models import CourseMembership

def _is_role(user, course, role):
    return CourseMembership.objects.filter(course=course, user=user, role=role).exists()

def _ensure_teacher(user, course):
    if not CourseMembership.objects.filter(course=course, user=user, role=MemberRole.TEACHER).exists():
        raise PermissionDenied("Teacher role required")

def _ensure_student(user, course):
    if not CourseMembership.objects.filter(course=course, user=user, role=MemberRole.STUDENT).exists():
        raise PermissionDenied("Student role required")

@transaction.atomic
def create_lecture(teacher, course, topic, presentation=None, is_published=False):
    _ensure_teacher(teacher, course)
    return Lecture.objects.create(
        course=course, topic=topic, presentation=presentation,
        is_published=is_published, created_by=teacher
    )

@transaction.atomic
def create_homework(teacher, lecture, text, due_at=None, is_active=True):
    _ensure_teacher(teacher, lecture.course)
    return Homework.objects.create(lecture=lecture, text=text, due_at=due_at, is_active=is_active)

@transaction.atomic
def submit(student, homework, content_text="", attachment=None):
    lecture = homework.lecture
    course = lecture.course

    is_teacher = _is_role(student, course, MemberRole.TEACHER)
    is_student_member = _is_role(student, course, MemberRole.STUDENT)

    if not (is_teacher or is_student_member):
        raise PermissionDenied("Not enrolled in course")

    if not is_teacher:
        if not homework.is_active:
            raise PermissionDenied("Homework inactive")
        if not lecture.is_published or not course.is_published:
            raise PermissionDenied("Lecture or course not published")

    if not content_text and not attachment:
        raise PermissionDenied("Empty submission")

    now = timezone.now()
    submission, created = Submission.objects.select_for_update().get_or_create(
        homework=homework,
        student=student,
        defaults={
            "content_text": content_text,
            "attachment": attachment,
            "is_late": bool(homework.due_at and now > homework.due_at),
            "state": SubmissionState.SUBMITTED,
        },
    )
    if created:
        return submission

    grade = getattr(submission, "grade", None)
    if grade:
        grade.delete()
    submission.content_text = content_text or submission.content_text
    if attachment is not None:
        submission.attachment = attachment
    submission.is_late = bool(homework.due_at and now > homework.due_at)
    submission.state = SubmissionState.RESUBMITTED
    submission.save()
    return submission

@transaction.atomic
def grade_submission(teacher, submission, value, comment=""):
    course = submission.homework.lecture.course
    _ensure_teacher(teacher, course)
    if not (0 <= value <= 100):
        raise PermissionDenied("Grade must be 0–100")
    submission = Submission.objects.select_for_update().get(pk=submission.pk)
    grade, created = Grade.objects.select_for_update().get_or_create(
        submission=submission,
        defaults={"graded_by": teacher, "value": value, "comment": comment},
    )
    if not created and (grade.value != value or grade.comment != comment or grade.graded_by_id != teacher.id):
        grade.value = value
        grade.comment = comment
        grade.graded_by = teacher
        grade.save()
    submission.state = SubmissionState.GRADED
    submission.save(update_fields=["state", "updated_at"])
    return grade

def list_homework_submissions_for_teacher(teacher, homework):
    _ensure_teacher(teacher, homework.lecture.course)
    return homework.submissions.select_related("student", "grade").all()