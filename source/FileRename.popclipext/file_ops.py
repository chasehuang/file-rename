#!/usr/bin/python3
"""One JSON request on stdin, one JSON response on stdout; no diagnostic paths."""

import base64
import binascii
import ctypes
import errno
import json
import math
import os
import re
import signal
import stat
import struct
import subprocess
import sys
import tempfile
import time


# Inline Gemini requests must stay below 20 MB after base64 and JSON encoding.
MAX_IMAGE_BYTES = 14 * 1024 * 1024
MAX_REQUEST_BYTES = 32 * 1024
MAX_STEM = 64
IMAGE_MAX_EDGE = 1600
IMAGE_PROCESS_SECONDS = 20
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
SNAPSHOT_FIELDS = ("dev", "ino", "size", "mtime_ns")
IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
VIDEO_DEMUXERS = {".mp4": "mov", ".mov": "mov", ".m4v": "mov", ".webm": "matroska", ".mkv": "matroska"}
VIDEO_TOTAL_SECONDS = 45
VIDEO_PROCESS_SECONDS = 8
VIDEO_TOOL_DIRECTORIES = ("/opt/homebrew/bin", "/usr/local/bin")
COMPOUND_EXTENSIONS = (".tar.gz", ".tar.bz2", ".tar.xz")
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*", re.ASCII)
# Apple's SDK sys/stdio.h and rename(2): EXCL fails atomically with EEXIST.
RENAME_EXCL = 0x00000004
RENAME_NOFOLLOW_ANY = 0x00000010


class FileOpError(Exception):
    def __init__(self, code):
        self.code = code


def _fail(code):
    raise FileOpError(code)


def _snapshot(info):
    # Nanosecond timestamps exceed JavaScript's safe integer range. Keep the
    # entire snapshot opaque and lossless through PopClip JSON.parse/stringify.
    return {"dev": str(info.st_dev), "ino": str(info.st_ino), "size": str(info.st_size), "mtime_ns": str(info.st_mtime_ns)}


def _expected_snapshot(value):
    if not isinstance(value, dict) or set(value) != set(SNAPSHOT_FIELDS):
        _fail("invalid_snapshot")
    for field in SNAPSHOT_FIELDS:
        number = value[field]
        pattern = r"(?:0|[1-9][0-9]{0,31})" if field != "mtime_ns" else r"(?:0|-?[1-9][0-9]{0,31})"
        if not isinstance(number, str) or re.fullmatch(pattern, number, re.ASCII) is None:
            _fail("invalid_snapshot")
    return value


def _path(value):
    if not isinstance(value, str) or not value or "\x00" in value or not os.path.isabs(value):
        _fail("invalid_path")
    if ".." in value.split(os.sep) or value.endswith(os.sep):
        _fail("invalid_path")
    name = os.path.basename(value)
    if name in ("", ".", ".."):
        _fail("invalid_path")
    path = os.path.normpath(value)
    # Do not silently resolve a directory symlink to a different location.
    # Callers must supply a real absolute path (e.g. /private/tmp, not /tmp).
    parent = os.sep
    for component in os.path.dirname(path).split(os.sep):
        if not component:
            continue
        parent = os.path.join(parent, component)
        info = os.lstat(parent)
        if stat.S_ISLNK(info.st_mode):
            _fail("symlink")
        if not stat.S_ISDIR(info.st_mode):
            _fail("invalid_path")
    return path


def _regular_info(path):
    info = os.lstat(path)
    if stat.S_ISLNK(info.st_mode):
        _fail("symlink")
    if not stat.S_ISREG(info.st_mode):
        _fail("not_regular_file")
    return info


def _checked_source(value, expected=None):
    path = _path(value)
    info = _regular_info(path)
    if expected is not None and _snapshot(info) != _expected_snapshot(expected):
        _fail("changed")
    return path, info


def _split_extension(name):
    lowered = name.lower()
    for suffix in COMPOUND_EXTENSIONS:
        if lowered.endswith(suffix) and len(name) > len(suffix):
            return name[:-len(suffix)], name[-len(suffix):]
    return os.path.splitext(name)


def _validate_slug(slug):
    if not isinstance(slug, str) or not 1 <= len(slug) <= MAX_STEM or SLUG.fullmatch(slug) is None:
        _fail("invalid_slug")
    return slug


