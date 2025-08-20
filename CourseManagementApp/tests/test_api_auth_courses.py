import pytest
from rest_framework.test import APIClient
from model_bakery import baker

pytestmark = pytest.mark.django_db

REGISTER_URL = "/api/v1/auth/register/"
TOKEN_URL = "/api/v1/auth/token/"
COURSES_URL = "/api/v1/courses/"

def auth_client(user):
    client = APIClient()
    token_resp = client.post(TOKEN_URL, {"email": user.email, "password": "pass1234"}, format="json")
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token_resp.data['access']}")
    return client

@pytest.fixture
def teacher():
    u = baker.make("users.User", email="t@example.com", role="TEACHER")
    u.set_password("pass1234")
    u.is_staff = True
    u.save()
    return u

@pytest.fixture
def student():
    u = baker.make("users.User", email="s@example.com", role="STUDENT")
    u.set_password("pass1234")
    u.save()
    return u

def test_course_create_and_visibility(teacher, student):
    t_client = auth_client(teacher)
    resp = t_client.post(COURSES_URL, {"title": "Algebra", "description": "", "is_public": True, "is_published": True}, format="json")
    assert resp.status_code == 201
    course_id = resp.data["id"]

    anon = APIClient()
    list_resp = anon.get(COURSES_URL)
    data = list_resp.data
    if isinstance(data, dict) and "results" in data:
        courses = data["results"]
    else:
        courses = data
    assert any(c["id"] == course_id for c in courses)

    s_client = auth_client(student)
    upd = s_client.patch(f"{COURSES_URL}{course_id}/", {"title": "Hack"}, format="json")
    assert upd.status_code == 403

def test_teacher_add_student_membership(teacher, student):
    t_client = auth_client(teacher)
    c_resp = t_client.post(COURSES_URL, {"title": "Course", "description": "", "is_public": False, "is_published": False}, format="json")
    course_id = c_resp.data["id"]
    add_resp = t_client.post(f"{COURSES_URL}{course_id}/members/add-student/", {"user_id": student.id, "role": "STUDENT"}, format="json")
    assert add_resp.status_code == 200