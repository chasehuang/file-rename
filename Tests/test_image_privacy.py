"""Synthetic fixtures exercise the real macOS image decoder without Pillow."""

import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import struct
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock
import zlib


SCRIPT = Path(__file__).resolve().parents[1] / "source" / "FileRename.popclipext" / "file_ops.py"
SPEC = importlib.util.spec_from_file_location("file_ops_image_privacy", SCRIPT)
file_ops = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(file_ops)

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
PNG_ALLOWED = {b"IHDR", b"PLTE", b"IDAT", b"IEND", b"tRNS"}
EXIF_SECRET = b"PRIVATE_EXIF_DESCRIPTION_DO_NOT_UPLOAD"
GPS_SECRET = b"PRIVATE_GPS_PROCESSING_DO_NOT_UPLOAD"
XMP_SECRET = b"PRIVATE_XMP_DOCUMENT_DO_NOT_UPLOAD"
TEXT_SECRET = b"PRIVATE_PNG_TEXT_DO_NOT_UPLOAD"
COMMENT_SECRET = b"PRIVATE_JPEG_COMMENT_DO_NOT_UPLOAD"
XMP = (b'<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF '
       b'xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
       b'<rdf:Description xmlns:dc="http://purl.org/dc/elements/1.1/" '
       b'dc:description="' + XMP_SECRET + b'"/></rdf:RDF></x:xmpmeta>')

# Created for these tests: 80 x 40 red/green/blue/yellow quadrants. The WebP
# uses alpha 128 on the left and 255 on the right. No fixture-generation tool
# or third-party Python package is required when running the tests.
JPEG_BASE = base64.b64decode("/9j/4AAQSkZJRgABAQAASABIAAD/4QB6RXhpZgAATU0AKgAAAAgAAYdpAAQAAAABAAAAGgAAAAAABJKGAAcAAAAiAAAAUKABAAMAAAABAAEAAKACAAQAAAABAAAAUKADAAQAAAABAAAAKAAAAABBU0NJSQAAAFBSSVZBVEVfU1lOVEhFVElDX01FVEFEQVRB/+0AOFBob3Rvc2hvcCAzLjAAOEJJTQQEAAAAAAAAOEJJTQQlAAAAAAAQ1B2M2Y8AsgTpgAmY7PhCfv/AABEIACgAUAMBIgACEQEDEQH/xAAfAAABBQEBAQEBAQAAAAAAAAAAAQIDBAUGBwgJCgv/xAC1EAACAQMDAgQDBQUEBAAAAX0BAgMABBEFEiExQQYTUWEHInEUMoGRoQgjQrHBFVLR8CQzYnKCCQoWFxgZGiUmJygpKjQ1Njc4OTpDREVGR0hJSlNUVVZXWFlaY2RlZmdoaWpzdHV2d3h5eoOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4eLj5OXm5+jp6vHy8/T19vf4+fr/xAAfAQADAQEBAQEBAQEBAAAAAAAAAQIDBAUGBwgJCgv/xAC1EQACAQIEBAMEBwUEBAABAncAAQIDEQQFITEGEkFRB2FxEyIygQgUQpGhscEJIzNS8BVictEKFiQ04SXxFxgZGiYnKCkqNTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqCg4SFhoeIiYqSk5SVlpeYmZqio6Slpqeoqaqys7S1tre4ubrCw8TFxsfIycrS09TV1tfY2dri4+Tl5ufo6ery8/T19vf4+fr/2wBDAAICAgICAgMCAgMFAwMDBQYFBQUFBggGBgYGBggKCAgICAgICgoKCgoKCgoMDAwMDAwODg4ODg8PDw8PDw8PDw//2wBDAQICAgQEBAcEBAcQCwkLEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBD/3QAEAAX/2gAMAwEAAhEDEQA/APi+iiiv5TP9/AooooAK/SivzXr9KK/LfEr/AJcf9vf+2n+Ff7aj/mlf+5z/AN1Aooor8tP8KwooooA//9D80f8Ahav/AFC//I//ANro/wCFq/8AUL/8j/8A2uvIaK/1S/4kl8Mf+hT/AOVsR/8ALT9A/wCJvvET/oZ/+UaH/wAqPXv+Fq/9Qv8A8j//AGuj/hav/UL/API//wBrryGij/iSXwx/6FP/AJWxH/y0P+JvvET/AKGf/lGh/wDKj17/AIWr/wBQv/yP/wDa6/oe/wCGdf8AqYP/ACU/+3V/MHX9ilf43ftbPC7IuAf9W/8AVPD/AFf6x9b9p706nN7P6tyfxZTtbnl8Nr31vZW+J4xxtXxQ9l/r0/rX1W/sv+XXL7W3P/B9nzc3s4fFe1tLXd/mf/hnX/qYP/JT/wC3Uf8ADOv/AFMH/kp/9ur6Yor/ABt/13zT/n9/5LH/ACPif+JW+BP+hf8A+Va3/wAsPmf/AIZ1/wCpg/8AJT/7dR/wzr/1MH/kp/8Abq+mKKP9d80/5/f+Sx/yD/iVvgT/AKF//lWt/wDLD//R/HOiiiv9/D8rCiiigAr+xSv466/sUr/AP9uZ/wA0j/3O/wDuofqnhn/zEf8Abv8A7cFFFFf4Bn6oFFFFAH//2Q==")
WEBP_BASE = base64.b64decode("UklGRj4AAABXRUJQVlA4TDEAAAAvT8AJEB8gEEjaH3oNAUGR/6PNv4Cg6LrlYjaRApEAiSc96UkbmRjR/wkYDHTvsNA9AA==")


