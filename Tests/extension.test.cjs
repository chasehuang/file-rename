const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const vm = require('node:vm');
const test = require('node:test');

const MAIN = path.join(__dirname, '..', 'source', 'FileRename.popclipext', 'main.js');
const SOURCE = fs.readFileSync(MAIN, 'utf8');
const KEY = 'gemini-unit-test-secret-DO-NOT-DISPLAY';
const LEGACY_KEY = 'obsolete-options-key-DO-NOT-USE';
const OPTION_KEY = 'gemini-settings-test-secret-DO-NOT-DISPLAY';
const ENV_PATH = '/tmp/file-rename-test/settings.env';
const IMAGE = 'data:image/png;base64,cHJpdmF0ZS10ZXN0LWltYWdl';
const RAW = 'PRIVATE_RAW_RESPONSE_DO_NOT_DISPLAY';
const VIDEO = {
  ok: true, duration: 10,
  frames: [
    { seconds: 0.15, mime: 'image/jpeg', dataUrl: 'data:image/jpeg;base64,Zmlyc3QtZnJhbWU=' },
    { seconds: 4.6, mime: 'image/jpeg', dataUrl: 'data:image/jpeg;base64,bWlkZGxlLWZyYW1l' },
    { seconds: 9.8, mime: 'image/jpeg', dataUrl: 'data:image/jpeg;base64,bGFzdC1mcmFtZQ==' }
  ]
};
const SNAPSHOT = {
  dev: '16777234', ino: '9007199254740993123', size: '1234', mtime_ns: '1793370490123456789'
};

const clone = value => JSON.parse(JSON.stringify(value));
const completed = value => ({ data: {
  candidates: [{ finishReason: 'STOP', content: { role: 'model', parts: [
    { text: typeof value === 'string' ? value : JSON.stringify(value) }
  ] } }]
} });

function makeHarness(config = {}) {
  const events = [];
  let finderCallCount = 0;
  const file = {
    path: '/tmp/private-parent-do-not-upload/Group 4.png', name: 'Group 4.png',
    stem: 'Group 4', extension: '.png', snapshot: clone(SNAPSHOT), image: { dataUrl: IMAGE },
    ...config.file
  };
  const context = config.context === undefined ? { appIdentifier: 'com.apple.TextEdit', canPaste: true } : config.context;
  const options = config.options === undefined ? { envFile: ENV_PATH } : config.options;
  const selected = config.selected === undefined ? '季度行銷計畫.png' : config.selected;
  const slug = config.slug === undefined ? 'quarterly-marketing-plan' : config.slug;
  const shown = () => events.filter(event => event.type === 'show').map(event => event.text).join('\n');
  const fileOps = () => events.filter(event => event.type === 'file').map(event => event.request);
  const writes = () => events.filter(event => ['paste', 'copy'].includes(event.type) || (event.type === 'file' && event.request.op === 'rename'));
  const axios = {
    async post(url, body, options) {
      events.push({ type: 'api', url, body: clone(body), options: clone(options) });
      if (config.apiError) throw config.apiError;
      return config.response === undefined ? completed({ slug }) : config.response;
    }
  };
  const popclip = {
    context: config.popclipContext || context,
    async runShellScript() {
      throw new Error('Python must run through the fixed interpreter launcher.');
    },
    async runShellScriptFile(name, options) {
      events.push({ type: 'script', name, options: clone(options) });
      if (name === 'finder.sh') {
        if (config.finderError) throw config.finderError;
        const response = config.finderOutputs && config.finderOutputs[finderCallCount++];
        return { status: 0, stdout: response === undefined ? (config.finderOutput === undefined ? `OK:${pathToFileURL(file.path).href}\n` : config.finderOutput) : response };
      }
      if (name === 'python.sh') {
        assert.equal(options.interpreter, '/bin/zsh');
        assert.equal(options.shellMode, 'none');
        if (options.arguments[0] === '-c') {
          events.push({ type: 'key', source: options.arguments[1], options: clone(options) });
          if (config.keyError) throw config.keyError;
          return { status: config.keyStatus === undefined ? 0 : config.keyStatus, stdout: config.fallbackKey === undefined ? KEY : config.fallbackKey };
        }
        assert.deepEqual(clone(options.arguments), ['file_ops.py']);
        if (config.pythonStatus !== undefined) return { status: config.pythonStatus, stdout: config.pythonOutput || '' };
        const request = JSON.parse(options.stdin);
        events.push({ type: 'file', request });
        if (config.fileThrow && config.fileThrow[request.op]) throw config.fileThrow[request.op];
        if (config.fileRaw && config.fileRaw[request.op]) return { status: 0, stdout: config.fileRaw[request.op] };
        const errorCode = config.fileErrors && config.fileErrors[request.op];
        if (errorCode) return { status: 0, stdout: JSON.stringify({ ok: false, errorCode }) };
        if (request.op === 'inspect' && config.recheckError && events.some(event => event.type === 'confirm')) {
          return { status: 0, stdout: JSON.stringify({ ok: false, errorCode: config.recheckError }) };
        }
        if (request.op === 'inspect' && request.include_image && config.imageReadError) {
          return { status: 0, stdout: JSON.stringify({ ok: false, errorCode: config.imageReadError }) };
        }
        let result;
        if (request.op === 'inspect') result = { ok: true, ...file, image: request.include_image === false ? null : file.image };
        else if (request.op === 'video_frames') result = config.video === undefined ? VIDEO : config.video;
        else if (request.op === 'suggest') result = { ok: true, filename: request.slug + file.extension };
        else if (request.op === 'rename') result = { ok: true, name: request.filename };
        else throw new Error(`Unexpected file operation: ${request.op}`);
        return { status: 0, stdout: JSON.stringify(result) };
      }
      if (name === 'confirm.sh') {
        events.push({ type: 'confirm', args: clone(options.arguments) });
        if (config.beforeConfirm) config.beforeConfirm({ events, fileOps: fileOps(), writes: writes() });
        if (config.confirmError) throw config.confirmError;
        const result = config.confirmResult === undefined ? `APPLY:${options.arguments[2]}` : config.confirmResult;
        return { status: 0, stdout: result + '\n' };
      }
      throw new Error(`Unexpected shell script: ${name}`);
    },
    async pressKey(...args) { events.push({ type: 'keyPress', args: clone(args) }); },
    async pasteText(text, options) { events.push({ type: 'paste', text, options: clone(options) }); },
    async copyText(text) { events.push({ type: 'copy', text }); },
    showText(text, options) { events.push({ type: 'show', text, options: clone(options) }); }
  };
  const sandbox = { exports: {}, URL, popclip, require(name) {
    assert.equal(name, 'axios', 'The VM must not load real filesystem/network modules.');
    return axios;
  } };
  vm.runInNewContext(SOURCE, sandbox, { filename: MAIN, timeout: 1000 });
  return {
    events, file, shown, fileOps, writes, actions: sandbox.exports.actions,
    async run() {
      const action = sandbox.exports.actions.find(item => item.identifier === (config.action || 'translate'));
      assert.equal(typeof action.code, 'function');
      await action.code({ text: selected }, options, config.omitActionContext ? undefined : context);
      return this;
    }
  };
}

function makeVideoHarness(config = {}) {
  return makeHarness({
    action: 'image', context: { appIdentifier: 'com.apple.finder' }, selected: '錄影 1.mp4',
    slug: 'file-renaming-demo', ...config,
    file: {
      path: '/tmp/private-parent-do-not-upload/錄影 1.mp4', name: '錄影 1.mp4',
      stem: '錄影 1', extension: '.mp4', image: null, ...config.file
    }
  });
}

const has = (h, type) => h.events.some(event => event.type === type);
const apiCall = h => h.events.find(event => event.type === 'api');
const confirmation = h => h.events.find(event => event.type === 'confirm');
const assertNoLookupOrWrite = h => {
  assert.equal(has(h, 'api'), false);
  assert.equal(has(h, 'keyPress'), false);
  assert.equal(has(h, 'confirm'), false);
  assert.deepEqual(h.writes(), []);
};
const assertNoSecrets = h => {
  for (const secret of [KEY, LEGACY_KEY, OPTION_KEY, IMAGE, RAW, h.file.path]) assert.equal(h.shown().includes(secret), false, `Feedback exposed ${secret}`);
};

