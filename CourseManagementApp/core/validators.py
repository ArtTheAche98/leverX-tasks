from django.core.exceptions import ValidationError
import magic

ALLOWED_PRESENTATION_MIME = {
    "application/pdf",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}
ALLOWED_ATTACHMENT_MIME = ALLOWED_PRESENTATION_MIME | {
    "text/plain",
    "application/zip",
    "image/png",
    "image/jpeg",
}

def validate_file_size(file_obj, max_mb=5):
    if file_obj and file_obj.size > max_mb * 1024 * 1024:
        raise ValidationError(f"File exceeds {max_mb} MB limit.")

def _probe_mime(file_obj):
    if not file_obj:
        return None
    header = file_obj.read(4096)
    file_obj.seek(0)
    return magic.from_buffer(header, mime=True)

def validate_presentation_mime(file_obj):
    mime = _probe_mime(file_obj)
    if mime and mime not in ALLOWED_PRESENTATION_MIME:
        raise ValidationError(f"Unsupported presentation mime: {mime}")

def validate_attachment_mime(file_obj):
    mime = _probe_mime(file_obj)
    if mime and mime not in ALLOWED_ATTACHMENT_MIME:
        raise ValidationError(f"Unsupported attachment mime: {mime}")