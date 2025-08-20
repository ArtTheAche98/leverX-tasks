"""Signal handlers for learning domain (e.g., update submission lateness on homework change)."""

from typing import  Any

from django.db.models.signals import post_save
from django.dispatch import receiver

from CourseManagementApp.learning.models import Homework, Submission

@receiver(post_save, sender=Homework)
def recompute_submission_lateness(
    sender: type[Homework],
    instance: Homework,
    created: bool,
    **kwargs: Any,
) -> None:
    """Recalculate is_late flag for all submissions when homework due date changes."""
    if created:
        return
    due_at = instance.due_at
    subs = Submission.objects.filter(homework=instance)
    if due_at is None:
        subs.filter(is_late=True).update(is_late=False)
        return
    subs_late_should = subs.filter(submitted_at__gt=due_at, is_late=False)
    subs_not_late_should = subs.filter(submitted_at__lte=due_at, is_late=True)
    if subs_late_should.exists():
        subs_late_should.update(is_late=True)
    if subs_not_late_should.exists():
        subs_not_late_should.update(is_late=False)