test('two static actions clearly separate text translation from Finder-only visual naming', () => {
  const h = makeHarness();
  assert.equal(Array.isArray(h.actions), true);
  assert.equal(h.actions.length, 2);
  const descriptors = clone(h.actions);
  assert.deepEqual(descriptors, [
    { identifier: 'translate', title: 'Translate Filename', icon: 'file:icons/translate.svg', requirements: ['text'] },
    { identifier: 'image', title: 'Name from Content', icon: 'file:icons/content.svg', requirements: ['text'], requiredApps: ['com.apple.finder'] }
  ]);
  assert.deepEqual(h.events, []);
});

test('packaged settings and native preview controls use English', () => {
  const packagePath = path.dirname(MAIN);
  const config = fs.readFileSync(path.join(packagePath, 'Config.yaml'), 'utf8');
  const dialog = fs.readFileSync(path.join(packagePath, 'confirm.sh'), 'utf8');
  for (const line of config.split('\n').filter(line => /^\s*(description|label):/.test(line))) {
    assert.doesNotMatch(line, /[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}]/u);
  }
  assert.match(config, /label: "?\.env path \(optional\)/);
  assert.match(dialog, /buttons \{"Cancel", "Apply"\} default button "Apply" cancel button "Cancel"/);
});

test('Japanese input stays intact while preview instructions and the suggested name use English', async () => {
  const selected = '週末のピクニック.jpg';
  const h = await makeHarness({ selected, slug: 'weekend-picnic', confirmResult: 'CANCEL' }).run();
  assert.deepEqual(JSON.parse(apiCall(h).body.contents[0].parts[0].text), {
    source_text: '週末のピクニック', source_kind: 'text'
  });
  const [title, prompt, proposed] = confirmation(h).args;
  assert.equal(title, 'File Rename');
  assert.equal(prompt.split('\n')[0], `Original: ${selected}`);
  assert.match(prompt, /Translated from the selected text/);
  assert.match(prompt, /Apply will replace the selected text/);
  assert.match(prompt, /choose Cancel/);
  assert.doesNotMatch(prompt.split('\n').slice(1).join('\n'), /[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}]/u);
  assert.equal(proposed, 'weekend-picnic.jpg');
  assert.deepEqual(h.writes(), []);
});

test('text uses Gemini JSON schema with header-only credentials, preserves .png, and confirms before paste', async () => {
  const h = await makeHarness({ beforeConfirm({ writes }) { assert.deepEqual(writes, []); } }).run();
  const api = apiCall(h);
  assert.equal(api.url, 'https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent');
  assert.equal(api.url.includes(KEY), false);
  assert.equal(api.url.includes('?'), false);
  assert.equal(SOURCE.includes('api.x.ai'), false);
  assert.equal(api.options.headers['x-goog-api-key'], KEY);
  assert.equal(api.options.headers.Authorization, undefined);
  assert.equal(api.options.maxRedirects, 0);
  assert.equal(api.body.generationConfig.responseMimeType, 'application/json');
  assert.deepEqual(api.body.generationConfig.responseJsonSchema.required, ['slug']);
  assert.equal(api.body.generationConfig.responseJsonSchema.additionalProperties, false);
  assert.equal(api.body.systemInstruction.parts.length, 1);
  assert.equal(typeof api.body.systemInstruction.parts[0].text, 'string');
  const content = api.body.contents.find(item => item.role === 'user').parts;
  assert.deepEqual(JSON.parse(content[0].text), { source_text: '季度行銷計畫', source_kind: 'text' });
  assert.equal(content.length, 1);
  assert.equal(JSON.stringify(api.body).includes(KEY), false);
  assert.equal(confirmation(h).args[2], 'quarterly-marketing-plan.png');
  assert.match(confirmation(h).args[1], /Translated from the selected text/);
  assert.deepEqual(h.writes(), [{ type: 'paste', text: 'quarterly-marketing-plan.png', options: { restore: true } }]);
  assert.ok(h.events.findIndex(event => event.type === 'confirm') < h.events.findIndex(event => event.type === 'paste'));
  assert.equal(h.events.some(event => event.type === 'script' && event.name === 'finder.sh'), false);
  assert.deepEqual(h.fileOps(), []);
});

test('read-only text offers copy, and copies the edited name only after approval', async () => {
  const h = await makeHarness({ context: { appIdentifier: 'com.apple.Safari', canPaste: false }, confirmResult: 'APPLY:edited-marketing-plan.png' }).run();
  assert.match(confirmation(h).args[1], /clipboard/);
  assert.deepEqual(h.writes(), [{ type: 'copy', text: 'edited-marketing-plan.png' }]);
  assert.ok(h.events.findIndex(event => event.type === 'confirm') < h.events.findIndex(event => event.type === 'copy'));
});

for (const mode of ['paste', 'copy', 'file']) {
  test(`cancelling ${mode} performs no paste, copy, or rename`, async () => {
    const h = await makeHarness({
      context: { appIdentifier: mode === 'file' ? 'com.apple.finder' : 'com.apple.TextEdit', canPaste: mode === 'paste' },
      selected: mode === 'file' ? 'Group 4' : '行銷計畫', confirmResult: 'CANCEL'
    }).run();
    assert.ok(confirmation(h));
    assert.deepEqual(h.writes(), []);
    assert.equal(has(h, 'keyPress'), false);
    assert.equal(h.events.some(event => event.type === 'show'), false);
  });
}

test('Finder decodes a descriptive filename, sends only its text, and renames only the approved name with the original snapshot', async () => {
  const h = await makeHarness({
    context: { appIdentifier: 'com.apple.finder', canPaste: true }, selected: '茶 #1', slug: 'tea-1',
    file: { path: '/tmp/private-parent-do-not-upload/茶 #1.png', name: '茶 #1.png', stem: '茶 #1' },
    confirmResult: 'APPLY:edited-tea-cup.png',
    beforeConfirm({ events, fileOps, writes }) {
      assert.deepEqual(fileOps.map(op => op.op), ['inspect', 'suggest']);
      assert.deepEqual(writes, []);
      assert.equal(events.some(event => event.type === 'keyPress'), false);
    }
  }).run();
  const calls = h.fileOps();
  assert.deepEqual(calls[0], { op: 'inspect', path: h.file.path, include_image: false });
  assert.deepEqual(calls[1], { op: 'suggest', path: h.file.path, snapshot: SNAPSHOT, slug: 'tea-1' });
  assert.deepEqual(calls[2], { op: 'inspect', path: h.file.path, snapshot: SNAPSHOT, include_image: false });
  assert.deepEqual(calls[3], { op: 'rename', path: h.file.path, snapshot: SNAPSHOT, filename: 'edited-tea-cup.png' });
  assert.ok(Object.values(calls[3].snapshot).every(value => typeof value === 'string'));
  const content = apiCall(h).body.contents.find(item => item.role === 'user').parts;
  assert.deepEqual(JSON.parse(content[0].text), { source_text: '茶 #1', source_kind: 'text' });
  assert.equal(content.length, 1);
  assert.match(confirmation(h).args[1], /Translated from the original filename/);
  const textPrompt = apiCall(h).body.systemInstruction.parts.map(item => item.text).join('\n') + content[0].text;
  for (const secret of [h.file.path, '/tmp/private-parent-do-not-upload', KEY, IMAGE]) assert.equal(textPrompt.includes(secret), false);
  assert.deepEqual(h.events.find(event => event.type === 'keyPress').args, ['escape', 0, { target: 'app' }]);
  const recheckIndex = h.events.findIndex(event => event.type === 'file' && event.request.op === 'inspect' && event.request.snapshot);
  const escapeIndex = h.events.findIndex(event => event.type === 'keyPress');
  assert.ok(h.events.findIndex(event => event.type === 'confirm') < recheckIndex);
  assert.ok(recheckIndex < escapeIndex);
  assert.ok(escapeIndex < h.events.findIndex(event => event.type === 'file' && event.request.op === 'rename'));
  assert.equal(h.events.filter(event => event.type === 'script' && event.name === 'finder.sh').length, 2);
  assert.ok(h.events.findIndex(event => event.type === 'confirm') < h.events.findIndex(event => event.type === 'file' && event.request.op === 'rename'));
  assert.equal(has(h, 'paste'), false);
  assert.equal(has(h, 'copy'), false);
  assert.match(h.shown(), /Renamed: edited-tea-cup\.png/);
});

