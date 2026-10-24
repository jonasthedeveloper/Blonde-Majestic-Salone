'use strict';
/* ---------- motion: js gate + image fade-in (part of the shipped app, no preview/dev-only behavior) ---------- */
document.documentElement.classList.add('js');
['load', 'error'].forEach(ev => document.addEventListener(ev, e => { const t = e.target; if (t && t.tagName === 'IMG') t.classList.add('ri'); }, true));
/* ---------- tiny helpers ---------- */
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
class Raw { constructor(s) { this.s = s; } }
const raw = s => new Raw(String(s));
const val = v => v == null || v === false ? '' : Array.isArray(v) ? v.map(val).join('') : v instanceof Raw ? v.s : esc(v);
const html = (st, ...v) => new Raw(st.reduce((o, s, i) => o + s + (i < v.length ? val(v[i]) : ''), ''));
const put = (el, t) => { el.innerHTML = t instanceof Raw ? t.s : esc(t); return el; };
const img = f => f ? '/uploads/' + f : '';
const aed = v => 'AED ' + Number(v || 0).toLocaleString('en', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const money = v => v == null ? 'Price on request' : 'AED ' + (Number.isInteger(v) ? v : Number(v).toFixed(2));
const t12 = s => { if (!s) return ''; const [h, m] = s.split(':').map(Number); return `${(h % 12) || 12}:${String(m).padStart(2, '0')} ${h < 12 ? 'AM' : 'PM'}`; };
const dparse = s => { const [y, m, d] = s.split('-').map(Number); return new Date(y, m - 1, d); };
const dshort = s => dparse(s).toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' });
const iso = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
const todayIso = () => iso(new Date());
const dtshort = s => s ? dshort(s.slice(0, 10)) + ', ' + t12(s.slice(11, 16)) : '';
const STATUS = { pending: 'Pending', confirmed: 'Confirmed', in_progress: 'In Progress', completed: 'Completed', cancelled: 'Cancelled', no_show: 'No Show' };
const pill = (s, label) => html`<span class="pill ${s}">${label || STATUS[s] || s}</span>`;
const stars = n => { const r = Math.round(n); return raw(`<span class="stars" role="img" aria-label="${r} out of 5 stars">${'★'.repeat(r)}<i>${'★'.repeat(5 - r)}</i></span>`); };
const debounce = (fn, ms = 300) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };
const RM = () => !!(window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches);
const ICONS = {
  home: '<path d="M3 11l9-8 9 8v10a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1z"/>', calendar: '<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
  chat: '<path d="M21 11.5a8.4 8.4 0 0 1-9 8.4 8.5 8.5 0 0 1-3.8-.9L3 21l1.9-5.2A8.4 8.4 0 1 1 21 11.5z"/>', user: '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
  bell: '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9M13.7 21a2 2 0 0 1-3.4 0"/>', menu: '<path d="M3 6h18M3 12h18M3 18h18"/>',
  phone: '<path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .4 1.9.7 2.8a2 2 0 0 1-.5 2.1L8.1 9.9a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.8.7a2 2 0 0 1 1.7 2z"/>',
  pin: '<path d="M21 10c0 7-9 13-9 13S3 17 3 10a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/>', wifi: '<path d="M5 12.6a10 10 0 0 1 14 0M1.4 9a15 15 0 0 1 21.2 0M8.5 16.1a5 5 0 0 1 7 0"/><path d="M12 20h.01"/>',
  globe: '<circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15 15 0 0 1 0 20 15 15 0 0 1 0-20z"/>', facebook: '<path d="M18 2h-3a5 5 0 0 0-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 0 1 1-1h3z"/>',
  scissors: '<circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M20 4 8.1 15.9M14.5 14.5 20 20M8.1 8.1 12 12"/>', grid: '<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>',
  users: '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8"/>',
  package: '<path d="M21 16V8a2 2 0 0 0-1-1.7l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.7l7 4a2 2 0 0 0 2 0l7-4a2 2 0 0 0 1-1.7z"/><path d="M3.3 7 12 12l8.7-5M12 22V12"/>',
  tag: '<path d="M20.6 13.4 13.4 20.6a2 2 0 0 1-2.8 0L2 12V2h10l8.6 8.6a2 2 0 0 1 0 2.8z"/><path d="M7 7h.01"/>', star: '<path d="m12 2 3.1 6.3 6.9 1-5 4.9 1.2 6.8-6.2-3.3-6.2 3.3L7 14.2 2 9.3l6.9-1z"/>',
  dollar: '<path d="M12 1v22M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>', sliders: '<path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6"/>',
  chart: '<path d="M12 20V10M18 20V4M6 20v-4"/>', inbox: '<path d="M22 12h-6l-2 3h-4l-2-3H2"/><path d="M5.5 5.1 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.5-6.9A2 2 0 0 0 16.7 4H7.2a2 2 0 0 0-1.7 1.1z"/>',
  x: '<path d="M18 6 6 18M6 6l12 12"/>', coffee: '<path d="M18 8h1a4 4 0 0 1 0 8h-1M2 8h16v9a4 4 0 0 1-4 4H6a4 4 0 0 1-4-4z"/><path d="M6 1v3M10 1v3M14 1v3"/>',
  car: '<path d="M5 17h14M3 13l2-6h14l2 6v4H3z"/><circle cx="7.5" cy="17" r="1.5"/><circle cx="16.5" cy="17" r="1.5"/>', access: '<circle cx="12" cy="4" r="2"/><path d="M12 7v6h5l2 6M12 13a5 5 0 1 0 5 5"/>',
  card: '<rect x="1" y="4" width="22" height="16" rx="2"/><path d="M1 10h22"/>', sparkle: '<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"/>',
  logout: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/>', plus: '<path d="M12 5v14M5 12h14"/>', clock: '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
  send: '<path d="m22 2-11 11M22 2l-7 20-4-9-9-4z"/>', check: '<path d="M20 6 9 17l-5-5"/>', msg: '<path d="M4 4h16a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z"/><path d="m22 6-10 7L2 6"/>',
};
const icon = (n, cls = '') => raw(`<svg class="${cls}" viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[n] || ICONS.sparkle}</svg>`);
const amenityIcon = t => { t = t.toLowerCase(); return /wi-?fi/.test(t) ? 'wifi' : /wheel|access/.test(t) ? 'access' : /bever|drink|coffee|tea/.test(t) ? 'coffee' : /park/.test(t) ? 'car' : 'sparkle'; };
const initials = n => String(n || '?').split(/[\s/&]+/).filter(Boolean).slice(0, 2).map(w => w[0]).join('').toUpperCase();
const pic = (file, name, i = 0, alt) => file ? html`<img src="${img(file)}" alt="${alt || name}" loading="lazy" decoding="async">` : html`<div class="ph ph${i % 4}" aria-hidden="true"><span>${initials(name)}</span></div>`;

