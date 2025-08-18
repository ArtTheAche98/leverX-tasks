from django.db.models import QuerySet, Q

from CourseManagementApp.core.choices import MemberRole

class CourseQuerySet(QuerySet):
    def public_published(self):
        return self.filter(is_public=True, is_published=True)

    def for_owner(self, user):
        return self.filter(owner=user)

    def where_user_member(self, user):
        return self.filter(memberships__user=user).distinct()

    def visible_to(self, user):
        if not user or not user.is_authenticated:
            return self.public_published()
        return self.filter(
            Q(is_public=True, is_published=True) |
            Q(owner=user) |
            Q(memberships__user=user)
        ).distinct()


class LectureQuerySet(QuerySet):
    def published_for_student(self, user):
        return self.filter(
            is_published=True,
            course__memberships__user=user,
            course__memberships__role=MemberRole.STUDENT
        )

    def visible_to(self, user):
        """
        Lectures visible to a user:
          - Owner or teacher: all lectures of their courses
          - Student: only published lectures of enrolled courses
          - Anonymous: published lectures of public & published courses
        """
        if not user or not user.is_authenticated:
            return self.filter(
                is_published=True,
                course__is_public=True,
                course__is_published=True,
            )
        return self.filter(
            Q(course__owner=user) |
            Q(course__memberships__user=user,
              course__memberships__role=MemberRole.TEACHER) |
            Q(is_published=True,
              course__memberships__user=user,
              course__memberships__role=MemberRole.STUDENT) |
            Q(is_published=True,
              course__is_public=True,
              course__is_published=True)
        ).distinct()


class HomeworkQuerySet(QuerySet):
    def visible_to(self, user):
        if not user or not user.is_authenticated:
            return self.filter(
                lecture__is_published=True,
                lecture__course__is_public=True,
                lecture__course__is_published=True,
                is_active=True,
            )
        return self.filter(
            Q(lecture__course__owner=user) |
            Q(lecture__course__memberships__user=user,
              lecture__course__memberships__role=MemberRole.TEACHER) |
            Q(lecture__is_published=True, is_active=True,
              lecture__course__memberships__user=user,
              lecture__course__memberships__role=MemberRole.STUDENT) |
            Q(lecture__is_published=True, is_active=True,
              lecture__course__is_public=True,
              lecture__course__is_published=True)
        ).distinct()

class SubmissionQuerySet(QuerySet):
    def for_teacher(self, user):
        return self.filter(
            homework__lecture__course__memberships__user=user,
            homework__lecture__course__memberships__role=MemberRole.TEACHER
        )

    def for_student(self, user):
        return self.filter(student=user)