test('a descriptive Chinese picnic name reaches translation intact and gets a short proposal', async () => {
  const stem = '野餐照片 2A | 餐盤＋四格 | 藍色桌布 3';
  const slug = 'picnic-photo';
  const h = await makeHarness({
    context: { appIdentifier: 'com.apple.finder' }, selected: `${stem}.webp`, slug,
    file: { path: `/tmp/private-parent-do-not-upload/${stem}.webp`, name: `${stem}.webp`, stem, extension: '.webp' },
    confirmResult: 'CANCEL'
  }).run();
  const content = apiCall(h).body.contents.find(item => item.role === 'user').parts;
  assert.deepEqual(content, [{ text: JSON.stringify({ source_text: stem, source_kind: 'text' }) }]);
  assert.equal(JSON.stringify(apiCall(h).body).includes(IMAGE), false);
  assert.equal(h.fileOps().filter(op => op.op === 'inspect').length, 1);
  assert.equal(h.fileOps()[0].include_image, false);
  assert.equal(confirmation(h).args[2], `${slug}.webp`);
  assert.match(confirmation(h).args[1], /Translated from the original filename/);
  assert.deepEqual(h.writes(), []);
});

for (const stem of [
  'Group 4 野餐照片', 'IMG_1234 公園', '圖片整理方法', '截圖 野餐藍桌布',
  '2001-02-03', '1234', '2A', 'deadbeef', 'marketing-v3', 'Group Therapy', '未知作品名稱',
  'Group 4', 'IMG_1234', 'CleanShot 2001-02-03 at 12.34.56@2x'
]) {
  test(`translation action stays text-only regardless of filename: ${stem}`, async () => {
    const h = await makeHarness({
      context: { appIdentifier: 'com.apple.finder' }, selected: `${stem}.png`, confirmResult: 'CANCEL',
      file: { name: `${stem}.png`, stem }, imageReadError: 'image_too_large'
    }).run();
    const content = apiCall(h).body.contents.find(item => item.role === 'user').parts;
    assert.equal(content.length, 1);
    assert.deepEqual(JSON.parse(content[0].text), { source_text: stem, source_kind: 'text' });
    assert.deepEqual(h.fileOps().filter(op => op.op === 'inspect'), [{ op: 'inspect', path: h.file.path, include_image: false }]);
    assert.match(confirmation(h).args[1], /Translated from the original filename/);
    assert.deepEqual(h.writes(), []);
  });
}

for (const stem of [
  'Group 4', 'Frame 12', 'Untitled 3', 'IMG_1234', 'IMG_E1234', 'DSC_0123', 'PXL_20010203_123456',
  'CleanShot 2001-02-03 at 12.34.56@2x', 'Screenshot 2001-02-03 at 12.34.56',
  '螢幕截圖 2001-02-03 下午12.34.56', '野餐照片 2A | 餐盤＋四格 | 藍色桌布 3',
  'weekend-picnic-plan'
]) {
  test(`visual naming explicitly reads the image regardless of existing name: ${stem}`, async () => {
    const h = await makeHarness({
      action: 'image',
      context: { appIdentifier: 'com.apple.finder' }, selected: `${stem}.png`, confirmResult: 'CANCEL',
      file: { name: `${stem}.png`, stem }
    }).run();
    const calls = h.fileOps();
    assert.deepEqual(calls.slice(0, 2), [
      { op: 'inspect', path: h.file.path, include_image: false },
      { op: 'inspect', path: h.file.path, snapshot: SNAPSHOT, include_image: true }
    ]);
    const content = apiCall(h).body.contents.find(item => item.role === 'user').parts;
    assert.deepEqual(JSON.parse(content[0].text), { source_kind: 'image' });
    assert.deepEqual(content[1], { inlineData: { mimeType: 'image/png', data: IMAGE.split(',')[1] } });
    assert.equal(content.length, 2);
    assert.match(confirmation(h).args[1], /Based on the image subject and asset type/);
    assert.equal(JSON.stringify(apiCall(h).body).includes(h.file.path), false);
    assert.deepEqual(h.writes(), []);
  });
}

test('image naming uploads only the image and source kind, keeping names, paths, and helper metadata local', async () => {
  const stem = 'PRIVATE_IMAGE_FILENAME_DO_NOT_UPLOAD';
  const metadata = 'PRIVATE_IMAGE_METADATA_DO_NOT_UPLOAD';
  const localPath = `/tmp/private-image-parent/${stem}.png`;
  const h = await makeHarness({
    action: 'image', context: { appIdentifier: 'com.apple.finder' }, selected: 'PRIVATE_IMAGE', confirmResult: 'CANCEL',
    file: {
      path: localPath, name: `${stem}.png`, stem, metadata,
      image: { dataUrl: IMAGE, filename: `${stem}.png`, path: localPath, metadata }
    }
  }).run();
  const body = apiCall(h).body;
  assert.deepEqual(body.contents, [{ role: 'user', parts: [
    { text: JSON.stringify({ source_kind: 'image' }) },
    { inlineData: { mimeType: 'image/png', data: IMAGE.split(',')[1] } }
  ] }]);
  const serialized = JSON.stringify(body);
  for (const privateValue of [stem, h.file.name, localPath, metadata, ...Object.values(SNAPSHOT), KEY]) {
    assert.equal(serialized.includes(privateValue), false, `Unexpected local value in image request: ${privateValue}`);
  }
  assert.equal(confirmation(h).args[1].split('\n')[0], `Original: ${stem}.png`);
  assert.match(confirmation(h).args[1], /Based on the image subject and asset type/);
  assert.deepEqual(h.writes(), []);
});

test('visual naming confirms before renaming and carries the original snapshot through both reads and apply', async () => {
  const h = await makeHarness({
    action: 'image', context: { appIdentifier: 'com.apple.finder' }, selected: 'Group 4.png',
    slug: 'solopreneur-book-mockup', confirmResult: 'APPLY:edited-book-mockup.png',
    beforeConfirm({ writes }) { assert.deepEqual(writes, []); }
  }).run();
  assert.deepEqual(h.fileOps(), [
    { op: 'inspect', path: h.file.path, include_image: false },
    { op: 'inspect', path: h.file.path, snapshot: SNAPSHOT, include_image: true },
    { op: 'suggest', path: h.file.path, snapshot: SNAPSHOT, slug: 'solopreneur-book-mockup' },
    { op: 'inspect', path: h.file.path, snapshot: SNAPSHOT, include_image: false },
    { op: 'rename', path: h.file.path, snapshot: SNAPSHOT, filename: 'edited-book-mockup.png' }
  ]);
  assert.equal(h.writes().length, 1);
  assert.equal(has(h, 'paste'), false);
  assert.equal(has(h, 'copy'), false);
  assert.ok(h.events.findIndex(event => event.type === 'confirm') < h.events.findIndex(event => event.type === 'file' && event.request.op === 'rename'));
});