/* ---------- app state ---------- */
const App = { settings: {}, cats: [], rating: { average: 0, total: 0 }, staff: [], promos: [], testimonials: [], user: null, unread: 0, chatUnread: 0, timers: [], mode: null, smsReady: false };
const isStaffUser = () => App.user && (App.user.role === 'admin' || App.user.role === 'staff');

async function api(path, { method = 'GET', body, form } = {}) {
  const opt = { method, headers: { 'X-Requested-With': 'fetch' }, credentials: 'same-origin' };
  if (form) opt.body = form; else if (body !== undefined) { opt.headers['Content-Type'] = 'application/json'; opt.body = JSON.stringify(body); }
  let r;
  try { r = await fetch(path, opt); } catch (e) { throw new Error('You appear to be offline. Please check your connection and try again.'); }
  if ((r.headers.get('content-type') || '').includes('json')) {
    const d = await r.json();
    if (!r.ok) { const e = new Error(d.error || 'Something went wrong.'); e.status = r.status; throw e; }
    return d;
  }
  if (!r.ok) { const e = new Error('Something went wrong.'); e.status = r.status; throw e; }
  return r;
}
async function download(path, name) {
  const r = await api(path); const b = await r.blob(); const u = URL.createObjectURL(b);
  const a = document.createElement('a'); a.href = u; a.download = name; document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(u), 2000);
}
const qs = o => { const p = new URLSearchParams(); Object.entries(o).forEach(([k, v]) => { if (v !== '' && v != null) p.set(k, v); }); const s = p.toString(); return s ? '?' + s : ''; };

