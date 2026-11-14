'use strict';

const studioOrigin = 'http://127.0.0.1:8001';
const uuid = /^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/i;
const sceneIds = new Set(['1', '2', '3', '3A', '3B', '4']);

chrome.runtime.onMessage.addListener((message, sender, respond) => {
  if (message?.type !== 'remember-studio-scene') return;
  const source = sender.url && new URL(sender.url);
  if (source?.origin !== studioOrigin || source.pathname !== '/app' ||
      sender.frameId !== 0 || !Number.isInteger(sender.tab?.id)) return;

  const {requestId, sessionId, bundleRevision, sceneId, productName} = message.selection ?? {};
  if (typeof requestId !== 'string' || !uuid.test(requestId) ||
      typeof sessionId !== 'string' || !uuid.test(sessionId) ||
      !Number.isSafeInteger(bundleRevision) || bundleRevision < 1 ||
      !sceneIds.has(sceneId) || typeof productName !== 'string' || productName.length > 300) {
    respond(false);
    return;
  }

  const scene = {requestId, sessionId, bundleRevision, sceneId, productName, tabId: sender.tab.id};
  chrome.storage.session.set({scene}).then(() => respond(true), () => respond(false));
  return true;
});
