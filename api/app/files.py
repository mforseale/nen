"""Metadata and permission projection shared by file routes and profiles."""
from pathlib import PurePosixPath

from app.models import ProfilePost

MAX_FILE_SIZE = 25 * 1024 * 1024
MAX_POST_SIZE = 50 * 1024 * 1024
MAX_FILES = 10


def clean_name(name):
    return ("".join(c for c in PurePosixPath((name or "file").replace("\\", "/")).name if ord(c) >= 32 and ord(c) != 127).strip() or "file")[:200]


def classify_file(name, content):
    suffix = PurePosixPath(name).suffix.lower()
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image", "image/png"
    if content.startswith(b"\xff\xd8\xff"):
        return "image", "image/jpeg"
    if content[:6] in (b"GIF87a", b"GIF89a"):
        return "image", "image/gif"
    if content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return "image", "image/webp"
    if content.startswith(b"RIFF") and content[8:12] == b"WAVE":
        return "audio", "audio/wav"
    if content.startswith(b"ID3") or len(content) > 2 and content[0] == 255 and content[1] & 0xE0 == 0xE0 and suffix == ".mp3":
        return "audio", "audio/mpeg"
    if content.startswith(b"fLaC"):
        return "audio", "audio/flac"
    if content.startswith(b"OggS"):
        return ("video", "video/ogg") if suffix == ".ogv" else ("audio", "audio/ogg")
    if content[4:8] == b"ftyp" and suffix in (".mp4", ".m4a", ".m4v", ".mov"):
        return ("audio", "audio/mp4") if suffix == ".m4a" else ("video", "video/mp4")
    if content.startswith(b"\x1aE\xdf\xa3") and suffix == ".webm":
        return "video", "video/webm"
    return "file", "application/octet-stream"


def file_visible(db, item, viewer):
    # Imported at call time to share the existing policy without module cycles.
    from app.profile_data import visible
    if item.post_id:
        post = db.get(ProfilePost, item.post_id)
        return bool(post and visible(db, post, viewer))
    return visible(db, item, viewer)


def file_view(item, db=None):
    post = db.get(ProfilePost, item.post_id) if db is not None and item.post_id else None
    return {"id": item.id, "post_id": item.post_id, "name": item.name, "size": item.size,
            "kind": item.kind, "media_type": item.media_type, "pinned": item.pinned,
            "visibility": post.visibility if post else item.visibility, "created_at": item.created_at,
            "url": f"/api/v1/profile/files/{item.id}/content",
            "download_url": f"/api/v1/profile/files/{item.id}/content?download=true"}
