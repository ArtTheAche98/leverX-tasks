import pytest
from django.utils import timezone
from model_bakery import baker
from CourseManagementApp.domain.services import learning_service, course_service
from CourseManagementApp.core.choices import MemberRole, SubmissionState

pytestmark = pytest.mark.django_db

def make_course(owner):
    course = course_service.create_course(owner,
    {"title": "C1", "description": "", "is_public": True, "is_published": True})
    return course

def test_create_lecture_teacher_only():
    teacher = baker.make("users.User")
    course = make_course(teacher)
    lecture = learning_service.create_lecture(teacher, course, topic="Intro")
    assert lecture.topic == "Intro"

def test_create_lecture_reject_non_teacher():
    teacher = baker.make("users.User")
    other = baker.make("users.User")
    course = make_course(teacher)
    with pytest.raises(Exception):
        learning_service.create_lecture(other, course, topic="Fail")

def test_submission_flow_resubmission_clears_grade():
    teacher = baker.make("users.User")
    student = baker.make("users.User")
    course = make_course(teacher)
    baker.make(
        "courses.CourseMembership",
        course=course,
        user=student,
        role=MemberRole.STUDENT,
        added_by=teacher)
    lecture = learning_service.create_lecture(teacher, course, topic="Intro", is_published=True)
    hw = learning_service.create_homework(teacher, lecture, text="Do it")
    sub = learning_service.submit(student, hw, content_text="v1")
    assert sub.state == SubmissionState.SUBMITTED
    learning_service.grade_submission(teacher, sub, 90, "Good")
    sub.refresh_from_db()
    assert sub.state == SubmissionState.GRADED
    sub2 = learning_service.submit(student, hw, content_text="v2")
    assert sub2.id == sub.id
    assert sub2.state == SubmissionState.RESUBMITTED
    from CourseManagementApp.learning.models import Grade
    assert not Grade.objects.filter(submission=sub2).exists()

def test_late_submission_flag():
    teacher = baker.make("users.User")
    student = baker.make("users.User")
    course = make_course(teacher)
    baker.make(
        "courses.CourseMembership",
        course=course,
        user=student,
        role=MemberRole.STUDENT,
        added_by=teacher)
    lecture = learning_service.create_lecture(teacher, course, topic="Intro", is_published=True)
    past = timezone.now() - timezone.timedelta(days=1)
    hw = learning_service.create_homework(teacher, lecture, text="Late", due_at=past)
    sub = learning_service.submit(student, hw, content_text="after deadline")
    assert sub.is_late is True
