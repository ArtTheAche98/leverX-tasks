"""REST API views for authentication, courses, lectures, homework, submissions, grades and comments."""

from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.db.models import Q

from rest_framework import status, mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied

from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    OpenApiResponse,
    OpenApiParameter,
)

from CourseManagementApp.courses.models import Course, CourseMembership, CourseWaitlistEntry
from CourseManagementApp.core.access import is_teacher, is_owner
from CourseManagementApp.api.mixins import PaginationMixin
from CourseManagementApp.api.throttles import SubmissionRateThrottle
from CourseManagementApp.core.permissions import ParticipantPermission
from CourseManagementApp.core.choices import MemberRole
from CourseManagementApp.domain.services import course_service, learning_service
from CourseManagementApp.learning.models import (
    Lecture,
    Homework,
    Submission,
    Grade,
    GradeComment,
)
from CourseManagementApp.core.permissions import (
    IsCourseTeacher,
    IsCourseTeacherOrOwner,
    ParticipantPermission,
    IsGradeParticipant,
    IsGradeCommentParticipant,
    IsSubmissionAccess,
    IsSubmissionOwner,
)
from CourseManagementApp.api.serializers import (
    RegistrationSerializer,
    UserSerializer,
    CourseWriteSerializer,
    CourseReadSerializer,
    MembershipWriteSerializer,
    LectureWriteSerializer,
    LectureReadSerializer,
    HomeworkWriteSerializer,
    HomeworkReadSerializer,
    SubmissionWriteSerializer,
    SubmissionReadSerializer,
    GradeWriteSerializer,
    GradeReadSerializer,
    GradeCommentWriteSerializer,
    GradeCommentReadSerializer,
    CourseWaitlistEntrySerializer,
    WaitlistRequestSerializer
)

AUTH_RESPONSES = {
    401: OpenApiResponse(description="Authentication required."),
    403: OpenApiResponse(description="Forbidden"),
    404: OpenApiResponse(description="Not Found"),
}

VALIDATION_RESPONSE = {
    422: OpenApiResponse(description="Semantic validation failed."),
}

User = get_user_model()

# ---------- Auth ----------
@extend_schema(
    tags=["Auth"],
    request=RegistrationSerializer,
    responses={201: UserSerializer,**AUTH_RESPONSES, **VALIDATION_RESPONSE},
    description="Register a new user. Teacher role requires staff privileges."
)
class RegistrationView(APIView):
    """User registration endpoint."""
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        """Create a user after validating role constraints."""
        ser = RegistrationSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        user = ser.save()
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


