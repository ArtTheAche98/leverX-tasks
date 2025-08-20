"""API throttling classes."""

from rest_framework.throttling import UserRateThrottle

class SubmissionRateThrottle(UserRateThrottle):
    """Throttle limiting submission create requests per user."""
    scope = "submission_create"
    rate = "10/hour"