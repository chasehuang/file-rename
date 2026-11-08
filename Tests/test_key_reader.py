"""Exercise the extension's actual dotenv reader with temporary, synthetic files."""

import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


MAIN = Path(__file__).resolve().parents[1] / "source" / "FileRename.popclipext" / "main.js"
SOURCE = MAIN.read_text(encoding="utf-8")
READER = re.search(r"const READ_KEY = String.raw`(.*?)`;", SOURCE, re.DOTALL).group(1)
KEY = "gemini-reader-unit-test-key"
OTHER_KEY = "gemini-other-unit-test-key"


class KeyReaderTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="popclip-key-reader-test-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name).resolve()
        self.env_path = self.root / "settings" / ".env"

    def write(self, path, content):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def read(self, env_path=None):
        # A fresh HOME and minimal environment prevent access to real credentials.
        return subprocess.run(
            [sys.executable, "-I", "-X", "utf8", "-c", READER]
            + ([] if env_path is None else [str(env_path)]),
            cwd=self.root,
            env={"HOME": str(self.root), "PATH": os.defpath, "LANG": "C.UTF-8"},
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=5,
            check=False,
        )

    def assert_key(self, result, expected=KEY):
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, expected)
        self.assertEqual(result.stderr, "")

    def assert_no_private_output(self, result):
        for secret in (KEY, OTHER_KEY, str(self.root)):
            self.assertNotIn(secret, result.stdout + result.stderr)

    def test_no_path_reads_neither_the_home_nor_other_env_files(self):
        self.write(self.root / ".env", f"GEMINI_API_KEY_POP={KEY}\n")
        self.write(self.env_path, f"GEMINI_API_KEY_POP={OTHER_KEY}\n")
        for requested in (None, "", " \t "):
            with self.subTest(requested=requested):
                result = self.read(requested)
                self.assertEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
                self.assertEqual(result.stderr, "")

    def test_only_the_exact_variable_name_is_accepted(self):
        self.write(self.env_path, "\n".join([
            f"XAI_API_KEY={OTHER_KEY}",
            f"GEMINI_API_KEY={OTHER_KEY}",
            f"GEMINI_API_KEY_POP_EXTRA={OTHER_KEY}",
            f"PREFIX_GEMINI_API_KEY_POP={OTHER_KEY}",
            f"GEMINI_API_KEY_POP={KEY}",
        ]))
        self.assert_key(self.read(self.env_path))

    def test_export_quotes_and_comments_are_parsed_without_a_shell(self):
        fixtures = [
            f"GEMINI_API_KEY_POP={KEY}",
            f"  export GEMINI_API_KEY_POP = {KEY}  # comment",
            f"GEMINI_API_KEY_POP='{KEY}'",
            f'GEMINI_API_KEY_POP="{KEY}" # comment',
            f"# unrelated\nGEMINI_API_KEY_POP={KEY}\r\n",
        ]
        for content in fixtures:
            with self.subTest(content=content):
                self.write(self.env_path, content)
                self.assert_key(self.read(self.env_path))

    def test_custom_absolute_path_does_not_read_another_env_file(self):
        self.write(self.env_path, f"GEMINI_API_KEY_POP={OTHER_KEY}")
        custom = self.write(self.root / "custom folder" / "api.env", f"GEMINI_API_KEY_POP={KEY}")
        self.assert_key(self.read(custom))

    def test_tilde_path_is_relative_to_the_test_home(self):
        self.write(self.env_path, f"GEMINI_API_KEY_POP={OTHER_KEY}")
        self.write(self.root / "settings" / "gemini.env", f"GEMINI_API_KEY_POP={KEY}")
        self.assert_key(self.read("~/settings/gemini.env"))

    def test_missing_explicit_file_does_not_fall_back_to_another_file(self):
        self.write(self.env_path, f"GEMINI_API_KEY_POP={OTHER_KEY}")
        result = self.read(self.root / "missing.env")
        self.assert_no_private_output(result)

    def test_relative_path_is_not_read(self):
        self.write(self.root / "relative.env", f"GEMINI_API_KEY_POP={KEY}")
        self.assert_no_private_output(self.read("relative.env"))

    def test_missing_directory_and_non_utf8_files_do_not_leak_private_paths(self):
        invalid_utf8 = self.root / "invalid.env"
        invalid_utf8.write_bytes(b"\xff\xfe\x00")
        for target in (self.root / "missing.env", self.root, invalid_utf8):
            with self.subTest(target=target):
                self.assert_no_private_output(self.read(target))

    def test_empty_whitespace_and_unclosed_quoted_keys_are_not_returned(self):
        for value in ("", "' '", '"two words"', "'unclosed", '"unclosed'):
            with self.subTest(value=value):
                self.write(self.env_path, f"GEMINI_API_KEY_POP={value}")
                result = self.read(self.env_path)
                self.assertEqual(result.stdout, "")
                self.assertEqual(result.stderr, "")

    def test_env_content_is_never_sourced_or_evaluated(self):
        marker = self.root / "must-not-exist"
        self.write(self.env_path, "\n".join([
            f"touch '{marker}'",
            f"OTHER=$(touch '{marker}')",
            f"GEMINI_API_KEY_POP={KEY}",
        ]))
        self.assert_key(self.read(self.env_path))
        self.assertFalse(marker.exists())

    def test_env_value_is_not_expanded(self):
        self.write(self.env_path, "GEMINI_API_KEY_POP='$SHELL_LITERAL_VALUE'")
        self.assert_key(self.read(self.env_path), "$SHELL_LITERAL_VALUE")

    def test_shell_metacharacters_in_custom_path_are_literal(self):
        custom = self.write(self.root / "$(touch filename-marker) `literal` .env", f"GEMINI_API_KEY_POP={KEY}")
        self.assert_key(self.read(custom))
        self.assertFalse((self.root / "filename-marker").exists())


if __name__ == "__main__":
    unittest.main()
