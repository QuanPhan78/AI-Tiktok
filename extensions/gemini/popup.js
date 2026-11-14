import {fillGeminiComposer} from './composer.js';

const geminiOrigin = 'https://gemini.google.com';
const selectionLabel = document.querySelector('#selection');
const status = document.querySelector('#status');
const fill = document.querySelector('#fill');
const messages = {
  'wrong-tab': 'Hãy mở chat trên gemini.google.com rồi mở lại tiện ích.',
  editor: 'Chưa tìm thấy ô soạn Gemini. Mở chat và thử lại, hoặc dùng Sao chép ở Content Studio.',
  draft: 'Ô soạn đang có nội dung. Hãy dùng một ô trống để giữ bản đang soạn.',
  verify: 'Hãy đối chiếu prompt trong ô soạn trước khi bấm tạo video.',
  filled: 'Đã điền prompt. Kiểm tra nội dung rồi bấm Tạo video trên Gemini.',
  stale: 'Bản prompt đã thay đổi hoặc đang xử lý. Hãy chọn lại cảnh ở Bước 7.',
  unavailable: 'Chưa đọc được phiên Content Studio. Kiểm tra web đang chạy rồi thử lại.',
  'source-closed': 'Tab Content Studio đã đóng hoặc mất kết nối. Hãy mở lại Bước 7 và chọn cảnh.'
};

function isGemini(tab) {
  return tab?.url && new URL(tab.url).origin === geminiOrigin;
}

async function initialize() {
  const [target] = await chrome.tabs.query({active: true, currentWindow: true});
  const {scene} = await chrome.storage.session.get('scene');

  if (scene) selectionLabel.textContent = `${scene.productName} · Cảnh ${scene.sceneId} · prompt r${scene.bundleRevision}`;
  if (!isGemini(target)) {
    status.textContent = messages['wrong-tab'];
    return;
  }
  if (!scene) {
    status.textContent = 'Bấm Chọn cảnh cho Gemini tại Bước 7 trước.';
    return;
  }
  status.textContent = 'Điền vào ô soạn trống trong tab Gemini đang mở.';
  fill.disabled = false;
  fill.addEventListener('click', () => fillSelectedScene(scene, target.id));
}

async function fillSelectedScene(scene, targetId) {
  fill.disabled = true;
  status.textContent = 'Đang kiểm tra bản prompt đã chốt…';
  try {
    let response;
    try {
      response = await chrome.tabs.sendMessage(scene.tabId, {type: 'load-studio-prompt', scene});
    } catch {
      status.textContent = messages['source-closed'];
      return;
    }
    if (response?.status !== 'ready') {
      status.textContent = messages[response?.status] ?? messages.unavailable;
      return;
    }

    const {scene: current} = await chrome.storage.session.get('scene');
    if (current?.requestId !== scene.requestId) {
      status.textContent = 'Cảnh đã chọn thay đổi. Hãy mở lại tiện ích để xem cảnh mới.';
      return;
    }
    const [target] = await chrome.tabs.query({active: true, currentWindow: true});
    if (target?.id !== targetId || !isGemini(target)) {
      status.textContent = messages['wrong-tab'];
      return;
    }
    const [result] = await chrome.scripting.executeScript({
      target: {tabId: targetId}, func: fillGeminiComposer, args: [response.prompt]
    });
    status.textContent = messages[result?.result] ?? messages.editor;
  } catch {
    status.textContent = messages.editor;
  } finally {
    fill.disabled = false;
  }
}

initialize().catch(() => { status.textContent = messages.unavailable; });
