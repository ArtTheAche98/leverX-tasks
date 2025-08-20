"""Domain service functions for lectures, homework, submissions, and grading.

Enforces role/visibility rules:
- Only teachers can create lectures/homework or assign grades.
- Students (or teachers acting as students) submit/resubmit homework.
State transitions for submissions:
    SUBMITTED -> RESUBMITTED (on resubmission) -> GRADED (after grading).
Grades are replaced on resubmission (previous grade deleted).
"""

from typing import Any

from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from CourseManagementApp.learning.models import Lecture, Homework, Submission, Grade
from CourseManagementApp.core.choices import SubmissionState, MemberRole
from CourseManagementApp.courses.models import CourseMembership, User



def _is_role(user: User, course, role: str) -> bool:
    """Return True if user has specified role in the course."""
    return CourseMembership.objects.filter(course=course, user=user, role=role).exists()

def _ensure_teacher(user: User, course) -> None:
    """Ensure user is a teacher of course."""
    if not CourseMembership.objects.filter(course=course, user=user, role=MemberRole.TEACHER).exists():
        raise PermissionDenied("Teacher role required")

def _ensure_student(user: User, course) -> None:
    """Ensure user is a student of course."""
    if not CourseMembership.objects.filter(course=course, user=user, role=MemberRole.STUDENT).exists():
        raise PermissionDenied("Student role required")

@transaction.atomic
def create_lecture(
    teacher: User,
    course,
    topic: str,
    presentation: Any | None = None,
    presentation_url: str | None = None,
    is_published: bool = False,
) -> Lecture:
    """Create a lecture (teacher only); enforce exclusive file vs URL.

    Raises:
        PermissionDenied: If role invalid or both resources provided.
    """
    _ensure_teacher(teacher, course)
    if presentation and presentation_url:
        raise PermissionDenied("Choose file or URL, not both")
    return Lecture.objects.create(
        course=course,
        topic=topic,
        presentation=presentation,
        presentation_url=presentation_url,
        is_published=is_published,
        created_by=teacher
    )

@transaction.atomic
def create_homework(
    teacher: User,
    lecture: Lecture,
    text: str,
    due_at=None,
    is_active: bool = True,
) -> Homework:
    """Create homework under a lecture (teacher only)."""
    _ensure_teacher(teacher, lecture.course)
    return Homework.objects.create(lecture=lecture, text=text, due_at=due_at, is_active=is_active)

@transaction.atomic
def submit(
    student: User,
    homework: Homework,
    content_text: str = "",
    attachment: Any | None = None,
) -> Submission:
    """Create or resubmit a submission.

    Rules:
        - User must be enrolled (teacher or student role).
        - Non-teacher submissions require active homework & published lecture/course.
        - At least one of content_text or attachment required.
        - On resubmit: prior grade (if any) is deleted and state changes to RESUBMITTED.
    """
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

    if hasattr(submission, "grade"):
        submission.grade.delete()

    if content_text:
        submission.content_text = content_text
    if attachment is not None:
        submission.attachment = attachment

    submission.is_late = bool(homework.due_at and now > homework.due_at)
    submission.state = SubmissionState.RESUBMITTED
    submission.save()
    return submission

@transaction.atomic
def grade_submission(
    teacher: User,
    submission: Submission,
    value: int,
    comment: str = "",
) -> Grade:
    """Create or update a grade for a submission (teacher only).

    Validates:
        value within 0–100 inclusive.
    Updates submission state to GRADED.
    """
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

def list_homework_submissions_for_teacher(
    teacher: User, homework: Homework
) -> QuerySet[Submission]:
    """List all submissions for a homework (teacher only)."""
    _ensure_teacher(teacher, homework.lecture.course)
    return homework.submissions.select_related("student", "grade").all()