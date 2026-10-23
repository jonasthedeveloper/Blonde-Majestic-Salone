'use strict';
/* Customer chat: "Chat with AI" (automated, database-grounded) and "Chat with Salon" (real people). */
const aiHistory = [];
function bubble(m, who) {
  return html`<div class="bubble ${who}">${m.body}${m.actions && m.actions.length ? html`<div class="acts">${m.actions.map(a => html`<a class="chip" href="${a.href}">${a.label}</a>`)}</div>` : ''}${m.created ? html`<time>${dtshort(m.created)}</time>` : ''}</div>`;
}
route('/chat', () => go('/chat/ai'));
route('/chat/:mode', async ({ mode }) => {
  const v = view();
  put(v, html`<div class="container" style="padding:28px 0 40px;max-width:820px"><h1 style="font-size:2.4rem">Chat</h1>
    <div class="tabs" role="tablist"><a href="#/chat/ai" class="${mode === 'ai' ? 'on' : ''}">Chat with AI</a><a href="#/chat/salon" class="${mode === 'salon' ? 'on' : ''}" style="position:relative">Chat with Salon <span class="dot hidden" data-badge="chat">0</span></a></div><div id="chat"></div></div>`);
  mode === 'salon' ? salonChat($('#chat')) : aiChat($('#chat'));
});

function aiChat(box) {
  put(box, html`<div class="chatbox"><div class="head"><b>AI Assistant</b><div class="small muted">Automated assistant · answers only from the salon’s own information. Not a person.</div></div>
    <div class="msgs" id="msgs" aria-live="polite"></div>
    <div style="padding:8px 12px 0;background:var(--ivory)" class="chips">${['What are your hours?', 'What services do you offer?', 'Any promotions?', 'How do I book?', 'Where are you located?'].map(q => html`<button class="chip" data-q="${q}">${q}</button>`)}</div>
    <form class="composer" id="f"><input id="in" placeholder="Ask about hours, services, prices…" maxlength="500" autocomplete="off" aria-label="Your message"><button class="btn gold" aria-label="Send">${icon('send')}</button></form></div>`);
  const msgs = $('#msgs', box);
  const draw = () => { put(msgs, html`${bubble({ body: `Hello! I’m the ${S('business_name')} AI assistant. I can help with opening hours, services, prices, our team, promotions and booking. If I don’t know something, I’ll point you to the salon team.`, actions: [{ label: 'Chat with Salon', href: '#/chat/salon' }] }, 'them')}${aiHistory.map(m => bubble(m, m.me ? 'me' : 'them'))}`); msgs.scrollTop = msgs.scrollHeight; };
  draw();
  async function send(text) {
    text = text.trim(); if (!text) return; aiHistory.push({ body: text, me: true }); draw();
    const t = document.createElement('div'); t.className = 'typing'; t.textContent = 'AI Assistant is typing…'; msgs.appendChild(t); msgs.scrollTop = msgs.scrollHeight;
    try { const r = await api('/api/ai-chat', { method: 'POST', body: { message: text } }); aiHistory.push({ body: r.reply, actions: r.actions }); }
    catch (e) { aiHistory.push({ body: e.message || 'Sorry, something went wrong. Please try again or call ' + S('phone') + '.', actions: [] }); }
    draw();
  }
  $('#f', box).onsubmit = e => { e.preventDefault(); const i = $('#in', box); const t = i.value; i.value = ''; send(t); };
  $('.chips', box).onclick = e => { const b = e.target.closest('[data-q]'); if (b) send(b.dataset.q); };
}

async function salonChat(box) {
  if (!App.user) { put(box, html`<div class="empty"><b>Sign in to message the salon</b>Your conversation is saved so the team can reply and you’ll be notified.<p><a class="btn gold" href="#/login?next=${encodeURIComponent('/chat/salon')}">Sign in or create account</a></p></div>`); return; }
  if (isStaffUser()) { put(box, html`<div class="empty"><b>You’re signed in as ${App.user.role}</b>Reply to customers from the <a href="#/admin/messages">Messages inbox</a>.</div>`); return; }
  put(box, html`<div class="chatbox"><div class="head"><b>${S('business_name')} team</b><div class="small muted">You’re chatting with the salon team (real people, not AI). Replies appear here and you’ll get a notification.</div></div><div class="msgs" id="msgs"></div>
    <form class="composer" id="f"><input id="in" placeholder="Write a message…" maxlength="1000" autocomplete="off" aria-label="Your message"><button class="btn gold" aria-label="Send">${icon('send')}</button></form></div>`);
  const msgs = $('#msgs', box); let last = 0, first = true;
  async function pull() {
    try {
      const r = await api('/api/my/chat?after=' + last); if (!r.messages.length && !first) return;
      const near = msgs.scrollHeight - msgs.scrollTop - msgs.clientHeight < 80;
      if (first && !r.messages.length) put(msgs, html`<p class="muted center" style="margin:auto">Say hello! For example: “Hi, is Elma available tomorrow?”</p>`);
      else { if (first) msgs.innerHTML = ''; else $('.muted', msgs)?.remove(); r.messages.forEach(m => { msgs.insertAdjacentHTML('beforeend', bubble(m, m.sender === 'customer' ? 'me' : 'them').s); last = m.id; }); }
      if (first || near) msgs.scrollTop = msgs.scrollHeight; first = false; pollNotifications();
    } catch (e) { if (first) put(msgs, html`<div class="form-error">${e.message}</div>`); }
  }
  await pull(); every(pull, 5000);
  $('#f', box).onsubmit = async e => {
    e.preventDefault(); const i = $('#in', box); const body = i.value.trim(); if (!body) return; i.value = '';
    try { await api('/api/my/chat', { method: 'POST', body: { body } }); if (first) { msgs.innerHTML = ''; first = false; } await pull(); msgs.scrollTop = msgs.scrollHeight; }
    catch (er) { i.value = body; toast(er.message, 'err'); }
  };
}
