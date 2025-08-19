from rest_framework import serializers
from django.contrib.auth import get_user_model

from CourseManagementApp.courses.models import Course, CourseMembership, CourseWaitlistEntry
from CourseManagementApp.learning.models import Lecture, Homework, Submission, Grade, GradeComment
from CourseManagementApp.core.choices import MemberRole, UserRole, SubmissionState
from CourseManagementApp.core.validators import validate_file_size, validate_presentation_mime, validate_attachment_mime, validate_resource_url

User = get_user_model()

class RegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, help_text="User password (write‑only).")

    class Meta:
        model = User
        fields = ["id", "email", "password", "first_name", "last_name", "role"]

    def validate_role(self, value):
        request = self.context.get("request")
        if value == UserRole.TEACHER and (not request or not request.user.is_staff):
            raise serializers.ValidationError("Teacher registration requires staff privileges.")
        return value

    def create(self, validated):
        user = User(
            email=validated["email"],
            first_name=validated.get("first_name", ""),
            last_name=validated.get("last_name", ""),
            role=validated["role"],
            username=validated["email"],
        )
        user.set_password(validated["password"])
        user.save()
        return user


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "role"]


class CourseWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = ["title", "description", "is_public", "is_published"]


class CourseReadSerializer(serializers.ModelSerializer):
    owner = UserSerializer()
    class Meta:
        model = Course
        fields = ["id", "title", "description", "is_public", "is_published", "owner", "created_at", "updated_at"]


class MembershipWriteSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    role = serializers.ChoiceField(choices=MemberRole.choices)


class LectureWriteSerializer(serializers.ModelSerializer):
    presentation_url = serializers.URLField(
        required=False,
        allow_null=True,
        allow_blank=True,
        help_text="HTTPS URL to external presentation resource."
    )

    class Meta:
        model = Lecture
        fields = ["topic", "presentation", "presentation_url", "is_published"]
        extra_kwargs = {
            "topic": {"help_text": "Lecture topic/title."},
            "presentation": {"help_text": "Optional uploaded presentation file."},
            "presentation_url": {
                "help_text": "HTTPS URL to presentation resource (e.g., GitHub, Drive)."
            },
            "is_published": {"help_text": "Publish flag controlling student visibility."},
        }

    def validate_presentation_url(self, url):
        if url:
            validate_resource_url(url)
        return url

    def validate(self, attrs):
        if attrs.get("presentation") and attrs.get("presentation_url"):
            raise serializers.ValidationError("Provide either presentation file or presentation_url, not both.")
        return attrs

class LectureReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lecture
        fields = ["id", "course", "topic", "presentation", "presentation_url", "is_published", "created_by", "created_at", "updated_at"]


class HomeworkWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Homework
        fields = ["text", "due_at", "is_active"]


class HomeworkReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Homework
        fields = ["id", "lecture", "text", "due_at", "is_active", "created_at", "updated_at"]


class GradeMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Grade
        fields = ["id", "value", "comment"]


class SubmissionWriteSerializer(serializers.ModelSerializer):
    content_text = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Textual answer (optional if attachment provided)."
    )
    attachment = serializers.FileField(
        required=False,
        allow_null=True,
        help_text="Optional file attachment."
    )

    class Meta:
        model = Submission
        fields = ["content_text", "attachment"]
        extra_kwargs = {
            "attachment": {"help_text": "File; size/type validated."},
        }

    def validate_attachment(self, attachment):
        if attachment:
            validate_file_size(attachment)
            validate_attachment_mime(attachment)
        return attachment

    def validate(self, attrs):
        if not attrs.get("content_text") and not attrs.get("attachment"):
            raise serializers.ValidationError("Either content_text or attachment must be provided.")
        return attrs


class SubmissionReadSerializer(serializers.ModelSerializer):
    grade = GradeMiniSerializer(read_only=True)
    student = UserSerializer(read_only=True)
    homework = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Submission
        fields = [
            "id", "homework", "student", "content_text", "attachment",
            "submitted_at", "updated_at", "is_late", "state", "grade"
        ]
        read_only_fields = [
            "id", "homework", "student", "submitted_at",
            "updated_at", "is_late", "state", "grade"
        ]


class GradeReadSerializer(serializers.ModelSerializer):
    graded_by = UserSerializer(read_only=True)

    class Meta:
        model = Grade
        fields = ["id", "submission", "graded_by", "value", "comment", "created_at", "updated_at"]
        read_only_fields = ["graded_by", "created_at", "updated_at"]


class GradeWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Grade
        fields = ["submission", "value", "comment"]


class GradeCommentWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = GradeComment
        fields = ["grade", "text"]


class GradeCommentReadSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)

    class Meta:
        model = GradeComment
        fields = ["id", "grade", "author", "text", "created_at"]
        read_only_fields = ["author", "created_at"]


class CourseWaitlistEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = CourseWaitlistEntry
        fields = ['id', 'course', 'student', 'created_at', 'approved']
        read_only_fields = ['id', 'created_at', 'approved']