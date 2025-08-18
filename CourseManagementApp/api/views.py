from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.exceptions import PermissionDenied

from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.contrib.auth import get_user_model
from drf_spectacular.utils import (
    extend_schema, extend_schema_view, OpenApiParameter, OpenApiResponse
)

from CourseManagementApp.courses.models import Course, CourseMembership
from CourseManagementApp.learning.models import Lecture, Homework, Submission, Grade, GradeComment
from CourseManagementApp.core.choices import MemberRole
from CourseManagementApp.domain.services import course_service, learning_service
from CourseManagementApp.core.permissions import (
    IsCourseOwner, IsCourseTeacher, IsSubmissionParticipant,
    IsGradeParticipant, IsGradeCommentParticipant
)
from CourseManagementApp.api.serializers import (
    RegistrationSerializer, UserSerializer,
    CourseWriteSerializer, CourseReadSerializer, MembershipWriteSerializer,
    LectureWriteSerializer, LectureReadSerializer,
    HomeworkWriteSerializer, HomeworkReadSerializer,
    SubmissionWriteSerializer, SubmissionReadSerializer,
    GradeWriteSerializer, GradeReadSerializer,
    GradeCommentWriteSerializer, GradeCommentReadSerializer,
)

User = get_user_model()


@extend_schema_view(
    list=extend_schema(tags=["Courses"]),
    retrieve=extend_schema(tags=["Courses"]),
    create=extend_schema(tags=["Courses"], responses={201: OpenApiResponse(response=CourseReadSerializer)}),
    update=extend_schema(tags=["Courses"]),
    partial_update=extend_schema(tags=["Courses"]),
    destroy=extend_schema(tags=["Courses"], responses={204: OpenApiResponse(description="Deleted")}),
    course_lectures=extend_schema(
        tags=["Lectures"],
        parameters=[OpenApiParameter("pk", int, OpenApiParameter.PATH)],
        responses={200: LectureReadSerializer(many=True)}
    ),
    teachers=extend_schema(tags=["Courses"], responses={204: OpenApiResponse(description="Added")}),
    students=extend_schema(tags=["Courses"], responses={204: OpenApiResponse(description="Added")}),
)
class CourseViewSet(viewsets.ModelViewSet):
    queryset = Course.objects.select_related("owner")

    def get_permissions(self):
        if self.action in ("update", "partial_update", "destroy"):
            return [IsCourseOwner()]
        if self.action in ("teachers", "students", "remove_teacher", "remove_student"):
            return [IsCourseTeacher()]
        return [IsAuthenticated()]

    def get_queryset(self):
        return Course.objects.visible_to(self.request.user).select_related("owner")

    def get_serializer_class(self):
        return CourseWriteSerializer if self.action in ("create", "update", "partial_update") else CourseReadSerializer

    def perform_create(self, serializer):
        self._created_course = course_service.create_course(self.request.user, serializer.validated_data)

    def create(self, request, *args, **kwargs):
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        self.perform_create(ser)
        return Response(CourseReadSerializer(self._created_course).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        course = self.get_object()
        if course.owner_id != request.user.id:
            return Response({"detail": "Only owner can update"}, status=403)
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        course = self.get_object()
        if course.owner_id != request.user.id:
            return Response({"detail": "Only owner can delete"}, status=403)
        return super().destroy(request, *args, **kwargs)

    def _require_teacher(self, request, course):
        if not CourseMembership.objects.filter(course=course, user=request.user, role=MemberRole.TEACHER).exists():
            return Response({"detail": "Teacher role required"}, status=403)

    @action(detail=True, methods=["post"])
    def teachers(self, request, pk=None):
        course = self.get_object()
        resp = self._require_teacher(request, course)
        if resp: return resp
        ser = MembershipWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        if ser.validated_data["role"] != MemberRole.TEACHER:
            return Response({"detail": "role must be TEACHER"}, status=400)
        user = get_object_or_404(User, id=ser.validated_data["user_id"])
        course_service.add_teacher(request.user, course, user)
        return Response(status=204)

    @teachers.mapping.delete
    def remove_teacher(self, request, pk=None):
        course = self.get_object()
        resp = self._require_teacher(request, course)
        if resp: return resp
        user_id = request.query_params.get("user_id")
        user = get_object_or_404(User, id=user_id)
        course_service.remove_member(request.user, course, user)
        return Response(status=204)

    @action(detail=True, methods=["post"])
    def students(self, request, pk=None):
        course = self.get_object()
        resp = self._require_teacher(request, course)
        if resp: return resp
        ser = MembershipWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        if ser.validated_data["role"] != MemberRole.STUDENT:
            return Response({"detail": "role must be STUDENT"}, status=400)
        user = get_object_or_404(User, id=ser.validated_data["user_id"])
        course_service.add_student(request.user, course, user)
        return Response(status=204)

    @students.mapping.delete
    def remove_student(self, request, pk=None):
        course = self.get_object()
        resp = self._require_teacher(request, course)
        if resp: return resp
        user_id = request.query_params.get("user_id")
        user = get_object_or_404(User, id=user_id)
        course_service.remove_member(request.user, course, user)
        return Response(status=204)

    @action(detail=True, methods=["get"], url_path="lectures")
    def course_lectures(self, request, pk=None):
        course = self.get_object()
        qs = Lecture.objects.filter(course=course)
        if not CourseMembership.objects.filter(course=course, user=request.user).exists() and course.owner_id != request.user.id:
            qs = qs.filter(is_published=True, course__is_published=True, course__is_public=True)
        page = self.paginate_queryset(qs)
        ser = LectureReadSerializer(page or qs, many=True)
        if page is not None:
            return self.get_paginated_response(ser.data)
        return Response(ser.data)


@extend_schema_view(
    list=extend_schema(tags=["Lectures"]),
    retrieve=extend_schema(tags=["Lectures"]),
    create=extend_schema(tags=["Lectures"], request=LectureWriteSerializer, responses={201: LectureReadSerializer}),
    update=extend_schema(tags=["Lectures"], request=LectureWriteSerializer),
    partial_update=extend_schema(tags=["Lectures"], request=LectureWriteSerializer),
    destroy=extend_schema(tags=["Lectures"], responses={204: OpenApiResponse(description="Deleted")}),
    lecture_homework=extend_schema(
        tags=["Homework"], responses={200: HomeworkReadSerializer(many=True)}
    ),
)
class LectureViewSet(viewsets.ModelViewSet):
    queryset = Lecture.objects.select_related("course", "created_by")

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [IsAuthenticated(), IsCourseTeacher()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        return LectureWriteSerializer if self.action in ("create", "update", "partial_update") else LectureReadSerializer

    def get_queryset(self):
        qs = Lecture.objects.select_related("course", "created_by").visible_to(self.request.user)
        course_id = self.kwargs.get("course_pk") or self.request.query_params.get("course")
        if course_id:
            qs = qs.filter(course_id=course_id)
        return qs

    def perform_create(self, serializer):
        course = get_object_or_404(Course, pk=self.kwargs["course_pk"])
        self._created_lecture = learning_service.create_lecture(
            teacher=self.request.user,
            course=course,
            topic=serializer.validated_data["topic"],
            presentation=serializer.validated_data.get("presentation"),
            is_published=serializer.validated_data.get("is_published", False),
        )

    def create(self, request, *args, **kwargs):
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        self.perform_create(ser)
        return Response(LectureReadSerializer(self._created_lecture).data, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        lecture = self.get_object()
        if not CourseMembership.objects.filter(course=lecture.course, user=self.request.user,
                                               role=MemberRole.TEACHER).exists():
            raise PermissionDenied("Only teachers can modify lectures")
        serializer.save()

    def perform_destroy(self, instance):
        if not CourseMembership.objects.filter(course=instance.course, user=self.request.user,
                                               role=MemberRole.TEACHER).exists():
            raise PermissionDenied("Only teachers can delete lectures")
        super().perform_destroy(instance)

    @action(detail=True, methods=["get"], url_path="homework")
    def lecture_homework(self, request, pk=None):
        lecture = self.get_object()
        qs = lecture.homeworks.all()
        if not CourseMembership.objects.filter(course=lecture.course, user=request.user).exists() and lecture.course.owner_id != request.user.id:
            qs = qs.none()
        page = self.paginate_queryset(qs)
        ser = HomeworkReadSerializer(page or qs, many=True)
        if page is not None:
            return self.get_paginated_response(ser.data)
        return Response(ser.data)


@extend_schema_view(
    list=extend_schema(tags=["Homework"]),
    retrieve=extend_schema(tags=["Homework"]),
    create=extend_schema(tags=["Homework"], request=HomeworkWriteSerializer, responses={201: HomeworkReadSerializer}),
    update=extend_schema(tags=["Homework"], request=HomeworkWriteSerializer),
    partial_update=extend_schema(tags=["Homework"], request=HomeworkWriteSerializer),
    destroy=extend_schema(tags=["Homework"], responses={204: OpenApiResponse(description="Deleted")}),
    homework_submissions=extend_schema(
        tags=["Submissions"], responses={200: SubmissionReadSerializer(many=True)}
    ),
)
class HomeworkViewSet(viewsets.ModelViewSet):
    queryset = Homework.objects.select_related("lecture", "lecture__course")

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [IsAuthenticated(), IsCourseTeacher()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        return HomeworkWriteSerializer if self.action in ("create", "update", "partial_update") else HomeworkReadSerializer

    def get_queryset(self):
        qs = Homework.objects.select_related("lecture", "lecture__course").visible_to(self.request.user)
        lecture_id = self.kwargs.get("lecture_pk") or self.request.query_params.get("lecture")
        if lecture_id:
            qs = qs.filter(lecture_id=lecture_id)
        return qs

    def perform_create(self, serializer):
        lecture = get_object_or_404(Lecture, pk=self.kwargs["lecture_pk"])
        self._created_homework = learning_service.create_homework(
            teacher=self.request.user,
            lecture=lecture,
            text=serializer.validated_data["text"],
            due_at=serializer.validated_data.get("due_at"),
            is_active=serializer.validated_data.get("is_active", True),
        )

    def create(self, request, *args, **kwargs):
        ser = self.get_serializer(data=request.body and request.data)
        ser.is_valid(raise_exception=True)
        self.perform_create(ser)
        return Response(HomeworkReadSerializer(self._created_homework).data, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        hw = self.get_object()
        if not CourseMembership.objects.filter(course=hw.lecture.course, user=self.request.user,
                                               role=MemberRole.TEACHER).exists():
            raise PermissionDenied("Only teachers can modify homework")
        serializer.save()

    def perform_destroy(self, instance):
        if not CourseMembership.objects.filter(course=instance.lecture.course, user=self.request.user,
                                               role=MemberRole.TEACHER).exists():
            raise PermissionDenied("Only teachers can delete homework")
        super().perform_destroy(instance)

    @action(detail=True, methods=["get"], url_path="submissions")
    def homework_submissions(self, request, pk=None):
        hw = self.get_object()
        is_teacher = CourseMembership.objects.filter(
            course=hw.lecture.course, user=request.user, role=MemberRole.TEACHER
        ).exists()
        if not is_teacher and hw.lecture.course.owner_id != request.user.id:
            return Response({"detail": "Forbidden"}, status=403)
        qs = hw.submissions.select_related("student", "grade")
        page = self.paginate_queryset(qs)
        ser = SubmissionReadSerializer(page or qs, many=True)
        if page is not None:
            return self.get_paginated_response(ser.data)
        return Response(ser.data)


@extend_schema_view(
    retrieve=extend_schema(tags=["Submissions"]),
    create=extend_schema(
        tags=["Submissions"],
        request=SubmissionWriteSerializer,
        responses={201: SubmissionReadSerializer, 403: OpenApiResponse(description="Forbidden"), 404: OpenApiResponse(description="Not found")}
    ),
    partial_update=extend_schema(
        tags=["Submissions"],
        request=SubmissionWriteSerializer,
        responses={200: SubmissionReadSerializer}
    ),
    destroy=extend_schema(tags=["Submissions"], responses={204: OpenApiResponse(description="Deleted")}),
    mine=extend_schema(tags=["Submissions"], responses={200: SubmissionReadSerializer(many=True)}),
    grade=extend_schema(
        tags=["Grades"],
        request=GradeWriteSerializer,
        responses={201: GradeReadSerializer, 403: OpenApiResponse(description="Forbidden")}
    ),
    homework_submissions=extend_schema(
        tags=["Submissions"],
        parameters=[OpenApiParameter("homework_id", int, OpenApiParameter.PATH)],
        responses={200: SubmissionReadSerializer(many=True), 403: OpenApiResponse(description="Forbidden")}
    ),
)
class SubmissionViewSet(viewsets.GenericViewSet,
                        mixins.CreateModelMixin,
                        mixins.RetrieveModelMixin,
                        mixins.DestroyModelMixin):
    queryset = Submission.objects.select_related("homework__lecture__course", "student", "grade")

    def get_permissions(self):
        if self.action in ("create", "mine", "homework_submissions", "grade"):
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsSubmissionParticipant()]

    def get_serializer_class(self):
        return SubmissionWriteSerializer if self.action in ("create", "partial_update") else SubmissionReadSerializer

    def create(self, request, *args, **kwargs):
        ser = SubmissionWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        homework_id = request.data.get("homework")
        hw = get_object_or_404(Homework.objects.select_related("lecture__course"), id=homework_id)
        submission = learning_service.submit(
            student=request.user,
            homework=hw,
            content_text=ser.validated_data.get("content_text", ""),
            attachment=ser.validated_data.get("attachment"),
        )
        return Response(SubmissionReadSerializer(submission).data, status=201)

    def partial_update(self, request, pk=None):
        submission = self.get_object()
        ser = SubmissionWriteSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        # Resubmit
        updated = learning_service.submit(
            student=request.user,
            homework=submission.homework,
            content_text=ser.validated_data.get("content_text", submission.content_text),
            attachment=ser.validated_data.get("attachment", submission.attachment),
        )
        return Response(SubmissionReadSerializer(updated).data)

    @action(detail=False, methods=["get"])
    def mine(self, request):
        qs = Submission.objects.for_student(request.user).select_related("homework__lecture__course", "grade", "student")
        page = self.paginate_queryset(qs)
        ser = SubmissionReadSerializer(page or qs, many=True)
        if page is not None:
            return self.get_paginated_response(ser.data)
        return Response(ser.data)

    @action(detail=True, methods=["post"], url_path="grade")
    def grade(self, request, pk=None):
        submission = self.get_object()
        value = int(request.data.get("value", -1))
        comment = request.data.get("comment", "")
        grade = learning_service.grade_submission(request.user, submission, value, comment)
        return Response(GradeReadSerializer(grade).data, status=201)

    @action(detail=False, methods=["get"], url_path=r"homework/(?P<homework_id>\d+)/submissions")
    def homework_submissions(self, request, homework_id=None):
        hw = get_object_or_404(Homework.objects.select_related("lecture__course"), id=homework_id)
        is_teacher = CourseMembership.objects.filter(
            course=hw.lecture.course, user=request.user, role=MemberRole.TEACHER
        ).exists()
        if not is_teacher and hw.lecture.course.owner_id != request.user.id:
            return Response({"detail": "Forbidden"}, status=403)
        qs = Submission.objects.filter(homework=hw).select_related("grade", "student")
        page = self.paginate_queryset(qs)
        ser = SubmissionReadSerializer(page or qs, many=True)
        if page is not None:
            return self.get_paginated_response(ser.data)
        return Response(ser.data)


@extend_schema_view(
    retrieve=extend_schema(tags=["Grades"]),
    update=extend_schema(tags=["Grades"], request=GradeWriteSerializer, responses={200: GradeReadSerializer}),
    partial_update=extend_schema(tags=["Grades"], request=GradeWriteSerializer, responses={200: GradeReadSerializer}),
    mine=extend_schema(tags=["Grades"], responses={200: GradeReadSerializer(many=True)}),
    by_submission=extend_schema(
        tags=["Grades"],
        parameters=[OpenApiParameter("submission_id", int, OpenApiParameter.PATH)],
        responses={200: GradeReadSerializer, 404: OpenApiResponse(description="No grade")}
    ),
)
class GradeViewSet(viewsets.GenericViewSet,
                   mixins.RetrieveModelMixin,
                   mixins.UpdateModelMixin):
    queryset = Grade.objects.select_related(
        "submission__homework__lecture__course", "graded_by", "submission__student"
    )
    permission_classes = [IsAuthenticated, IsGradeParticipant]

    def get_serializer_class(self):
        return GradeWriteSerializer if self.action in ("update", "partial_update") else GradeReadSerializer

    def partial_update(self, request, pk=None):
        grade = self.get_object()
        ser = GradeWriteSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        value = ser.validated_data.get("value", grade.value)
        comment = ser.validated_data.get("comment", grade.comment)
        updated = learning_service.grade_submission(request.user, grade.submission, value, comment)
        return Response(GradeReadSerializer(updated).data)

    def update(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)

    @action(detail=False, methods=["get"])
    def mine(self, request):
        qs = self.get_queryset().filter(submission__student=request.user)
        page = self.paginate_queryset(qs)
        ser = GradeReadSerializer(page or qs, many=True)
        if page is not None:
            return self.get_paginated_response(ser.data)
        return Response(ser.data)

    @action(detail=False, methods=["get"], url_path=r"submission/(?P<submission_id>\d+)")
    def by_submission(self, request, submission_id=None):
        submission = get_object_or_404(Submission.objects.select_related("homework__lecture__course"), id=submission_id)
        grade = getattr(submission, "grade", None)
        if not grade:
            return Response({"detail": "No grade"}, status=404)
        # Object permission already enforced on retrieve; explicit check for student/teacher:
        if submission.student_id != request.user.id and not CourseMembership.objects.filter(
            course=submission.homework.lecture.course, user=request.user, role=MemberRole.TEACHER
        ).exists():
            return Response({"detail": "Forbidden"}, status=403)
        return Response(GradeReadSerializer(grade).data)


@extend_schema_view(
    list=extend_schema(tags=["GradeComments"]),
    retrieve=extend_schema(tags=["GradeComments"]),
    create=extend_schema(
        tags=["GradeComments"],
        request=GradeCommentWriteSerializer,
        responses={201: GradeCommentReadSerializer, 403: OpenApiResponse(description="Forbidden")}
    ),
    update=extend_schema(tags=["GradeComments"], request=GradeCommentWriteSerializer),
    partial_update=extend_schema(tags=["GradeComments"], request=GradeCommentWriteSerializer),
    destroy=extend_schema(tags=["GradeComments"], responses={204: OpenApiResponse(description="Deleted")}),
)
class GradeCommentViewSet(viewsets.ModelViewSet):
    queryset = GradeComment.objects.select_related(
        "grade__submission__homework__lecture__course", "author", "grade__submission__student"
    )
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        return GradeCommentWriteSerializer if self.action in ("create", "update", "partial_update") else GradeCommentReadSerializer

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        grade_id = self.request.query_params.get("grade")
        if grade_id:
            qs = qs.filter(grade_id=grade_id)
        # Allow: author, course teacher, or submission student
        return qs.filter(
            Q(author=user) |
            Q(grade__submission__student=user) |
            Q(grade__submission__homework__lecture__course__memberships__user=user,
              grade__submission__homework__lecture__course__memberships__role=MemberRole.TEACHER)
        ).distinct()

    def perform_create(self, serializer):
        grade = serializer.validated_data["grade"]
        submission = grade.submission
        course = submission.homework.lecture.course
        is_teacher = CourseMembership.objects.filter(
            course=course, user=self.request.user, role=MemberRole.TEACHER
        ).exists()
        is_student_owner = submission.student_id == self.request.user.id
        if not (is_teacher or is_student_owner):
            raise PermissionDenied("Not allowed to comment")
        serializer.save(author=self.request.user)

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        submission = obj.grade.submission
        course = submission.homework.lecture.course
        is_teacher = CourseMembership.objects.filter(course=course, user=request.user, role=MemberRole.TEACHER).exists()
        if obj.author_id != request.user.id and not is_teacher:
            return Response({"detail": "Only author or teacher can delete"}, status=403)
        return super().destroy(request, *args, **kwargs)