def _validate_filename(filename, extension):
    if not isinstance(filename, str) or not filename or any(c in filename for c in ("/", "\\", "\x00")) or ".." in filename:
        _fail("invalid_filename")
    if extension:
        if not filename.endswith(extension):
            _fail("extension_mismatch")
        stem = filename[:-len(extension)]
    else:
        if "." in filename:
            _fail("extension_mismatch")
        stem = filename
    _validate_slug(stem)
    return filename


def _detect_image_mime(header):
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return "image/webp"
    return None


def _png_pixels_only(data):
    """Keep only pixel/format/transparency chunks from a freshly encoded PNG."""
    if not data.startswith(PNG_SIGNATURE):
        _fail("image_sanitization_failed")
    output = bytearray(PNG_SIGNATURE)
    position = len(PNG_SIGNATURE)
    seen_header = False
    seen_pixels = False
    allowed = {b"IHDR", b"PLTE", b"IDAT", b"IEND", b"tRNS"}
    while position + 12 <= len(data):
        length = struct.unpack_from(">I", data, position)[0]
        end = position + 12 + length
        if end > len(data):
            _fail("image_sanitization_failed")
        kind = data[position + 4:position + 8]
        payload = data[position + 8:end - 4]
        crc = struct.unpack_from(">I", data, end - 4)[0]
        if binascii.crc32(kind + payload) & 0xffffffff != crc:
            _fail("image_sanitization_failed")
        if not seen_header:
            if kind != b"IHDR" or length != 13:
                _fail("image_sanitization_failed")
            width, height = struct.unpack_from(">II", payload)
            if not 1 <= width <= IMAGE_MAX_EDGE or not 1 <= height <= IMAGE_MAX_EDGE:
                _fail("image_sanitization_failed")
            seen_header = True
        elif kind == b"IHDR":
            _fail("image_sanitization_failed")
        # Unknown critical chunks indicate an unsupported pixel format.
        if kind not in allowed and not kind[0] & 0x20:
            _fail("image_sanitization_failed")
        if kind in allowed:
            output.extend(data[position:end])
        if kind == b"IDAT":
            seen_pixels = True
        if kind == b"IEND":
            if length or not seen_pixels or end != len(data):
                _fail("image_sanitization_failed")
            return bytes(output)
        position = end
    _fail("image_sanitization_failed")


def _cancel_image(_signum, _frame):
    # Let subprocess.run kill/wait its child and TemporaryDirectory clean up.
    _fail("image_cancelled")


def _sanitize_image(data, extension):
    """Convert only a temporary copy; failure never falls back to original bytes."""
    if sys.platform != "darwin":
        _fail("image_sanitization_failed")
    helper = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sanitize-image.js")
    previous_handlers = {}
    try:
        for signum in (signal.SIGTERM, signal.SIGINT):
            previous_handlers[signum] = signal.signal(signum, _cancel_image)
        with tempfile.TemporaryDirectory(prefix="popclip-image-upload-") as temporary:
            source = os.path.join(temporary, "input" + extension.lower())
            target = os.path.join(temporary, "pixels.png")
            with open(source, "xb") as stream:
                stream.write(data)
            try:
                result = subprocess.run(
                    ["/usr/bin/osascript", "-l", "JavaScript", helper, source, target],
                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                    timeout=IMAGE_PROCESS_SECONDS, check=False,
                )
            except subprocess.TimeoutExpired:
                _fail("image_timeout")
            except OSError:
                _fail("image_sanitization_failed")
            if result.returncode != 0 or result.stdout.strip() != b"OK" or not os.path.isfile(target):
                _fail("image_sanitization_failed")
            with open(target, "rb") as stream:
                encoded = stream.read(MAX_IMAGE_BYTES + 1)
            if len(encoded) > MAX_IMAGE_BYTES:
                _fail("image_too_large")
            return _png_pixels_only(encoded)
    finally:
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)


