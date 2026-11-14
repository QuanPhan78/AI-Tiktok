'use strict';

(() => {
  const studioOrigin = 'http://127.0.0.1:8001';
  if (location.origin !== studioOrigin || location.pathname !== '/app') return;

  window.addEventListener('message', async event => {
    if (event.source !== window || event.origin !== studioOrigin ||
        event.data?.type !== 'content-studio:gemini-prepare') return;
    const selection = event.data.selection;
    if (typeof selection?.requestId !== 'string') return;
    let ok = false;
    try {
      ok = await chrome.runtime.sendMessage({type: 'remember-studio-scene', selection}) === true;
    } catch {
      // Reloading an installed extension can invalidate this script until the tab is reloaded.
    }
    window.postMessage({
      type: 'content-studio:gemini-prepared', requestId: selection.requestId, ok
    }, studioOrigin);
  });

  async function loadApprovedPrompt({sessionId, bundleRevision, sceneId}) {
    try {
      const response = await fetch('/api/v2/sessions/' + encodeURIComponent(sessionId), {
        cache: 'no-store', redirect: 'error', signal: AbortSignal.timeout(6000)
      });
      if (response.status === 404) return {status: 'stale'};
      if (!response.ok) return {status: 'unavailable'};
      const session = await response.json();
      if (session.id !== sessionId || session.step !== 7 || session.status === 'processing' ||
          session.bundle?.revision !== bundleRevision) return {status: 'stale'};
      const prompt = session.bundle.scenes.find(scene => scene.id === sceneId)?.prompt_en;
      if (typeof prompt !== 'string' || !prompt.trim()) return {status: 'stale'};
      return {status: 'ready', prompt};
    } catch {
      return {status: 'unavailable'};
    }
  }

  chrome.runtime.onMessage.addListener((message, sender, respond) => {
    if (sender.id !== chrome.runtime.id || message?.type !== 'load-studio-prompt') return;
    loadApprovedPrompt(message.scene).then(respond, () => respond({status: 'unavailable'}));
    return true;
  });
})();
