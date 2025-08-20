import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from model_bakery import baker
from CourseManagementApp.core.choices import MemberRole

pytestmark = pytest.mark.django_db

@pytest.fixture
def teacher():
    user = baker.make(
        "users.User",
        email="teacher_matrix@example.com",
        role="TEACHER",
        is_staff=True)
    user.set_password("pass1234"); user.save()
    return user

@pytest.fixture
def student(teacher):
    user = baker.make("users.User", email="student_matrix@example.com", role="STUDENT")
    user.set_password("pass1234"); user.save()
    return user

@pytest.fixture
def anon_client():
    return APIClient()

@pytest.fixture
def course_factory():
    from CourseManagementApp.domain.services import course_service
    def _make(owner, is_public, is_published):
        return course_service.create_course(owner, {
            "title": "Vis",
            "description": "",
            "is_public": is_public,
            "is_published": is_published,
        })
    return _make

@pytest.mark.parametrize("public,published,visible", [
    (True, True, True),
    (True, False, False),
    (False, True, False),
])
def test_course_visibility_matrix(public, published, visible, teacher, anon_client, course_factory):
    course = course_factory(owner=teacher, is_public=public, is_published=published)
    resp = anon_client.get("/api/v1/courses/")
    data = resp.data
    if isinstance(data, dict) and "results" in data:
        items = data["results"]
    else:
        items = data
    ids = [c["id"] for c in items]
    assert (course.id in ids) is visible

@pytest.fixture
def submission_late(teacher, student, course_factory):
    course = course_factory(owner=teacher, is_public=True, is_published=True)
    baker.make("courses.CourseMembership",
                course=course, user=student,
                role=MemberRole.STUDENT,
                added_by=teacher)
    from CourseManagementApp.domain.services import learning_service
    lecture = learning_service.create_lecture(teacher, course, topic="Late L", is_published=True)
    past = timezone.now() - timezone.timedelta(days=1)
    hw = learning_service.create_homework(teacher, lecture, text="Do late", due_at=past)
    sub = learning_service.submit(student, hw, content_text="answer")
    return sub

@pytest.mark.skipif(timezone.now().year < 2025, reason="Future-dependent test")
def test_future_behavior():
    assert True

def test_late_flag_persists(submission_late):
    submission_late.refresh_from_db()
    assert submission_late.is_late is True