def _jpeg_pixels_only(data):
    """Remove all APP/COM segments, including metadata between JPEG scans."""
    if not data.startswith(b"\xff\xd8"):
        _fail("invalid_video")
    output = bytearray(b"\xff\xd8")
    position = 2
    seen_scan = False
    while position < len(data):
        start = position
        if data[position] != 0xff:
            _fail("invalid_video")
        while position < len(data) and data[position] == 0xff:
            position += 1
        if position >= len(data):
            _fail("invalid_video")
        marker = data[position]
        position += 1
        if marker == 0xd9:
            if not seen_scan or position != len(data):
                _fail("invalid_video")
            output.extend(b"\xff\xd9")
            return bytes(output)
        if marker in (0, 0xd8) or 0xd0 <= marker <= 0xd7:
            _fail("invalid_video")
        if marker == 1:  # TEM has no length field.
            output.extend(data[start:position])
            continue
        if position + 2 > len(data):
            _fail("invalid_video")
        length = struct.unpack_from(">H", data, position)[0]
        end = position + length
        if length < 2 or end > len(data):
            _fail("invalid_video")
        if not (0xe0 <= marker <= 0xef or marker == 0xfe):
            output.extend(data[start:end])
        position = end
        if marker == 0xda:
            seen_scan = True
            scan_start = position
            while position < len(data):
                if data[position] != 0xff:
                    position += 1
                    continue
                next_marker = position + 1
                while next_marker < len(data) and data[next_marker] == 0xff:
                    next_marker += 1
                if next_marker >= len(data):
                    _fail("invalid_video")
                if data[next_marker] == 0 or 0xd0 <= data[next_marker] <= 0xd7:
                    position = next_marker + 1
                    continue
                break
            output.extend(data[scan_start:position])
    _fail("invalid_video")


def _image(path, info, extension):
    expected_mime = IMAGE_TYPES.get(extension.lower())
    if expected_mime is None:
        return None  # Other file types use their filename, without reading bytes.
    if info.st_size > MAX_IMAGE_BYTES:
        _fail("image_too_large")
    initial = _snapshot(info)
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, "rb") as stream:
        if _snapshot(os.fstat(stream.fileno())) != initial:
            _fail("changed")
        header = stream.read(12)
        if _detect_image_mime(header) != expected_mime:
            _fail("image_type_mismatch")
        remainder = stream.read(MAX_IMAGE_BYTES + 1 - len(header))
        data = header + remainder
        if _snapshot(os.fstat(stream.fileno())) != initial or _snapshot(_regular_info(path)) != initial:
            _fail("changed")
        if len(data) > MAX_IMAGE_BYTES:
            _fail("image_too_large")
        if len(data) != info.st_size:
            _fail("changed")
    sanitized = _sanitize_image(data, extension)
    # Native decoding can take time: recheck identity before returning a payload.
    _checked_source(path, initial)
    return {"mime": "image/png", "dataUrl": "data:image/png;base64," + base64.b64encode(sanitized).decode("ascii")}


def inspect(path, include_image=True, snapshot=None):
    if not isinstance(include_image, bool):
        _fail("bad_request")
    path, info = _checked_source(path, snapshot)
    name = os.path.basename(path)
    stem, extension = _split_extension(name)
    return {"ok": True, "path": path, "name": name, "stem": stem, "extension": extension,
            "snapshot": _snapshot(info), "image": _image(path, info, extension) if include_image else None}


def _video_tools():
    tools = []
    for name in ("ffmpeg", "ffprobe"):
        candidate = next((os.path.join(directory, name) for directory in VIDEO_TOOL_DIRECTORIES
                          if os.path.isfile(os.path.join(directory, name)) and
                          os.access(os.path.join(directory, name), os.X_OK)), None)
        if candidate is None:
            _fail("missing_video_tools")
        tools.append(candidate)
    return tools


def _run_video(command, descriptor, deadline, capture=False):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        _fail("video_timeout")
    # Every subprocess receives the already-open source descriptor, not a path
    # that could resolve to a replacement file between validation and decoding.
    os.lseek(descriptor, 0, os.SEEK_SET)
    with tempfile.TemporaryFile() as output:
        try:
            result = subprocess.run(command, stdin=subprocess.DEVNULL,
                                    stdout=output if capture else subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, pass_fds=(descriptor,),
                                    timeout=min(VIDEO_PROCESS_SECONDS, remaining), check=False)
        except subprocess.TimeoutExpired:
            _fail("video_timeout")
        if result.returncode != 0:
            _fail("invalid_video")
        if capture:
            output.seek(0)
            value = output.read(65537)
            if len(value) > 65536:
                _fail("invalid_video")
            return value
    return b""


def _video_source_unchanged(path, descriptor, expected):
    _checked_source(path, expected)
    if _snapshot(os.fstat(descriptor)) != expected:
        _fail("changed")