/* ---------- toast / modal / lightbox ---------- */
function toast(msg, kind = '') {
  const t = document.createElement('div'); t.className = 'toast ' + kind; t.textContent = msg; $('#toasts').appendChild(t);
  setTimeout(() => { if (RM()) { t.remove(); return; } t.classList.add('out'); setTimeout(() => t.remove(), 240); }, kind === 'err' ? 6000 : 3800);
}
function modal(title, content, { wide = false, onClose } = {}) {
  const ov = document.createElement('div'); ov.className = 'overlay';
  put(ov, html`<div class="dialog ${wide ? 'wide' : ''}" role="dialog" aria-modal="true" aria-label="${title}"><header><h3>${title}</h3><button class="iconbtn" data-close aria-label="Close">${icon('x')}</button></header><div class="content">${content}</div></div>`);
  const prevFocus = document.activeElement;
  let state = 0; // 0 open · 1 closing · 2 closed
  const cleanup = () => { if (state === 2) return; state = 2; ov.remove(); document.removeEventListener('keydown', key); if (!document.querySelector('.overlay')) { document.body.style.overflow = ''; prevFocus && prevFocus.focus && prevFocus.focus(); } };
  const exit = notify => { if (state) return; state = 1; notify && onClose && onClose(); if (RM()) return cleanup(); ov.classList.add('closing'); setTimeout(cleanup, 240); };
  const close = () => exit(true);
  const key = e => { if (e.key === 'Escape') close(); };
  ov.addEventListener('click', e => { if (e.target === ov || e.target.closest('[data-close]')) close(); });
  document.addEventListener('keydown', key); document.body.appendChild(ov); document.body.style.overflow = 'hidden';
  return { el: $('.content', ov), root: ov, close, destroy: () => exit(false) };
}
const confirmBox = (title, msg, okLabel = 'Confirm', danger = false) => new Promise(res => {
  const m = modal(title, html`<p>${msg}</p><div style="display:flex;gap:10px;justify-content:flex-end;flex-wrap:wrap"><button class="btn ghost" data-no>Cancel</button><button class="btn ${danger ? 'danger' : ''}" data-yes>${okLabel}</button></div>`, { onClose: () => res(false) });
  $('[data-no]', m.el).onclick = () => { m.close(); };
  $('[data-yes]', m.el).onclick = () => { res(true); m.destroy(); };
});
function lightbox(files, start = 0) {
  let i = start; const ov = document.createElement('div'); ov.className = 'lightbox'; ov.tabIndex = -1;
  const draw = () => put(ov, html`<button class="x" aria-label="Close">×</button>${files.length > 1 ? html`<button class="p" aria-label="Previous">‹</button><button class="n" aria-label="Next">›</button>` : ''}<img src="${img(files[i])}" alt="Photo ${i + 1} of ${files.length}" draggable="false"><div class="c">${i + 1} / ${files.length}</div>`);
  const go = d => { i = (i + d + files.length) % files.length; draw(); };
  let lstate = 0;
  const lclean = () => { if (lstate === 2) return; lstate = 2; ov.remove(); document.removeEventListener('keydown', key); document.body.style.overflow = ''; };
  const close = () => { if (lstate) return; lstate = 1; if (RM()) return lclean(); ov.classList.add('closing'); setTimeout(lclean, 240); };
  const key = e => { if (lstate) return; if (e.key === 'Escape') close(); if (e.key === 'ArrowLeft') go(-1); if (e.key === 'ArrowRight') go(1); };
  ov.addEventListener('click', e => { const b = e.target.closest('button'); if (b) { if (b.className === 'x') close(); else go(b.className === 'p' ? -1 : 1); } else if (e.target === ov) close(); });
  let x0 = null; ov.addEventListener('touchstart', e => { x0 = e.touches[0].clientX; }, { passive: true });
  ov.addEventListener('touchend', e => { if (x0 == null) return; const dx = e.changedTouches[0].clientX - x0; if (Math.abs(dx) > 50 && files.length > 1) go(dx < 0 ? 1 : -1); x0 = null; });
  document.addEventListener('keydown', key); document.body.appendChild(ov); document.body.style.overflow = 'hidden'; draw();
}
function gallery(files, name) {
  if (!files.length) return html`<div class="cover" style="aspect-ratio:1/1;border-radius:var(--r)">${pic('', name)}</div>`;
  const id = 'g' + Math.random().toString(36).slice(2, 7);
  setTimeout(() => {
    const root = document.getElementById(id); if (!root) return; const tr = $('.track', root);
    const sync = () => { const k = Math.round(tr.scrollLeft / tr.clientWidth); $$('.thumbs button', root).forEach((b, j) => b.classList.toggle('on', j === k)); const c = $('.count-badge', root); if (c) c.textContent = `${k + 1} / ${files.length}`; };
    tr.addEventListener('scroll', debounce(sync, 60));
    $$('.thumbs button', root).forEach((b, j) => b.onclick = () => tr.scrollTo({ left: j * tr.clientWidth, behavior: 'smooth' }));
    $$('.slide', root).forEach((s, j) => s.onclick = () => lightbox(files, j));
  }, 0);
  return html`<div class="gallery" id="${id}"><div class="track">${files.map(f => html`<div class="slide"><img src="${img(f)}" alt="${name}" loading="lazy"></div>`)}</div>${files.length > 1 ? html`<span class="count-badge">1 / ${files.length}</span><div class="thumbs">${files.map((f, j) => html`<button class="${j ? '' : 'on'}" aria-label="Show photo ${j + 1}"><img src="${img(f)}" alt=""></button>`)}</div>` : ''}</div>`;
}

