# Contributing

File Rename provides two PopClip actions: translate a filename/selection, or name a Finder image/video from its visible content. Keep the preview-before-apply behavior, original extension, and explicit choice of naming basis. Use English for the extension UI and maintain both English and Traditional Chinese guides.

## Source layout

```text
source/FileRename.popclipext/      Installable extension source
  Config.yaml                     Metadata, permissions and options
  main.js                         Actions, prompts and Gemini requests
  python.sh                       Finds a supported local Python
  file_ops.py                     File checks, media preparation and rename
  sanitize-image.js               ImageIO/CoreGraphics upload-copy preparation
  finder.sh                       Reads the current Finder selection
  confirm.sh                      Editable preview dialog
  README.md                       Short bilingual package description
  icons/                          Bundled outline SVGs and their upstream license
Tests/                            Mocked JavaScript and local Python tests
build.sh                          Validates and builds both archives
popclip-directory.yaml            Optional official-directory submission metadata
```

Use the extension identifier `com.chasehuang.popclip.file-rename`, action identifiers `translate` / `image`, and option identifiers `geminiApiKey` / `envFile`. Keep these identifiers stable in future versions so installed settings continue to work. The `image` action also handles videos. The package lives at `source/FileRename.popclipext` and builds to `FileRename.popclipextz`. The extension has not been submitted to the official PopClip directory; after submission, keep the package path stable. See the [official package instructions](https://www.popclip.app/extensions/submit#package).

## Icons

The outline set uses [Lucide 1.17.0](https://github.com/lucide-icons/lucide/tree/896aba0d195a4fec38ad7c4a90d00cb3389ebfea/icons): `text-cursor-input` for the extension, `languages` for translation, and `scan-eye` for content naming. The bundled SVGs preserve the upstream paths and use a 1.75 stroke width. The complete upstream license, including the applicable ISC and Feather/MIT notices, is included in [icons/LICENSE](source/FileRename.popclipext/icons/LICENSE).

The bundled files are `icons/file-rename.svg`, `icons/translate.svg` and `icons/content.svg`. Keep them local to the package and listed in `build.sh`. PopClip renders them as monochrome icons, so they follow the menu's appearance without downloading icon assets at runtime.

## Development prerequisites

- macOS: filesystem tests exercise the macOS-specific `renamex_np` operation.
- Node.js 22 or later for JavaScript tests, and Python 3.9 or later. There are no npm or pip dependencies to install for these tests. Building the archives requires Python, not Node.js.
- ffmpeg and ffprobe for video extraction tests.
- PopClip 2026.8.1 (6221) or later for manual integration checks.

The extension launcher searches only `/opt/homebrew/bin/python3`, `/usr/local/bin/python3`, then `/usr/bin/python3`, accepting Python 3.9+. It does not use an arbitrary shell PATH, virtualenv or Conda environment. The system candidate requires an existing Xcode Command Line Tools installation. It does not launch dependency installers.

Image preparation uses macOS's built-in ImageIO/CoreGraphics through `osascript`; it requires no extra app or pip package.

The preparation environment was macOS 27.0.1, Node.js 25.2.1 and Python 3.14.7. These are observed development versions, not a declaration of minimum supported macOS or Node.js versions.

## Setup tools

Finder renaming needs Python 3.9+. Naming videos also needs ffmpeg and ffprobe. If Homebrew is already installed, open Terminal and run:

在 Finder 改名需要 Python 3.9 以上；影片命名另外需要 ffmpeg 與 ffprobe。如果電腦已經裝好 Homebrew，打開「終端機」執行：

```sh
brew install python
brew install ffmpeg
```

The second command installs both video tools; skip it if you will only use text or images. If Homebrew is not installed, follow its official installation instructions first. The extension does not install these tools for you.

第二行會一起安裝影片需要的兩個工具；只處理文字或圖片的人可以跳過。如果還沒裝 Homebrew，請先依它的官方說明安裝。外掛不會自動替你安裝這些工具。

The supported Python paths are listed above. Both video executables must be in `/opt/homebrew/bin` or `/usr/local/bin`. A Python installed only in a virtual environment is not detected. Text translation outside Finder does not need these tools when the API key is entered directly in PopClip settings; the optional `.env` workflow still needs Python.

Python 的支援位置見上方說明；影片工具需位於 `/opt/homebrew/bin` 或 `/usr/local/bin`。只在其他 App 翻譯反白文字、且直接在 PopClip 設定填入 Key 時，不需要這些工具；使用 `.env` 的方式仍需要 Python。

## Tests and build

From the repository root:

```sh
node --test Tests/extension.test.cjs
python3 -m unittest discover -s Tests -p 'test_*.py'
bash build.sh
```

JavaScript tests mock PopClip and API requests. Python tests use temporary files to check dotenv parsing, file identity, exclusive rename, collisions, path restrictions and video sampling/cleanup. They do not require real credentials or upload user files. If video tests are skipped because tools are missing, report those skips; do not describe the video path as verified.

The build validates the source and produces:

- `dist/FileRename.popclipextz` — unsigned PopClip install package.
- `dist/file-rename-source.zip` — standalone source archive, excluding `.git`, build output, secrets and local test artifacts.

Do not hand-edit generated archives. Make changes in `source/FileRename.popclipext`, update both root READMEs, and rebuild. A clean source archive should also build after extraction into a fresh directory.

## Manual integration checks before a release

Use disposable files you created for testing. Automated checks do not prove native PopClip selection, macOS permissions or dialog behavior.

1. Install the newly built package and confirm both icon actions are available in Finder. Check that the content action is absent outside Finder.
2. Enter a test API key in PopClip settings and verify the extension works without a readable `.env`. Then leave the key blank and test an explicitly configured `.env` path. A bad custom path must fail without falling back elsewhere. Leaving both fields blank must prompt for setup without trying to read any file.
3. In Finder, enter name editing and mouse-select only part of a filename, omitting its extension. Verify translation uses the complete original name and the preview retains the extension.
4. Cancel a preview and confirm neither the filename nor Finder's editing state is altered by an Escape action. Then apply an approved name to a disposable file.
5. Try image and video naming; verify the prompt basis and preview, and confirm unsupported formats give a useful error. Check that source file contents are unchanged after upload-copy preparation. Video naming should send frames, not a whole video or audio.
6. Change the selected file or modify the file while its preview is open. Verify that Apply refuses stale input. Check an existing target name and a collision created after the preview; no file should be overwritten.
7. Test selected text in another app, both in an editable field and in a read-only selection. Verify replacement or clipboard behavior matches the preview.

## Validation status

On 2026-11-08, all 312 automated checks passed: 251 JavaScript tests and 61 Python tests. Earlier that day, a native TextEdit check succeeded with the installed v0.1.0 GitHub package: selecting `週末野餐採買清單`, opening the suggestion preview and clicking Apply replaced it with `weekend-picnic-list`.

The full Finder selection → preview → Apply flows for filename translation, image naming and video naming have not yet been verified. Passing automated checks does not establish that these native UI flows work. Record the actual macOS, PopClip, Python and media-tool versions alongside future manual check results.

2026-11-08 的 312 項程式測試皆通過，包含 251 項 JavaScript 與 61 項 Python 測試。當天稍早已安裝 GitHub v0.1.0 版本並在 TextEdit 實測：反白「週末野餐採買清單」、開啟建議視窗並按「套用」，文字成功換成 `weekend-picnic-list`。Finder 裡的檔名翻譯、圖片命名與影片命名，從選取到套用的完整操作仍待驗證。

If adding a screenshot or demonstration, capture the real extension using self-created, non-sensitive fixtures. Do not use private files, API keys, or a simulated interface presented as a real run.

## Media upload contract

Only translation requests include `source_text`. Image requests include the image source kind and prepared pixels, without the old filename or path. Video requests include the video source kind and frames in sequence, without filenames, paths, duration or actual timestamps. Keep local preview/rename information out of content-naming requests.

For PNG/JPEG/WebP source files up to 14 MiB, ImageIO reads the first frame, applies orientation and renders a fresh sRGB RGBA image. Animated WebP also uses only its first frame. The PNG upload copy retains alpha, has a maximum long edge of 1,600 pixels without upscaling, and permits only pixel/format/transparency chunks. Remove EXIF/GPS, XMP, IPTC, ICC profiles, comments, timestamps and thumbnails. Preparation has a 20-second limit and must fail without uploading the original when sanitization fails. Use private temporary copies, clean them up and never modify source file bytes.

Video extraction removes inherited metadata; JPEG upload copies also strip APP and COM segments. Keep the existing maximum of eight frames, 1,600-pixel long edge and 14 MiB combined frame data. Removing embedded metadata does not remove text, faces or location watermarks from pixels. Uploads still occur before the preview, and Cancel cannot retract them.

Regression checks should cover image orientation, alpha, dimensions, first-frame handling, metadata removal, unchanged source bytes, cleanup on success/failure, refusal to upload on sanitization errors, and the exact request fields for each action. Use generated fixtures and mocked API requests; never upload private images as a test.

## Local credentials

The Gemini API Key setting uses PopClip's secret option with local macOS Keychain storage. An entered key takes priority and bypasses `.env`. See [PopClip's secret-option documentation](https://www.popclip.app/dev/options#option-types).

For an optional local `.env` workflow, leave the key setting blank and set .env path (optional) to an absolute path or a path starting with `~/`. The file you choose must contain:

```dotenv
GEMINI_API_KEY_POP=your-own-gemini-api-key
```

A configured path is used exclusively: an unreadable file or missing key produces an error without falling back. There is no default `.env` location. With both settings blank, the extension asks you to set up a key without reading any file. The reader loads only the file you chose and uses `GEMINI_API_KEY_POP` as the credential; it does not execute the file or transmit other variables. Neither the source nor install package includes an API key. Keep real credentials outside version control and shared archives.

一般使用者直接在 Gemini API Key 填入 Key 即可，PopClip 會存進這台 Mac 的鑰匙圈。想使用 `.env` 的人，請將 Key 欄位留白，並在 .env path (optional) 填入檔案的完整位置，或以 `~/` 開頭的位置。外掛只讀取你指定的檔案；找不到檔案或 Key 時會顯示錯誤，不會改讀其他地方。兩個欄位都留白時，會提醒你先設定 Key。

## Credentials, diagnostics and code changes

- Never commit a real `.env`, API key, private filename, user image/video, or unredacted request/response log.
- The `geminiApiKey` secret option is preferred; `envFile` is consulted only when that key is blank. Do not silently change these precedence rules or read unrelated environment values.
- Keep credentials in request headers and do not include them in URLs, console output or user-visible errors.
- Preserve argument-safe subprocess calls, file identity checks, explicit Apply, and exclusive rename. Do not replace these with shell interpolation or an overwrite-capable rename.
- Keep model input as untrusted data. Text found in images, filenames or a selection must not become instructions to the extension.
- Add meaningful regression tests when changing these behaviors. UI changes still need an actual PopClip check.

For bug reports, include macOS and PopClip versions, the action used, file type, whether the key came from settings or `.env` (never the key itself), sanitized error text and a minimal reproduction. Say whether the failure occurred before the preview, on Cancel or on Apply.

## Publishing

Use [GitHub Releases](https://github.com/chasehuang/file-rename/releases/latest) for the latest version and its [ready-to-install FileRename.popclipextz](https://github.com/chasehuang/file-rename/releases/latest/download/FileRename.popclipextz).

For each release, record test coverage and any unverified flows, inspect both archives for private data, and build from the tagged source. Attach the install package and source archive to the release. Use `FileRename.popclipextz` as the install asset name and keep the documentation links in sync with it.

最新版與可直接安裝的檔案放在 GitHub Releases。每次發行時，記錄已完成與尚未驗證的測試項目，從該版本的原始碼打包，並檢查下載包沒有私人資料。

GitHub hosting and official PopClip directory acceptance are separate. For an official submission, follow [PopClip's submission process](https://www.popclip.app/extensions/submit): provide the source package and metadata, tag a version, and complete the required agreement/review. Do not claim official signing before it occurs.

This extension's Python and ffmpeg dependencies matter for eligibility: the [directory's front-page guidelines](https://www.popclip.app/extensions/submit#listing-guidelines) restrict additional executables. A public GitHub release does not remove those restrictions or guarantee a front-page listing.

Contributions are provided under the project's [MIT License](LICENSE).