def _cancel_video(_signum, _frame):
    # Raising lets subprocess.run kill/wait its child before TemporaryDirectory
    # and the open source descriptor unwind. SIGKILL cannot be intercepted.
    _fail("video_cancelled")


def video_frames(path, snapshot):
    expected = _expected_snapshot(snapshot)
    path, _ = _checked_source(path, expected)
    demuxer = VIDEO_DEMUXERS.get(os.path.splitext(path)[1].lower())
    if demuxer is None:
        _fail("unsupported_video")
    ffmpeg, ffprobe = _video_tools()
    deadline = time.monotonic() + VIDEO_TOTAL_SECONDS
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    previous_handlers = {}
    try:
        for signum in (signal.SIGTERM, signal.SIGINT):
            previous_handlers[signum] = signal.signal(signum, _cancel_video)
        _video_source_unchanged(path, descriptor, expected)
        # fd alone permits no network or secondary local file protocol. Force
        # the expected container rather than auto-detecting an HLS/concat list.
        input_options = ["-protocol_whitelist", "fd", "-fd", str(descriptor),
                         "-f", demuxer, "-probesize", "5000000", "-analyzeduration", "5000000"]
        if demuxer == "mov":
            input_options += ["-enable_drefs", "0", "-use_absolute_path", "0"]
        probe = [ffprobe, "-v", "error"] + input_options + [
            "-select_streams", "v:0", "-show_entries", "stream=duration,width,height,avg_frame_rate:format=duration",
            "-of", "json", "-i", "fd:"]
        raw = _run_video(probe, descriptor, deadline, capture=True)
        _video_source_unchanged(path, descriptor, expected)
        try:
            metadata = json.loads(raw)
            streams = metadata.get("streams", [])
            if not streams or not streams[0].get("width", 0) or not streams[0].get("height", 0):
                _fail("invalid_video")
            duration = None
            for value in (streams[0].get("duration"), metadata.get("format", {}).get("duration")):
                try:
                    number = float(value)
                    if math.isfinite(number) and number > 0:
                        duration = number
                        break
                except (ValueError, TypeError):
                    pass
            if duration is None:
                _fail("invalid_video")
        except (ValueError, TypeError, AttributeError):
            _fail("invalid_video")
        count = min(8, max(1, math.floor(duration * 4)))
        final_position = duration * 0.95
        # Avoid seeking beyond the final frame of a low-frame-rate short clip.
        # Most videos still use the full requested 5%–95% interval.
        try:
            numerator, denominator = streams[0].get("avg_frame_rate", "0/1").split("/")
            frame_rate = float(numerator) / float(denominator)
            if math.isfinite(frame_rate) and frame_rate > 0:
                final_position = min(final_position, max(0.0, duration - 1 / frame_rate))
                count = min(count, max(1, math.ceil(duration * frame_rate)))
        except (ValueError, TypeError, ZeroDivisionError):
            pass
        first_position = min(duration * 0.05, final_position)
        positions = [0.0] if count == 1 else [first_position + (final_position - first_position) * index / (count - 1) for index in range(count)]
        frames = []
        total_bytes = 0
        with tempfile.TemporaryDirectory(prefix="popclip-video-frames-") as temporary:
            for index, seconds in enumerate(positions):
                _video_source_unchanged(path, descriptor, expected)
                target = os.path.join(temporary, "frame-%02d.jpg" % index)
                command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y"] + input_options + [
                    "-ss", "%.6f" % seconds, "-threads", "1", "-i", "fd:",
                    "-map", "0:v:0", "-an", "-sn", "-dn", "-frames:v", "1",
                    "-map_metadata", "-1", "-map_chapters", "-1",
                    "-vf", "scale=w=min(1600\\,iw):h=min(1600\\,ih):force_original_aspect_ratio=decrease",
                    "-c:v", "mjpeg", "-q:v", "3", "-threads", "1", "-f", "image2", "-update", "1",
                    "-fs", str(MAX_IMAGE_BYTES + 1), target]
                _run_video(command, descriptor, deadline)
                _video_source_unchanged(path, descriptor, expected)
                if not os.path.isfile(target):
                    _fail("invalid_video")
                size = os.path.getsize(target)
                if size > MAX_IMAGE_BYTES or total_bytes + size > MAX_IMAGE_BYTES:
                    _fail("video_frames_too_large")
                with open(target, "rb") as image:
                    data = image.read(MAX_IMAGE_BYTES - total_bytes + 1)
                if len(data) != size or not data.startswith(b"\xff\xd8\xff"):
                    _fail("invalid_video")
                data = _jpeg_pixels_only(data)
                total_bytes += len(data)
                frames.append({"seconds": round(seconds, 6), "mime": "image/jpeg",
                               "dataUrl": "data:image/jpeg;base64," + base64.b64encode(data).decode("ascii")})
        _video_source_unchanged(path, descriptor, expected)
        if time.monotonic() > deadline:
            _fail("video_timeout")
        return {"ok": True, "duration": duration, "frames": frames}
    finally:
        os.close(descriptor)
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)


