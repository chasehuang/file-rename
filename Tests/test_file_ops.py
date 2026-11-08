import base64
import builtins
import importlib.util
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from test_image_privacy import JPEG_BASE, WEBP_BASE, png_fixture


SCRIPT = Path(__file__).resolve().parents[1] / "source" / "FileRename.popclipext" / "file_ops.py"
SPEC = importlib.util.spec_from_file_location("file_ops", SCRIPT)
file_ops = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(file_ops)


class FileOperationsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="popclip-filename-test-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name).resolve()

    def make(self, name="原始 檔案.txt", data=b"original bytes\x00\xff"):
        path = self.root / name
        path.write_bytes(data)
        return path

    def inspect(self, path):
        result = file_ops.handle({"op": "inspect", "path": str(path)})
        self.assertTrue(result["ok"], result)
        return result

    def apply(self, path, snapshot, filename):
        return file_ops.handle({"op": "rename", "path": str(path), "snapshot": snapshot, "filename": filename})

    def assert_error(self, result, expected):
        self.assertEqual(result, {"ok": False, "errorCode": expected})

    def test_inspect_nonimage_does_not_read_contents(self):
        source = self.make()
        with mock.patch.object(file_ops.os, "open", side_effect=AssertionError("No nonimage file reads")):
            result = self.inspect(source)
        self.assertIsNone(result["image"])
        self.assertEqual(result["name"], source.name)
        self.assertEqual(result["stem"], "原始 檔案")
        self.assertEqual(result["extension"], ".txt")
        self.assertEqual(set(result["snapshot"]), {"dev", "ino", "size", "mtime_ns"})
        self.assertTrue(all(isinstance(value, str) for value in result["snapshot"].values()))
        self.assertEqual(result["snapshot"]["mtime_ns"], str(source.stat().st_mtime_ns))

    @unittest.skipUnless(sys.platform == "darwin", "ImageIO is a macOS API")
    def test_supported_images_are_reencoded_as_png(self):
        fixtures = [
            ("截圖.PNG", png_fixture()),
            ("相片.JpEg", JPEG_BASE),
            ("圖.webp", WEBP_BASE),
        ]
        for name, data in fixtures:
            with self.subTest(name=name):
                result = self.inspect(self.make(name, data))
                self.assertEqual(result["image"]["mime"], "image/png")
                prefix, encoded = result["image"]["dataUrl"].split(",", 1)
                self.assertEqual(prefix, "data:image/png;base64")
                self.assertTrue(base64.b64decode(encoded).startswith(b"\x89PNG\r\n\x1a\n"))
                self.assertEqual((self.root / name).read_bytes(), data)

    def test_image_extension_mismatch_rejected(self):
        for name, data in [("fake.png", b"\xff\xd8\xffjpeg"), ("fake.jpg", b"not an image"), ("fake.webp", b"RIFFshort")]:
            self.assert_error(file_ops.handle({"op": "inspect", "path": str(self.make(name, data))}), "image_type_mismatch")

    def test_oversized_image_is_rejected_before_open(self):
        source = self.make("huge.png", b"")
        with source.open("wb") as stream:
            stream.truncate(file_ops.MAX_IMAGE_BYTES + 1)
        with mock.patch.object(file_ops.os, "open", side_effect=AssertionError("Oversized image must not be read")):
            self.assert_error(file_ops.handle({"op": "inspect", "path": str(source)}), "image_too_large")

    def test_metadata_only_does_not_open_or_validate_image_contents(self):
        for name in ("封面 米白底.png", "封面 米白底.webp"):
            with self.subTest(name=name):
                source = self.make(name, b"not an image")
                if name.endswith(".webp"):
                    with source.open("wb") as stream:
                        stream.truncate(file_ops.MAX_IMAGE_BYTES + 1)
                with mock.patch.object(file_ops.os, "open", side_effect=AssertionError("Metadata must not read image bytes")):
                    result = file_ops.handle({"op": "inspect", "path": str(source), "include_image": False})
                self.assertTrue(result["ok"], result)
                self.assertIsNone(result["image"])
                self.assertEqual(result["stem"], "封面 米白底")
                self.assertEqual(result["snapshot"]["size"], str(source.stat().st_size))

    def test_explicit_image_inspection_still_checks_format_and_size(self):
        invalid = self.make("invalid.png", b"not an image")
        self.assert_error(file_ops.handle({"op": "inspect", "path": str(invalid), "include_image": True}), "image_type_mismatch")
        oversized = self.make("oversized.png", b"")
        with oversized.open("wb") as stream:
            stream.truncate(file_ops.MAX_IMAGE_BYTES + 1)
        with mock.patch.object(file_ops.os, "open", side_effect=AssertionError("Oversized image must not be read")):
            self.assert_error(file_ops.handle({"op": "inspect", "path": str(oversized), "include_image": True}), "image_too_large")

    @unittest.skipUnless(sys.platform == "darwin", "ImageIO is a macOS API")
    def test_second_inspection_checks_metadata_snapshot_before_reading(self):
        source = self.make("Group 4.png", png_fixture())
        metadata = file_ops.handle({"op": "inspect", "path": str(source), "include_image": False})
        image = file_ops.handle({"op": "inspect", "path": str(source), "include_image": True, "snapshot": metadata["snapshot"]})
        self.assertTrue(image["ok"], image)
        self.assertEqual(image["snapshot"], metadata["snapshot"])
        self.assertEqual(image["image"]["mime"], "image/png")
        source.write_bytes(b"changed after metadata")
        with mock.patch.object(file_ops.os, "open", side_effect=AssertionError("Changed source must not be read")):
            for include_image in (False, True):
                self.assert_error(file_ops.handle({"op": "inspect", "path": str(source), "include_image": include_image, "snapshot": metadata["snapshot"]}), "changed")

    def test_inspect_rejects_nonboolean_image_flag_and_invalid_snapshot(self):
        source = self.make()
        for include_image in (None, 0, 1, "false", [], {}):
            with self.subTest(include_image=include_image):
                self.assert_error(file_ops.handle({"op": "inspect", "path": str(source), "include_image": include_image}), "bad_request")
        for snapshot in (None, {}, "invalid"):
            with self.subTest(snapshot=snapshot):
                self.assert_error(file_ops.handle({"op": "inspect", "path": str(source), "snapshot": snapshot}), "invalid_snapshot")

    def test_oversized_nonimage_still_uses_metadata(self):
        source = self.make("large.bin", b"")
        with source.open("wb") as stream:
            stream.truncate(file_ops.MAX_IMAGE_BYTES + 1)
        with mock.patch.object(file_ops.os, "open", side_effect=AssertionError("No nonimage reads")):
            self.assertIsNone(self.inspect(source)["image"])

    @unittest.skipUnless(sys.platform == "darwin", "renamex_np is a macOS API")
    def test_rename_preserves_bytes_unicode_source_and_extension_case(self):
        data = JPEG_BASE
        source = self.make("旅行 作品.JPEG", data)
        snapshot = self.inspect(source)["snapshot"]
        result = self.apply(source, snapshot, "travel-artwork.JPEG")
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["name"], "travel-artwork.JPEG")
        self.assertEqual(Path(result["path"]).read_bytes(), data)
        self.assertEqual(str(Path(result["path"]).stat().st_ino), snapshot["ino"])
        self.assertFalse(source.exists())

    @unittest.skipUnless(sys.platform == "darwin", "renamex_np is a macOS API")
    def test_compound_extension_case_preserved(self):
        for suffix in (".tar.gz", ".TAR.Bz2", ".Tar.xZ"):
            with self.subTest(suffix=suffix):
                source = self.make("壓縮 檔案" + suffix)
                inspected = self.inspect(source)
                self.assertEqual(inspected["extension"], suffix)
                self.assertEqual(inspected["stem"], "壓縮 檔案")
                result = self.apply(source, inspected["snapshot"], "project-backup" + suffix)
                self.assertTrue(result["ok"], result)
                self.assertEqual(Path(result["path"]).suffix, Path(source).suffix)

    @unittest.skipUnless(sys.platform == "darwin", "renamex_np is a macOS API")
    def test_existing_destination_is_never_overwritten(self):
        source = self.make("source.txt", b"source")
        target = self.make("destination.txt", b"precious target")
        snapshot = self.inspect(source)["snapshot"]
        self.assert_error(self.apply(source, snapshot, target.name), "collision")
        self.assertEqual(source.read_bytes(), b"source")
        self.assertEqual(target.read_bytes(), b"precious target")

    @unittest.skipUnless(sys.platform == "darwin", "renamex_np is a macOS API")
    def test_collision_arriving_after_preview_is_still_atomic(self):
        source = self.make("source.txt", b"source")
        snapshot = self.inspect(source)["snapshot"]
        original_rename = file_ops._rename_exclusive
        def racing_destination(src, dst):
            Path(dst).write_bytes(b"arrived after preview")
            return original_rename(src, dst)
        with mock.patch.object(file_ops, "_rename_exclusive", side_effect=racing_destination):
            self.assert_error(self.apply(source, snapshot, "destination.txt"), "collision")
        self.assertEqual(source.read_bytes(), b"source")
        self.assertEqual((self.root / "destination.txt").read_bytes(), b"arrived after preview")

    def test_changed_source_is_rejected_for_suggest_and_rename(self):
        source = self.make()
        snapshot = self.inspect(source)["snapshot"]
        source.write_bytes(b"changed after inspection")
        self.assert_error(self.apply(source, snapshot, "updated.txt"), "changed")
        self.assert_error(file_ops.handle({"op": "suggest", "path": str(source), "snapshot": snapshot, "slug": "updated"}), "changed")
        self.assertFalse((self.root / "updated.txt").exists())

    def test_replaced_inode_is_rejected_even_with_size_and_mtime_restored(self):
        source = self.make()
        snapshot = self.inspect(source)["snapshot"]
        backup = self.root / "held-original"
        source.rename(backup)
        source.write_bytes(backup.read_bytes())
        os.utime(source, ns=(int(snapshot["mtime_ns"]), int(snapshot["mtime_ns"])))
        self.assert_error(self.apply(source, snapshot, "updated.txt"), "changed")

    def test_symlinks_and_directories_are_rejected(self):
        source = self.make()
        snapshot = self.inspect(source)["snapshot"]
        link = self.root / "linked.txt"
        link.symlink_to(source)
        directory = self.root / "folder"
        directory.mkdir()
        for path, code in ((link, "symlink"), (directory, "not_regular_file")):
            self.assert_error(file_ops.handle({"op": "inspect", "path": str(path)}), code)
            self.assert_error(self.apply(path, snapshot, "updated.txt"), code)

    def test_source_replaced_by_symlink_after_inspection_is_rejected(self):
        source = self.make()
        snapshot = self.inspect(source)["snapshot"]
        source.unlink()
        source.symlink_to(self.make("unrelated.txt", b"untouched"))
        self.assert_error(self.apply(source, snapshot, "updated.txt"), "symlink")
        self.assertEqual((self.root / "unrelated.txt").read_bytes(), b"untouched")

    def test_symlink_parent_is_rejected_without_following_it(self):
        real = self.root / "real-folder"
        real.mkdir()
        source = real / "source.txt"
        source.write_bytes(b"untouched")
        snapshot = self.inspect(source)["snapshot"]
        alias = self.root / "alias-folder"
        alias.symlink_to(real, target_is_directory=True)
        through_alias = alias / source.name
        self.assert_error(file_ops.handle({"op": "inspect", "path": str(through_alias)}), "symlink")
        self.assert_error(self.apply(through_alias, snapshot, "renamed.txt"), "symlink")
        self.assertEqual(source.read_bytes(), b"untouched")
        self.assertFalse((real / "renamed.txt").exists())

    def test_traversal_bad_slug_and_extension_changes_are_rejected(self):
        source = self.make()
        snapshot = self.inspect(source)["snapshot"]
        for name in ("../escape.txt", "/tmp/escape.txt", "nested/new.txt", "nested\\new.txt", "foo..txt", "x\x00.txt"):
            self.assert_error(self.apply(source, snapshot, name), "invalid_filename")
        for name in ("Upper.txt", "中文.txt", "two words.txt", "bad--slug.txt", "-leading.txt", "a" * 65 + ".txt"):
            self.assert_error(self.apply(source, snapshot, name), "invalid_slug")
        for name in ("changed.md", "changed.TXT", "changed"):
            self.assert_error(self.apply(source, snapshot, name), "extension_mismatch")
        self.assertTrue(source.exists())

    def test_snapshot_shape_and_relative_paths_are_rejected(self):
        source = self.make()
        snapshot = self.inspect(source)["snapshot"]
        for bad in (None, {}, {**snapshot, "size": True}, {**snapshot, "ino": int(snapshot["ino"])}, {**snapshot, "mtime_ns": "01"}, {**snapshot, "extra": 1}):
            self.assert_error(self.apply(source, bad, "updated.txt"), "invalid_snapshot")
        for path in (source.name, str(self.root / ".." / source.name), "", "bad\x00path"):
            self.assert_error(file_ops.handle({"op": "inspect", "path": path}), "invalid_path")

    def test_suggest_suffixes_without_mutating_files_and_preserves_extension(self):
        source = self.make("原名.TXT")
        snapshot = self.inspect(source)["snapshot"]
        self.make("project.TXT")
        (self.root / "project-2.TXT").symlink_to(self.root / "missing-target")
        (self.root / "project-3.TXT").mkdir()
        result = file_ops.handle({"op": "suggest", "path": str(source), "snapshot": snapshot, "slug": "project"})
        self.assertEqual(result, {"ok": True, "filename": "project-4.TXT"})
        self.assertFalse((self.root / result["filename"]).exists())
        self.assertTrue(source.exists())

    def test_suggest_numbered_suffix_never_exceeds_stem_limit(self):
        source = self.make()
        snapshot = self.inspect(source)["snapshot"]
        slug = "x" * 64
        self.make(slug + ".txt")
        result = file_ops.handle({"op": "suggest", "path": str(source), "snapshot": snapshot, "slug": slug})
        self.assertEqual(result, {"ok": True, "filename": "x" * 62 + "-2.txt"})

    def test_same_name_is_nochange(self):
        source = self.make("already-english.txt")
        snapshot = self.inspect(source)["snapshot"]
        self.assert_error(self.apply(source, snapshot, source.name), "nochange")
        self.assert_error(file_ops.handle({"op": "suggest", "path": str(source), "snapshot": snapshot, "slug": "already-english"}), "nochange")

    def test_cli_errors_are_json_without_paths_or_tracebacks(self):
        for data in (b"{broken", json.dumps({"op": "inspect", "path": str(self.root / "private-name.txt")}).encode(), b"x" * (file_ops.MAX_REQUEST_BYTES + 1)):
            completed = subprocess.run([sys.executable, str(SCRIPT)], input=data, capture_output=True, timeout=10)
            self.assertEqual(completed.returncode, 0)
            self.assertEqual(completed.stderr, b"")
            result = json.loads(completed.stdout)
            self.assertFalse(result["ok"])
            self.assertEqual(set(result), {"ok", "errorCode"})
            self.assertNotIn(str(self.root).encode(), completed.stdout)


class VideoFramesTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="popclip-video-test-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name).resolve()

    def make(self, name="fixture.mp4", data=b"synthetic source"):
        source = self.root / name
        source.write_bytes(data)
        return source

    def request(self, source, snapshot=None):
        if snapshot is None:
            snapshot = file_ops.inspect(str(source), False)["snapshot"]
        return {"op": "video_frames", "path": str(source), "snapshot": snapshot}

    def fake_runner(self, calls, duration=2, image=JPEG_BASE):
        def run(command, descriptor, deadline, capture=False):
            calls.append((command, descriptor, deadline, capture))
            self.assertTrue(stat.S_ISREG(os.fstat(descriptor).st_mode))
            if capture:
                return json.dumps({"streams": [{"width": 320, "height": 180, "duration": str(duration), "avg_frame_rate": "10/1"}]}).encode()
            Path(command[-1]).write_bytes(image)
            return b""
        return run

    def tools(self):
        try:
            return file_ops._video_tools()
        except file_ops.FileOpError:
            self.skipTest("ffmpeg/ffprobe are not installed")

    def synthetic(self, name="fixture.mp4", size="320x180", duration="2", rate="10", audio=False):
        ffmpeg, _ = self.tools()
        source = self.root / name
        command = [ffmpeg, "-v", "error", "-f", "lavfi", "-i", f"testsrc2=size={size}:rate={rate}:duration={duration}"]
        if audio:
            command += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}"]
        command += ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "30"]
        if audio:
            command += ["-c:a", "aac", "-shortest"]
        result = subprocess.run(command + [str(source)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
        self.assertEqual(result.returncode, 0)
        return source

    def jpeg_size(self, data):
        offset = 2
        while offset < len(data):
            self.assertEqual(data[offset], 255)
            marker = data[offset + 1]
            length = int.from_bytes(data[offset + 2:offset + 4], "big")
            if marker in (192, 193, 194):
                return (int.from_bytes(data[offset + 7:offset + 9], "big"),
                        int.from_bytes(data[offset + 5:offset + 7], "big"))
            offset += 2 + length
        self.fail("JPEG has no dimensions")

    def test_real_video_with_audio_returns_eight_ordered_downscaled_jpegs(self):
        source = self.synthetic(size="1920x1080", audio=True)
        before = source.stat()
        result = file_ops.handle(self.request(source))
        self.assertTrue(result["ok"], result)
        self.assertAlmostEqual(result["duration"], 2, places=2)
        self.assertEqual(len(result["frames"]), 8)
        seconds = [frame["seconds"] for frame in result["frames"]]
        self.assertEqual(seconds, sorted(set(seconds)))
        self.assertAlmostEqual(seconds[0], .1, places=3)
        self.assertAlmostEqual(seconds[-1], 1.9, places=3)
        total = 0
        for frame in result["frames"]:
            self.assertEqual(frame["mime"], "image/jpeg")
            self.assertTrue(frame["dataUrl"].startswith("data:image/jpeg;base64,"))
            data = base64.b64decode(frame["dataUrl"].split(",", 1)[1])
            self.assertEqual(self.jpeg_size(data), (1600, 900))
            total += len(data)
        self.assertLessEqual(total, file_ops.MAX_IMAGE_BYTES)
        self.assertEqual(source.stat().st_mtime_ns, before.st_mtime_ns)
        self.assertEqual(source.stat().st_size, before.st_size)

    def test_real_tiny_low_rate_video_returns_one_frame_without_upscale(self):
        source = self.synthetic(duration="0.1", rate="10")
        result = file_ops.handle(self.request(source))
        self.assertTrue(result["ok"], result)
        self.assertEqual(len(result["frames"]), 1)
        data = base64.b64decode(result["frames"][0]["dataUrl"].split(",", 1)[1])
        self.assertEqual(self.jpeg_size(data), (320, 180))
        self.assertEqual(result["frames"][0]["seconds"], 0)

    def test_real_matroska_container_and_low_frame_rate(self):
        source = self.synthetic(name="fixture.mkv", duration="1", rate="2")
        result = file_ops.handle(self.request(source))
        self.assertTrue(result["ok"], result)
        self.assertGreaterEqual(len(result["frames"]), 1)
        self.assertLessEqual(len(result["frames"]), 2)

    def test_fake_playlist_with_video_extension_is_rejected(self):
        self.tools()
        source = self.make(data=b"#EXTM3U\n#EXTINF:1,\nhttps://example.invalid/never-fetch.ts\n")
        self.assertEqual(file_ops.handle(self.request(source)), {"ok": False, "errorCode": "invalid_video"})

    def test_supported_extensions_force_container_and_disable_external_inputs_audio_subtitles(self):
        for suffix, demuxer in ((".MP4", "mov"), (".mov", "mov"), (".m4v", "mov"), (".webm", "matroska"), (".mkv", "matroska")):
            with self.subTest(suffix=suffix):
                source = self.make("fixture" + suffix)
                calls = []
                with mock.patch.object(file_ops, "_video_tools", return_value=("/fixed/ffmpeg", "/fixed/ffprobe")), mock.patch.object(file_ops, "_run_video", side_effect=self.fake_runner(calls)):
                    result = file_ops.handle(self.request(source))
                self.assertTrue(result["ok"], result)
                self.assertEqual(len(calls), 9)
                for command, descriptor, _, capture in calls:
                    self.assertNotIn(str(source), command)
                    self.assertEqual(command[command.index("-protocol_whitelist") + 1], "fd")
                    self.assertEqual(command[command.index("-fd") + 1], str(descriptor))
                    self.assertEqual(command[command.index("-f") + 1], demuxer)
                    self.assertEqual(command[command.index("-i") + 1], "fd:")
                    if demuxer == "mov":
                        self.assertEqual(command[command.index("-enable_drefs") + 1], "0")
                        self.assertEqual(command[command.index("-use_absolute_path") + 1], "0")
                    if not capture:
                        for option in ("-an", "-sn", "-dn"):
                            self.assertIn(option, command)
                        self.assertEqual(command[command.index("-map_metadata") + 1], "-1")
                        self.assertEqual(command[command.index("-map_chapters") + 1], "-1")
                        self.assertEqual(command[command.index("-map") + 1], "0:v:0")
                        self.assertFalse(Path(command[-1]).parent.exists())
                with self.assertRaises(OSError):
                    os.fstat(calls[0][1])

    def test_unsupported_container_and_missing_tools_have_fixed_errors(self):
        self.assertEqual(file_ops.handle(self.request(self.make("fixture.avi"))), {"ok": False, "errorCode": "unsupported_video"})
        with mock.patch.object(file_ops, "VIDEO_TOOL_DIRECTORIES", ()):
            self.assertEqual(file_ops.handle(self.request(self.make())), {"ok": False, "errorCode": "missing_video_tools"})

    def test_changed_source_and_symlink_are_rejected_before_decode(self):
        source = self.make()
        request = self.request(source)
        source.write_bytes(b"changed")
        with mock.patch.object(file_ops, "_run_video", side_effect=AssertionError("No decoder after change")):
            self.assertEqual(file_ops.handle(request), {"ok": False, "errorCode": "changed"})
        link = self.root / "linked.mp4"
        link.symlink_to(source)
        self.assertEqual(file_ops.handle({**request, "path": str(link)}), {"ok": False, "errorCode": "symlink"})

    def test_change_during_extraction_discards_frames_and_cleans_temporary_files(self):
        source = self.make()
        calls = []
        runner = self.fake_runner(calls)
        def change(command, descriptor, deadline, capture=False):
            result = runner(command, descriptor, deadline, capture)
            if not capture:
                source.write_bytes(b"changed during decode")
            return result
        with mock.patch.object(file_ops, "_video_tools", return_value=("/fixed/ffmpeg", "/fixed/ffprobe")), mock.patch.object(file_ops, "_run_video", side_effect=change):
            self.assertEqual(file_ops.handle(self.request(source)), {"ok": False, "errorCode": "changed"})
        self.assertFalse(Path(calls[-1][0][-1]).parent.exists())

    def test_total_frame_budget_is_enforced_and_cleaned_up(self):
        source = self.make()
        calls = []
        with mock.patch.object(file_ops, "MAX_IMAGE_BYTES", 30), mock.patch.object(file_ops, "_video_tools", return_value=("/fixed/ffmpeg", "/fixed/ffprobe")), mock.patch.object(file_ops, "_run_video", side_effect=self.fake_runner(calls)):
            self.assertEqual(file_ops.handle(self.request(source)), {"ok": False, "errorCode": "video_frames_too_large"})
        self.assertFalse(Path(calls[-1][0][-1]).parent.exists())

    def test_timeout_kills_subprocess_and_returns_fixed_error_without_stderr(self):
        source = self.make()
        with mock.patch.object(file_ops, "_video_tools", return_value=("/fixed/ffmpeg", "/fixed/ffprobe")), mock.patch.object(file_ops.subprocess, "run", side_effect=subprocess.TimeoutExpired("private-command", 8, stderr=b"private-path")) as run:
            self.assertEqual(file_ops.handle(self.request(source)), {"ok": False, "errorCode": "video_timeout"})
        self.assertLessEqual(run.call_args.kwargs["timeout"], 8)
        self.assertEqual(run.call_args.kwargs["stderr"], subprocess.DEVNULL)
        self.assertEqual(run.call_args.kwargs["stdin"], subprocess.DEVNULL)
        self.assertEqual(len(run.call_args.kwargs["pass_fds"]), 1)

    def test_overall_deadline_prevents_new_decoder_process(self):
        source = self.make()
        descriptor = os.open(source, os.O_RDONLY)
        self.addCleanup(os.close, descriptor)
        with mock.patch.object(file_ops.time, "monotonic", return_value=100), mock.patch.object(file_ops.subprocess, "run", side_effect=AssertionError("Deadline already expired")):
            with self.assertRaises(file_ops.FileOpError) as error:
                file_ops._run_video(["unused"], descriptor, 99)
        self.assertEqual(error.exception.code, "video_timeout")

    def test_large_source_is_never_loaded_into_python_memory(self):
        source = self.make()
        with source.open("wb") as stream:
            stream.truncate(1024 * 1024 * 1024)
        calls = []
        real_open = builtins.open
        def guarded_open(file, *args, **kwargs):
            if os.fspath(file) == str(source):
                self.fail("Video source must not be loaded using Python file reads")
            return real_open(file, *args, **kwargs)
        with mock.patch.object(file_ops, "_video_tools", return_value=("/fixed/ffmpeg", "/fixed/ffprobe")), mock.patch.object(file_ops, "_run_video", side_effect=self.fake_runner(calls)), mock.patch.object(builtins, "open", side_effect=guarded_open):
            result = file_ops.handle(self.request(source))
        self.assertTrue(result["ok"], result)
        self.assertEqual(len(result["frames"]), 8)

    def test_cancel_signal_cleans_temp_frames_and_reaps_decoder_process(self):
        source = self.make()
        original_runner = file_ops._run_video
        for signum in (signal.SIGTERM, signal.SIGINT):
            with self.subTest(signum=signum):
                original_handler = signal.getsignal(signum)
                calls = []
                runner = self.fake_runner(calls)
                pidfile = self.root / (str(signum) + ".pid")
                def interrupt(command, descriptor, deadline, capture=False):
                    if capture:
                        return runner(command, descriptor, deadline, capture)
                    calls.append((command, descriptor, deadline, capture))
                    self.assertIs(signal.getsignal(signum), file_ops._cancel_video)
                    script = "import os,signal,time,pathlib; pathlib.Path(%r).write_text(str(os.getpid())); os.kill(os.getppid(), %d); time.sleep(10)" % (str(pidfile), signum)
                    return original_runner([sys.executable, "-c", script], descriptor, deadline)
                with mock.patch.object(file_ops, "_video_tools", return_value=("/fixed/ffmpeg", "/fixed/ffprobe")), mock.patch.object(file_ops, "_run_video", side_effect=interrupt):
                    result = file_ops.handle(self.request(source))
                self.assertEqual(result, {"ok": False, "errorCode": "video_cancelled"})
                self.assertFalse(Path(calls[-1][0][-1]).parent.exists())
                self.assertIs(signal.getsignal(signum), original_handler)
                child_pid = int(pidfile.read_text())
                with self.assertRaises(ProcessLookupError):
                    os.kill(child_pid, 0)


if __name__ == "__main__":
    unittest.main()