test('video naming sends only source kind and numbered frames in order; names, paths, timing, and metadata stay local', async () => {
  const videoOnly = 'FULL_VIDEO_PRIVATE_DO_NOT_UPLOAD';
  const audioOnly = 'AUDIO_PRIVATE_DO_NOT_UPLOAD';
  const metadata = 'PRIVATE_VIDEO_METADATA_DO_NOT_UPLOAD';
  const stem = 'PRIVATE_VIDEO_FILENAME_DO_NOT_UPLOAD';
  const duration = 12345.6789;
  const timestamps = [0.1234567, 6789.1234567, 12345.3456789];
  const localPath = `/tmp/private-video-parent/${stem}.mp4`;
  const h = await makeVideoHarness({
    selected: 'PRIVATE_VIDEO',
    file: { path: localPath, name: `${stem}.mp4`, stem, metadata },
    video: {
      ...VIDEO, duration, filename: `${stem}.mp4`, path: localPath, metadata, videoBase64: videoOnly, audioData: audioOnly,
      frames: VIDEO.frames.map((frame, index) => ({ ...frame, seconds: timestamps[index], metadata }))
    },
    confirmResult: 'CANCEL'
  }).run();
  assert.deepEqual(h.fileOps(), [
    { op: 'inspect', path: h.file.path, include_image: false },
    { op: 'video_frames', path: h.file.path, snapshot: SNAPSHOT },
    { op: 'suggest', path: h.file.path, snapshot: SNAPSHOT, slug: 'file-renaming-demo' }
  ]);
  const api = apiCall(h);
  const parts = api.body.contents[0].parts;
  assert.deepEqual(parts, [
    { text: JSON.stringify({ source_kind: 'video' }) },
    { text: 'Frame 1/3:' },
    { inlineData: { mimeType: 'image/jpeg', data: 'Zmlyc3QtZnJhbWU=' } },
    { text: 'Frame 2/3:' },
    { inlineData: { mimeType: 'image/jpeg', data: 'bWlkZGxlLWZyYW1l' } },
    { text: 'Frame 3/3:' },
    { inlineData: { mimeType: 'image/jpeg', data: 'bGFzdC1mcmFtZQ==' } }
  ]);
  const serialized = JSON.stringify(api.body);
  for (const privateValue of [
    stem, h.file.name, localPath, videoOnly, audioOnly, metadata, KEY, ...Object.values(SNAPSHOT),
    String(duration), ...timestamps.flatMap(seconds => [String(seconds), seconds.toFixed(2)])
  ]) {
    assert.equal(serialized.includes(privateValue), false, `Unexpected local value in video request: ${privateValue}`);
  }
  assert.doesNotMatch(JSON.stringify(parts), /source_text|filename|duration|seconds|timestamp|metadata|snapshot|path/i);
  const prompt = api.body.systemInstruction.parts.map(part => part.text).join('\n');
  assert.doesNotMatch(prompt, /timestamps?|duration/i);
  assert.match(prompt, /chronological order/);
  assert.match(prompt, /do not claim unseen steps or infer speech, music or other audio/);
  assert.equal(confirmation(h).args[1].split('\n')[0], `Original: ${stem}.mp4`);
  assert.match(confirmation(h).args[1], /Based on 3 sampled video frames/);
  assert.equal(confirmation(h).args[2], 'file-renaming-demo.mp4');
  assert.deepEqual(h.writes(), []);
});

test('video naming preserves the approved extension and only renames after confirmation', async () => {
  const h = await makeVideoHarness({
    confirmResult: 'APPLY:edited-workflow-demo.mp4',
    beforeConfirm({ writes }) { assert.deepEqual(writes, []); }
  }).run();
  assert.deepEqual(h.writes(), [{
    type: 'file', request: { op: 'rename', path: h.file.path, snapshot: SNAPSHOT, filename: 'edited-workflow-demo.mp4' }
  }]);
  assert.ok(h.events.findIndex(event => event.type === 'confirm') < h.events.findIndex(event => event.type === 'file' && event.request.op === 'rename'));
  assert.match(h.shown(), /Renamed: edited-workflow-demo\.mp4/);
});

for (const extension of ['.mp4', '.MOV', '.m4v', '.WebM', '.MKV']) {
  test(`content naming explicitly extracts frames for ${extension}`, async () => {
    const h = await makeVideoHarness({
      selected: `錄影 1${extension}`, file: { name: `錄影 1${extension}`, extension }, confirmResult: 'CANCEL'
    }).run();
    assert.equal(h.fileOps().filter(op => op.op === 'video_frames').length, 1);
    assert.equal(h.fileOps().some(op => op.include_image), false);
    assert.equal(JSON.parse(apiCall(h).body.contents[0].parts[0].text).source_kind, 'video');
    assert.equal(confirmation(h).args[2], `file-renaming-demo${extension}`);
    assert.deepEqual(h.writes(), []);
  });
  for (const appIdentifier of ['com.apple.finder', 'com.apple.TextEdit']) {
    test(`translation of ${extension} in ${appIdentifier} preserves the extension without video access`, async () => {
      const h = await makeVideoHarness({
        action: 'translate', context: { appIdentifier, canPaste: true }, selected: `錄影 1${extension}`,
        file: { name: `錄影 1${extension}`, extension }, confirmResult: 'CANCEL',
        fileErrors: { video_frames: 'invalid_video' }
      }).run();
      const parts = apiCall(h).body.contents[0].parts;
      assert.deepEqual(parts, [{ text: JSON.stringify({ source_text: '錄影 1', source_kind: 'text' }) }]);
      assert.equal(h.fileOps().some(op => op.op === 'video_frames' || op.include_image), false);
      assert.equal(confirmation(h).args[2], `file-renaming-demo${extension}`);
      assert.deepEqual(h.writes(), []);
    });
  }
}

for (const extension of ['.avi', '.mp3', '.pdf']) {
  test(`content naming rejects unsupported ${extension} without frame extraction or API access`, async () => {
    const h = await makeVideoHarness({ selected: `錄影 1${extension}`, file: { name: `錄影 1${extension}`, extension } }).run();
    assert.equal(h.fileOps().length, 1);
    assert.equal(has(h, 'api'), false);
    assert.equal(has(h, 'confirm'), false);
    assert.match(h.shown(), /Content naming supports/);
    assert.deepEqual(h.writes(), []);
  });
}

for (const [label, video] of [
  ['missing duration', { ok: true, frames: VIDEO.frames }],
  ['zero duration', { ...VIDEO, duration: 0 }],
  ['negative duration', { ...VIDEO, duration: -1 }],
  ['string duration', { ...VIDEO, duration: '10' }],
  ['nonfinite duration', { ...VIDEO, duration: Infinity }],
  ['missing frames', { ok: true, duration: 10 }],
  ['wrong frames type', { ...VIDEO, frames: {} }],
  ['empty frames', { ...VIDEO, frames: [] }],
  ['too many frames', { ...VIDEO, frames: Array.from({ length: 9 }, (_, seconds) => ({ ...VIDEO.frames[0], seconds })) }],
  ['null frame', { ...VIDEO, frames: [null] }],
  ['missing timestamp', { ...VIDEO, frames: [{ mime: 'image/jpeg', dataUrl: VIDEO.frames[0].dataUrl }] }],
  ['negative timestamp', { ...VIDEO, frames: [{ ...VIDEO.frames[0], seconds: -1 }] }],
  ['past-duration timestamp', { ...VIDEO, frames: [{ ...VIDEO.frames[0], seconds: 10.01 }] }],
  ['string timestamp', { ...VIDEO, frames: [{ ...VIDEO.frames[0], seconds: '0.15' }] }],
  ['nonfinite timestamp', { ...VIDEO, frames: [{ ...VIDEO.frames[0], seconds: NaN }] }],
  ['reversed timestamps', { ...VIDEO, frames: [...VIDEO.frames].reverse() }],
  ['duplicate timestamps', { ...VIDEO, frames: [VIDEO.frames[0], VIDEO.frames[0]] }],
  ['wrong frame MIME', { ...VIDEO, frames: [{ ...VIDEO.frames[0], mime: 'video/mp4' }] }],
  ['non-JPEG data URL', { ...VIDEO, frames: [{ ...VIDEO.frames[0], dataUrl: IMAGE }] }],
  ['raw video URL', { ...VIDEO, frames: [{ ...VIDEO.frames[0], dataUrl: 'data:video/mp4;base64,AAAA' }] }],
  ['malformed frame base64', { ...VIDEO, frames: [{ ...VIDEO.frames[0], dataUrl: 'data:image/jpeg;base64,AA\nAA' }] }]
]) {
  test(`invalid video helper result (${label}) stops before API, preview, or rename`, async () => {
    const h = await makeVideoHarness({ video }).run();
    assert.deepEqual(h.fileOps().map(op => op.op), ['inspect', 'video_frames']);
    assert.equal(has(h, 'api'), false);
    assert.equal(has(h, 'confirm'), false);
    assert.match(h.shown(), /Could not extract usable video frames/);
    assert.deepEqual(h.writes(), []);
    assertNoSecrets(h);
  });
}

test('video payload limit applies to total encoded frames before sending an API request', async () => {
  const dataUrl = `data:image/jpeg;base64,${'A'.repeat(10 * 1024 * 1024)}`;
  const h = await makeVideoHarness({ video: {
    ok: true, duration: 10, frames: [
      { seconds: 0, mime: 'image/jpeg', dataUrl }, { seconds: 5, mime: 'image/jpeg', dataUrl }
    ]
  } }).run();
  assert.equal(has(h, 'api'), false);
  assert.equal(has(h, 'confirm'), false);
  assert.match(h.shown(), /video frames are too large/);
  assert.deepEqual(h.writes(), []);
});