def png_chunk(kind, payload):
    return (struct.pack(">I", len(payload)) + kind + payload +
            struct.pack(">I", zlib.crc32(kind + payload) & 0xffffffff))


def png_fixture(width=4, height=2, pixels=None, extra_chunks=()):
    if pixels is None:
        row = bytes((240, 20, 40, 255)) * width
        raw = (b"\0" + row) * height
    else:
        raw = b"".join(b"\0" + bytes(channel for pixel in row for channel in pixel) for row in pixels)
    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (PNG_SIGNATURE + png_chunk(b"IHDR", header) +
            b"".join(png_chunk(kind, payload) for kind, payload in extra_chunks) +
            png_chunk(b"IDAT", zlib.compress(raw)) + png_chunk(b"IEND", b""))


def png_chunks(data):
    if not data.startswith(PNG_SIGNATURE):
        raise ValueError("Not PNG")
    offset, chunks = len(PNG_SIGNATURE), []
    while offset < len(data):
        if offset + 12 > len(data):
            raise ValueError("Truncated PNG chunk")
        length = struct.unpack_from(">I", data, offset)[0]
        kind = data[offset + 4:offset + 8]
        payload = data[offset + 8:offset + 8 + length]
        end = offset + 12 + length
        if end > len(data) or zlib.crc32(kind + payload) & 0xffffffff != struct.unpack_from(">I", data, end - 4)[0]:
            raise ValueError("Invalid PNG chunk checksum")
        chunks.append((kind, payload))
        offset = end
        if kind == b"IEND":
            if offset != len(data):
                raise ValueError("Data after PNG end")
            break
    return chunks


def rgba_pixels(data):
    """Decode 8-bit non-interlaced PNG test output using only the stdlib."""
    chunks = png_chunks(data)
    width, height, depth, color, compression, filtering, interlace = struct.unpack(">IIBBBBB", chunks[0][1])
    if (depth, compression, filtering, interlace) != (8, 0, 0, 0):
        raise ValueError("Unexpected PNG encoding for an 8-bit fixture")
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color]
    encoded = zlib.decompress(b"".join(payload for kind, payload in chunks if kind == b"IDAT"))
    stride = width * channels
    if len(encoded) != (stride + 1) * height:
        raise ValueError("Incorrect decoded PNG length")
    palette = next((payload for kind, payload in chunks if kind == b"PLTE"), b"")
    transparency = next((payload for kind, payload in chunks if kind == b"tRNS"), b"")
    rows, previous = [], bytearray(stride)
    for y in range(height):
        start = y * (stride + 1)
        filter_type = encoded[start]
        row = bytearray(encoded[start + 1:start + 1 + stride])
        for index in range(stride):
            left = row[index - channels] if index >= channels else 0
            up = previous[index]
            upper_left = previous[index - channels] if index >= channels else 0
            if filter_type == 0:
                predictor = 0
            elif filter_type == 1:
                predictor = left
            elif filter_type == 2:
                predictor = up
            elif filter_type == 3:
                predictor = (left + up) // 2
            elif filter_type == 4:
                p = left + up - upper_left
                distances = (abs(p - left), abs(p - up), abs(p - upper_left))
                predictor = (left, up, upper_left)[distances.index(min(distances))]
            else:
                raise ValueError("Unknown PNG filter")
            row[index] = (row[index] + predictor) & 255
        pixels = []
        for x in range(width):
            values = tuple(row[x * channels:(x + 1) * channels])
            if color == 6:
                pixel = values
            elif color == 2:
                alpha = 0 if transparency and values == struct.unpack(">HHH", transparency) else 255
                pixel = values + (alpha,)
            elif color == 4:
                pixel = (values[0],) * 3 + (values[1],)
            elif color == 0:
                alpha = 0 if transparency and values[0] == struct.unpack(">H", transparency)[0] else 255
                pixel = (values[0],) * 3 + (alpha,)
            else:
                index = values[0]
                pixel = tuple(palette[index * 3:index * 3 + 3]) + (transparency[index] if index < len(transparency) else 255,)
            pixels.append(pixel)
        rows.append(pixels)
        previous = row
    return width, height, rows


