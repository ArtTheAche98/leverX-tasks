import pytest
from rest_framework.test import APIClient
from model_bakery import baker
from CourseManagementApp.core.choices import MemberRole

pytestmark = pytest.mark.django_db

def login(user):
    client = APIClient()
    token = client.post("/api/v1/auth/token/", {"email": user.email, "password": "pass1234"}, format="json").data["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client

@pytest.fixture
def teacher():
    u = baker.make("users.User", email="t2@example.com", role="TEACHER", is_staff=True)
    u.set_password("pass1234"); u.save()
    return u

@pytest.fixture
def student():
    u = baker.make("users.User", email="s2@example.com", role="STUDENT")
    u.set_password("pass1234"); u.save()
    return u

@pytest.fixture
def course(teacher):
    from CourseManagementApp.domain.services import course_service
    return course_service.create_course(teacher, {"title": "X", "description": "", "is_public": True, "is_published": True})

@pytest.fixture
def lecture(course, teacher):
    from CourseManagementApp.domain.services import learning_service
    return learning_service.create_lecture(teacher, course, "L1", is_published=True)

@pytest.fixture
def homework(lecture, teacher):
    from CourseManagementApp.domain.services import learning_service
    return learning_service.create_homework(teacher, lecture, "HW")

def test_submit_and_grade(teacher, student, course, lecture, homework):
    baker.make("courses.CourseMembership", course=course, user=student, role=MemberRole.STUDENT, added_by=teacher)

    s_client = login(student)
    post = s_client.post(
        f"/api/v1/courses/{course.id}/lectures/{lecture.id}/homework/{homework.id}/submissions/",
        {"content_text": "answer"},
        format="multipart"
    )
    assert post.status_code == 201
    submission_id = post.data["id"]

    t_client = login(teacher)
    grade_resp = t_client.post(
        f"/api/v1/courses/{course.id}/lectures/{lecture.id}/homework/{homework.id}/submissions/{submission_id}/grade/",
        {"submission": submission_id, "value": 95, "comment": "Great"},
        format="json"
    )
    assert grade_resp.status_code == 201
    assert grade_resp.data["value"] == 95