for (const frames of [
  [{ ...VIDEO.frames[0], seconds: 0 }],
  [{ ...VIDEO.frames[0], seconds: 0 }, { ...VIDEO.frames[1], seconds: 10 }],
  Array.from({ length: 8 }, (_, seconds) => ({ ...VIDEO.frames[0], seconds }))
]) {
  test(`accepts ${frames.length} valid video samples including inclusive time boundaries`, async () => {
    const h = await makeVideoHarness({ video: { ...VIDEO, frames }, confirmResult: 'CANCEL' }).run();
    assert.equal(apiCall(h).body.contents[0].parts.length, 1 + 2 * frames.length);
    assert.ok(confirmation(h));
    assert.deepEqual(h.writes(), []);
  });
}

for (const errorCode of ['missing_video_tools', 'unsupported_video', 'invalid_video', 'video_timeout', 'video_frames_too_large', 'changed', 'permission_denied']) {
  test(`video extraction failure (${errorCode}) stops without leaking data or renaming`, async () => {
    const h = await makeVideoHarness({ fileErrors: { video_frames: errorCode } }).run();
    assert.equal(has(h, 'api'), false);
    assert.equal(has(h, 'confirm'), false);
    assert.deepEqual(h.writes(), []);
    assert.ok(h.shown());
    assertNoSecrets(h);
  });
}

for (const extension of ['.HEIC', '.gif', '.png']) {
  test(`descriptive ${extension} names translate without reading even oversized or unsupported image content`, async () => {
    const stem = '藍色桌布野餐照 2A';
    const h = await makeHarness({
      context: { appIdentifier: 'com.apple.finder' }, selected: `${stem}${extension}`, confirmResult: 'CANCEL',
      file: { name: `${stem}${extension}`, stem, extension, snapshot: { ...SNAPSHOT, size: '23068672' } },
      imageReadError: 'image_too_large'
    }).run();
    assert.ok(confirmation(h));
    assert.equal(apiCall(h).body.contents.find(item => item.role === 'user').parts.length, 1);
    assert.equal(h.fileOps().some(op => op.include_image), false);
    assert.equal(confirmation(h).args[2], `quarterly-marketing-plan${extension}`);
    assert.deepEqual(h.writes(), []);
  });
}

for (const errorCode of ['image_too_large', 'image_type_mismatch', 'image_sanitization_failed', 'image_timeout', 'image_cancelled', 'changed', 'permission_denied']) {
  test(`a failed second image read (${errorCode}) never sends an API request or changes the file`, async () => {
    const h = await makeHarness({
      action: 'image', context: { appIdentifier: 'com.apple.finder' }, selected: 'Group 4.png', imageReadError: errorCode
    }).run();
    assert.deepEqual(h.fileOps().map(op => op.op), ['inspect', 'inspect']);
    assert.equal(has(h, 'api'), false);
    assert.equal(has(h, 'confirm'), false);
    assert.ok(h.shown());
    assert.deepEqual(h.writes(), []);
    assertNoSecrets(h);
  });
}

test('visual naming rejects HEIC before reading bytes or requesting AI', async () => {
  const h = await makeHarness({
    action: 'image',
    context: { appIdentifier: 'com.apple.finder' }, selected: 'IMG_1234.HEIC',
    file: { name: 'IMG_1234.HEIC', stem: 'IMG_1234', extension: '.HEIC', image: null }
  }).run();
  assert.equal(h.fileOps().length, 1);
  assert.equal(h.fileOps()[0].include_image, false);
  assert.equal(has(h, 'api'), false);
  assert.equal(has(h, 'confirm'), false);
  assert.match(h.shown(), /Content naming supports/);
  assert.deepEqual(h.writes(), []);
});

test('generic text selected outside Finder never gains image access', async () => {
  const h = await makeHarness({ selected: 'Group 4.png', confirmResult: 'CANCEL' }).run();
  const content = apiCall(h).body.contents.find(item => item.role === 'user').parts;
  assert.deepEqual(JSON.parse(content[0].text), { source_text: 'Group 4', source_kind: 'text' });
  assert.equal(content.length, 1);
  assert.deepEqual(h.fileOps(), []);
  assert.match(confirmation(h).args[1], /Translated from the selected text/);
  assert.deepEqual(h.writes(), []);
});

for (const appIdentifier of ['com.apple.TextEdit', 'com.apple.finder.other', '', undefined]) {
  test(`does not consult Finder for source app ${String(appIdentifier)}`, async () => {
    const h = await makeHarness({ context: { appIdentifier, canPaste: true } }).run();
    assert.equal(h.events.some(event => event.type === 'script' && event.name === 'finder.sh'), false);
    assert.deepEqual(h.fileOps(), []);
    assert.equal(has(h, 'keyPress'), false);
  });
  test(`visual naming rejects non-Finder source ${String(appIdentifier)} before key, file, or API access`, async () => {
    const h = await makeHarness({ action: 'image', options: {}, context: { appIdentifier, canPaste: true } }).run();
    assertNoLookupOrWrite(h);
    assert.deepEqual(h.fileOps(), []);
    assert.equal(has(h, 'key'), false);
    assert.equal(has(h, 'script'), false);
    assert.match(h.shown(), /select an image or video in Finder/);
  });
}

for (const action of ['translate', 'image']) {
  test(`${action} uses popclip.context when no action context is supplied`, async () => {
    const h = await makeHarness({ action, omitActionContext: true, popclipContext: { appIdentifier: 'com.apple.finder', canPaste: false }, selected: 'Group 4.png' }).run();
    assert.deepEqual(h.fileOps().map(op => op.op), action === 'image' ? ['inspect', 'inspect', 'suggest', 'inspect', 'rename'] : ['inspect', 'suggest', 'inspect', 'rename']);
  });
}

for (const selected of ['different-file.png', 'Group 5', 'Group  4', ' Group 4.png ', 'Group 4.png\n']) {
  test(`Finder rejects text that is not a literal filename substring: ${JSON.stringify(selected)}`, async () => {
    const h = await makeHarness({ context: { appIdentifier: 'com.apple.finder' }, selected }).run();
    assertNoLookupOrWrite(h);
    assert.match(h.shown(), /selected text is not part of the selected Finder filename/);
  });
}

test('Finder accepts canonically equivalent Unicode filenames', async () => {
  const h = await makeHarness({ context: { appIdentifier: 'com.apple.finder' }, selected: 'cafe\u0301.png', file: { name: 'café.png', stem: 'café' } }).run();
  assert.ok(apiCall(h));
  assert.equal(h.fileOps().at(-1).op, 'rename');
});

for (const [name, stem, extension, selected] of [
  ['野餐照片 2A | 餐盤＋四格 | 藍色桌布 3.webp', '野餐照片 2A | 餐盤＋四格 | 藍色桌布 3', '.webp', '餐盤＋四格'],
  ['年度規劃.png', '年度規劃', '.png', '年度規劃'],
  ['Group 4.png', 'Group 4', '.png', 'Group'],
  ['proposal.final.v2.pdf', 'proposal.final.v2', '.pdf', 'final.v2'],
  ['季度備份.tar.gz', '季度備份', '.tar.gz', '季度備份.tar'],
  ['Café cover.png', 'Café cover', '.png', 'Cafe\u0301'],
  ['Cafe\u0301 cover.png', 'Cafe\u0301 cover', '.png', 'Café'],
  ['prefix middle suffix.PNG', 'prefix middle suffix', '.PNG', 'middle']
]) {
  test(`partial Finder text resolves the full original stem and extension: ${JSON.stringify(selected)} in ${JSON.stringify(name)}`, async () => {
    const h = await makeHarness({
      context: { appIdentifier: 'com.apple.finder' }, selected, confirmResult: 'CANCEL',
      file: { path: `/tmp/private-parent-do-not-upload/${name}`, name, stem, extension }
    }).run();
    const content = apiCall(h).body.contents[0].parts;
    assert.deepEqual(content, [{ text: JSON.stringify({ source_text: stem, source_kind: 'text' }) }]);
    assert.equal(confirmation(h).args[1].split('\n')[0], `Original: ${name}`);
    assert.equal(confirmation(h).args[2], `quarterly-marketing-plan${extension}`);
    assert.equal(h.events.filter(event => event.type === 'script' && event.name === 'finder.sh').length, 1);
    assert.equal(has(h, 'keyPress'), false);
    assert.deepEqual(h.writes(), []);
  });
}