def exif_tiff(orientation=1):
    """A valid little-endian TIFF with orientation, description, and GPS IFD."""
    description = EXIF_SECRET + b"\0"
    gps_method = b"ASCII\0\0\0" + GPS_SECRET
    description_offset = 8 + 2 + 3 * 12 + 4
    gps_offset = description_offset + len(description)
    latitude_offset = gps_offset + 2 + 6 * 12 + 4
    longitude_offset = latitude_offset + 24
    method_offset = longitude_offset + 24

    def entry(tag, value_type, count, value):
        raw = struct.pack("<I", value) if isinstance(value, int) else value
        return struct.pack("<HHI", tag, value_type, count) + raw

    first = (struct.pack("<H", 3) +
             entry(0x010e, 2, len(description), description_offset) +
             entry(0x0112, 3, 1, struct.pack("<H", orientation) + b"\0\0") +
             entry(0x8825, 4, 1, gps_offset) + b"\0" * 4)
    gps = (struct.pack("<H", 6) +
           entry(0, 1, 4, b"\x02\x03\0\0") +
           entry(1, 2, 2, b"N\0\0\0") + entry(2, 5, 3, latitude_offset) +
           entry(3, 2, 2, b"E\0\0\0") + entry(4, 5, 3, longitude_offset) +
           entry(27, 7, len(gps_method), method_offset) + b"\0" * 4)
    coordinates = struct.pack("<IIIIIIIIIIII", 25, 1, 2, 1, 3, 1, 121, 1, 30, 1, 15, 1)
    return b"II\x2a\0\x08\0\0\0" + first + description + gps + coordinates + gps_method


def jpeg_segment(marker, payload):
    return b"\xff" + bytes((marker,)) + struct.pack(">H", len(payload) + 2) + payload


def jpeg_fixture(orientation=6):
    # Remove the base fixture's APP/COM sections before adding our known data.
    kept, offset = [b"\xff\xd8"], 2
    while offset < len(JPEG_BASE):
        if JPEG_BASE[offset] != 255:
            raise ValueError("Invalid JPEG fixture")
        marker = JPEG_BASE[offset + 1]
        if marker == 0xda:
            kept.append(JPEG_BASE[offset:])
            break
        length = struct.unpack_from(">H", JPEG_BASE, offset + 2)[0]
        end = offset + 2 + length
        if not (0xe0 <= marker <= 0xef or marker == 0xfe):
            kept.append(JPEG_BASE[offset:end])
        offset = end
    metadata = (jpeg_segment(0xe1, b"Exif\0\0" + exif_tiff(orientation)) +
                jpeg_segment(0xe1, b"http://ns.adobe.com/xap/1.0/\0" + XMP) +
                jpeg_segment(0xfe, COMMENT_SECRET))
    return kept[0] + metadata + b"".join(kept[1:])


def riff_chunk(kind, payload):
    return kind + struct.pack("<I", len(payload)) + payload + (b"\0" if len(payload) % 2 else b"")


