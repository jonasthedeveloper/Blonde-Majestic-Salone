"""Image upload validation and storage. Type is detected from file contents, never from the client's name/headers."""
import secrets, io
from . import config
from .web import ApiError

try:
    from PIL import Image  # optional: used only to downscale large photos if Pillow is installed
except Exception:  # pragma: no cover
    Image = None

MAX_SIDE = 1600


def sniff(data):
    if data[:3] == b"\xff\xd8\xff":
        return "jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def save_image(data):
    if len(data) > config.MAX_UPLOAD_MB * 1024 * 1024:
        raise ApiError(400, "Image is too large. Maximum size is %g MB." % config.MAX_UPLOAD_MB)
    ext = sniff(data)
    if not ext:
        raise ApiError(400, "Unsupported image. Please upload a JPG, PNG, WEBP or GIF file.")
    if Image is not None and ext in ("jpg", "png", "webp"):
        try:
            im = Image.open(io.BytesIO(data))
            if max(im.size) > MAX_SIDE:
                im.thumbnail((MAX_SIDE, MAX_SIDE))
                buf = io.BytesIO()
                im.save(buf, format={"jpg": "JPEG", "png": "PNG", "webp": "WEBP"}[ext], quality=85, optimize=True)
                data = buf.getvalue()
        except Exception:
            raise ApiError(400, "That image could not be read. Please try another file.")
    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    name = secrets.token_hex(12) + "." + ext
    (config.UPLOAD_DIR / name).write_bytes(data)
    return name


def delete_image(name):
    if name and "/" not in name and "\\" not in name and ".." not in name:
        try:
            (config.UPLOAD_DIR / name).unlink()
        except OSError:
            pass