test('partially selected image filename still reads the selected full image and previews the full original name', async () => {
  const name = '野餐照片 2A 餐盤四格 藍色桌布 3.webp';
  const stem = name.slice(0, -5);
  const h = await makeHarness({
    action: 'image', context: { appIdentifier: 'com.apple.finder' }, selected: '餐盤四格', confirmResult: 'CANCEL',
    file: { path: `/tmp/private-parent-do-not-upload/${name}`, name, stem, extension: '.webp', image: { dataUrl: IMAGE.replace('image/png', 'image/webp') } }
  }).run();
  const parts = apiCall(h).body.contents[0].parts;
  assert.deepEqual(JSON.parse(parts[0].text), { source_kind: 'image' });
  assert.equal(parts[1].inlineData.mimeType, 'image/webp');
  assert.deepEqual(h.fileOps().map(op => op.op), ['inspect', 'inspect', 'suggest']);
  assert.equal(confirmation(h).args[1].split('\n')[0], `Original: ${name}`);
  assert.equal(confirmation(h).args[2], 'quarterly-marketing-plan.webp');
  assert.equal(has(h, 'keyPress'), false);
  assert.deepEqual(h.writes(), []);
});

test('partially selected video filename still extracts frames for the selected full video', async () => {
  const h = await makeVideoHarness({ selected: '錄影', confirmResult: 'CANCEL' }).run();
  const source = JSON.parse(apiCall(h).body.contents[0].parts[0].text);
  assert.deepEqual(source, { source_kind: 'video' });
  assert.deepEqual(h.fileOps()[1], { op: 'video_frames', path: h.file.path, snapshot: SNAPSHOT });
  assert.equal(confirmation(h).args[1].split('\n')[0], 'Original: 錄影 1.mp4');
  assert.equal(has(h, 'keyPress'), false);
  assert.deepEqual(h.writes(), []);
});

test('Finder preview keeps the entire filename even when it exceeds the ordinary text preview limit', async () => {
  const stem = `cover-${'a'.repeat(170)}-tail-marker`;
  const name = `${stem}.webp`;
  const h = await makeHarness({
    context: { appIdentifier: 'com.apple.finder' }, selected: 'cover', confirmResult: 'CANCEL',
    file: { name, stem, extension: '.webp' }
  }).run();
  assert.equal(confirmation(h).args[1].split('\n')[0], `Original: ${name}`);
  assert.equal(JSON.parse(apiCall(h).body.contents[0].parts[0].text).source_text, stem);
  assert.equal(has(h, 'keyPress'), false);
});

test('non-Finder text preview retains its 160-character display limit while API receives the entire selection', async () => {
  const selected = `course-${'b'.repeat(170)}-tail-marker`;
  const h = await makeHarness({ selected, confirmResult: 'CANCEL' }).run();
  assert.equal(confirmation(h).args[1].split('\n')[0], `Original: ${selected.slice(0, 160)}`);
  assert.equal(JSON.parse(apiCall(h).body.contents[0].parts[0].text).source_text, selected);
  assert.deepEqual(h.fileOps(), []);
});

for (const action of ['translate', 'image']) {
  test(`${action} does not Escape or rename when Finder selection changes after preview`, async () => {
    const h = await makeHarness({
      action, context: { appIdentifier: 'com.apple.finder' }, selected: 'Group',
      finderOutputs: [undefined, 'OK:file:///tmp/private-parent-do-not-upload/different.png\n']
    }).run();
    assert.ok(confirmation(h));
    assert.equal(h.events.filter(event => event.type === 'script' && event.name === 'finder.sh').length, 2);
    assert.equal(has(h, 'keyPress'), false);
    assert.deepEqual(h.writes(), []);
    assert.equal(h.fileOps().at(-1).op, 'suggest');
    assert.match(h.shown(), /Finder selection changed/);
  });

  test(`${action} checks the original snapshot before Escape and stops if the file changed during preview`, async () => {
    const h = await makeHarness({
      action, context: { appIdentifier: 'com.apple.finder' }, selected: 'Group', recheckError: 'changed'
    }).run();
    assert.ok(confirmation(h));
    assert.deepEqual(h.fileOps().at(-1), { op: 'inspect', path: h.file.path, snapshot: SNAPSHOT, include_image: false });
    assert.equal(has(h, 'keyPress'), false);
    assert.deepEqual(h.writes(), []);
    assert.match(h.shown(), /The file changed/);
  });

  test(`${action} validates the approved name before rechecking Finder or sending Escape`, async () => {
    const h = await makeHarness({
      action, context: { appIdentifier: 'com.apple.finder' }, selected: 'Group', confirmResult: 'APPLY:changed-extension.jpg'
    }).run();
    assert.ok(confirmation(h));
    assert.equal(h.events.filter(event => event.type === 'script' && event.name === 'finder.sh').length, 1);
    assert.equal(has(h, 'keyPress'), false);
    assert.deepEqual(h.writes(), []);
    assert.match(h.shown(), /Keep the original file extension/);
  });
}

for (const config of [
  { apiError: new Error(RAW) },
  { response: completed(RAW) },
  { fileErrors: { suggest: 'collision' } },
  { confirmError: new Error(RAW) }
]) {
  test('Finder lookup, generation, or preview failure leaves the rename field untouched', async () => {
    const h = await makeHarness({ ...config, context: { appIdentifier: 'com.apple.finder' }, selected: 'Group' }).run();
    assert.equal(has(h, 'keyPress'), false);
    assert.deepEqual(h.writes(), []);
    assert.ok(h.shown());
    assertNoSecrets(h);
  });
}

for (const [output, expected] of [
  ['ERR:SELECTION\n', /Select one file in Finder/],
  ['ERR:PERMISSION\n', /Allow PopClip to control Finder/],
  ['ERR:FINDER\n', /Cannot read the Finder selection/],
  ['OK:https://example.com/private.png\n', /Cannot read the Finder selection/],
  ['OK:file://remote-host/private.png\n', /Cannot read the Finder selection/],
  ['OK:file:///tmp/bad%ZZ.png\n', /Cannot read the Finder selection/]
]) {
  test(`Finder stops safely for ${output.trim()}`, async () => {
    const h = await makeHarness({ context: { appIdentifier: 'com.apple.finder' }, selected: 'Group 4', finderOutput: output }).run();
    assertNoLookupOrWrite(h);
    assert.deepEqual(h.fileOps(), []);
    assert.match(h.shown(), expected);
  });
}

for (const slug of ['../escape', 'path/name', 'path\\name', 'Upper-Case', 'with space', 'bad--slug', 'name.png', '-name', 'name-', '', 'a'.repeat(65), 42, null]) {
  test(`rejects invalid model slug ${JSON.stringify(slug)}`, async () => {
    const h = await makeHarness({ slug }).run();
    assert.equal(has(h, 'confirm'), false);
    assert.deepEqual(h.writes(), []);
    assert.match(h.shown(), /Could not generate a valid English filename/);
  });
}

// The API schema and local guard must agree; manual edits remain independent.
for (const slug of ['icon', 'one-two-three-four-five', 'orange-command-symbol-thin-keycap-icon']) {
  test(`rejects a model suggestion outside the word budget: ${slug}`, async () => {
    const h = await makeHarness({ slug }).run();
    const schema = apiCall(h).body.generationConfig.responseJsonSchema.properties.slug;
    assert.equal(new RegExp(schema.pattern).test(slug), false);
    assert.equal(has(h, 'confirm'), false);
    assert.deepEqual(h.writes(), []);
  });
}

for (const slug of ['command-icon', 'command-key-icon', 'tokyo-family-trip-photo', 'international-architecture-exhibition']) {
  test(`accepts a short-word-budget suggestion without truncation: ${slug}`, async () => {
    const h = await makeHarness({ slug, confirmResult: 'CANCEL' }).run();
    const schema = apiCall(h).body.generationConfig.responseJsonSchema.properties.slug;
    assert.equal(new RegExp(schema.pattern).test(slug), true);
    assert.equal(confirmation(h).args[2], `${slug}.png`);
    assert.deepEqual(h.writes(), []);
  });
}

test('a manually edited preview can add details beyond the AI word budget', async () => {
  const edited = 'orange-command-key-icon-light-theme.png';
  const h = await makeHarness({ slug: 'command-key-icon', confirmResult: `APPLY:${edited}` }).run();
  assert.deepEqual(h.writes(), [{ type: 'paste', text: edited, options: { restore: true } }]);
});

