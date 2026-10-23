(function () {
  'use strict';
  if (window.SnusChat) return;
  const root = document.createElement('div');
  root.id = 'snus-chat';
  root.innerHTML = `<section aria-label="Chat Snus Sài Gòn">
      <header><span class="identity"><span class="dot" aria-hidden="true"></span><strong>Snus Sài Gòn</strong></span><button type="button" data-reset aria-label="Chat mới" title="Chat mới"><svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path d="M12 5v14M5 12h14"/></svg></button></header>
      <div class="log" role="log" aria-live="polite"></div>
      <div class="status" role="status"></div>
      <form><textarea rows="1" aria-label="Tin nhắn" placeholder="Nhắn tin…" maxlength="2000" required></textarea><button type="submit" aria-label="Gửi"><svg viewBox="0 0 24 24" width="21" height="21" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 19V5m-6 6 6-6 6 6"/></svg></button></form>
    </section>`;
  document.body.appendChild(root);
  const style = document.createElement('style');
  style.textContent = `
    #snus-chat{color:#202822;font:15px/1.65 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;padding:24px}
    #snus-chat *{box-sizing:border-box}
    #snus-chat section{display:flex;flex-direction:column;width:100%;max-width:760px;height:calc(100dvh - 48px);min-height:260px;margin:0 auto;background:#fff;border:1px solid #e6eae6;border-radius:20px;overflow:hidden}
    #snus-chat header{display:flex;align-items:center;justify-content:space-between;min-height:76px;padding:16px 26px;border-bottom:1px solid #f0f2ef}
    #snus-chat .identity{display:flex;align-items:center;gap:11px}
    #snus-chat strong{font-size:15px;font-weight:600;letter-spacing:-.2px}
    #snus-chat .dot{width:8px;height:8px;border-radius:50%;background:#42785c}
    #snus-chat button{display:inline-flex;align-items:center;justify-content:center;border:0;cursor:pointer;font:inherit;flex-shrink:0}
    #snus-chat header button{width:36px;height:36px;border-radius:10px;background:transparent;color:#6c756e}
    #snus-chat header button:hover{background:#f1f4f1;color:#243e2e}
    #snus-chat .log{display:flex;flex-direction:column;align-items:flex-start;gap:18px;flex:1;overflow-y:auto;padding:30px 26px;scrollbar-width:thin}
    #snus-chat .bubble{max-width:86%;padding:13px 17px;border-radius:17px 17px 17px 4px;background:#f2f4f1;margin:0;white-space:pre-wrap;overflow-wrap:anywhere}
    #snus-chat .user{align-self:flex-end;border-radius:17px 17px 4px 17px;background:#244b38;color:#fff}
    #snus-chat form{display:flex;align-items:flex-end;gap:12px;margin:0 24px 24px;padding:9px 10px 9px 17px;border:1px solid #e0e6df;border-radius:16px;background:#fff}
    #snus-chat form:focus-within{border-color:#94ac9a;box-shadow:0 0 0 3px #244b3808}
    #snus-chat textarea{display:block;resize:none;min-width:0;flex:1;max-height:140px;padding:7px 0;border:0;outline:0;background:transparent;color:#202822;font:inherit;line-height:1.6}
    #snus-chat textarea::placeholder{color:#929a93}
    #snus-chat form button{width:38px;height:38px;border-radius:11px;background:#244b38;color:#fff}
    #snus-chat form button:hover{background:#183b29}
    #snus-chat button:disabled{opacity:.45;cursor:wait}
    #snus-chat .status{padding:0 28px 10px;color:#788177;font-size:13px}
    #snus-chat .status:empty{display:none}
    #snus-chat button:focus-visible{outline:2px solid #7f9e86;outline-offset:3px}
    @media(max-width:600px){#snus-chat{padding:0}#snus-chat section{height:100dvh;border:0;border-radius:0}#snus-chat header{min-height:68px;padding:14px 20px}#snus-chat .log{padding:24px 18px;gap:15px}#snus-chat .bubble{max-width:91%}#snus-chat form{margin:0 14px max(14px,env(safe-area-inset-bottom));gap:8px}#snus-chat .status{padding-left:20px}}
  `;
  document.head.appendChild(style);
  const log = root.querySelector('.log'), input = root.querySelector('textarea');
  const form = root.querySelector('form'), submit = form.querySelector('button');
  const status = root.querySelector('.status');
  let history = [], controller = null, conversationId;
  function add(text, who) {
    const p = document.createElement('p');
    p.className = 'bubble' + (who === 'user' ? ' user' : '');
    p.textContent = text;
    log.appendChild(p); log.scrollTop = log.scrollHeight;
  }
  function open() { input.focus(); }
  function reset() {
    if (controller) controller.abort();
    controller = null; conversationId = crypto.randomUUID(); history = []; log.replaceChildren(); status.textContent = ''; submit.disabled = false; input.value = ''; input.style.height = '';
    add('Chào bạn! Mình có thể giúp gì cho bạn?');
  }
  root.querySelector('[data-reset]').onclick = () => { reset(); input.focus(); };
  input.addEventListener('input', () => { input.style.height = 'auto'; input.style.height = Math.min(input.scrollHeight,140) + 'px'; });
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); if (!controller) form.requestSubmit(); }
  });
  window.SnusChat = { open, reset };
  reset();
  form.onsubmit = async e => {
    e.preventDefault();
    const message = input.value.trim();
    if (!message || controller) return;
    input.value = ''; input.style.height = ''; add(message, 'user'); submit.disabled = true; status.textContent = 'Đang trả lời…';
    const active = new AbortController(); controller = active;
    const requestId = crypto.randomUUID(), currentConversation = conversationId;
    const timer = setTimeout(() => active.abort(), 120000);
    try {
      const response = await fetch('/chat/api/message', {method:'POST', headers:{'content-type':'application/json'}, body:JSON.stringify({message, history, conversation_id:currentConversation, request_id:requestId}), signal:active.signal});
      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || error.error || `HTTP ${response.status}`);
      }
      const payload = await response.text();
      if (controller !== active) return;
      let answer = '';
      for (const event of payload.split(/\r?\n\r?\n/)) {
        if (!event.startsWith('event: message')) continue;
        const line = event.split(/\r?\n/).find(x => x.startsWith('data: '));
        if (line) answer += JSON.parse(line.slice(6)).text || '';
      }
      if (!answer) throw new Error('Server không trả nội dung.');
      add(answer); history.push({role:'user',content:message},{role:'assistant',content:answer}); history = history.slice(-8);
      status.textContent = '';
    } catch (error) {
      if (controller !== active) return;
      status.textContent = error.name === 'AbortError' ? 'Hết thời gian chờ. Bạn có thể gửi lại.' : `Lỗi: ${error.message}`;
    } finally {
      clearTimeout(timer);
      if (controller === active) { controller = null; submit.disabled = false; input.focus(); }
    }
  };
}());