/* ---------- scroll reveal (JS-gated: nothing is hidden when JS or reduced-motion says no) ---------- */
let revObs = null;
function revealScan() {
  const v = view(); if (!v || RM() || !('IntersectionObserver' in window)) return;
  if (!revObs) revObs = new IntersectionObserver(es => es.forEach(e => {
    if (!e.isIntersecting) return;
    const el = e.target; revObs.unobserve(el); el.classList.add('rev-in');
    // drop the reveal styles once they have played so each element's own transition
    // (card hover, stat hover, etc.) is not overridden by .rev.rev-in afterwards
    setTimeout(() => { el.classList.remove('rev', 'rev-in'); el.style.transitionDelay = ''; }, 640 + (parseInt(el.style.transitionDelay) || 0));
  }), { rootMargin: '0px 0px -6% 0px', threshold: .05 });
  const watch = (el, i) => { if (el.dataset.rev) return; el.dataset.rev = '1'; if (i) el.style.transitionDelay = Math.min(i, 6) * 55 + 'ms'; el.classList.add('rev'); revObs.observe(el); };
  [...v.children].forEach(el => { if (!el.dataset.rev && !el.classList.contains('grid')) watch(el, 0); });
  $$('.grid', v).forEach(g => [...g.children].forEach((c, i) => watch(c, i))); // staggered cards in every grid
}

/* ---------- router ---------- */
const routes = [];
function route(pattern, fn, opts = {}) { routes.push({ rx: new RegExp('^' + pattern.replace(/:(\w+)/g, '(?<$1>[^/]+)') + '$'), fn, ...opts }); }
const go = p => { location.hash = '#' + p; };
const clearTimers = () => { App.timers.forEach(clearInterval); App.timers = []; };
const every = (fn, ms) => { App.timers.push(setInterval(fn, ms)); };
function view() { return $(App.mode === 'admin' ? '#aview' : '#view'); }
let renderToken = 0;
async function render() {
  const h = location.hash.slice(1) || '/'; const [path, q] = h.split('?'); const query = Object.fromEntries(new URLSearchParams(q || ''));
  clearTimers(); const token = ++renderToken;
  const r = routes.find(r => r.rx.test(path)) || routes.find(r => r.notFound);
  const mode = path.startsWith('/admin') ? 'admin' : 'customer';
  if (App.mode !== mode) { App.mode = mode; mode === 'admin' ? buildAdminShell() : buildCustomerShell(); }
  window.scrollTo(0, 0);
  const params = r.rx.exec(path)?.groups || {};
  try {
    const adminPath = path.startsWith('/admin'); const adminOnly = r.admin ? r.adminOnly : adminPath;
    if (adminPath && !r.notFound) { if (!isStaffUser()) { return adminLogin(); } if (adminOnly && App.user.role !== 'admin') { return put(view(), html`<div class="empty"><b>Owner access only</b>This section is available to the salon owner.</div>`); } }
    if (r.auth && !App.user) { return go('/login?next=' + encodeURIComponent(h)); }
    markNav(path);
    await r.fn(params, query, token);
    if (token === renderToken) revealScan();
  } catch (e) {
    console.error(e);
    if (token === renderToken) put(view(), html`<div class="container" style="padding:60px 0"><div class="empty"><b>We couldn’t load this page</b>${e.message || 'Please try again.'}<p><button class="btn" id="retry">Try again</button></p></div></div>`), $('#retry') && ($('#retry').onclick = render);
  }
}
const stale = t => t !== renderToken;

/* ---------- notifications polling ---------- */
async function pollNotifications(first) {
  if (!App.user) return;
  try {
    const d = await api('/api/notifications');
    if (!first && d.unread > App.unread) { const n = d.notifications.find(x => !x.is_read); if (n) toast(n.title + (n.body ? ' — ' + n.body.slice(0, 70) : '')); }
    App.unread = d.unread; App.chatUnread = d.chat_unread;
    $$('[data-badge="notif"]').forEach(b => { b.textContent = App.unread > 99 ? '99+' : App.unread; b.classList.toggle('hidden', !App.unread); });
    $$('[data-badge="chat"]').forEach(b => { b.textContent = App.chatUnread; b.classList.toggle('hidden', !App.chatUnread); });
  } catch (e) { /* ignore transient errors */ }
}
async function loadBoot() {
  const [pub, me] = await Promise.all([api('/api/public'), api('/api/auth/me')]);
  Object.assign(App, { settings: pub.settings, cats: pub.categories, rating: pub.rating, staff: pub.staff, promos: pub.promotions, testimonials: pub.testimonials, smsReady: pub.sms_enabled, user: me.user });
}
const S = k => App.settings[k];
const telHref = p => 'tel:' + String(p || '').replace(/[^\d+]/g, '');
const webHref = u => /^https?:\/\//i.test(u) ? u : 'https://' + u;
const safeUrl = u => { try { const x = new URL(webHref(u)); return ['http:', 'https:'].includes(x.protocol) ? x.href : '#'; } catch (e) { return '#'; } };