for (const response of [
  completed('```json\n{"slug":"safe-name"}\n```'), completed(RAW),
  { data: { candidates: [] } },
  { data: { promptFeedback: { blockReason: 'SAFETY' } } },
  { data: { candidates: [{ finishReason: 'SAFETY', content: { parts: [{ text: '{"slug":"blocked-name"}' }] } }] } },
  { data: { candidates: [{ finishReason: 'MAX_TOKENS', content: { parts: [{ text: '{"slug":"truncated-name"}' }] } }] } },
  { data: { candidates: [{ content: { parts: [{ text: '{"slug":"missing-finish-reason"}' }] } }] } },
  { data: { candidates: [{ finishReason: 'STOP', content: { parts: [] } }] } },
  { data: { candidates: [{ finishReason: 'STOP', content: { parts: [{ thought: true, text: '{"slug":"thought-only"}' }] } }] } },
  { data: { candidates: [{ finishReason: 'STOP' }] } },
  { data: { ...completed({ slug: 'safe-name' }).data, error: { message: RAW } } }
]) {
  test('rejects malformed, fenced, incomplete, or errored model output before confirmation', async () => {
    const h = await makeHarness({ response }).run();
    assert.equal(has(h, 'confirm'), false);
    assert.deepEqual(h.writes(), []);
    assertNoSecrets(h);
  });
}

test('Gemini STOP response ignores thought and non-text parts and joins only final text', async () => {
  const h = await makeHarness({ response: { data: { candidates: [{
    finishReason: 'STOP', content: { role: 'model', parts: [
      { thought: true, text: RAW },
      { text: '{"slug":' },
      { text: '"final-english-name"}', thought: false },
      { inlineData: { mimeType: 'image/png', data: 'AAAA' } }
    ] }
  }] } } }).run();
  assert.equal(confirmation(h).args[2], 'final-english-name.png');
  assert.equal(h.writes()[0].text, 'final-english-name.png');
  assertNoSecrets(h);
});

for (const [extension, mimeType] of [['.png', 'image/png'], ['.JPEG', 'image/jpeg'], ['.webp', 'image/webp']]) {
  test(`Gemini visual input carries pure base64 and the exact MIME type for ${extension}`, async () => {
    const data = 'cHJpdmF0ZS10ZXN0LWltYWdl';
    const h = await makeHarness({
      action: 'image', context: { appIdentifier: 'com.apple.finder' }, selected: `Group 4${extension}`, confirmResult: 'CANCEL',
      file: { name: `Group 4${extension}`, extension, image: { dataUrl: `data:${mimeType};base64,${data}` } }
    }).run();
    const content = apiCall(h).body.contents[0].parts;
    assert.deepEqual(content[1], { inlineData: { mimeType, data } });
    assert.equal(JSON.stringify(apiCall(h).body).includes('data:image/'), false);
    assert.equal(JSON.stringify(apiCall(h).body).includes(KEY), false);
    assert.deepEqual(h.writes(), []);
  });
}

for (const dataUrl of ['data:image/png;base64,', 'data:image/svg+xml;base64,AAAA', 'data:image/png;base64,AA\nAA', 'https://example.com/image.png']) {
  test('malformed or unsupported inline image data is rejected before the Gemini request', async () => {
    const h = await makeHarness({
      action: 'image', context: { appIdentifier: 'com.apple.finder' }, selected: 'Group 4.png', file: { image: { dataUrl } }
    }).run();
    assert.equal(has(h, 'api'), false);
    assert.equal(has(h, 'confirm'), false);
    assert.match(h.shown(), /image format does not match its extension/);
    assert.deepEqual(h.writes(), []);
  });
}

for (const approved of ['safe-name.jpg', 'safe-name.PNG', '../escape.png', 'nested/name.png', 'Upper-Case.png', 'name.png\n']) {
  test(`rejects unsafe edit or changed extension ${JSON.stringify(approved)}`, async () => {
    const h = await makeHarness({ confirmResult: `APPLY:${approved}` }).run();
    assert.deepEqual(h.writes(), []);
    assert.match(h.shown(), /Keep the original file extension|lowercase English/);
  });
}

for (const extension of ['.PNG', '.tar.gz', '.tar.GZ']) {
  for (const mode of ['text', 'file']) {
    test(`${mode} preserves the exact case of ${extension}`, async () => {
      const h = await makeHarness({
        selected: `季度備份${extension}`, slug: 'quarterly-backup',
        context: { appIdentifier: mode === 'file' ? 'com.apple.finder' : 'com.apple.TextEdit', canPaste: true },
        file: { name: `季度備份${extension}`, stem: '季度備份', extension, image: null }
      }).run();
      assert.equal(confirmation(h).args[2], `quarterly-backup${extension}`);
      const write = h.writes()[0];
      assert.equal(mode === 'file' ? write.request.filename : write.text, `quarterly-backup${extension}`);
      assert.equal(apiCall(h).body.contents.find(item => item.role === 'user').parts.length, 1);
    });
  }
}

for (const errorCode of ['changed', 'collision']) {
  test(`helper ${errorCode} during suggest prevents confirmation and rename`, async () => {
    const h = await makeHarness({ context: { appIdentifier: 'com.apple.finder' }, selected: 'Group 4', fileErrors: { suggest: errorCode } }).run();
    assert.equal(has(h, 'confirm'), false);
    assert.deepEqual(h.writes(), []);
    assert.match(h.shown(), errorCode === 'changed' ? /The file changed/ : /filename is already in use/);
  });
  test(`helper ${errorCode} at rename reports failure after the approved request`, async () => {
    const h = await makeHarness({ context: { appIdentifier: 'com.apple.finder' }, selected: 'Group 4', fileErrors: { rename: errorCode } }).run();
    assert.equal(h.writes().length, 1);
    assert.deepEqual(h.writes()[0].request.snapshot, SNAPSHOT);
    assert.ok(confirmation(h));
    assert.equal(h.shown().includes('Renamed: '), false);
    assert.match(h.shown(), errorCode === 'changed' ? /The file changed/ : /filename is already in use/);
  });
}

for (const errorCode of ['symlink', 'not_regular_file', 'not_found', 'image_type_mismatch', 'image_too_large']) {
  test(`helper inspect ${errorCode} stops before lookup or Escape`, async () => {
    const h = await makeHarness({ context: { appIdentifier: 'com.apple.finder' }, selected: 'Group 4', fileErrors: { inspect: errorCode } }).run();
    assertNoLookupOrWrite(h);
    assertNoSecrets(h);
  });
}

test('missing API key performs no API or file action', async () => {
  const h = await makeHarness({ options: {}, fallbackKey: '', context: { appIdentifier: 'com.apple.finder' }, selected: 'Group 4' }).run();
  assertNoLookupOrWrite(h);
  assert.deepEqual(h.fileOps(), []);
  assert.equal(has(h, 'key'), false);
  assert.equal(h.events.some(event => event.type === 'script'), false);
  assert.match(h.shown(), /No Gemini API Key found/);
});

test('env key lookup is a fixed script and receives no selected text', async () => {
  const h = await makeHarness({ options: { envFile: ENV_PATH }, selected: 'UNTRUSTED_SELECTED_TEXT' }).run();
  const keyRead = h.events.find(event => event.type === 'key');
  assert.equal(keyRead.source.includes('UNTRUSTED_SELECTED_TEXT'), false);
  assert.equal(keyRead.source.includes('GEMINI_API_KEY_POP'), true);
  assert.equal(keyRead.source.includes('XAI_API_KEY'), false);
  assert.equal(keyRead.options.interpreter, '/bin/zsh');
  assert.equal(keyRead.options.shellMode, 'none');
  assert.deepEqual(keyRead.options.arguments, ['-c', keyRead.source, ENV_PATH]);
  assert.ok(apiCall(h));
});

test('obsolete options.apiKey cannot override the dedicated Gemini env key', async () => {
  const h = await makeHarness({ options: { apiKey: LEGACY_KEY, envFile: ENV_PATH } }).run();
  assert.equal(apiCall(h).options.headers['x-goog-api-key'], KEY);
  assert.equal(JSON.stringify(apiCall(h)).includes(LEGACY_KEY), false);
  assert.equal(h.events.filter(event => event.type === 'key').length, 1);
  assertNoSecrets(h);
});