# ---------- Courses ----------
@extend_schema_view(
    list=extend_schema(
        tags=["Courses"],
        responses={
            200: CourseReadSerializer(many=True),
            **AUTH_RESPONSES,
            **VALIDATION_RESPONSE,
        }
    ),
    retrieve=extend_schema(
        tags=["Courses"],
        responses={
            200: CourseReadSerializer,
            **AUTH_RESPONSES,
            **VALIDATION_RESPONSE,
        }
    ),
    create=extend_schema(
        tags=["Courses"],
        request=CourseWriteSerializer,
        responses={
            201: CourseReadSerializer,
            **AUTH_RESPONSES,
            **VALIDATION_RESPONSE,
        },
        extensions = {"x-permissions": {"required_roles": ["teacher", "owner"], "ownership": "owner-on-create"}},
    ),
    update=extend_schema(
        tags=["Courses"],
        request=CourseWriteSerializer,
        responses={
            200: CourseReadSerializer,
            **AUTH_RESPONSES,
            **VALIDATION_RESPONSE,
        },
        extensions = {"x-permissions": {"required_roles": ["teacher", "owner"], "ownership": "owner-on-create"}},
),
    partial_update=extend_schema(
        tags=["Courses"],
        request=CourseWriteSerializer,
        responses={
            200: CourseReadSerializer,
            **AUTH_RESPONSES,
            **VALIDATION_RESPONSE,
        },
        extensions={"x-permissions": {"required_roles": ["teacher", "owner"], "ownership": "owner-on-create"}},
    ),
    destroy=extend_schema(
        tags=["Courses"],
        responses={
            204: OpenApiResponse(description="Deleted"),
            **AUTH_RESPONSES,
            **VALIDATION_RESPONSE,
        },
        extensions={"x-permissions": {"required_roles": ["teacher", "owner"], "ownership": "owner-on-create"}},
    ),
    add_teacher=extend_schema(
        tags=["Membership"],
        request=MembershipWriteSerializer,
        responses={
            200: UserSerializer,
            **AUTH_RESPONSES,
            **VALIDATION_RESPONSE,
        },
        extensions={"x-permissions": {"required_roles": ["teacher", "owner"], "ownership": "owner-on-create"}},
    ),
    add_student=extend_schema(
        tags=["Membership"],
        request=MembershipWriteSerializer,
        responses={
            200: UserSerializer,
            **AUTH_RESPONSES,
            **VALIDATION_RESPONSE,
        },
        extensions={"x-permissions": {"required_roles": ["teacher", "owner"], "ownership": "owner-on-create"}},
    ),
    remove_member=extend_schema(
        tags=["Membership"],
        parameters=[OpenApiParameter("user_id", int, OpenApiParameter.PATH)],
        responses={
            204: OpenApiResponse(description="Removed"),
            **AUTH_RESPONSES,
            **VALIDATION_RESPONSE,
        },
        extensions={"x-permissions": {"required_roles": ["teacher", "owner"], "ownership": "owner-on-create"}},
    ),
    members=extend_schema(
        tags=["Membership"],
        responses={
            200: UserSerializer(many=True),
            **AUTH_RESPONSES,
            **VALIDATION_RESPONSE,
        }
    ),
    request_join = extend_schema(
        tags=["Courses"],
        request=WaitlistRequestSerializer,
        description="Request to join a course (creates a waitlist entry). Optional `message` may be provided.",
        responses={
            201: CourseWaitlistEntrySerializer,
            400: OpenApiResponse(description="Validation error."),
            409: OpenApiResponse(description="Already requested."),
            429: OpenApiResponse(description="Too many requests / throttled."),
            **AUTH_RESPONSES,
            **VALIDATION_RESPONSE,
        },
        extensions={"x-permissions": {"required_roles": ["student"], "ownership": "self"}},
    ),
    waitlist=extend_schema(
        tags=["Courses"],
        responses={
            200: CourseWaitlistEntrySerializer(many=True),
            **AUTH_RESPONSES,
            **VALIDATION_RESPONSE,
        }
    ),
    approve_waitlist=extend_schema(
        tags=["Courses"],
        parameters=[OpenApiParameter("entry_id", int, OpenApiParameter.PATH)],
        responses={
            200: CourseWaitlistEntrySerializer,
            **AUTH_RESPONSES,
            **VALIDATION_RESPONSE,
        },
        extensions={"x-permissions": {"required_roles": ["teacher", "owner"], "ownership": "owner-on-create"}},
    ),
)
class CourseViewSet(PaginationMixin, viewsets.ModelViewSet):

    """CRUD and membership management for courses."""
    queryset = Course.objects.all().select_related("owner")
    serializer_class = CourseWriteSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return CourseReadSerializer
        if self.action == "members":
            return UserSerializer
        if self.action in ("waitlist", "approve_waitlist"):
            return CourseWaitlistEntrySerializer
        return CourseWriteSerializer

    def get_permissions(self) -> list:
        """Respect method-level `permission_classes` if present, otherwise fall back to existing logic."""
        method = getattr(self, self.action, None)
        pcs = getattr(method, "permission_classes", None)
        if pcs:
            perms = []
            for p in pcs:
                perms.append(p() if isinstance(p, type) else p)
            return perms

        teacher_actions = {
            "create", "update", "partial_update", "destroy",
            "add_teacher", "add_student", "remove_member",
            "waitlist", "approve_waitlist",
        }
        if self.action in teacher_actions:
            return [IsAuthenticated(), IsCourseTeacherOrOwner()]
        return [AllowAny()]

    def list(self, request: Request, *args, **kwargs) -> Response:
        """List courses visible to the requesting user."""
        qs = self.get_queryset().order_by("id")
        return self.paginate_and_respond(qs, CourseReadSerializer)

    def retrieve(self, request: Request, *args, **kwargs) -> Response:
        """Retrieve a single course with visibility checks for anonymous users."""
        obj = self.get_object()
        if not request.user.is_authenticated and not (obj.is_public and obj.is_published):
            return Response({"detail": "Not found."}, status=404)
        return Response(CourseReadSerializer(obj).data)

    def get_queryset(self):
        """Return course queryset filtered by visibility."""
        return Course.objects.visible_to(self.request.user).select_related("owner")

    def perform_create(self, serializer) -> None:
        """Delegate course creation to domain service."""
        course = course_service.create_course(self.request.user, serializer.validated_data)
        serializer.instance = course

    def create(self, request: Request, *args, **kwargs) -> Response:
        """Create a course and return read representation."""
        write_ser = self.get_serializer(data=request.data)
        write_ser.is_valid(raise_exception=True)
        self.perform_create(write_ser)
        read_ser = CourseReadSerializer(write_ser.instance, context={"request": request})
        headers = self.get_success_headers(read_ser.data)
        return Response(read_ser.data, status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request: Request, *args, **kwargs) -> Response:
        """Update a course (owner only)."""
        return super().update(request, *args, **kwargs)

    def destroy(self, request: Request, *args, **kwargs) -> Response:
        """Delete a course (owner only)."""
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["get"], url_path="members")
    def members(self, request: Request, pk: int | None = None) -> Response:
        course = self.get_object()
        users = User.objects.filter(course_memberships__course=course).distinct()
        return self.paginate_and_respond(users, UserSerializer)

    @action(detail=True, methods=["post"], url_path="members/add-teacher")
    def add_teacher(self, request: Request, pk: int | None = None) -> Response:
        """Add a teacher to the course."""
        course = self.get_object()
        ser = MembershipWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user_id = int(ser.validated_data["user_id"])
        user = get_object_or_404(User, pk=user_id)
        membership = course_service.add_teacher(request.user, course, user)
        return Response(UserSerializer(membership.user).data)

    @action(detail=True, methods=["post"], url_path="members/add-student")
    def add_student(self, request: Request, pk: int | None = None) -> Response:
        """Add a student to the course."""
        course = self.get_object()
        ser = MembershipWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user_id = int(ser.validated_data["user_id"])
        user = get_object_or_404(User, pk=user_id)
        membership = course_service.add_student(request.user, course, user)
        return Response(UserSerializer(membership.user).data)

    @action(detail=True, methods=["delete"], url_path=r"members/(?P<user_id>\d+)")
    def remove_member(self, request: Request, pk: int | None = None, user_id: int | None = None) -> Response:
        """Remove a member from the course."""
        course = self.get_object()
        user = get_object_or_404(User, pk=user_id)
        course_service.remove_member(request.user, course, user)
        return Response(status=204)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def request_join(self, request: Request, pk: int | None = None) -> Response:
        """Create a waitlist entry for the requesting user."""
        ser = WaitlistRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        if not getattr(request.user, "is_authenticated", False):
            return Response({"detail": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)

        course = self.get_object()
        entry, created = CourseWaitlistEntry.objects.get_or_create(course=course, student=request.user)
        if not created:
            return Response({"detail": "Already requested."}, status=409)
        return Response(CourseWaitlistEntrySerializer(entry).data, status=201)

    @action(detail=True, methods=['get'], permission_classes=[IsCourseTeacherOrOwner])
    def waitlist(self, request: Request, pk: int | None = None) -> Response:
        """List pending waitlist entries."""
        course = self.get_object()
        entries = course.waitlist.filter(approved=None)
        ser = CourseWaitlistEntrySerializer(entries, many=True)
        return Response(ser.data)

    @action(detail=True, methods=['patch'], url_path='waitlist/(?P<entry_id>\\d+)/approve',
            permission_classes=[IsCourseTeacherOrOwner])
    def approve_waitlist(self, request: Request, pk: int | None = None, entry_id: int | None = None) -> Response:
        """Approve a waitlist entry and enroll the student."""
        course = self.get_object()
        entry = get_object_or_404(CourseWaitlistEntry, id=int(entry_id), course=course)
        entry.approved = True
        entry.save(update_fields=["approved"])
        if entry.approved:
            course_service.add_student(course.owner, course, entry.student)
        return Response(CourseWaitlistEntrySerializer(entry).data, status=200)


# ---------- Lectures ----------
@extend_schema_view(
    list=extend_schema(
        tags=["Lectures"],
        responses={
            200: LectureReadSerializer(many=True),
            **AUTH_RESPONSES,
            **VALIDATION_RESPONSE
        }
    ),
    retrieve=extend_schema(
        tags=["Lectures"],
        responses={
            200: LectureReadSerializer,
            **AUTH_RESPONSES,
            **VALIDATION_RESPONSE
        }
    ),
    create=extend_schema(
        tags=["Lectures"],
        request=LectureWriteSerializer,
        responses={
            201: LectureReadSerializer,
            **AUTH_RESPONSES,
            **VALIDATION_RESPONSE
        },
        extensions={"x-permissions": {"required_roles": ["teacher", "owner"], "ownership": "owner-on-create"}},
    ),
    update=extend_schema(
        tags=["Lectures"],
        request=LectureWriteSerializer,
        responses={
            200: LectureReadSerializer,
            **AUTH_RESPONSES,
            **VALIDATION_RESPONSE
        },
        extensions={"x-permissions": {"required_roles": ["teacher", "owner"], "ownership": "owner-on-create"}},
    ),
    partial_update=extend_schema(
        tags=["Lectures"],
        request=LectureWriteSerializer,
        responses={
            200: LectureReadSerializer,
            **AUTH_RESPONSES,
            **VALIDATION_RESPONSE
        },
        extensions={"x-permissions": {"required_roles": ["teacher", "owner"], "ownership": "owner-on-create"}},
    ),
    destroy=extend_schema(
        tags=["Lectures"],
        responses={
            204: OpenApiResponse(description="Deleted"),
            **AUTH_RESPONSES,
            **VALIDATION_RESPONSE
        },
        extensions={"x-permissions": {"required_roles": ["teacher", "owner"], "ownership": "owner-on-create"}},
    ),
)
class LectureViewSet(PaginationMixin, viewsets.ModelViewSet):
    """CRUD for lectures with course membership checks."""
    queryset = Lecture.objects.select_related("course", "created_by")

    def get_permissions(self) -> list:
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [IsAuthenticated(), IsCourseTeacherOrOwner()]
        return [AllowAny()]

    def get_serializer_class(self):
        return LectureWriteSerializer if self.action in ("create", "update", "partial_update") else LectureReadSerializer

    def get_queryset(self):
        """Filter lectures by visibility and optional course."""
        qs = Lecture.objects.select_related("course", "created_by").visible_to(self.request.user)
        course_id = self.kwargs.get("course_pk") or self.request.query_params.get("course")
        if course_id:
            qs = qs.filter(course_id=course_id)
        return qs

    def perform_create(self, serializer) -> None:
        """Create lecture via domain service."""
        course = get_object_or_404(Course, pk=self.kwargs["course_pk"])
        self._created_lecture = learning_service.create_lecture(
            teacher=self.request.user,
            course=course,
            topic=serializer.validated_data["topic"],
            presentation=serializer.validated_data.get("presentation"),
            presentation_url=serializer.validated_data.get("presentation_url"),
            is_published=serializer.validated_data.get("is_published", False),
        )

    def create(self, request: Request, *args, **kwargs) -> Response:
        """Create a lecture."""
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        self.perform_create(ser)
        return Response(LectureReadSerializer(self._created_lecture).data, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer) -> None:
        """Update a lecture (teacher only)."""
        serializer.save()

    def perform_destroy(self, instance) -> None:
        """Delete a lecture (teacher only).
        Deletion policy: *prohibit* deletion when dependent homework/submissions exist.
        """
        if Submission.objects.filter(homework__lecture=instance).exists():
            raise PermissionDenied("Lecture cannot be deleted while dependent submissions exist.")
        super().perform_destroy(instance)

# ---------- Homework ----------
@extend_schema_view(
    list=extend_schema(
        tags=["Homework"],
        responses={
            200: HomeworkReadSerializer(many=True),
            **AUTH_RESPONSES,
            **VALIDATION_RESPONSE
        }
    ),
    retrieve=extend_schema(
        tags=["Homework"],
        responses={
            200: HomeworkReadSerializer,
            **AUTH_RESPONSES,
            **VALIDATION_RESPONSE
        }
    ),
    create=extend_schema(
        tags=["Homework"],
        request=HomeworkWriteSerializer,
        responses={
            201: HomeworkReadSerializer,
            **AUTH_RESPONSES,
            **VALIDATION_RESPONSE
        },
        extensions={"x-permissions": {"required_roles": ["teacher", "owner"], "ownership": "owner-on-create"}},
    ),
    update=extend_schema(
        tags=["Homework"],
        request=HomeworkWriteSerializer,
        responses={
            200: HomeworkReadSerializer,
            **AUTH_RESPONSES,
            **VALIDATION_RESPONSE
        },
        extensions={"x-permissions": {"required_roles": ["teacher", "owner"], "ownership": "owner-on-create"}},
    ),
    partial_update=extend_schema(
        tags=["Homework"],
        request=HomeworkWriteSerializer,
        responses={
            200: HomeworkReadSerializer,
            **AUTH_RESPONSES,
            **VALIDATION_RESPONSE
        },
        extensions={"x-permissions": {"required_roles": ["teacher", "owner"], "ownership": "owner-on-create"}},
    ),
    destroy=extend_schema(
        tags=["Homework"],
        responses={
            204: OpenApiResponse(description="Deleted"),
            **AUTH_RESPONSES,
            **VALIDATION_RESPONSE
        },
        extensions={"x-permissions": {"required_roles": ["teacher", "owner"], "ownership": "owner-on-create"}},
    )
)
@extend_schema(
    parameters=[
        OpenApiParameter("course_pk", int, OpenApiParameter.PATH),
        OpenApiParameter("lecture_pk", int, OpenApiParameter.PATH),
    ]
)
class HomeworkViewSet(viewsets.ModelViewSet):
    """CRUD for homework assignments."""
    queryset = Homework.objects.select_related("lecture", "lecture__course")

    def get_permissions(self) -> list:
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [IsAuthenticated(), IsCourseTeacherOrOwner()]
        return [AllowAny()]

    def get_serializer_class(self):
        return HomeworkWriteSerializer if self.action in ("create", "update", "partial_update") else HomeworkReadSerializer

    def get_queryset(self):
        """Filter homework by visibility and optional lecture."""
        qs = Homework.objects.select_related("lecture", "lecture__course").visible_to(self.request.user)
        lecture_id = self.kwargs.get("lecture_pk") or self.request.query_params.get("lecture")
        if lecture_id:
            qs = qs.filter(lecture_id=lecture_id)
        return qs

    def perform_create(self, serializer) -> None:
        """Create homework via domain service."""
        lecture = get_object_or_404(Lecture, pk=self.kwargs["lecture_pk"])
        self._created_homework = learning_service.create_homework(
            teacher=self.request.user,
            lecture=lecture,
            text=serializer.validated_data["text"],
            due_at=serializer.validated_data.get("due_at"),
            is_active=serializer.validated_data.get("is_active", True),
        )

    def create(self, request: Request, *args, **kwargs) -> Response:
        """Create homework."""
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        self.perform_create(ser)
        return Response(HomeworkReadSerializer(self._created_homework).data, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer) -> None:
        """Update homework (teacher only)."""
        serializer.save()

    def perform_destroy(self, instance) -> None:
        """Delete homework (teacher only)."""
        super().perform_destroy(instance)


# ---------- Submissions ----------
@extend_schema_view(
    list=extend_schema(
        tags=["Submissions"],
        responses={
            200: SubmissionReadSerializer(many=True),
            **AUTH_RESPONSES,
        }
    ),
    retrieve=extend_schema(
        tags=["Submissions"],
        responses={
            200: SubmissionReadSerializer,
            **AUTH_RESPONSES,
        }
    ),
    create=extend_schema(
        tags=["Submissions"],
        request=SubmissionWriteSerializer,
        description=(
            "Create a submission. Endpoint is rate-limited; clients SHOULD provide an "
            "`Idempotency-Key` header to avoid duplicate writes on retries. Server will return "
            "rate-limit headers (e.g. `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `Retry-After`)."
        ),
        parameters=[
            OpenApiParameter("Idempotency-Key", str, OpenApiParameter.HEADER, required=False,
                             description="Client-provided idempotency key to deduplicate requests.")
        ],
        responses={
            201: SubmissionReadSerializer,
            400: OpenApiResponse(description="Validation error."),
            429: OpenApiResponse(description="Too many requests / throttled."),
            **AUTH_RESPONSES,
            **VALIDATION_RESPONSE,
        },
        extensions={"x-permissions": {"required_roles": ["student"], "ownership": "self"}},
    ),
    partial_update=extend_schema(
        tags=["Submissions"],
        request=SubmissionWriteSerializer,
        description=(
            "Update / resubmit a submission. Same throttling/idempotency guidance as create. "
            "Clients MAY supply `Idempotency-Key` to deduplicate retries."
        ),
        parameters=[
            OpenApiParameter("Idempotency-Key", str, OpenApiParameter.HEADER, required=False,
                             description="Client-provided idempotency key to deduplicate requests.")
        ],
        responses={
            200: SubmissionReadSerializer,
            400: OpenApiResponse(description="Validation error."),
            429: OpenApiResponse(description="Too many requests / throttled."),
            **AUTH_RESPONSES,
            **VALIDATION_RESPONSE,
        },
        extensions={"x-permissions": {"required_roles": ["student"], "ownership": "submission-owner"}},
    ),
)
@extend_schema(
    parameters=[
        OpenApiParameter("course_pk", int, OpenApiParameter.PATH),
        OpenApiParameter("lecture_pk", int, OpenApiParameter.PATH),
        OpenApiParameter("homework_pk", int, OpenApiParameter.PATH),
    ]
)
class SubmissionViewSet(
    PaginationMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """Submission creation, update and listing with throttling."""

    permission_classes = [IsAuthenticated, IsSubmissionAccess, ParticipantPermission]
    throttle_classes: list[type] = []
    queryset = Submission.objects.select_related("homework__lecture__course", "student", "grade")

    def get_serializer_class(self):
        return SubmissionWriteSerializer if self.action in ("create", "update", "partial_update") else SubmissionReadSerializer

    def get_throttles(self):
        """Apply rate throttle only on create."""
        if self.action == "create":
            self.throttle_classes = [SubmissionRateThrottle]
        return super().get_throttles()

    def get_queryset(self):
        """Restrict submissions to user unless teacher."""
        user = self.request.user
        qs = self.queryset
        hw_id = self.kwargs.get("homework_pk")
        if hw_id:
            qs = qs.filter(homework_id=hw_id)
            is_teacher = CourseMembership.objects.filter(
                course__lectures__homeworks__id=hw_id, user=user, role=MemberRole.TEACHER
            ).exists()
        else:
            is_teacher = CourseMembership.objects.filter(user=user, role=MemberRole.TEACHER).exists()
        if not is_teacher:
            qs = qs.filter(student=user)
        return qs

    def create(self, request: Request, *args, **kwargs) -> Response:
        """Create a submission."""
        ser = SubmissionWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        homework = get_object_or_404(
            Homework.objects.select_related("lecture__course"), pk=self.kwargs.get("homework_pk")
        )
        submission = learning_service.submit(
            request.user,
            homework,
            content_text=ser.validated_data.get("content_text", ""),
            attachment=ser.validated_data.get("attachment"),
        )
        read = SubmissionReadSerializer(submission)
        return Response(read.data, status=status.HTTP_201_CREATED)

    def partial_update(self, request: Request, *args, **kwargs) -> Response:
        """Update a submission (resubmit)."""
        submission = self.get_object()
        ser = SubmissionWriteSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        updated = learning_service.submit(
            request.user,
            submission.homework,
            content_text=ser.validated_data.get("content_text", submission.content_text),
            attachment=ser.validated_data.get("attachment", submission.attachment),
        )
        return Response(SubmissionReadSerializer(updated).data)

    @extend_schema(
        tags=["Grades"],
        request=GradeWriteSerializer,
        responses={
            201: GradeReadSerializer,
            **AUTH_RESPONSES
        },
        extensions={"x-permissions": {"required_roles": ["teacher", "owner"], "ownership": "owner-on-create"}},
    )
    @action(detail=True, methods=["post"], url_path="grade", permission_classes=[IsAuthenticated, IsCourseTeacher])
    def grade(self, request: Request, pk: int | None = None, *args, **kwargs) -> Response:
        """Grade a submission (teacher or owner)."""
        submission = self.get_object()
        ser = GradeWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        grade = learning_service.grade_submission(
            request.user,
            submission,
            ser.validated_data["value"],
            ser.validated_data.get("comment", ""),
        )
        return Response(GradeReadSerializer(grade).data, status=status.HTTP_201_CREATED)


# ---------- Grades ----------
@extend_schema_view(
    retrieve=extend_schema(
        tags=["Grades"],
        responses={
            200: GradeReadSerializer,
            **AUTH_RESPONSES,
        }
    ),
    update=extend_schema(
        tags=["Grades"],
        request=GradeWriteSerializer,
        responses={
            200: GradeReadSerializer,
            **AUTH_RESPONSES,
        }
    ),
    partial_update=extend_schema(
        tags=["Grades"],
        request=GradeWriteSerializer,
        responses={
            200: GradeReadSerializer,
            **AUTH_RESPONSES,
        }
    ),
)
class GradeViewSet(
    PaginationMixin,
    viewsets.GenericViewSet,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin):
    """View and update grades."""
    queryset = Grade.objects.select_related(
        "submission__homework__lecture__course", "graded_by", "submission__student"
    )
    permission_classes = [IsAuthenticated, ParticipantPermission]

    def get_serializer_class(self):
        return GradeWriteSerializer if self.action in ("update", "partial_update") else GradeReadSerializer

    def partial_update(self, request: Request, pk: int | None = None) -> Response:
        """Partially update grade (value or comment)."""
        grade = self.get_object()
        ser = GradeWriteSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        value = ser.validated_data.get("value", grade.value)
        comment = ser.validated_data.get("comment", grade.comment)
        updated = learning_service.grade_submission(request.user, grade.submission, value, comment)
        return Response(GradeReadSerializer(updated).data)

    def update(self, request: Request, *args, **kwargs) -> Response:
        """Alias to partial_update for full update."""
        return self.partial_update(request, *args, **kwargs)

    @extend_schema(
        tags=["Grades"],
        parameters=[OpenApiParameter("submission_id", int, OpenApiParameter.PATH)],
        responses={
            200: GradeReadSerializer,
            **AUTH_RESPONSES,
        },
        extensions={"x-permissions": {"required_roles": ["student"], "ownership": "submission-owner"}},
    )
    @action(detail=False, methods=["get"], url_path=r"submission/(?P<submission_id>\d+)", permission_classes=[IsAuthenticated, ParticipantPermission])
    def by_submission(self, request: Request, submission_id: int | None = None) -> Response:
        """Retrieve grade for a submission if permitted."""
        submission = get_object_or_404(Submission.objects.select_related("homework__lecture__course"), id=submission_id)
        grade = getattr(submission, "grade", None)
        if not grade:
            return Response({"detail": "No grade"}, status=404)
        return Response(GradeReadSerializer(grade).data)


# ---------- Grade Comments ----------
@extend_schema_view(
    list=extend_schema(
        tags=["GradeComments"],
        responses={
            200: GradeCommentReadSerializer(many=True),
            **AUTH_RESPONSES,
        }
    ),
    retrieve=extend_schema(
        tags=["GradeComments"],
        responses={
            200: GradeCommentReadSerializer,
            **AUTH_RESPONSES,
        }
    ),
    create=extend_schema(
        tags=["GradeComments"],
        request=GradeCommentWriteSerializer,
        responses={
            201: GradeCommentReadSerializer,
            **AUTH_RESPONSES,
        }
    ),
    update=extend_schema(
        tags=["GradeComments"],
        request=GradeCommentWriteSerializer,
        responses={
            200: GradeCommentReadSerializer,
            **AUTH_RESPONSES,
        }
    ),
    partial_update=extend_schema(
        tags=["GradeComments"],
        request=GradeCommentWriteSerializer,
        responses={
            200: GradeCommentReadSerializer,
            **AUTH_RESPONSES,
        }
    ),
    destroy=extend_schema(
        tags=["GradeComments"],
        responses={
            204: OpenApiResponse(description="Deleted"),
            **AUTH_RESPONSES,
        }
    ),
)
class GradeCommentViewSet(PaginationMixin, viewsets.ModelViewSet):
    """CRUD for grade comments with participant restrictions."""
    queryset = GradeComment.objects.select_related(
        "grade__submission__homework__lecture__course", "author", "grade__submission__student"
    )
    permission_classes = [IsAuthenticated, ParticipantPermission]

    def get_permissions(self):
        if self.action in ("create", "destroy"):
            return [IsAuthenticated(), IsGradeCommentParticipant()]
        return [IsAuthenticated(), ParticipantPermission()]

    def get_serializer_class(self):
        return GradeCommentWriteSerializer if self.action in ("create", "update", "partial_update") else GradeCommentReadSerializer

    def get_queryset(self):
        """Filter comments to those visible to the user."""
        user = self.request.user
        qs = super().get_queryset()
        grade_id = self.request.query_params.get("grade")
        if grade_id:
            qs = qs.filter(grade_id=grade_id)
        return qs.filter(
            Q(author=user) |
            Q(grade__submission__student=user) |
            Q(grade__submission__homework__lecture__course__memberships__user=user,
              grade__submission__homework__lecture__course__memberships__role=MemberRole.TEACHER)
        ).distinct()

    def perform_create(self, serializer) -> None:
        """Create comment if author is student or teacher."""
        serializer.save(author=self.request.user)

    def destroy(self, request: Request, *args, **kwargs) -> Response:
        """Delete comment (author or teacher only)."""
        return super().destroy(request, *args, **kwargs)