def suggest(path, snapshot, slug):
    expected = _expected_snapshot(snapshot)
    path, _ = _checked_source(path, expected)
    slug = _validate_slug(slug)
    original = os.path.basename(path)
    _, extension = _split_extension(original)
    parent = os.path.dirname(path)
    if slug + extension == original:
        _fail("nochange")
    for index in range(1, 1001):
        suffix = "" if index == 1 else "-" + str(index)
        # Keep the entire stem <=64 characters even when adding a suffix.
        base = slug[:MAX_STEM - len(suffix)].rstrip("-")
        filename = base + suffix + extension
        candidate = os.path.join(parent, filename)
        try:
            os.lstat(candidate)  # Counts directories and dangling links as occupied.
        except FileNotFoundError:
            _checked_source(path, expected)
            return {"ok": True, "filename": filename}
    _fail("name_exhausted")


def _rename_exclusive(source, target):
    if sys.platform != "darwin":
        _fail("unsupported_platform")
    library = ctypes.CDLL(None, use_errno=True)
    try:
        renamex = library.renamex_np
    except AttributeError:
        _fail("unsupported_platform")
    renamex.argtypes = (ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint)
    renamex.restype = ctypes.c_int
    # No overwrite, and no symbolic-link traversal during kernel resolution.
    result = renamex(os.fsencode(source), os.fsencode(target), RENAME_EXCL | RENAME_NOFOLLOW_ANY)
    if result != 0:
        number = ctypes.get_errno()
        if number == errno.EEXIST:
            _fail("collision")
        if number == errno.ELOOP:
            _fail("symlink")
        raise OSError(number, "rename_failed")


def rename(path, snapshot, filename):
    expected = _expected_snapshot(snapshot)
    path, _ = _checked_source(path, expected)
    original = os.path.basename(path)
    _, extension = _split_extension(original)
    filename = _validate_filename(filename, extension)
    if filename == original:
        _fail("nochange")
    target = os.path.join(os.path.dirname(path), filename)
    # Recheck immediately before applying. The kernel, not a prior exists check,
    # protects the target against a collision that arrives after the preview.
    _checked_source(path, expected)
    _rename_exclusive(path, target)
    return {"ok": True, "name": filename, "path": target}


def handle(request):
    try:
        if not isinstance(request, dict):
            _fail("bad_request")
        operation = request.get("op")
        if operation == "inspect":
            expected = _expected_snapshot(request["snapshot"]) if "snapshot" in request else None
            return inspect(request.get("path"), request.get("include_image", True), expected)
        if operation == "video_frames":
            return video_frames(request.get("path"), request.get("snapshot"))
        if operation == "suggest":
            return suggest(request.get("path"), request.get("snapshot"), request.get("slug"))
        if operation == "rename":
            return rename(request.get("path"), request.get("snapshot"), request.get("filename"))
        _fail("bad_request")
    except FileOpError as error:
        return {"ok": False, "errorCode": error.code}
    except FileNotFoundError:
        return {"ok": False, "errorCode": "not_found"}
    except PermissionError:
        return {"ok": False, "errorCode": "permission_denied"}
    except OSError as error:
        code = "symlink" if error.errno == errno.ELOOP else "io_error"
        return {"ok": False, "errorCode": code}
    except (TypeError, ValueError, UnicodeError, OverflowError):
        return {"ok": False, "errorCode": "bad_request"}


def main():
    try:
        raw = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
        if len(raw) > MAX_REQUEST_BYTES:
            _fail("bad_request")
        result = handle(json.loads(raw.decode("utf-8")))
    except (FileOpError, ValueError, UnicodeError):
        result = {"ok": False, "errorCode": "bad_request"}
    # Failures are structured data, not stderr/tracebacks containing file paths.
    sys.stdout.write(json.dumps(result, ensure_ascii=True, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
