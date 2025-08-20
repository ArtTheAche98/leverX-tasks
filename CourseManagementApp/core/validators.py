"""Validation helpers for uploaded files and external resource URLs."""

from urllib.parse import urlparse
from django.conf import settings
from django.core.exceptions import ValidationError
from typing import Any

import magic

ALLOWED_PRESENTATION_MIME: set[str] = {
    "application/pdf",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}
ALLOWED_ATTACHMENT_MIME: set[str] = ALLOWED_PRESENTATION_MIME | {
    "text/plain",
    "application/zip",
    "image/png",
    "image/jpeg",
}

def validate_file_size(file_obj: Any, max_mb: int = 5) -> None:
    """Ensure file size does not exceed max_mb megabytes."""
    if file_obj and file_obj.size > max_mb * 1024 * 1024:
        raise ValidationError(f"File exceeds {max_mb} MB limit.")

def _probe_mime(file_obj: Any) -> str | None:
    """Read initial bytes to detect MIME type using libmagic."""
    if not file_obj:
        return None
    header = file_obj.read(4096)
    file_obj.seek(0)
    return magic.from_buffer(header, mime=True)

def validate_presentation_mime(file_obj: Any) -> None:
    """Validate that a presentation file has an allowed MIME type."""
    mime = _probe_mime(file_obj)
    if mime and mime not in ALLOWED_PRESENTATION_MIME:
        raise ValidationError(f"Unsupported presentation mime: {mime}")

def validate_attachment_mime(file_obj: Any) -> None:
    """Validate that an uploaded attachment has an allowed MIME type."""
    mime = _probe_mime(file_obj)
    if mime and mime not in ALLOWED_ATTACHMENT_MIME:
        raise ValidationError(f"Unsupported attachment mime: {mime}")

def validate_resource_url(url: str) -> None:
    """Ensure URL uses https and matches an allowed domain suffix."""
    result = urlparse(url)
    if result.scheme != "https":
        raise ValidationError("URL must use https.")
    allowed = getattr(settings, "ALLOWED_RESOURCE_DOMAINS", [])
    if not any(result.netloc.endswith(d) for d in allowed):
        raise ValidationError("URL domain not allowed.")