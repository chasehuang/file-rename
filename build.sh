#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
date '+%Y-%m-%d %H:%M:%S %Z'

# Build tools use the developer's Python. The installed extension has its own
# small launcher so it can locate Python on the user's Mac.
"${POPCLIP_BUILD_PYTHON:-python3}" - <<'PY'
from pathlib import Path
import shutil
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile

project = Path.cwd()
package_name = "FileRename.popclipext"
package_source = Path("source") / package_name
runtime_files = (
    "Config.yaml", "main.js", "file_ops.py", "finder.sh", "confirm.sh",
    "python.sh", "sanitize-image.js", "README.md",
    "icons/file-rename.svg", "icons/translate.svg", "icons/content.svg", "icons/LICENSE",
)
repository_files = (
    "README.md", "README.zh-TW.md", "CONTRIBUTING.md", "CHANGELOG.md",
    "LICENSE", ".gitignore", "popclip-directory.yaml",
    "build.sh", ".github/workflows/test.yml", "assets/file-rename-demo.webp",
    "Tests/extension.test.cjs", "Tests/test_file_ops.py", "Tests/test_key_reader.py",
    "Tests/test_image_privacy.py",
)
source_files = [Path(name) for name in repository_files]
source_files.extend(package_source / name for name in runtime_files)

# Explicit allowlists keep local keys, caches, test output, and private files
# out of both downloads, even if they exist alongside the public sources.
for relative in source_files:
    file = project / relative
    if not file.is_file() or file.is_symlink():
        raise SystemExit(f"Missing or unsafe build input: {relative}")
dist = project / "dist"
dist.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix=".build-", dir=dist) as temporary:
    staging = Path(temporary)
    package = staging / package_name
    package.mkdir()
    for name in runtime_files:
        (package / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(project / package_source / name, package / name)
    shutil.copy2(project / "LICENSE", package / "LICENSE")

    extension_zip = staging / "FileRename.popclipextz"
    with ZipFile(extension_zip, "w", ZIP_DEFLATED) as archive:
        for name in (*runtime_files, "LICENSE"):
            archive.write(package / name, f"{package_name}/{name}")

    source_zip = staging / "file-rename-source.zip"
    with ZipFile(source_zip, "w", ZIP_DEFLATED) as archive:
        for relative in source_files:
            archive.write(project / relative, f"file-rename/{relative.as_posix()}")

    destination = dist / package_name
    if destination.is_symlink():
        raise SystemExit(f"Refusing to replace a symlink: {destination}")
    if destination.exists():
        shutil.rmtree(destination)
    shutil.move(str(package), destination)
    for artifact in (extension_zip, source_zip):
        artifact.replace(dist / artifact.name)

print("Built: dist/FileRename.popclipext")
print("Built: dist/FileRename.popclipextz")
print("Built: dist/file-rename-source.zip")
PY
