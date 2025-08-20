from django.core.management.base import BaseCommand
from django.utils import timezone
from CourseManagementApp.learning.models import Submission

class Command(BaseCommand):
    help = "Recompute is_late flags for all submissions."

    def handle(self, *args, **options):
        updated = 0
        for sub in Submission.objects.select_related("homework"):
            due = sub.homework.due_at
            should = bool(due and sub.submitted_at > due)
            if sub.is_late != should:
                sub.is_late = should
                sub.save(update_fields=["is_late"])
                updated += 1
        self.stdout.write(self.style.SUCCESS(f"Updated {updated} submissions"))