/* Session-scoped chat; content approval stays in studio.js. */
'use strict';
(() => {
  const $ = selector => document.querySelector(selector);
  const panel = $('#chat-panel'), input = $('#chat-input'), list = $('#chat-messages');
  let current = null, opened = false, loading = false, sending = false, epoch = 0, timer = null;
  let turns = new Map(), config = null, nextBefore = null, oldestLoaded = false;
  const key = id => 'studio-chat-draft:' + id;
  function saved(id) { try { return JSON.parse(localStorage.getItem(key(id)) || '{}'); } catch { return {}; } }
  function save(value) { if (current) { try { localStorage.setItem(key(current.id), JSON.stringify({mode: $('#chat-mode').value, ...value})); } catch {} } }
  function error(text = '') { $('#chat-error').textContent = text; $('#chat-error').hidden = !text; }
  function node(tag, text, className) { const n = document.createElement(tag); if (text != null) n.textContent = text; if (className) n.className = className; return n; }
  async function request(id, options = {}, before = null) {
    const r = await fetch(`/api/v2/sessions/${encodeURIComponent(id)}/chat/messages${before ? '?before=' + before : ''}`, options);
    const data = await r.json();
    if (!r.ok) { const e = new Error(typeof data.detail === 'string' ? data.detail : 'Câu hỏi chưa hợp lệ. Hãy kiểm tra rồi gửi lại.'); e.status = r.status; throw e; }
    return data;
  }
  function controls() {
    const pending = [...turns.values()].some(t => t.status === 'running');
    $('#chat-send').disabled = !current || sending || loading || pending || current.status === 'processing' || !input.value.trim();
    $('#chat-refresh').disabled = !current || loading;
    $('#chat-older').hidden = !nextBefore;
    $('#chat-older').disabled = loading;
    $('#chat-mode-ai').disabled = !config?.ai_enabled;
    $('#chat-mode').disabled = sending || pending;
    if (!config?.ai_enabled) $('#chat-mode').value = 'guide';
    $('#chat-config').textContent = config?.ai_enabled
      ? `Gemini: đã dùng ${config.used_today}/${config.daily_limit} lượt chat cho phép trong ứng dụng hôm nay. Hướng dẫn có sẵn không gọi AI.`
      : (config?.reason || 'Chọn một phiên để mở trợ lý.');
  }
  function render() {
    const nearBottom = list.scrollHeight - list.scrollTop - list.clientHeight < 70;
    list.replaceChildren();
    if (!turns.size) list.append(node('p', 'Hỏi về sản phẩm, lỗi hoặc bước tiếp theo. Trợ lý chỉ giải thích; nội dung đã duyệt được giữ nguyên.', 'chat-empty'));
    for (const turn of [...turns.values()].sort((a, b) => a.seq - b.seq)) {
      const article = node('article', null, 'chat-turn');
      article.append(node('p', turn.text, 'chat-question'));
      const reply = node('div', null, 'chat-reply');
      reply.append(node('small', `${turn.mode === 'gemini' ? 'Gemini' : 'Hướng dẫn có sẵn'} · tham chiếu phiên r${turn.revision}`));
      if (turn.stale || turn.revision !== current?.revision) reply.append(node('p', 'Câu trả lời này tham chiếu phiên bản cũ. Gửi câu hỏi mới để lấy nội dung hiện tại.', 'chat-stale'));
      if (turn.status === 'running') reply.append(node('p', 'Đang trả lời…', 'chat-waiting'));
      else if (turn.status === 'error') {
        reply.append(node('p', turn.error, 'chat-failure'));
        const retry = node('button', 'Soạn lại câu hỏi', 'quiet');
        retry.type = 'button';
        retry.addEventListener('click', () => {
          if (input.value.trim()) { error('Ô soạn đang có nội dung. Hãy xử lý bản nháp trước khi soạn lại câu hỏi cũ.'); return; }
          input.value = turn.text; save({text: turn.text}); controls(); input.focus();
        });
        reply.append(retry);
      } else if (turn.reply) {
        reply.append(node('p', turn.reply.answer, 'chat-answer'));
        for (const warning of turn.reply.warnings || []) reply.append(node('p', warning, 'chat-stale'));
        const sources = node('details', null, 'chat-sources');
        sources.append(node('summary', 'Căn cứ trả lời'));
        for (const source of turn.reply.sources || []) {
          sources.append(node('strong', source.label));
          sources.append(node('pre', source.excerpt + (source.truncated ? '\n[Nội dung đã rút gọn]' : '')));
        }
        reply.append(sources);
      }
      article.append(reply); list.append(article);
    }
    controls();
    if (nearBottom) list.scrollTop = list.scrollHeight;
  }
  function accept(data, older = false) {
    const firstLoad = !config;
    config = data.config;
    if (firstLoad && config.ai_enabled && saved(current.id).mode === 'gemini') $('#chat-mode').value = 'gemini';
    for (const turn of data.messages) turns.set(turn.message_id, turn);
    if (!oldestLoaded || older) { nextBefore = data.next_before; oldestLoaded = true; }
    render();
  }
  function poll() {
    clearTimeout(timer);
    if (opened && current && [...turns.values()].some(t => t.status === 'running')) timer = setTimeout(() => load(), 1000);
  }
  async function load(older = false) {
    if (!current || loading) return;
    const id = current.id, token = epoch;
    loading = true; controls();
    try {
      const data = await request(id, {}, older ? nextBefore : null);
      if (epoch !== token || current?.id !== id) return;
      accept(data, older); error();
    } catch (e) { if (epoch === token) error(e.message + ' Bấm Cập nhật chat để thử đọc lại.'); }
    finally { if (epoch === token) { loading = false; controls(); poll(); } }
  }
  async function send() {
    if (!current || $('#chat-send').disabled) return;
    const id = current.id, token = epoch, text = input.value.trim(), mode = $('#chat-mode').value;
    const previous = saved(id).attempt;
    const body = previous?.text === text && previous.mode === mode ? previous : {
      message_id: crypto.randomUUID(), expected_revision: current.revision, text, mode
    };
    save({text: input.value, attempt: body});
    sending = true; error(); controls();
    try {
      const data = await request(id, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
      if (epoch !== token || current?.id !== id) return;
      if (input.value.trim() === text) { input.value = ''; save({text: ''}); }
      accept(data); list.scrollTop = list.scrollHeight;
    } catch (e) {
      if (epoch === token) { error(e.message); if (e.status) save({text: input.value}); }
    } finally { if (epoch === token) { sending = false; controls(); poll(); } }
  }
  function setSession(meta) {
    const changed = meta?.id !== current?.id;
    if (changed) {
      if (current) save({...saved(current.id), text: input.value});
      current = meta; epoch++; clearTimeout(timer); loading = false; sending = false;
      turns = new Map(); config = null; nextBefore = null; oldestLoaded = false;
      input.value = meta ? (saved(meta.id).text || '') : ''; error(); render();
    } else {
      const revisionChanged = meta?.revision !== current?.revision;
      current = meta;
      if (revisionChanged && opened) load();
    }
    $('#chat-context').textContent = meta ? `${meta.productName} · Bước ${meta.step}/7 · phiên r${meta.revision}${meta.bundleRevision ? ' · prompt r' + meta.bundleRevision : ''}` : 'Mở hoặc tạo một phiên để bắt đầu.';
    input.disabled = !meta;
    if (changed && opened && meta) load();
    controls();
  }
  function toggle(show) {
    opened = show; panel.hidden = !show;
    $('#chat-launcher').setAttribute('aria-expanded', String(show));
    if (show) { load(); input.focus(); } else { clearTimeout(timer); $('#chat-launcher').focus(); }
  }
  $('#chat-launcher').addEventListener('click', () => toggle(!opened));
  $('#chat-close').addEventListener('click', () => toggle(false));
  $('#chat-refresh').addEventListener('click', () => load());
  $('#chat-older').addEventListener('click', () => load(true));
  $('#chat-form').addEventListener('submit', e => { e.preventDefault(); send(); });
  input.addEventListener('input', () => { save({...saved(current?.id), text: input.value}); controls(); });
  panel.addEventListener('keydown', e => { if (e.key === 'Escape') toggle(false); });
  for (const button of document.querySelectorAll('[data-chat-question]')) button.addEventListener('click', () => {
    if (input.value.trim()) { error('Ô soạn đang có nội dung. Hãy xử lý bản nháp trước khi chọn câu hỏi gợi ý.'); return; }
    input.value = button.dataset.chatQuestion; save({text: input.value}); controls(); input.focus();
  });
  window.ContentStudioChat = {setSession};
  controls();
})();
