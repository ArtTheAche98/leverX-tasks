from rest_framework import serializers
from django.contrib.auth import get_user_model

from CourseManagementApp.courses.models import Course, CourseMembership
from CourseManagementApp.learning.models import Lecture, Homework, Submission, Grade, GradeComment
from CourseManagementApp.core.choices import MemberRole
from CourseManagementApp.core.validators import validate_file_size, validate_presentation_mime, validate_attachment_mime

User = get_user_model()

class RegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    class Meta:
        model = User
        fields = ["id", "email", "password", "first_name", "last_name", "role"]

    def create(self, validated):
        user = User(
            email=validated["email"],
            first_name=validated.get("first_name", ""),
            last_name=validated.get("last_name", ""),
            role=validated["role"],
            username=validated["email"],  # if username retained
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
    class Meta:
        model = Lecture
        fields = ["topic", "presentation", "is_published"]

    def validate_presentation(self, file_obj):
        if file_obj:
            validate_file_size(file_obj)
            validate_presentation_mime(file_obj)
        return file_obj


class LectureReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lecture
        fields = ["id", "course", "topic", "presentation", "is_published", "created_by", "created_at", "updated_at"]


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
    class Meta:
        model = Submission
        fields = ["content_text", "attachment"]

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
