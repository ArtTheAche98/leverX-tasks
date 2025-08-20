from django.urls import path, include
from rest_framework_nested import routers
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from CourseManagementApp.api.views import (
    CourseViewSet,
    LectureViewSet,
    HomeworkViewSet,
    SubmissionViewSet,
    GradeViewSet,
    GradeCommentViewSet,
    RegistrationView,
)

router = routers.SimpleRouter()
router.register(r"courses", CourseViewSet, basename="course")
router.register(r"grades", GradeViewSet, basename="grade")
router.register(r"grade-comments", GradeCommentViewSet, basename="gradecomment")

courses_router = routers.NestedSimpleRouter(router, r"courses", lookup="course")
courses_router.register(r"lectures", LectureViewSet, basename="course-lectures")

lectures_router = routers.NestedSimpleRouter(courses_router, r"lectures", lookup="lecture")
lectures_router.register(r"homework", HomeworkViewSet, basename="lecture-homework")

homework_router = routers.NestedSimpleRouter(lectures_router, r"homework", lookup="homework")
homework_router.register(r"submissions", SubmissionViewSet, basename="homework-submissions")

urlpatterns = [
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
    path("auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/register/", RegistrationView.as_view(), name="auth-register"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("", include(router.urls)),
    path("", include(courses_router.urls)),
    path("", include(lectures_router.urls)),
    path("", include(homework_router.urls)),
]
