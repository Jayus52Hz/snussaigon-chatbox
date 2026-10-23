(function () {
  'use strict';
  if (window.SnusChat) return;
  const root = document.createElement('div');
  root.id = 'snus-chat';
  root.innerHTML = `<button type="button" class="launcher" aria-label="Mở chat tư vấn" aria-expanded="false">Chat ↗</button>
    <section hidden role="dialog" aria-label="Tư vấn Snus Sài Gòn">
      <header><div><strong>Snus Sài Gòn</strong><small>Tư vấn · 18+</small></div><button type="button" data-reset aria-label="Xóa hội thoại">↺</button><button type="button" data-close aria-label="Đóng chat">×</button></header>
      <div class="log" role="log" aria-live="polite"></div>
      <div class="status" role="status"></div>
      <form><input aria-label="Tin nhắn" placeholder="Nhập tin nhắn…" autocomplete="off" maxlength="2000" required><button type="submit">Gửi</button></form>
    </section>`;
  document.body.appendChild(root);
  const style = document.createElement('style');
  style.textContent = `#snus-chat{font:14px/1.5 system-ui,sans-serif;color:#242923}#snus-chat *{box-sizing:border-box}#snus-chat button{cursor:pointer;font:inherit}#snus-chat .launcher{position:fixed;right:24px;bottom:24px;z-index:9999;border:0;border-radius:28px;padding:17px 23px;background:#264b39;color:#fff;box-shadow:0 4px 18px #0003}#snus-chat section{position:fixed;right:24px;bottom:96px;z-index:9999;width:min(390px,calc(100vw - 32px));height:min(540px,calc(100dvh - 125px));background:#fff;border:1px solid #d9ddd4;border-radius:18px;box-shadow:0 10px 40px #0002;display:flex;flex-direction:column;overflow:hidden}#snus-chat section[hidden]{display:none}#snus-chat header{display:flex;align-items:center;gap:12px;padding:16px;background:#264b39;color:#fff}#snus-chat header div{flex:1}#snus-chat small{display:block;opacity:.75;font-size:11px;letter-spacing:0}#snus-chat header button{background:none;color:#fff;border:0;font-size:24px;padding:0 4px}#snus-chat .log{padding:16px;overflow:auto;flex:1;white-space:pre-wrap}#snus-chat .bubble{max-width:92%;border-radius:12px;padding:10px 12px;background:#f0f2ed;margin:0 0 12px;overflow-wrap:anywhere}#snus-chat .user{margin-left:auto;background:#e3eee6}#snus-chat form{display:flex;border-top:1px solid #e2e5de;padding:8px;gap:8px}#snus-chat input{min-width:0;flex:1;padding:10px;border:0;font:inherit;background:#fff;color:#242923}#snus-chat form button{padding:0 15px;border:0;border-radius:9px;background:#264b39;color:#fff}#snus-chat button:disabled{opacity:.5;cursor:wait}#snus-chat .status{padding:0 16px 8px;color:#6e746a;font-size:12px}#snus-chat button:focus-visible,#snus-chat input:focus-visible{outline:2px solid #81ac6f;outline-offset:2px}@media(max-width:480px){#snus-chat section{right:16px;bottom:88px}#snus-chat .launcher{right:16px;bottom:16px}}`;
  document.head.appendChild(style);
  const panel = root.querySelector('section'), launcher = root.querySelector('.launcher');
  const log = root.querySelector('.log'), input = root.querySelector('input');
  const form = root.querySelector('form'), submit = form.querySelector('button');
  const status = root.querySelector('.status');
  let history = [], controller = null;
  function add(text, who) {
    const p = document.createElement('p');
    p.className = 'bubble' + (who === 'user' ? ' user' : '');
    p.textContent = text;
    log.appendChild(p); log.scrollTop = log.scrollHeight;
  }
  function open() { panel.hidden = false; launcher.setAttribute('aria-expanded', 'true'); input.focus(); }
  function close() { panel.hidden = true; launcher.setAttribute('aria-expanded', 'false'); launcher.focus(); }
  function reset() {
    if (controller) controller.abort();
    controller = null; history = []; log.replaceChildren(); status.textContent = ''; submit.disabled = false; input.value = '';
    add('Xin chào! Bạn muốn thử hỏi điều gì? Sản phẩm chỉ dành cho người đủ 18 tuổi.');
  }
  launcher.onclick = open;
  root.querySelector('[data-close]').onclick = close;
  root.querySelector('[data-reset]').onclick = reset;
  root.addEventListener('keydown', e => { if (e.key === 'Escape') close(); });
  window.SnusChat = { open, reset };
  reset();
  form.onsubmit = async e => {
    e.preventDefault();
    const message = input.value.trim();
    if (!message || controller) return;
    input.value = ''; add(message, 'user'); submit.disabled = true; status.textContent = 'Đang trả lời…';
    const active = new AbortController(); controller = active;
    const timer = setTimeout(() => active.abort(), 65000);
    try {
      const response = await fetch('/chat/api/message', {method:'POST', headers:{'content-type':'application/json'}, body:JSON.stringify({message, history}), signal:active.signal});
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