test('the Gemini key entered in extension settings takes precedence without reading any env file', async () => {
  const h = await makeHarness({
    options: { geminiApiKey: `  ${OPTION_KEY}  `, apiKey: LEGACY_KEY, envFile: 'invalid-but-unused.env' },
    keyError: new Error('Settings key must not trigger an env lookup.')
  }).run();
  assert.equal(apiCall(h).options.headers['x-goog-api-key'], OPTION_KEY);
  assert.equal(has(h, 'key'), false);
  assert.equal(h.events.some(event => event.type === 'script' && event.name === 'python.sh'), false);
  assert.deepEqual(h.fileOps(), []);
  assertNoSecrets(h);
});

for (const options of [{}, { geminiApiKey: '' }, { geminiApiKey: ' \t\n ' }, { geminiApiKey: null }]) {
  test('an empty Gemini settings field uses an explicitly selected dotenv file', async () => {
    const h = await makeHarness({ options: { ...options, envFile: ENV_PATH } }).run();
    assert.equal(apiCall(h).options.headers['x-goog-api-key'], KEY);
    assert.equal(h.events.filter(event => event.type === 'key').length, 1);
    assert.equal(h.events.find(event => event.type === 'key').options.arguments[2], ENV_PATH);
    assertNoSecrets(h);
  });
}

for (const geminiApiKey of ['bad key', 'bad\nkey', 'bad\tkey', 123, true, {}, []]) {
  test('an invalid entered key stops rather than silently using the dotenv key', async () => {
    const h = await makeHarness({
      options: { geminiApiKey }, context: { appIdentifier: 'com.apple.finder' }, selected: 'Group'
    }).run();
    assertNoLookupOrWrite(h);
    assert.equal(has(h, 'key'), false);
    assert.deepEqual(h.fileOps(), []);
    assert.match(h.shown(), /Gemini API Key/);
    if (typeof geminiApiKey === 'string') assert.equal(h.shown().includes(geminiApiKey), false);
    assertNoSecrets(h);
  });
}

test('a custom dotenv path is passed only as a literal argument to the fixed Python reader', async () => {
  const envFile = '/private/tmp/custom $(do-not-run) `literal` key.env';
  const h = await makeHarness({ options: { envFile }, selected: 'UNTRUSTED_SELECTED_TEXT' }).run();
  const keyRead = h.events.find(event => event.type === 'key');
  assert.equal(keyRead.options.arguments[2], envFile);
  assert.equal(keyRead.source.includes(envFile), false);
  assert.equal(keyRead.source.includes('UNTRUSTED_SELECTED_TEXT'), false);
  assert.equal(keyRead.options.shellMode, 'none');
  assert.equal(apiCall(h).options.headers['x-goog-api-key'], KEY);
  assert.equal(JSON.stringify(apiCall(h)).includes(envFile), false);
  assert.equal(h.shown().includes(envFile), false);
  assertNoSecrets(h);
});

for (const envFile of ['', ' \t ', undefined, null]) {
  test('no key and no explicit env path stops before reading files or launching Python', async () => {
    const h = await makeHarness({ options: { geminiApiKey: ' \t ', envFile }, keyStatus: 127 }).run();
    assertNoLookupOrWrite(h);
    assert.equal(has(h, 'key'), false);
    assert.equal(h.events.some(event => event.type === 'script'), false);
    assert.deepEqual(h.fileOps(), []);
    assert.match(h.shown(), /No Gemini API Key found/);
    assertNoSecrets(h);
  });
}

for (const envFile of ['relative.env', '../private.env', '~someone/private.env', 123, {}]) {
  test('an invalid custom env path fails without reading credentials or exposing the path', async () => {
    const h = await makeHarness({ options: { envFile } }).run();
    assertNoLookupOrWrite(h);
    assert.equal(has(h, 'key'), false);
    assert.deepEqual(h.fileOps(), []);
    assert.match(h.shown(), /\.env/);
    if (typeof envFile === 'string') assert.equal(h.shown().includes(envFile), false);
    assertNoSecrets(h);
  });
}

test('missing Python during dotenv lookup gets actionable feedback and performs no lookup or writes', async () => {
  const h = await makeHarness({ keyStatus: 127, fallbackKey: '', selected: 'Group', context: { appIdentifier: 'com.apple.finder' } }).run();
  assertNoLookupOrWrite(h);
  assert.deepEqual(h.fileOps(), []);
  assert.match(h.shown(), /Python 3/);
  assertNoSecrets(h);
});

test('missing Python in Finder is reported even when a settings key avoids dotenv lookup', async () => {
  const h = await makeHarness({
    options: { geminiApiKey: OPTION_KEY }, pythonStatus: 127,
    context: { appIdentifier: 'com.apple.finder' }, selected: 'Group'
  }).run();
  assertNoLookupOrWrite(h);
  assert.equal(has(h, 'key'), false);
  assert.match(h.shown(), /Python 3/);
  assertNoSecrets(h);
});

for (const mode of ['dotenv', 'finder']) {
  test(`a rejected Python launcher promise in ${mode} reports the dependency without leaking script output`, async () => {
    const failure = Object.assign(new Error(`${KEY} ${OPTION_KEY} ${RAW}`), {
      status: 127, stdout: '{"ok":false,"errorCode":"missing_python"}', stderr: `${KEY} ${RAW}`
    });
    const h = await makeHarness({
      ...(mode === 'dotenv' ? { keyError: failure } : {
        options: { geminiApiKey: OPTION_KEY }, fileThrow: { inspect: failure }
      }),
      context: { appIdentifier: 'com.apple.finder' }, selected: 'Group'
    }).run();
    assertNoLookupOrWrite(h);
    assert.match(h.shown(), /Python 3/);
    assertNoSecrets(h);
  });
}

test('settings-key API errors never fall back to dotenv or expose the entered key', async () => {
  const h = await makeHarness({
    options: { geminiApiKey: OPTION_KEY },
    apiError: Object.assign(new Error(`${OPTION_KEY} ${RAW}`), { response: { status: 401, data: RAW } })
  }).run();
  assert.equal(has(h, 'key'), false);
  assert.equal(h.events.filter(event => event.type === 'api').length, 1);
  assert.deepEqual(h.writes(), []);
  assert.match(h.shown(), /Gemini API Key/);
  assertNoSecrets(h);
});

for (const config of [{ fallbackKey: '' }, { fallbackKey: 'bad key' }, { keyStatus: 1 }, { keyError: new Error(RAW) }]) {
  test('missing or unreadable env key never falls back to obsolete extension options', async () => {
    const h = await makeHarness({ ...config, options: { apiKey: LEGACY_KEY, envFile: ENV_PATH }, context: { appIdentifier: 'com.apple.finder' }, selected: 'Group 4' }).run();
    assertNoLookupOrWrite(h);
    assert.deepEqual(h.fileOps(), []);
    assert.match(h.shown(), /GEMINI_API_KEY_POP/);
    assertNoSecrets(h);
  });
}

for (const config of [
  { apiError: Object.assign(new Error(`${KEY} ${IMAGE} ${RAW}`), { response: { status: 401, data: RAW } }) },
  { apiError: Object.assign(new Error(`${KEY} ${IMAGE} ${RAW}`), { response: { status: 429, data: RAW } }) },
  { apiError: Object.assign(new Error(`${KEY} ${IMAGE} ${RAW}`), { code: 'ETIMEDOUT' }) },
  { apiError: new Error(`${KEY} ${IMAGE} ${RAW}`) },
  { confirmError: new Error(`${KEY} ${IMAGE} ${RAW}`) },
  { context: { appIdentifier: 'com.apple.finder' }, selected: 'Group 4', finderError: new Error(`${KEY} ${IMAGE} ${RAW}`) },
  { context: { appIdentifier: 'com.apple.finder' }, selected: 'Group 4', fileRaw: { inspect: `${KEY} ${IMAGE} ${RAW}` } },
  { response: completed(`${KEY} ${IMAGE} ${RAW}`) }
]) {
  test('failure feedback never exposes credentials, image data, file path, or raw error/response', async () => {
    const h = await makeHarness(config).run();
    assert.ok(h.shown());
    assert.deepEqual(h.writes(), []);
    assertNoSecrets(h);
  });
}