def webp_fixture():
    # Add a valid extended RIFF header advertising alpha, EXIF, and XMP.
    dimensions = (79).to_bytes(3, "little") + (39).to_bytes(3, "little")
    body = (b"WEBP" + riff_chunk(b"VP8X", b"\x1c\0\0\0" + dimensions) + WEBP_BASE[12:] +
            riff_chunk(b"EXIF", b"Exif\0\0" + exif_tiff()) + riff_chunk(b"XMP ", XMP))
    return b"RIFF" + struct.pack("<I", len(body)) + body


@unittest.skipUnless(sys.platform == "darwin", "The extension uses macOS ImageIO via osascript")
class ImagePrivacyTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="popclip-image-privacy-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()

    def inspect_sanitized(self, name, original):
        source = self.root / name
        source.write_bytes(original)
        before = source.stat()
        digest = hashlib.sha256(original).digest()
        metadata = file_ops.handle({"op": "inspect", "path": str(source), "include_image": False})
        self.assertTrue(metadata["ok"], metadata)
        result = file_ops.handle({"op": "inspect", "path": str(source), "include_image": True,
                                  "snapshot": metadata["snapshot"]})
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["image"]["mime"], "image/png")
        prefix, encoded = result["image"]["dataUrl"].split(",", 1)
        self.assertEqual(prefix, "data:image/png;base64")
        data = base64.b64decode(encoded, validate=True)
        chunks = png_chunks(data)
        self.assertEqual(chunks[0][0], b"IHDR")
        self.assertEqual(chunks[-1], (b"IEND", b""))
        self.assertTrue(any(kind == b"IDAT" for kind, _ in chunks))
        self.assertLessEqual({kind for kind, _ in chunks}, PNG_ALLOWED)
        width, height = struct.unpack_from(">II", chunks[0][1])
        self.assertGreater(min(width, height), 0)
        self.assertLessEqual(max(width, height), 1600)
        for secret in (EXIF_SECRET, GPS_SECRET, XMP_SECRET, TEXT_SECRET, COMMENT_SECRET, b"PRIVATE_SYNTHETIC_METADATA"):
            self.assertNotIn(secret, data)
        self.assertEqual(hashlib.sha256(source.read_bytes()).digest(), digest)
        after = source.stat()
        self.assertEqual((after.st_size, after.st_mtime_ns, after.st_ino), (before.st_size, before.st_mtime_ns, before.st_ino))
        self.assertEqual(result["snapshot"], metadata["snapshot"])
        return data

    def test_png_text_itxt_exif_gps_and_compressed_text_are_removed(self):
        fixture = png_fixture(extra_chunks=[
            (b"tEXt", b"Comment\0" + TEXT_SECRET),
            (b"iTXt", b"XML:com.adobe.xmp\0\0\0\0\0" + XMP),
            (b"zTXt", b"Description\0\0" + zlib.compress(TEXT_SECRET)),
            (b"eXIf", exif_tiff()),
        ])
        for secret in (TEXT_SECRET, XMP_SECRET, EXIF_SECRET, GPS_SECRET):
            self.assertIn(secret, fixture)
        clean = self.inspect_sanitized("private.png", fixture)
        self.assertEqual(rgba_pixels(clean)[:2], (4, 2), "Small images must not be enlarged")

    def test_jpeg_exif_gps_xmp_and_comments_are_removed_and_orientation_is_baked(self):
        fixture = jpeg_fixture(orientation=6)
        for secret in (EXIF_SECRET, GPS_SECRET, XMP_SECRET, COMMENT_SECRET):
            self.assertIn(secret, fixture)
        clean = self.inspect_sanitized("private-orientation.jpg", fixture)
        width, height, pixels = rgba_pixels(clean)
        self.assertEqual((width, height), (40, 80))
        # Orientation 6 rotates clockwise: blue/red/yellow/green quadrants.
        corners = (pixels[10][10], pixels[10][-11], pixels[-11][10], pixels[-11][-11])
        for actual, expected in zip(corners, ((0, 0, 255), (255, 0, 0), (255, 255, 0), (0, 255, 0))):
            self.assertTrue(all(abs(actual[index] - expected[index]) < 35 for index in range(3)), (actual, expected))

    def test_png_alpha_is_preserved(self):
        pixels = [[(240, 20, 40, alpha) for alpha in (0, 64, 128, 255)] for _ in range(2)]
        clean = self.inspect_sanitized("transparent.png", png_fixture(pixels=pixels))
        width, height, actual = rgba_pixels(clean)
        self.assertEqual((width, height), (4, 2))
        self.assertEqual([[pixel[3] for pixel in row] for row in actual], [[0, 64, 128, 255]] * 2)

    def test_webp_exif_and_xmp_are_removed_without_losing_alpha(self):
        fixture = webp_fixture()
        for secret in (EXIF_SECRET, GPS_SECRET, XMP_SECRET):
            self.assertIn(secret, fixture)
        clean = self.inspect_sanitized("transparent.webp", fixture)
        width, height, pixels = rgba_pixels(clean)
        self.assertEqual((width, height), (80, 40))
        self.assertEqual((pixels[10][10][3], pixels[10][70][3]), (128, 255))

    def test_large_images_are_resized_proportionally_to_1600_pixels(self):
        clean = self.inspect_sanitized("large.png", png_fixture(2400, 1200))
        dimensions = struct.unpack_from(">II", png_chunks(clean)[0][1])
        self.assertEqual(dimensions, (1600, 800))

    def test_video_jpeg_filter_removes_every_app_and_comment_segment(self):
        fixture = jpeg_fixture()
        # Exercise all APP types as well as metadata after the compressed scan.
        extras = b"".join(jpeg_segment(marker, b"PRIVATE_APP_DATA") for marker in range(0xe0, 0xf0))
        fixture = fixture[:2] + extras + fixture[2:-2] + jpeg_segment(0xfe, COMMENT_SECRET) + fixture[-2:]
        clean = file_ops._jpeg_pixels_only(fixture)
        self.assertTrue(clean.startswith(b"\xff\xd8"))
        self.assertTrue(clean.endswith(b"\xff\xd9"))
        self.assertIn(b"\xff\xda", clean, "The compressed image scan must be retained")
        for marker in (*range(0xe0, 0xf0), 0xfe):
            self.assertNotIn(b"\xff" + bytes((marker,)), clean)
        for secret in (EXIF_SECRET, GPS_SECRET, XMP_SECRET, COMMENT_SECRET, b"PRIVATE_APP_DATA"):
            self.assertNotIn(secret, clean)
        # The bytes remaining after filtering must still decode as an image.
        decoded = file_ops._sanitize_image(clean, ".jpg")
        self.assertEqual(rgba_pixels(decoded)[:2], (80, 40))

    def test_malformed_png_chunks_fail_closed(self):
        fixture = png_fixture()
        bad_crc = fixture[:-1] + bytes((fixture[-1] ^ 1,))
        no_pixels = PNG_SIGNATURE + png_chunk(b"IHDR", png_chunks(fixture)[0][1]) + png_chunk(b"IEND", b"")
        cases = {
            "truncated chunk": fixture[:-1],
            "bad checksum": bad_crc,
            "unknown critical chunk": png_fixture(extra_chunks=[(b"SECR", TEXT_SECRET)]),
            "missing image data": no_pixels,
            "trailing private bytes": fixture + TEXT_SECRET,
        }
        for label, data in cases.items():
            with self.subTest(label=label), self.assertRaises(file_ops.FileOpError) as raised:
                file_ops._png_pixels_only(data)
            self.assertEqual(raised.exception.code, "image_sanitization_failed")

    def test_malformed_jpeg_segments_fail_closed(self):
        fixture = jpeg_fixture()
        cases = {
            "truncated segment": b"\xff\xd8\xff\xe1\0\x20" + EXIF_SECRET[:3],
            "invalid segment length": b"\xff\xd8\xff\xe1\0\x01",
            "missing end marker": fixture[:-2],
            "end before scan": b"\xff\xd8\xff\xd9",
            "trailing private bytes": fixture + COMMENT_SECRET,
        }
        for label, data in cases.items():
            with self.subTest(label=label), self.assertRaises(file_ops.FileOpError) as raised:
                file_ops._jpeg_pixels_only(data)
            self.assertEqual(raised.exception.code, "invalid_video")

    def test_source_changed_during_decoding_discards_the_sanitized_payload(self):
        source = self.root / "changed-during-decoding.png"
        source.write_bytes(png_fixture())
        replacement = png_fixture(5, 3)
        real_run = subprocess.run

        def replace_after_decode(command, **kwargs):
            result = real_run(command, **kwargs)
            self.assertEqual(result.returncode, 0)
            source.write_bytes(replacement)  # Simulate an unrelated editor.
            return result

        with mock.patch.object(file_ops.subprocess, "run", side_effect=replace_after_decode) as decoder:
            result = file_ops.handle({"op": "inspect", "path": str(source), "include_image": True})
        self.assertEqual(decoder.call_count, 1)
        self.assertEqual(result, {"ok": False, "errorCode": "changed"})
        self.assertEqual(source.read_bytes(), replacement)

    def test_corrupt_image_fails_closed_without_returning_source_bytes(self):
        original = PNG_SIGNATURE + b"CORRUPT_PRIVATE_IMAGE_DO_NOT_UPLOAD"
        source = self.root / "corrupt.png"
        source.write_bytes(original)
        before = source.stat().st_mtime_ns
        result = file_ops.handle({"op": "inspect", "path": str(source), "include_image": True})
        self.assertEqual(result, {"ok": False, "errorCode": "image_sanitization_failed"})
        self.assertEqual(source.read_bytes(), original)
        self.assertEqual(source.stat().st_mtime_ns, before)

    def test_decoder_timeout_fails_closed_without_returning_source_bytes(self):
        original = png_fixture()
        source = self.root / "timeout.png"
        source.write_bytes(original)
        before = source.stat().st_mtime_ns
        with mock.patch.object(file_ops.subprocess, "run", side_effect=subprocess.TimeoutExpired("osascript", 20)):
            result = file_ops.handle({"op": "inspect", "path": str(source), "include_image": True})
        self.assertEqual(result, {"ok": False, "errorCode": "image_timeout"})
        self.assertEqual(source.read_bytes(), original)
        self.assertEqual(source.stat().st_mtime_ns, before)

    def test_cancel_signal_reaps_decoder_and_removes_temporary_image_copies(self):
        original = png_fixture(extra_chunks=[(b"tEXt", b"Comment\0" + TEXT_SECRET)])
        source = self.root / "cancel.png"
        source.write_bytes(original)
        before = source.stat().st_mtime_ns
        worker_code = r'''
import importlib.util, json, subprocess, sys
spec = importlib.util.spec_from_file_location("isolated_file_ops", sys.argv[1])
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
real_run = subprocess.run
def blocked_decoder(command, **kwargs):
    code = "import os,pathlib,sys,time; pathlib.Path(sys.argv[1]).write_text(str(os.getpid())); time.sleep(60)"
    return real_run([sys.executable, "-c", code, sys.argv[3]], **kwargs)
helper.subprocess.run = blocked_decoder
print(json.dumps(helper.handle({"op": "inspect", "path": sys.argv[2], "include_image": True})), flush=True)
'''
        for signum in (signal.SIGTERM, signal.SIGINT):
            with self.subTest(signum=signum):
                temporary = self.root / f"isolated-temp-{signum}"
                temporary.mkdir()
                pidfile = self.root / f"decoder-{signum}.pid"
                worker = subprocess.Popen(
                    [sys.executable, "-c", worker_code, str(SCRIPT), str(source), str(pidfile)],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    env={**os.environ, "TMPDIR": str(temporary)}, text=True,
                )
                try:
                    deadline = time.monotonic() + 10
                    while not pidfile.exists() and worker.poll() is None and time.monotonic() < deadline:
                        time.sleep(0.02)
                    self.assertTrue(pidfile.exists(), "Decoder did not reach the cancellable stage")
                    self.assertTrue(list(temporary.glob("popclip-image-upload-*")))
                    worker.send_signal(signum)
                    output, errors = worker.communicate(timeout=5)
                    self.assertEqual(worker.returncode, 0, errors)
                    self.assertEqual(json.loads(output), {"ok": False, "errorCode": "image_cancelled"})
                    self.assertEqual(list(temporary.iterdir()), [])
                    child_pid = int(pidfile.read_text())
                    with self.assertRaises(ProcessLookupError):
                        os.kill(child_pid, 0)
                finally:
                    if worker.poll() is None:
                        worker.kill()
                        worker.communicate(timeout=5)
                self.assertEqual(source.read_bytes(), original)
                self.assertEqual(source.stat().st_mtime_ns, before)


if __name__ == "__main__":
    unittest.main()
