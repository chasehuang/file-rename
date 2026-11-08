# File Rename

Rename files by translating their current names or looking at a picture or video. Original names can be in Chinese, Japanese or other languages; this version suggests English names. Edit the suggestion, then click **套用 (Apply)** to rename. **取消 (Cancel)** leaves the name unchanged. The buttons and messages are currently in Traditional Chinese.

| Icon | What it does | Example |
| --- | --- | --- |
| Language — 譯檔名 | Translates a filename or selected words. | `週末野餐照片.jpg` → `weekend-picnic-photo.jpg` |
| Scan — 看內容命名 | Names a picture or video from its content. | `picnic-photo.jpg`, `cooking-tutorial.mp4` |

Suggestions use **2–4 words** and aim for **no more than 32 characters**, keeping the main subject and asset type, such as `command-key-icon.webp`. Unnecessary color, line-style and background details are left out. Translation keeps the source meaning without guessing the file's contents. You can edit the suggestion and add more words before applying it.

## Start using it

You need a Mac with PopClip **2026.8.1 or later**, your own **Gemini API Key** (Google's key that lets the extension use AI), **Python 3.9+** for renaming files in Finder, and **ffmpeg** for videos only. Tool setup is explained in CONTRIBUTING.md in the source download. Translating text in another app does not need these tools if you enter your key directly in the extension settings.

[**Download FileRename.popclipextz**](https://github.com/chasehuang/file-rename/releases/latest/download/FileRename.popclipextz) · [Release notes](https://github.com/chasehuang/file-rename/releases/latest)

While the repository is private, sign in to a GitHub account with access to download it. These links will stay the same if the repository becomes public. Double-click the downloaded file, confirm PopClip's unsigned-extension prompt, and enter your Gemini API Key in the **File Rename** extension settings.

PopClip saves the key in your Mac's Keychain. To use a local `.env` file instead, leave the key field blank and enter the file's path in **.env path (optional)**. There is no default file location; leaving both fields blank asks you to set up a key. The optional file method is explained in CONTRIBUTING.md in the source download.

In Finder:

1. Select one file and press Return.
2. Use the mouse to highlight any part of its name.
3. Click the translation or scan icon.
4. Edit the suggestion if needed, then choose Apply or Cancel.

Selecting just `野餐` in `週末野餐照片.jpg` still translates the whole name, for example to `weekend-picnic-photo.jpg`. Japanese names work too: `週末のピクニック.jpg` can become `weekend-picnic.jpg`. Return alone does not bring up PopClip. The file keeps its extension. In other apps, select words and use the translation icon; the approved name replaces the selection where possible or is copied for you to paste.

Pictures: PNG, JPEG and WebP, up to about 14.7 MB per original file. Animated pictures use their first frame. Videos: MP4, MOV, M4V, WebM and MKV, using up to eight pictures from the video. You can also translate the names of documents and audio files, without reading or listening to their contents. One file at a time; folders cannot be renamed. Select the original file rather than a shortcut that points elsewhere. Names use lowercase English letters, numbers and `-`. The 32-character target excludes endings such as `.jpg`; longer names are allowed when needed, up to 64 characters. Selected text can be up to 2,000 characters.

## What is sent to Google

Naming runs in Google's cloud. **Clicking an icon sends the material before the suggestion appears. Cancel stops the rename but cannot take back the upload.**

- **Translate filename:** sends the file's current name or the words you highlighted to Gemini, which turns them into an English filename.
- **Name a picture:** removes recorded details such as where and when the picture was taken, then lets Gemini look at it and suggest an English filename. Your original picture is unchanged.
- **Name a video:** takes up to eight pictures from the video for Gemini to name it. The full video and its sound are not uploaded.

If the extension cannot remove the picture's extra recorded details, it stops the upload. Visible faces, words and location labels are still sent. Using Gemini 3.1 Flash-Lite counts toward your Google allowance and may cost money. See [Google's pricing](https://ai.google.dev/gemini-api/docs/pricing) and [service terms](https://ai.google.dev/gemini-api/terms).

## 繁體中文

翻譯原有檔名，或根據圖片與影片內容，替檔案取一個清楚的名字。原檔名可以是中文、日文或其他語言；這一版產生的新名字是英文。可以先修改建議，按「套用」才更名；按「取消」則保留原名。

| 圖示 | 用途 | 例子 |
| --- | --- | --- |
| 語言 — 譯檔名 | 翻譯檔名或反白文字。 | `週末野餐照片.jpg` → `weekend-picnic-photo.jpg` |
| 掃描 — 看內容命名 | 根據圖片或影片內容命名。 | `picnic-photo.jpg`、`cooking-tutorial.mp4` |

建議名稱使用 **2～4 個單字**，並以 **32 個字元內**為目標，保留主題和素材類型，例如 `command-key-icon.webp`。不必要的顏色、線條樣式和背景細節會省略。翻譯時仍以原名稱的意思為準，不會猜測檔案內容；套用前可以自己修改、加上更多單字。

需要 Mac、PopClip **2026.8.1 以上**、自己的 **Gemini API Key**（Google 讓這個外掛使用 AI 的金鑰），以及更改 Finder 檔名需要的小工具 **Python 3.9 以上**。只有影片需要 **ffmpeg**。工具的安裝步驟見原始碼下載包裡的 CONTRIBUTING.md。如果只在其他 App 翻譯文字、直接在外掛設定填好 Key，就不需要這些工具。

[**下載 FileRename.popclipextz 安裝檔**](https://github.com/chasehuang/file-rename/releases/latest/download/FileRename.popclipextz) · [查看更新說明](https://github.com/chasehuang/file-rename/releases/latest)

目前 repo 維持私人，請登入有存取權的 GitHub 帳號才能下載。之後公開 repo，這些連結可以繼續使用。下載後，雙擊檔案、確認 PopClip 的未簽署外掛提示，再到「File Rename」外掛設定填入自己的 Gemini API Key。

Key 會存進這台 Mac 的鑰匙圈。如果想使用本機 `.env` 檔案，請將 Key 欄位留白，並在「.env 路徑（選填）」填入檔案的位置。外掛不會自行尋找檔案；兩個欄位都留白時，會提醒你先設定 Key。詳細做法見原始碼下載包裡的 CONTRIBUTING.md。

在 Finder 使用：

1. 選一個檔案，按 Return。
2. 用滑鼠反白檔名的任意一段。
3. 點翻譯或掃描圖示。
4. 視需要修改建議，再按「套用」或「取消」。

例如只反白 `週末野餐照片.jpg` 裡的「野餐」，仍會翻譯完整檔名，建議為 `weekend-picnic-photo.jpg`。日文也可以，例如 `週末のピクニック.jpg` → `weekend-picnic.jpg`。只按 Return 不會叫出 PopClip，副檔名會保留。在其他 App 反白文字後，點翻譯圖示；確認後會取代選取文字，不能貼上的地方則先複製，讓你自行貼上。

圖片支援 PNG、JPEG、WebP，原檔上限約 14.7 MB，動畫圖片只取第一畫面。影片支援 MP4、MOV、M4V、WebM、MKV，最多取八張畫面判斷。文件和音樂也可以翻譯檔名，目前不會閱讀文件或聽音訊。一次處理一個檔案，不能更改資料夾名稱，請直接選原始檔案。檔名使用小寫英文字母、數字和 `-`。32 個字元的目標不包含 `.jpg` 等結尾；有必要時可以超過，最多 64 個字元。一次最多反白 2,000 個字元。

### 傳送給 Google 的內容

命名由 Google 雲端處理。**點圖示時就會傳送內容，之後才出現建議；取消只取消更名，不能撤回上傳。**

- **翻譯檔名：**把檔案原本的名稱，或你反白的文字，傳給 Gemini 翻成英文檔名。
- **圖片命名：**先移除圖片裡記錄的拍攝地點、日期等資訊，再讓 Gemini 看圖取英文檔名。原圖不會被修改。
- **影片命名：**從影片取出最多 8 張畫面，讓 Gemini 看這些畫面取英文檔名，不會上傳整段影片或聲音。

如果無法移除圖片的附加資訊，外掛就停止上傳。畫面中看得見的人臉、文字與位置標示仍會送出。使用 Gemini 3.1 Flash-Lite 會消耗自己的 Google 額度，可能產生費用；請見上方 Google 價格說明與條款連結。

This version still needs a full Finder check before public release. / 這一版公開前，仍需完整驗證一次 Finder 選檔到套用更名的流程。

MIT License / MIT 授權。

## Translation cost / 翻譯檔名的費用

Measured on **2026-11-06** with Gemini 3.1 Flash-Lite and the naming instructions from before the short-name update: five Chinese/Japanese example filenames, one request each. The average was about **586 tokens**: 574 sent and 12 received. This includes the extension's naming instructions, not just the filename. Tokens measure how much text AI processes; they are not the same as characters.

At Google's standard paid prices, that is about **US$0.000162 per translation**, **US$0.16 for 1,000**, or **roughly 6,000 translations for US$1**. The five examples ranged from 580–602 total tokens and US$0.000155–US$0.00017675 each.

於 **2026-11-06** 使用 Gemini 3.1 Flash-Lite，將 5 個中日文範例檔名各翻譯一次，當時還沒套用縮短檔名的新規則，平均約 **586 token**：送出約 574、回覆約 12。token 是 AI 計算文字份量的單位，不等於字數；用量也包含外掛給 AI 的命名說明，不只是檔名本身。

按標準付費價格試算，平均**每次約 US$0.000162，1,000 次約 US$0.16，US$1 約能翻譯 6,000 次**。這 5 個範例每次共用了 580～602 token，費用介於 US$0.000155～US$0.00017675。

[Google pricing / Google 官方價格](https://ai.google.dev/gemini-api/docs/pricing#gemini-3.1-flash-lite): US$0.25 per million input tokens; US$1.50 per million output tokens, including thinking. These five requests reported no additional thinking tokens. / 每 100 萬 token，送出 US$0.25、回覆 US$1.50，回覆費用包含思考用量；這 5 次沒有回報額外思考用量。

These are small-sample estimates for **filename translation only**, before tax, free allowances or discounts. Usage can change with the name, response and extension version. Image/video naming is not included. See the full examples in the source download's main README. / 這是**翻譯檔名**的小樣本估算，不計免費額度或折扣，也不含稅；實際用量會隨檔名、回覆及外掛版本變動。**看圖片、影片取名不適用此估算**。完整範例表格見原始碼下載包的主 README。
