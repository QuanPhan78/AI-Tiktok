// This function runs by itself in the Gemini tab when the user clicks the popup.
export async function fillGeminiComposer(prompt) {
  if (location.origin !== 'https://gemini.google.com') return 'wrong-tab';

  const selector = 'rich-textarea [contenteditable="true"][role="textbox"]';
  const visible = Array.from(document.querySelectorAll(selector)).filter(editor => {
    const style = getComputedStyle(editor);
    return editor.getClientRects().length && style.display !== 'none' &&
      style.visibility === 'visible' && !editor.closest('[hidden], [inert], [aria-hidden="true"]');
  });
  if (visible.length !== 1) return 'editor';

  const editor = visible[0];
  const hasDraft = () => editor.textContent !== '' ||
    editor.querySelector('img, [contenteditable="false"]');
  if (hasDraft()) return 'draft';
  editor.focus();
  if (!editor.isConnected || document.activeElement !== editor) return 'editor';
  if (hasDraft()) return 'draft';

  // Chromium inserts text through the editor's normal input path and preserves line breaks.
  const selection = window.getSelection();
  const range = document.createRange();
  range.selectNodeContents(editor);
  range.collapse(true);
  selection.removeAllRanges();
  selection.addRange(range);
  if (!document.execCommand('insertText', false, prompt)) return 'editor';

  // Quill may normalize the resulting nodes into one paragraph per input line.
  await new Promise(resolve => setTimeout(resolve, 0));
  const lines = Array.from(editor.childNodes);
  const paragraphs = lines.length && lines.every(node =>
    node.nodeType === Node.ELEMENT_NODE && node.matches('p, div'));
  const displayed = paragraphs ? lines.map(line => line.textContent).join('\n') : editor.innerText;
  return displayed === prompt || editor.innerText === prompt ? 'filled' : 'verify';
}
