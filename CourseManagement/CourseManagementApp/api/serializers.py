"""Serializers for user registration, courses, learning objects, submissions, grades, and comments."""

from rest_framework import serializers
from django.contrib.auth import get_user_model

from CourseManagementApp.courses.models import Course, CourseMembership, CourseWaitlistEntry
from CourseManagementApp.learning.models import Lecture, Homework, Submission, Grade, GradeComment
from CourseManagementApp.core.choices import MemberRole, UserRole, SubmissionState
from CourseManagementApp.core.validators import validate_file_size, validate_presentation_mime, validate_attachment_mime, validate_resource_url

User = get_user_model()

class RegistrationSerializer(serializers.ModelSerializer):
    """Serializer handling user registration with role validation."""
    password = serializers.CharField(write_only=True, help_text="User password (write‑only).")

    class Meta:
        model = User
        fields = ["id", "email", "password", "first_name", "last_name", "role"]

    def validate_role(self, value: str) -> str:
        """Restrict teacher role creation to staff users."""
        request = self.context.get("request")
        if value == UserRole.TEACHER and (not request or not request.user.is_staff):
            raise serializers.ValidationError("Teacher registration requires staff privileges.")
        return value

    def create(self, validated: dict) -> User:
        """Create and return a new user instance."""
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
    """Public, safe representation of a user."""

    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "role"]


class CourseWriteSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating a course."""

    class Meta:
        model = Course
        fields = ["title", "description", "is_public", "is_published"]


class CourseReadSerializer(serializers.ModelSerializer):
    """Serializer for reading course details including owner."""
    owner = UserSerializer()

    class Meta:
        model = Course
        fields = ["id", "title", "description", "is_public", "is_published", "owner", "created_at", "updated_at"]


class MembershipWriteSerializer(serializers.Serializer):
    """Serializer to add or modify a course membership."""

    user_id = serializers.IntegerField()
    role = serializers.ChoiceField(choices=MemberRole.choices)


class LectureWriteSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating lecture metadata and resources."""

    presentation = serializers.FileField(
        required=False,
        allow_null=True,
        help_text=(
        "Binary presentation file. Accepted MIME types: application/pdf, application/vnd.ms-powerpoint, "
        "application/vnd.openxmlformats-officedocument.presentationml.presentation. Max size: 10MB."
    ))

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

    def validate(self, data):
        has_file = bool(data.get("presentation"))
        has_url = bool(data.get("presentation_url"))
        if has_file == has_url:
            # both true or both false -> invalid
            raise serializers.ValidationError(
                "Exactly one of `presentation` or `presentation_url` must be provided."
            )
        # optional: enforce file size/MIME here if presentation present
        file = data.get("presentation")
        if file:
            # Example size check (10MB)
            max_bytes = 10 * 1024 * 1024
            if file.size > max_bytes:
                raise serializers.ValidationError("Presentation file exceeds 10MB limit.")
            # MIME check if available
            content_type = getattr(file, "content_type", None)
            allowed = {"application/pdf", "application/vnd.ms-powerpoint", "application/vnd.openxmlformats-officedocument.presentationml.presentation"}
            if content_type and content_type not in allowed:
                raise serializers.ValidationError(f"Unsupported presentation MIME type: {content_type}.")
        return super().validate(data)



class LectureReadSerializer(serializers.ModelSerializer):
    """Serializer for reading lecture details."""

    class Meta:
        model = Lecture
        fields = ["id", "course", "topic", "presentation", "presentation_url", "is_published", "created_by", "created_at", "updated_at"]


class HomeworkWriteSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating homework."""

    class Meta:
        model = Homework
        fields = ["text", "due_at", "is_active"]


class HomeworkReadSerializer(serializers.ModelSerializer):
    """Serializer for reading homework details."""

    class Meta:
        model = Homework
        fields = ["id", "lecture", "text", "due_at", "is_active", "created_at", "updated_at"]


class GradeMiniSerializer(serializers.ModelSerializer):
    """Compact grade representation attached to a submission."""

    class Meta:
        model = Grade
        fields = ["id", "value", "comment"]


class SubmissionWriteSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating a submission."""

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

    def validate_attachment(self, attachment: object | None) -> object | None:
        """Validate attachment size and MIME if provided."""
        if attachment:
            validate_file_size(attachment)
            validate_attachment_mime(attachment)
        return attachment

    def validate(self, data):
        if not data.get("content_text") and not data.get("attachment"):
            raise serializers.ValidationError("At least one of `content_text` or `attachment` is required.")
        return super().validate(data)


class SubmissionReadSerializer(serializers.ModelSerializer):
    """Detailed submission view including grade and student."""
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
    """Serializer for reading a grade."""
    graded_by = UserSerializer(read_only=True)

    class Meta:
        model = Grade
        fields = ["id", "submission", "graded_by", "value", "comment", "created_at", "updated_at"]
        read_only_fields = ["graded_by", "created_at", "updated_at"]


class GradeWriteSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating a grade."""
    class Meta:
        model = Grade
        fields = ["submission", "value", "comment"]


class GradeCommentWriteSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating a grade comment."""
    class Meta:
        model = GradeComment
        fields = ["grade", "text"]


class GradeCommentReadSerializer(serializers.ModelSerializer):
    """Serializer for reading grade comment details."""
    author = UserSerializer(read_only=True)

    class Meta:
        model = GradeComment
        fields = ["id", "grade", "author", "text", "created_at"]
        read_only_fields = ["author", "created_at"]


class CourseWaitlistEntrySerializer(serializers.ModelSerializer):
    """Serializer for course waitlist entries."""

    class Meta:
        model = CourseWaitlistEntry
        fields = ['id', 'course', 'student', 'created_at', 'approved']
        read_only_fields = ['id', 'created_at', 'approved']


class WaitlistRequestSerializer(serializers.Serializer):
    """Explicit body for a course join request (optional note)."""
    message = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Optional note sent with the join request."
    )