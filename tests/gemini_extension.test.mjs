import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import test from 'node:test';
import {runInNewContext} from 'node:vm';

const studio = 'http://127.0.0.1:8001';
const gemini = 'https://gemini.google.com';
const source = name => readFileSync(new URL('../extensions/gemini/' + name, import.meta.url), 'utf8');
const turn = () => new Promise(resolve => setImmediate(resolve));
const scene = {
  requestId: '642972de-d00a-4b62-bce6-bca36a9bb7f3',
  sessionId: '94d7a58c-1cc6-4af1-9808-d2e36b87834c',
  bundleRevision: 26, sceneId: '3A', productName: 'Sản phẩm thử', tabId: 20
};
const prompt = 'Cảnh 3A: “Giữ đúng lời thoại”.\n\nUse <product> & show the reference image.';

test('the worker accepts only a top-level Studio tab and keeps the latest scene metadata', async () => {
  let listener;
  let saved;
  const chrome = {
    runtime: {onMessage: {addListener: fn => { listener = fn; }}},
    storage: {session: {set: async value => { saved = value.scene; }}}
  };
  runInNewContext(source('worker.js'), {chrome, URL});
  const prepare = {...scene, tabId: 999, prompt: 'unexpected prompt'};
  const message = {type: 'remember-studio-scene', selection: prepare};
  const sender = {url: studio + '/app', frameId: 0, tab: {id: 20}};
  assert.equal(listener(message, {...sender, url: studio.replace('8001', '8002') + '/app'}, assert.fail), undefined);
  assert.equal(listener(message, {...sender, frameId: 1}, assert.fail), undefined);
  assert.equal(saved, undefined);
  assert.equal(await new Promise(resolve => listener(message, sender, resolve)), true);
  assert.equal(saved.tabId, 20);
  assert.equal(saved.sceneId, '3A');
  assert.equal(saved.prompt, undefined);
  assert.equal(await new Promise(resolve => listener(
    {...message, selection: {...prepare, sceneId: '3B'}}, sender, resolve
  )), true);
  assert.equal(saved.sceneId, '3B');
});

test('Studio resolves 3A and 3B from the approved bundle and refuses stale or reopened revisions', async () => {
  let windowListener;
  let extensionListener;
  let posted;
  let session = {
    id: scene.sessionId, step: 7, status: 'ready',
    bundle: {revision: 26, scenes: [
      {id: '3A', prompt_en: prompt}, {id: '3B', prompt_en: 'Cảnh 3B'}
    ]}
  };
  const window = {
    addEventListener: (_, fn) => { windowListener = fn; },
    postMessage: msg => { posted = msg; }
  };
  const chrome = {runtime: {
    id: 'test-extension',
    onMessage: {addListener: fn => { extensionListener = fn; }},
    sendMessage: async () => true
  }};
  runInNewContext(source('studio-bridge.js'), {
    location: {origin: studio, pathname: '/app'}, window, chrome, AbortSignal,
    fetch: async (url, options) => {
      assert.equal(url, '/api/v2/sessions/' + scene.sessionId);
      assert.equal(options.cache, 'no-store');
      return {ok: true, json: async () => session};
    }
  });
  const prepare = {type: 'content-studio:gemini-prepare', selection: scene};
  await windowListener({source: window, origin: gemini, data: prepare});
  assert.equal(posted, undefined);
  await windowListener({source: window, origin: studio, data: prepare});
  assert.equal(posted.ok, true);
  assert.equal(posted.requestId, scene.requestId);

  const load = sceneId => new Promise(resolve => extensionListener(
    {type: 'load-studio-prompt', scene: {...scene, sceneId}}, {id: 'test-extension'}, resolve
  ));
  assert.equal((await load('3A')).prompt, prompt);
  assert.equal((await load('3B')).prompt, 'Cảnh 3B');
  session = {...session, bundle: {...session.bundle, revision: 27}};
  assert.equal((await load('3A')).status, 'stale');
  session = {...session, step: 6, bundle: null};
  assert.equal((await load('3B')).status, 'stale');
});

async function popup({url = gemini + '/app', readPrompt}) {
  let inserted;
  let click;
  const status = {textContent: ''};
  const button = {disabled: true, addEventListener: (_, fn) => { click = fn; }};
  runInNewContext(source('popup.js').split('\n').slice(1).join('\n'), {
    URL, fillGeminiComposer() {},
    document: {querySelector: selector => selector === '#status' ? status : selector === '#fill' ? button : {}},
    chrome: {
      tabs: {
        query: async () => [{id: 9, url}],
        sendMessage: readPrompt
      },
      storage: {session: {get: async () => ({scene})}},
      scripting: {executeScript: async request => {
        inserted = request.args[0];
        return [{result: 'filled'}];
      }}
    }
  });
  await turn();
  if (click) await click();
  return {status: status.textContent, inserted};
}

test('the popup stops on wrong tab, closed source and stale bundle before touching Gemini', async () => {
  const wrong = await popup({url: 'https://gemini.google.com.example.test/app', readPrompt: assert.fail});
  assert.match(wrong.status, /gemini\.google\.com/);
  assert.equal(wrong.inserted, undefined);
  const closed = await popup({readPrompt: async () => { throw Error('closed'); }});
  assert.match(closed.status, /đã đóng/);
  assert.equal(closed.inserted, undefined);
  const stale = await popup({readPrompt: async () => ({status: 'stale'})});
  assert.match(stale.status, /đã thay đổi/);
  assert.equal(stale.inserted, undefined);
  const ready = await popup({readPrompt: async () => ({status: 'ready', prompt})});
  assert.equal(ready.inserted, prompt);
  assert.match(ready.status, /Đã điền/);
});

test('the composer preserves an existing draft and inserts the exact prompt into a single empty editor', async () => {
  let edits = 0;
  const document = {
    activeElement: null,
    querySelectorAll: () => [editor],
    createRange: () => ({selectNodeContents() {}, collapse() {}}),
    execCommand: (command, _, text) => {
      assert.equal(command, 'insertText');
      edits++;
      editor.innerText = text;
      return true;
    }
  };
  const editor = {
    isConnected: true, textContent: 'Bản nháp của người dùng', innerText: '', childNodes: [],
    getClientRects: () => [1], closest: () => null, querySelector: () => null,
    focus: () => { document.activeElement = editor; }
  };
  const fill = runInNewContext(
    source('composer.js').replace('export async function', 'async function') + '\nfillGeminiComposer;',
    {document, location: {origin: gemini}, setTimeout, Node: {ELEMENT_NODE: 1},
      getComputedStyle: () => ({visibility: 'visible', display: 'block'}),
      window: {getSelection: () => ({removeAllRanges() {}, addRange() {}})}}
  );
  assert.equal(await fill(prompt), 'draft');
  assert.equal(edits, 0);
  editor.textContent = '';
  assert.equal(await fill(prompt), 'filled');
  assert.equal(editor.innerText, prompt);
  document.querySelectorAll = () => [editor, editor];
  assert.equal(await fill(prompt), 'editor');
  assert.equal(edits, 1);
});
