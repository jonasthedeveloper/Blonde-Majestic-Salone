'use strict';
/* ---------- admin shell ---------- */
function buildAdminShell() {
  if (!isStaffUser()) { put($('#app'), html`<div class="container" style="max-width:460px;padding:60px 0"><div id="aview"></div></div>`); return; }
  const adm = App.user.role === 'admin';
  const L = adm ? [['/admin', 'Dashboard', 'grid'], ['/admin/appointments', 'Appointments', 'calendar'], ['/admin/customers', 'Customers', 'users'], ['-', 'Catalogue'], ['/admin/services', 'Services', 'scissors'], ['/admin/staff', 'Staff', 'user'], ['/admin/products', 'Products', 'package'], ['/admin/promotions', 'Promotions', 'tag'],
  ['-', 'Community'], ['/admin/reviews', 'Reviews', 'star'], ['/admin/testimonials', 'Testimonials', 'sparkle'], ['/admin/messages', 'Messages', 'inbox'], ['/admin/notifications', 'Notifications', 'bell'], ['-', 'Business'], ['/admin/revenue', 'Revenue', 'dollar'], ['/admin/analytics', 'Analytics', 'chart'], ['/admin/settings', 'Settings', 'sliders']]
    : [['/admin/appointments', 'My appointments', 'calendar'], ...(App.user.can_chat ? [['/admin/messages', 'Messages', 'inbox']] : []), ['/admin/notifications', 'Notifications', 'bell']];
  put($('#app'), html`<div class="adm"><aside class="side" id="side"><a class="brand" href="#/admin"><b>Blonde Majestic</b><span>${adm ? 'Owner console' : 'Staff'}</span></a><nav aria-label="Admin">${L.map(([h, l, i]) => h === '-' ? html`<div class="grp">${l}</div>` : html`<a href="#${h}">${icon(i)}${l}${h.endsWith('notifications') ? raw('<span class="dot hidden" data-badge="notif" style="margin-left:auto">0</span>') : h.endsWith('messages') ? raw('<span class="dot hidden" data-badge="adminchat" style="margin-left:auto">0</span>') : ''}</a>`)}</nav></aside>
    <div class="amain"><div class="atop"><button class="iconbtn menubtn" id="menu" aria-label="Menu">${icon('menu')}</button><h1 id="atitle">Admin</h1><a class="btn ghost sm" href="#/">View site</a><span class="small muted desk">${App.user.name}</span><button class="btn light sm" id="lo">Sign out</button></div><div class="apage" id="aview"></div></div></div>`);
  $('#menu').onclick = () => { $('#side').classList.add('open'); const s = document.createElement('div'); s.className = 'scrim'; s.onclick = () => { $('#side').classList.remove('open'); s.classList.add('out'); setTimeout(() => s.remove(), RM() ? 0 : 240); }; document.body.appendChild(s); };
  $('#lo').onclick = logout; pollNotifications(true); adminBadges();
}
async function adminBadges() { try { if (App.user.role === 'admin' || App.user.can_chat) { const c = await api('/api/admin/conversations'); const n = c.reduce((a, x) => a + x.admin_unread, 0); $$('[data-badge="adminchat"]').forEach(b => { b.textContent = n; b.classList.toggle('hidden', !n); }); } } catch (e) { } }
function adminLogin() {
  put(view(), html`<div style="text-align:center"><a class="brand" style="align-items:center;margin:0 auto 20px" href="#/"><b>Blonde Majestic</b><span>Ladies Salon</span></a></div><div class="card pad"><h2 style="font-size:2rem">Owner & staff sign in</h2><p class="muted small">Customers can’t access this area. Sign in with the account created for you by the salon owner.</p><div id="err"></div>
    <form id="lf"><label class="fld"><span>Email</span><input name="email" type="email" autocomplete="username" required></label><label class="fld"><span>Password</span><input name="password" type="password" autocomplete="current-password" required></label><button class="btn gold block">Sign in</button></form></div>`);
  $('#lf').onsubmit = async e => {
    e.preventDefault(); const b = $('button.btn', e.target); b.disabled = true; b.classList.add('busy');
    try { const r = await api('/api/auth/login', { method: 'POST', body: Object.fromEntries(new FormData(e.target)) }); if (r.user.role === 'customer') { await api('/api/auth/logout', { method: 'POST', body: {} }); throw new Error('This area is for salon staff only.'); } await afterAuth(r.user, location.hash.slice(1).startsWith('/admin') ? location.hash.slice(1) : '/admin'); render(); }
    catch (er) { b.disabled = false; b.classList.remove('busy'); put($('#err'), html`<div class="form-error">${er.message}</div>`); }
  };
}
const setTitle = t => { const e = $('#atitle'); if (e) e.textContent = t; document.title = t + ' · Admin'; };
const A = (p, o) => api('/api/admin/' + p, o);
const sel = (opts, cur, ph) => html`${ph != null ? html`<option value="">${ph}</option>` : ''}${opts.map(([v, l]) => html`<option value="${v}" ${String(v) === String(cur) ? 'selected' : ''}>${l}</option>`)}`;
const adminAlert = e => toast(e.message || 'Something went wrong.', 'err');

/* ---------- generic CRUD ---------- */
const WD = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
function fieldHtml(f, v, deps) {
  const o = f.opts ? f.opts(deps) : [], lab = html`<span>${f.label}${f.req ? ' *' : ''}${f.help ? html` <small>${f.help}</small>` : ''}</span>`;
  switch (f.type) {
    case 'textarea': return html`<label class="fld">${lab}<textarea name="${f.k}" maxlength="${f.max || 2000}">${v ?? ''}</textarea></label>`;
    case 'select': return html`<label class="fld">${lab}<select name="${f.k}" ${f.req ? 'required' : ''}>${sel(o, v, f.req ? null : (f.ph || 'None'))}</select></label>`;
    case 'check': return html`<label class="check"><input type="checkbox" name="${f.k}" ${v ? 'checked' : ''}> ${f.label}${f.help ? html` <small class="muted">${f.help}</small>` : ''}</label>`;
    case 'image': return html`<div class="fld">${lab}<div class="imgedit"><div class="pv" data-pv>${v ? html`<img src="${img(v)}" alt="">` : ''}</div><input type="hidden" name="${f.k}" value="${v || ''}"><input type="file" accept="image/jpeg,image/png,image/webp,image/gif" data-up style="max-width:260px"><button type="button" class="btn ghost sm" data-rm>Remove</button></div></div>`;
    case 'multi': return html`<div class="fld">${lab}<div class="multi" data-multi="${f.k}">${o.length ? o.map(([id, l]) => html`<label class="check"><input type="checkbox" value="${id}" ${(v || []).includes(id) ? 'checked' : ''}> ${l}</label>`) : html`<span class="muted small">Nothing to select yet.</span>`}</div></div>`;
    case 'days': return html`<div class="fld">${lab}<div class="multi" data-multi="${f.k}">${WD.map((d, i) => html`<label class="check"><input type="checkbox" value="${i}" ${(v || [0, 1, 2, 3, 4, 5, 6]).includes(i) ? 'checked' : ''}> ${d}</label>`)}</div></div>`;
    case 'hours': return html`<div class="fld">${lab}<div data-hours>${(v || []).map(h => html`<div class="hrs"><span>${WD[h.weekday].slice(0, 3)}</span><select data-mode><option value="salon" ${!h.custom ? 'selected' : ''}>Salon hours</option><option value="custom" ${h.custom && !h.off ? 'selected' : ''}>Custom</option><option value="off" ${h.custom && h.off ? 'selected' : ''}>Day off</option></select><input type="time" data-s value="${h.start || '10:00'}"><input type="time" data-e value="${h.end || '22:00'}"></div>`)}</div></div>`;
    default: return html`<label class="fld">${lab}<input name="${f.k}" type="${f.type || 'text'}" ${f.step ? raw(`step="${f.step}"`) : ''} ${f.min != null ? raw(`min="${f.min}"`) : ''} ${f.req ? 'required' : ''} maxlength="${f.max || 200}" value="${v ?? ''}"></label>`;
  }
}
function bindFields(form) {
  $$('[data-up]', form).forEach(inp => inp.onchange = async () => {
    const file = inp.files[0]; if (!file) return; const fd = new FormData(); fd.append('file', file);
    try { const r = await A('upload', { method: 'POST', form: fd }); const wrapEl = inp.closest('.imgedit'); $('input[type=hidden]', wrapEl).value = r.filenames[0]; put($('[data-pv]', wrapEl), html`<img src="${img(r.filenames[0])}" alt="">`); } catch (e) { adminAlert(e); inp.value = ''; }
  });
  $$('[data-rm]', form).forEach(b => b.onclick = () => { const w = b.closest('.imgedit'); $('input[type=hidden]', w).value = ''; $('[data-pv]', w).innerHTML = ''; });
}
function readFields(form, fields) {
  const out = {};
  fields.forEach(f => {
    if (f.type === 'check') out[f.k] = $(`[name="${f.k}"]`, form).checked;
    else if (f.type === 'multi' || f.type === 'days') out[f.k] = $$(`[data-multi="${f.k}"] input:checked`, form).map(i => +i.value);
    else if (f.type === 'hours') out[f.k] = $$('[data-hours] .hrs', form).map((r, i) => { const m = $('[data-mode]', r).value; return { weekday: i, custom: m !== 'salon', off: m === 'off', start: $('[data-s]', r).value, end: $('[data-e]', r).value }; });
    else { const v = $(`[name="${f.k}"]`, form).value; out[f.k] = f.type === 'number' ? (v === '' ? null : +v) : v; }
  });
  return out;
}
function formDialog(title, fields, row, deps, save, { extra = '', wide = false, after } = {}) {
  const m = modal(title, html`<form id="cf" novalidate><div id="err"></div>${fields.map(f => fieldHtml(f, row ? row[f.k] : f.def, deps))}${extra}<div style="display:flex;gap:10px;justify-content:flex-end;position:sticky;bottom:0;background:var(--ivory);padding-top:8px"><button type="button" class="btn ghost" data-close>Cancel</button><button class="btn gold">Save</button></div></form>`, { wide });
  const form = $('#cf', m.el); bindFields(form); after && after(m, form);
  form.onsubmit = async e => { e.preventDefault(); const b = $('.btn.gold', form); b.disabled = true; b.classList.add('busy'); try { await save(readFields(form, fields), m); } catch (er) { b.disabled = false; b.classList.remove('busy'); put($('#err', m.el), html`<div class="form-error">${er.message}</div>`); $('#err', m.el).scrollIntoView({ block: 'nearest' }); } };
  return m;
}
async function crudPage(cfg) {
  setTitle(cfg.title); const v = view(); const deps = {}; for (const k in (cfg.deps || {})) deps[k] = await cfg.deps[k]();
  let rows = [], term = '';
  const tabs = cfg.tabs ? html`<div class="tabs">${cfg.tabs.map(([h, l]) => html`<a href="#${h}" class="${location.hash.slice(1) === h ? 'on' : ''}">${l}</a>`)}</div>` : '';
  const draw = () => {
    const shown = rows.filter(r => !term || JSON.stringify(r).toLowerCase().includes(term));
    put(v, html`${tabs}<div class="toolbar"><label class="fld grow"><span>Search</span><input id="s" type="search" value="${term}" placeholder="Search…"></label><button class="btn gold" id="add">${icon('plus')} ${cfg.addLabel || 'Add'}</button></div>${cfg.intro ? html`<div class="notice">${cfg.intro}</div>` : ''}
      ${shown.length ? html`<div class="tblwrap"><table class="tbl"><thead><tr>${cfg.cols.map(c => html`<th>${c.label}</th>`)}<th></th></tr></thead><tbody>${shown.map(r => html`<tr>${cfg.cols.map(c => html`<td data-l="${c.label}" class="${c.num ? 'num' : ''}">${c.get(r, deps)}</td>`)}<td class="num" style="white-space:nowrap"><button class="btn light sm" data-e="${r.id}">Edit</button> ${cfg.rowExtra ? cfg.rowExtra(r) : ''}<button class="btn light sm" data-d="${r.id}" aria-label="Delete">${icon('x')}</button></td></tr>`)}</tbody></table></div>` : emptyBox('Nothing here yet', cfg.empty || 'Add your first item with the button above.')}`);
    const s = $('#s'); s.oninput = debounce(e => { term = e.target.value.toLowerCase(); draw(); const n = $('#s'); n.focus(); n.setSelectionRange(n.value.length, n.value.length); }, 200);
  };
  const load = async () => { rows = await A(cfg.api); draw(); }; cfg.reload = load;
  const open = r => formDialog((r ? 'Edit ' : 'Add ') + cfg.singular, cfg.fields, r || (cfg.defaults ? { ...cfg.defaults } : null), deps, async (data, m) => {
    const res = await A(cfg.api + (r ? '/' + r.id : ''), { method: r ? 'PUT' : 'POST', body: data }); m.close(); toast('Saved.', 'ok'); await load(); if (cfg.afterSave) cfg.afterSave(res, !r, open, load);
  }, { extra: cfg.extraForm ? cfg.extraForm(r, deps, load) : '', wide: cfg.wide, after: (m, form) => cfg.afterOpen && cfg.afterOpen(m, form, r) });
  v.onclick = async e => {
    const ed = e.target.closest('[data-e]'), de = e.target.closest('[data-d]'), x = e.target.closest('[data-x]');
    if (e.target.closest('#add')) open(null);
    else if (ed) open(rows.find(r => r.id == ed.dataset.e));
    else if (x) cfg.onExtra(x.dataset.x, rows.find(r => r.id == x.dataset.id), load);
    else if (de && await confirmBox('Delete this item?', 'This can’t be undone. If it’s linked to bookings, disable it instead.', 'Delete', true)) { try { await A(cfg.api + '/' + de.dataset.d, { method: 'DELETE' }); toast('Deleted.'); await load(); } catch (er) { adminAlert(er); } }
  };
  await load();
}
const yn = v => v ? pill('paid', 'Yes') : pill('cancelled', 'No');
const catOpts = async () => (await A('categories')).map(c => [c.id, c.name]);

/* ---------- services & categories ---------- */
const SV_TABS = [['/admin/services', 'Services'], ['/admin/service-categories', 'Categories']];
route('/admin/services', () => crudPage({ title: 'Services', singular: 'service', addLabel: 'Add service', api: 'services', tabs: SV_TABS, wide: true,
  deps: { cats: catOpts, staff: async () => (await A('staff')).map(s => [s.id, s.name]) },
  intro: 'Every service is stored in the database. Set a price and duration for each, and assign the stylists who perform it — a service with no stylist can’t be booked online.',
  cols: [{ label: 'Service', get: r => html`<b>${r.name}</b><div class="small muted">${r.category_name}</div>` }, { label: 'Price', get: r => r.price == null ? html`<span class="muted">Not set</span>` : aed(r.price), num: 1 }, { label: 'Duration', get: r => r.duration_min + ' min', num: 1 }, { label: 'Stylists', get: (r, d) => r.staff_ids.length ? r.staff_ids.map(i => (d.staff.find(s => s[0] === i) || [])[1]).join(', ') : html`<span class="small" style="color:var(--bad)">None assigned</span>` }, { label: 'Active', get: r => yn(r.active) }],
  fields: [{ k: 'name', label: 'Service name', req: 1, max: 120 }, { k: 'category_id', label: 'Category', type: 'select', req: 1, opts: d => d.cats }, { k: 'description', label: 'Description', type: 'textarea' }, { k: 'price', label: 'Price (AED)', type: 'number', step: '0.01', min: 0, help: 'leave empty = "Price on request"' }, { k: 'duration_min', label: 'Duration (minutes)', type: 'number', req: 1, min: 5, def: S('default_duration') },
  { k: 'image', label: 'Service image', type: 'image' }, { k: 'staff_ids', label: 'Available stylists', type: 'multi', opts: d => d.staff }, { k: 'avail_days', label: 'Available on', type: 'days' }, { k: 'active', label: 'Enabled (visible & bookable)', type: 'check', def: true }], defaults: { active: 1, duration_min: S('default_duration') } }));
route('/admin/service-categories', () => crudPage({ title: 'Service categories', singular: 'category', addLabel: 'Add category', api: 'categories', tabs: SV_TABS,
  cols: [{ label: 'Category', get: r => html`<div style="display:flex;gap:10px;align-items:center">${r.image ? html`<div class="pv" style="width:40px;height:40px;border-radius:8px;overflow:hidden;background:var(--blush);flex:none"><img src="${img(r.image)}" alt="" style="width:100%;height:100%;object-fit:cover"></div>` : ''}<b>${r.name}</b></div>` }, { label: 'Order', get: r => r.sort, num: 1 }, { label: 'Active', get: r => yn(r.active) }],
  fields: [{ k: 'name', label: 'Name', req: 1 }, { k: 'description', label: 'Description', type: 'textarea', max: 300 }, { k: 'image', label: 'Category image', type: 'image' }, { k: 'sort', label: 'Display order', type: 'number', min: 0, def: 0 }, { k: 'active', label: 'Active', type: 'check', def: true }], defaults: { active: 1 } }), { admin: true, adminOnly: true });

/* ---------- staff ---------- */
route('/admin/staff', () => crudPage({ title: 'Staff', singular: 'staff member', addLabel: 'Add staff', api: 'staff', wide: true,
  deps: { svcs: async () => (await A('services')).map(s => [s.id, s.name]) },
  cols: [{ label: 'Name', get: r => html`<div style="display:flex;gap:10px;align-items:center"><div class="pv" style="width:40px;height:40px;border-radius:50%;overflow:hidden;background:var(--blush)">${r.image ? html`<img src="${img(r.image)}" alt="" style="width:100%;height:100%;object-fit:cover">` : ''}</div><div><b>${r.name}</b><div class="small muted">${r.specialty}</div></div></div>` }, { label: 'Services', get: r => r.service_ids.length }, { label: 'Login', get: r => r.login ? html`${r.login.email} ${r.login.can_chat ? pill('confirmed', 'chat') : ''}` : html`<span class="muted small">No login</span>` }, { label: 'Active', get: r => yn(r.active) }],
  fields: [{ k: 'name', label: 'Name', req: 1 }, { k: 'specialty', label: 'Specialty', max: 160 }, { k: 'bio', label: 'Short bio', type: 'textarea', max: 800 }, { k: 'image', label: 'Profile image', type: 'image' }, { k: 'service_ids', label: 'Assigned services', type: 'multi', opts: d => d.svcs },
  { k: 'hours', label: 'Working hours', type: 'hours', help: 'default = salon hours; customised hours must sit inside them' }, { k: 'active', label: 'Active (appears on site and can be booked)', type: 'check', def: true }],
  defaults: { active: 1, hours: WD.map((_, i) => ({ weekday: i, custom: false })) }, rowExtra: r => html`<button class="btn light sm" data-x="login" data-id="${r.id}">Login</button> `,
  onExtra: (act, r, reload) => {
    const m = modal('Login for ' + r.name, html`<p class="small muted">Staff can see only their own appointments${''}. Set a password of at least 8 characters${r.login ? ' (leave empty to keep the current one)' : ''}.</p><form id="lf"><div id="err"></div><label class="fld"><span>Email</span><input name="email" type="email" value="${r.login?.email || ''}" required></label><label class="fld"><span>Password</span><input name="password" type="password" autocomplete="new-password"></label><label class="check"><input type="checkbox" name="can_chat" ${r.login?.can_chat ? 'checked' : ''}> Can reply to customer chats</label><div style="display:flex;gap:10px;justify-content:space-between"><span>${r.login ? html`<button type="button" class="btn danger sm" id="rm">Remove login</button>` : ''}</span><button class="btn gold">Save login</button></div></form>`);
    $('#lf', m.el).onsubmit = async e => { e.preventDefault(); const f = new FormData(e.target); const b = $('button.btn.gold', e.target); b.disabled = true; b.classList.add('busy'); try { await A(`staff/${r.id}/login`, { method: 'POST', body: { email: f.get('email'), password: f.get('password'), can_chat: !!f.get('can_chat') } }); m.close(); toast('Login saved.', 'ok'); reload(); } catch (er) { b.disabled = false; b.classList.remove('busy'); put($('#err', m.el), html`<div class="form-error">${er.message}</div>`); } };
    $('#rm', m.el) && ($('#rm', m.el).onclick = async () => { await A(`staff/${r.id}/login`, { method: 'DELETE' }); m.close(); reload(); });
  } }), { admin: true, adminOnly: true });

/* ---------- products ---------- */
const PR_TABS = [['/admin/products', 'Products'], ['/admin/product-categories', 'Categories']];
route('/admin/products', () => crudPage({ title: 'Products', singular: 'product', addLabel: 'Add product', api: 'products', tabs: PR_TABS, wide: true, deps: { cats: async () => (await A('product-categories')).map(c => [c.id, c.name]) },
  cols: [{ label: 'Product', get: r => html`<div style="display:flex;gap:10px;align-items:center"><div style="width:44px;height:44px;border-radius:12px;overflow:hidden;background:var(--blush)">${r.images[0] ? html`<img src="${img(r.images[0].filename)}" alt="" style="width:100%;height:100%;object-fit:cover">` : ''}</div><div><b>${r.name}</b><div class="small muted">${r.category_name || 'Uncategorised'} · ${r.images.length} photo${r.images.length === 1 ? '' : 's'}</div></div></div>` }, { label: 'Price', get: r => aed(r.price), num: 1 }, { label: 'Stock', get: r => r.stock, num: 1 }, { label: 'Active', get: r => yn(r.active) }],
  fields: [{ k: 'name', label: 'Product name', req: 1, max: 140 }, { k: 'category_id', label: 'Category', type: 'select', opts: d => d.cats, ph: 'Uncategorised' }, { k: 'price', label: 'Price (AED)', type: 'number', step: '0.01', min: 0, req: 1 }, { k: 'stock', label: 'Stock quantity', type: 'number', min: 0, def: 0 }, { k: 'description', label: 'Description', type: 'textarea' }, { k: 'active', label: 'Enabled (visible to customers)', type: 'check', def: true }],
  defaults: { active: 1, stock: 0 },
  extraForm: (r, d, reload) => r ? html`<div class="fld"><span>Product photos <small>— add as many as you like (front, back, side, packaging, close-up…)</small></span><div class="pimgs" id="pimgs">${r.images.map(i => html`<div class="it"><img src="${img(i.filename)}" alt=""><button type="button" data-delimg="${i.id}" aria-label="Remove photo">×</button></div>`)}</div><input type="file" id="pup" accept="image/jpeg,image/png,image/webp,image/gif" multiple></div>` : html`<div class="notice">Save the product first, then you can upload its photos.</div>`,
  afterOpen: (m, form, r) => {
    const up = $('#pup', form); if (!up) return; form.dataset.pid = r.id;
    up.onchange = async () => { const fd = new FormData(); [...up.files].forEach(f => fd.append('f', f)); try { const r = await A(`products/${form.dataset.pid}/images`, { method: 'POST', form: fd }); drawImgs(r.images); toast('Photos added.', 'ok'); } catch (e) { adminAlert(e); } up.value = ''; };
    const drawImgs = list => put($('#pimgs', form), list.map(i => html`<div class="it"><img src="${img(i.filename)}" alt=""><button type="button" data-delimg="${i.id}" aria-label="Remove photo">×</button></div>`));
    form.onclick = async e => { const b = e.target.closest('[data-delimg]'); if (b) { await A('product-images/' + b.dataset.delimg, { method: 'DELETE' }); b.closest('.it').remove(); } };
  },
  afterSave: (res, created, open) => { if (created) { toast('Now add photos to your new product.'); open(res); } } }));
route('/admin/product-categories', () => crudPage({ title: 'Product categories', singular: 'category', addLabel: 'Add category', api: 'product-categories', tabs: PR_TABS, cols: [{ label: 'Category', get: r => html`<b>${r.name}</b>` }, { label: 'Order', get: r => r.sort, num: 1 }], fields: [{ k: 'name', label: 'Name', req: 1 }, { k: 'sort', label: 'Display order', type: 'number', min: 0, def: 0 }] }), { admin: true, adminOnly: true });

/* ---------- promotions ---------- */
route('/admin/promotions', () => crudPage({ title: 'Promotions', singular: 'promotion', addLabel: 'Create promotion', api: 'promotions', wide: true, deps: { svcs: async () => (await A('services')).map(s => [s.id, s.name]) },
  intro: 'Creating an active promotion notifies all registered customers. Leave “Applies to” empty to apply to every service; tick “requires all” for package deals (e.g. Hair + Nail).',
  cols: [{ label: 'Promotion', get: r => html`<b>${r.title}</b><div class="small muted">${r.description.slice(0, 70)}</div>` }, { label: 'Discount', get: r => r.discount_type === 'percent' ? r.discount_value + '%' : aed(r.discount_value), num: 1 }, { label: 'Dates', get: r => (r.start_date || 'Any') + ' → ' + (r.end_date || 'Open') }, { label: 'Active', get: r => yn(r.active) }],
  fields: [{ k: 'title', label: 'Title', req: 1, max: 120 }, { k: 'description', label: 'Description', type: 'textarea' }, { k: 'image', label: 'Promotion image', type: 'image' }, { k: 'discount_type', label: 'Discount type', type: 'select', req: 1, opts: () => [['percent', 'Percentage (%)'], ['fixed', 'Fixed amount (AED)']], def: 'percent' }, { k: 'discount_value', label: 'Discount value', type: 'number', step: '0.01', min: 0, req: 1 },
  { k: 'service_ids', label: 'Applies to services', type: 'multi', opts: d => d.svcs }, { k: 'requires_all', label: 'Package: customer must book ALL selected services', type: 'check' }, { k: 'start_date', label: 'Start date', type: 'date' }, { k: 'end_date', label: 'End date', type: 'date' }, { k: 'active', label: 'Enabled', type: 'check', def: true }], defaults: { active: 1, discount_type: 'percent' } }), { admin: true, adminOnly: true });

/* ---------- customers ---------- */
route('/admin/customers', async () => {
  setTitle('Customers'); const v = view(); let term = '';
  const load = async () => {
    const rows = await A('customers' + qs({ q: term })); put($('#tb'), rows.length ? html`<div class="tblwrap"><table class="tbl"><thead><tr><th>Customer</th><th>Contact</th><th>Bookings</th><th>Completed</th><th>Last visit</th><th>Spent</th><th></th></tr></thead><tbody>${rows.map(r => html`<tr class="${r.registered ? 'click' : ''}" data-id="${r.id || ''}"><td data-l="Customer"><b>${r.name}</b> ${r.registered ? '' : pill('cancelled', 'Guest')} ${r.active ? '' : pill('no_show', 'Blocked')}</td><td data-l="Contact">${r.phone}<div class="small muted">${r.email || ''}</div></td><td data-l="Bookings">${r.appointments}</td><td data-l="Completed">${r.completed}</td><td data-l="Last visit">${r.last_visit ? dshort(r.last_visit) : '–'}</td><td data-l="Spent" class="num">${r.registered ? aed(r.spent) : '–'}</td><td>${r.registered ? 'View' : ''}</td></tr>`)}</tbody></table></div>` : emptyBox('No customers yet', 'Customers appear here when they register or book.'));
  };
  put(v, html`<div class="toolbar"><label class="fld grow"><span>Search by name, email or phone</span><input id="s" type="search"></label></div><div id="tb"></div>`);
  $('#s').oninput = debounce(e => { term = e.target.value; load(); }); await load();
  $('#tb').onclick = async e => {
    const tr = e.target.closest('tr[data-id]'); if (!tr || !tr.dataset.id) return; const d = await A('customers/' + tr.dataset.id);
    const m = modal(d.customer.name, html`<p>${d.customer.email} · ${d.customer.phone}<br><span class="small muted">Joined ${dtshort(d.customer.created)}</span></p><label class="check"><input type="checkbox" id="act" ${d.customer.active ? 'checked' : ''}> Account active (untick to block sign-in)</label><h4>Appointments (${d.appointments.length})</h4>${d.appointments.map(a => html`<div class="apt"><time>${dshort(a.date)}</time><div class="grow">${a.items.map(i => i.service_name).join(', ')}<div class="small muted">${a.ref}</div></div>${pill(a.status)}</div>`)}<h4>Reviews (${d.reviews.length})</h4>${d.reviews.map(r => html`<p>${stars(r.rating)} ${r.body}</p>`)}`, { wide: true });
    $('#act', m.el).onchange = async ev => { await A('customers/' + d.customer.id, { method: 'PUT', body: { active: ev.target.checked } }); toast('Updated.', 'ok'); load(); };
  };
}, { admin: true, adminOnly: true });

/* ---------- appointments ---------- */
route('/admin/appointments', async (_, q, t) => {
  const adm = App.user.role === 'admin'; setTitle(adm ? 'Appointments' : 'My appointments'); const v = view();
  const [staff, svcs] = adm ? await Promise.all([A('staff'), A('services')]) : [[], []]; const f = { date_from: q.date_from || todayIso(), date_to: '', status: '', staff_id: '', service_id: '', q: '' };
  put(v, html`<div class="toolbar"><label class="fld"><span>From</span><input type="date" id="f1" value="${f.date_from}"></label><label class="fld"><span>To</span><input type="date" id="f2"></label><label class="fld"><span>Status</span><select id="f3">${sel(Object.entries(STATUS), '', 'All statuses')}</select></label>
    ${adm ? html`<label class="fld"><span>Staff</span><select id="f4">${sel(staff.map(s => [s.id, s.name]), '', 'All staff')}</select></label><label class="fld"><span>Service</span><select id="f5">${sel(svcs.map(s => [s.id, s.name]), '', 'All services')}</select></label>` : ''}
    <label class="fld grow"><span>Search</span><input id="f6" type="search" placeholder="Name, phone or reference"></label>${adm ? html`<button class="btn gold" id="new">${icon('plus')} New booking</button>` : ''}<button class="btn ghost" id="clr">Clear</button></div><div id="tb"></div>`);
  const load = async () => {
    const rows = await A('appointments' + qs(f)); if (stale(t)) return;
    put($('#tb'), rows.length ? html`<div class="tblwrap"><table class="tbl"><thead><tr><th>When</th><th>Customer</th><th>Services</th><th>Status</th>${adm ? html`<th>Payment</th>` : ''}</tr></thead><tbody>${rows.map(a => html`<tr class="click" data-id="${a.id}"><td data-l="When"><b>${dshort(a.date)}</b><div class="small muted">${t12(a.start_time)} – ${t12(a.end_time)}</div></td><td data-l="Customer">${a.customer_name}<div class="small muted">${a.customer_phone} · ${a.ref}</div></td><td data-l="Services">${a.items.map(i => html`<div>${i.service_name} <span class="small muted">· ${i.staff_name || '–'}</span></div>`)}</td><td data-l="Status">${pill(a.status)}</td>${adm ? html`<td data-l="Payment">${a.payment ? pill(a.payment.status) : html`<span class="muted small">–</span>`}</td>` : ''}</tr>`)}</tbody></table></div>` : emptyBox('No appointments found', 'Try widening the date range or clearing filters.'));
    $('#tb').onclick = e => { const tr = e.target.closest('tr[data-id]'); if (tr) apptDialog(rows.find(a => a.id == tr.dataset.id), load); };
  };
  const bind = (id, k) => { const el = $(id); el && (el.onchange = el.oninput = debounce(e => { f[k] = e.target.value; load(); }, 250)); };
  bind('#f1', 'date_from'); bind('#f2', 'date_to'); bind('#f3', 'status'); bind('#f4', 'staff_id'); bind('#f5', 'service_id'); bind('#f6', 'q');
  $('#clr').onclick = () => { Object.assign(f, { date_from: '', date_to: '', status: '', staff_id: '', service_id: '', q: '' }); ['#f1', '#f2', '#f3', '#f4', '#f5', '#f6'].forEach(i => $(i) && ($(i).value = '')); load(); };
  $('#new') && ($('#new').onclick = () => { const m = modal('New booking', html`<div id="nb"></div>`, { wide: true }); const box = document.createElement('div'); $('#nb', m.el).appendChild(box); bookingWizard(box, { admin: true, onDone: load }); });
  await load();
});
function apptDialog(a, reload) {
  const adm = App.user.role === 'admin'; const p = a.payment;
  const m = modal('Appointment ' + a.ref, html`<div style="display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap"><div><b style="font-size:1.2rem">${a.customer_name}</b><div><a href="${telHref(a.customer_phone)}">${a.customer_phone}</a>${a.customer_email ? ' · ' + a.customer_email : ''}</div></div>${pill(a.status)}</div>
    <p><b>${dshort(a.date)}</b> · ${t12(a.start_time)} – ${t12(a.end_time)} <span class="small muted">· ${a.source === 'admin' ? 'created by salon' : 'online booking'}</span></p>
    <div class="tblwrap"><table class="tbl"><tbody>${a.items.map(i => html`<tr><td>${i.service_name}<div class="small muted">${t12(i.start_time)} – ${t12(i.end_time)} · ${i.staff_name || 'Unassigned'}</div></td>${adm ? html`<td class="num">${i.price == null ? html`<span class="muted small">price not set</span>` : aed(i.price)}</td>` : ''}</tr>`)}</tbody></table></div>
    ${a.promo_title ? html`<p class="small">Promotion: <b>${a.promo_title}</b></p>` : ''}${a.customer_notes ? html`<div class="notice"><b>Customer note:</b> ${a.customer_notes}</div>` : ''}
    ${p ? html`<div class="panel" style="margin-top:14px"><h4>Payment ${pill(p.status)}</h4><dl class="kv"><dt>Original</dt><dd>${aed(p.gross)}</dd><dt>Discount</dt><dd>${aed(p.discount)}</dd><dt>Amount ${p.status === 'paid' ? 'paid' : 'due'}</dt><dd><b>${aed(p.net)}</b></dd>${p.refunded_amount ? html`<dt>Refunded</dt><dd>${aed(p.refunded_amount)}</dd>` : ''}<dt>Method</dt><dd>${p.method || '–'}</dd><dt>Paid at</dt><dd>${p.paid_at ? dtshort(p.paid_at) : '–'}</dd></dl>
      ${adm ? html`<div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:10px">${p.status === 'pending' ? html`<button class="btn sm gold" data-pay>Mark as paid</button>` : ''}${p.status === 'paid' ? html`<button class="btn sm light" data-refund>Refund</button>` : ''}${['pending', 'paid'].includes(p.status) ? html`<button class="btn sm light" data-void>Void</button>` : ''}</div>` : ''}</div>` : ''}
    <label class="fld" style="margin-top:14px"><span>Internal notes</span><textarea id="an" maxlength="1000">${a.admin_notes}</textarea></label><button class="btn light sm" id="sn">Save notes</button>
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:18px;border-top:1px solid var(--line);padding-top:16px">
    ${!['completed', 'cancelled', 'no_show'].includes(a.status) ? html`${adm && a.status === 'pending' ? html`<button class="btn sm" data-st="confirmed">Confirm</button>` : ''}${a.status !== 'in_progress' ? html`<button class="btn sm light" data-st="in_progress">Start (in progress)</button>` : ''}${adm ? html`<button class="btn sm gold" data-complete>Complete & record payment</button>${['pending', 'confirmed'].includes(a.status) ? html`<button class="btn sm light" data-resched>Reschedule</button>` : ''}<button class="btn sm light" data-st="no_show">No-show</button>${['pending', 'confirmed'].includes(a.status) ? html`<button class="btn sm danger" data-cancel>Cancel</button>` : ''}` : ''}` : ''}</div>`, { wide: true });
  const st = async (status, extra = {}) => { try { await A('appointments/' + a.id, { method: 'PUT', body: { status, ...extra } }); m.close(); toast('Updated.', 'ok'); reload(); } catch (e) { adminAlert(e); } };
  $('#sn', m.el).onclick = async () => { const b = $('#sn', m.el); b.disabled = true; b.classList.add('busy'); try { await A('appointments/' + a.id, { method: 'PUT', body: { admin_notes: $('#an', m.el).value } }); b.disabled = false; b.classList.remove('busy'); toast('Notes saved.', 'ok'); reload(); } catch (e) { b.disabled = false; b.classList.remove('busy'); adminAlert(e); } };
  m.el.onclick = async e => {
    const b = e.target.closest('button'); if (!b) return;
    if (b.dataset.st) { if (b.dataset.st === 'no_show' && !await confirmBox('Mark as no-show?', 'No-shows are excluded from income.', 'Mark no-show', true)) return; st(b.dataset.st); }
    else if ('cancel' in b.dataset) { const r = prompt('Reason for cancelling (optional, sent to the customer):'); if (r !== null) st('cancelled', { reason: r }); }
    else if ('resched' in b.dataset) { m.close(); rescheduleDialog(a, { admin: true, onDone: reload }); }
    else if ('complete' in b.dataset) { m.close(); completeDialog(a, reload); }
    else if ('pay' in b.dataset) { m.close(); payDialog(p, reload); }
    else if ('refund' in b.dataset) { m.close(); refundDialog(p, reload); }
    else if ('void' in b.dataset) { const r = prompt('Reason for voiding this transaction:'); if (r) { try { await A(`payments/${p.id}/void`, { method: 'POST', body: { reason: r } }); m.close(); toast('Transaction voided — income adjusted.'); reload(); } catch (er) { adminAlert(er); } } }
  };
}
const methodSelect = () => html`<label class="fld"><span>Payment method *</span><select name="method" required>${sel((S('payment_methods_record') || []).map(x => [x, x]), '', 'Choose…')}</select></label>`;
async function completeDialog(a, reload) {
  const promos = (await A('promotions')).filter(x => x.active); let pid = a.promo_id || '';
  const m = modal('Complete & record payment', html`<p class="muted small">Enter what the customer was charged for each service. Discounts are calculated automatically from the promotion. Only transactions that are <b>paid</b> and <b>completed</b> count as income.</p><form id="cf"><div id="err"></div>
    ${a.items.map(i => html`<label class="fld"><span>${i.service_name} (AED)</span><input type="number" step="0.01" min="0" data-item="${i.id}" data-svc="${i.service_id}" value="${i.price ?? ''}" required></label>`)}
    <label class="fld"><span>Promotion</span><select id="pr">${sel(promos.map(x => [x.id, x.title + ' (' + (x.discount_type === 'percent' ? x.discount_value + '%' : aed(x.discount_value)) + ')']), pid, 'No promotion')}</select></label>
    <div class="summary" id="tot"></div><label class="check" style="margin-top:14px"><input type="checkbox" id="paid" checked> Customer has paid</label><div id="mth">${methodSelect()}</div><button class="btn gold block">Complete appointment</button></form>`);
  const calc = () => {
    const rows = $$('[data-item]', m.el).map(i => ({ svc: +i.dataset.svc, price: +i.value || 0 })), p = promos.find(x => String(x.id) === $('#pr', m.el).value); let d = 0;
    if (p) { const ids = p.service_ids; const ok = !ids.length || (p.requires_all ? ids.every(i => rows.some(r => r.svc === i)) : true); const base = ok ? rows.filter(r => !ids.length || ids.includes(r.svc)).reduce((x, r) => x + r.price, 0) : 0; d = Math.min(base, p.discount_type === 'percent' ? base * p.discount_value / 100 : p.discount_value); }
    const g = rows.reduce((x, r) => x + r.price, 0); put($('#tot', m.el), html`<div class="ln"><span>Original price</span><b>${aed(g)}</b></div><div class="ln"><span>Discount</span><b>− ${aed(d)}</b></div><div class="ln"><span>Final amount</span><b>${aed(g - d)}</b></div>`);
  };
  calc(); m.el.oninput = calc; $('#paid', m.el).onchange = e => $('#mth', m.el).classList.toggle('hidden', !e.target.checked);
  $('#cf', m.el).onsubmit = async e => {
    e.preventDefault(); const paid = $('#paid', m.el).checked; const b = $('button.btn.gold', e.target); b.disabled = true; b.classList.add('busy');
    try { await A(`appointments/${a.id}/complete`, { method: 'POST', body: { items: $$('[data-item]', m.el).map(i => ({ id: +i.dataset.item, price: i.value })), promo_id: $('#pr', m.el).value || null, paid, method: paid ? $('[name=method]', m.el).value : '' } }); m.close(); toast(paid ? 'Completed and payment recorded. Revenue updated.' : 'Completed — payment is pending.', 'ok'); reload(); }
    catch (er) { b.disabled = false; b.classList.remove('busy'); put($('#err', m.el), html`<div class="form-error">${er.message}</div>`); }
  };
}
function payDialog(p, reload) {
  const m = modal('Mark payment as paid', html`<p>Amount due: <b>${aed(p.net)}</b></p><form id="pf"><div id="err"></div>${methodSelect()}<button class="btn gold block">Record payment</button></form>`);
  $('#pf', m.el).onsubmit = async e => { e.preventDefault(); const b = $('button.btn', e.target); b.disabled = true; b.classList.add('busy'); try { await A(`payments/${p.id}/pay`, { method: 'POST', body: { method: $('[name=method]', m.el).value } }); m.close(); toast('Payment recorded.', 'ok'); reload(); } catch (er) { b.disabled = false; b.classList.remove('busy'); put($('#err', m.el), html`<div class="form-error">${er.message}</div>`); } };
}
function refundDialog(p, reload) {
  const left = +(p.net - p.refunded_amount).toFixed(2);
  const m = modal('Refund', html`<p>Refundable: <b>${aed(left)}</b>. Income is reduced by the refunded amount.</p><form id="rf"><div id="err"></div><label class="fld"><span>Refund amount (AED)</span><input name="amount" type="number" step="0.01" min="0.01" max="${left}" value="${left}" required></label><label class="fld"><span>Reason *</span><input name="reason" required maxlength="200"></label><button class="btn danger block">Refund</button></form>`);
  $('#rf', m.el).onsubmit = async e => { e.preventDefault(); const f = Object.fromEntries(new FormData(e.target)); const b = $('button.btn', e.target); b.disabled = true; b.classList.add('busy'); try { await A(`payments/${p.id}/refund`, { method: 'POST', body: f }); m.close(); toast('Refund recorded — income adjusted.'); reload(); } catch (er) { b.disabled = false; b.classList.remove('busy'); put($('#err', m.el), html`<div class="form-error">${er.message}</div>`); } };
}

/* ---------- reviews & testimonials ---------- */
async function reviewsPage(onlyFeatured) {
  setTitle(onlyFeatured ? 'Testimonials' : 'Reviews'); const v = view(); const [svcs] = await Promise.all([A('services')]);
  const f = { rating: '', service_id: '', staff_id: '', featured: onlyFeatured ? '1' : '', visible: '' };
  put(v, html`<div class="notice">${onlyFeatured ? 'Featured reviews appear on the home page. Add a testimonial you collected in person with the button below.' : 'The average rating combines the initial baseline (set in Settings) with every visible review below, so hiding or deleting a review updates it automatically.'}</div>
    <div class="toolbar"><label class="fld"><span>Rating</span><select id="a1">${sel([5, 4, 3, 2, 1].map(n => [n, n + ' stars']), '', 'All')}</select></label><label class="fld"><span>Service</span><select id="a2">${sel(svcs.map(s => [s.id, s.name]), '', 'All')}</select></label><label class="fld"><span>Staff</span><select id="a3">${sel(App.staff.map(s => [s.id, s.name]), '', 'All')}</select></label>
    ${onlyFeatured ? '' : html`<label class="fld"><span>Featured</span><select id="a4">${sel([[1, 'Featured'], [0, 'Not featured']], '', 'All')}</select></label>`}<button class="btn gold" id="addt">${icon('plus')} Add testimonial</button></div><div id="tb" class="grid"></div>`);
  const load = async () => {
    const rows = await A('reviews' + qs(f)); put($('#tb'), rows.length ? rows.map(r => html`<div class="card review" style="${r.visible ? '' : 'opacity:.6'}"><div class="who"><b>${r.author_name} ${r.source === 'admin' ? pill('cancelled', 'added by salon') : ''}${r.verified ? pill('paid', 'verified') : ''}</b><span class="small muted">${dshort(r.created.slice(0, 10))}</span></div>${stars(r.rating)}<p>${r.body}</p><div class="small muted">${[r.service_name, r.staff_name].filter(Boolean).join(' · ')}</div>${r.image ? html`<img class="rimg" src="${img(r.image)}" alt="" loading="lazy">` : ''}
      <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:12px"><button class="btn sm ${r.featured ? 'gold' : 'light'}" data-ft="${r.id}" data-v="${r.featured ? 0 : 1}">${r.featured ? '★ Featured' : 'Feature'}</button><button class="btn sm light" data-vs="${r.id}" data-v="${r.visible ? 0 : 1}">${r.visible ? 'Hide' : 'Show'}</button><button class="btn sm light" data-del="${r.id}">Delete</button></div></div>`) : emptyBox('No reviews yet', 'Customer reviews will appear here.'));
  };
  [['#a1', 'rating'], ['#a2', 'service_id'], ['#a3', 'staff_id'], ['#a4', 'featured']].forEach(([i, k]) => $(i) && ($(i).onchange = e => { f[k] = e.target.value; load(); }));
  v.onclick = async e => {
    const b = e.target.closest('button'); if (!b) return;
    try {
      if (b.dataset.ft) await A('reviews/' + b.dataset.ft, { method: 'PUT', body: { featured: +b.dataset.v } });
      else if (b.dataset.vs) await A('reviews/' + b.dataset.vs, { method: 'PUT', body: { visible: +b.dataset.v } });
      else if (b.dataset.del) { if (!await confirmBox('Delete review?', 'The rating average will be recalculated.', 'Delete', true)) return; await A('reviews/' + b.dataset.del, { method: 'DELETE' }); }
      else if (b.id === 'addt') return formDialog('Add testimonial', [{ k: 'author_name', label: 'Customer name', req: 1 }, { k: 'rating', label: 'Rating (1–5)', type: 'number', req: 1, min: 1, def: 5 }, { k: 'body', label: 'Testimonial', type: 'textarea', max: 1000 }, { k: 'image', label: 'Photo (optional)', type: 'image' }, { k: 'featured', label: 'Feature on home page', type: 'check', def: true }], null, {}, async (d, m) => { await A('testimonials', { method: 'POST', body: d }); m.close(); load(); });
      else return; const p = await api('/api/public'); Object.assign(App, { rating: p.rating, testimonials: p.testimonials }); load();
    } catch (er) { adminAlert(er); }
  };
  load();
}
route('/admin/reviews', () => reviewsPage(false), { admin: true, adminOnly: true });
route('/admin/testimonials', () => reviewsPage(true), { admin: true, adminOnly: true });

/* ---------- messages ---------- */
async function messagesPage(id) {
  setTitle('Messages'); const v = view(); let term = '', arch = false;
  put(v, html`<div class="split ${id ? 'thread' : ''}"><div><div class="toolbar"><label class="fld grow"><span>Search customers</span><input id="s" type="search"></label><label class="check" style="margin:0 0 8px"><input type="checkbox" id="arch"> Archived</label></div><div class="convlist" id="cl"></div></div><div class="threadpane" id="tp"></div></div>`);
  const list = async () => {
    const c = await A('conversations' + qs({ q: term, archived: arch ? 1 : '' })); put($('#cl'), c.length ? c.map(x => html`<a class="conv ${x.id == id ? 'on' : ''}" href="#/admin/messages/${x.id}"><b><span>${x.name}</span>${x.admin_unread ? html`<span class="dot">${x.admin_unread}</span>` : ''}</b><p>${x.last_body}</p><p class="small">${dtshort(x.last_message_at)}</p></a>`) : emptyBox('No conversations', arch ? 'Nothing archived.' : 'Customer messages will appear here.'));
    const n = c.reduce((a, x) => a + x.admin_unread, 0); $$('[data-badge="adminchat"]').forEach(b => { b.textContent = n; b.classList.toggle('hidden', !n); });
  };
  $('#s').oninput = debounce(e => { term = e.target.value; list(); }); $('#arch').onchange = e => { arch = e.target.checked; list(); }; await list(); every(list, 8000);
  if (!id) return put($('#tp'), emptyBox('Select a conversation', 'Choose a customer on the left to read and reply.'));
  let last = 0; const d = await A('conversations/' + id);
  put($('#tp'), html`<div class="chatbox"><div class="head" style="display:flex;justify-content:space-between;gap:10px;align-items:center"><div><a href="#/admin/messages" class="small muted">← Inbox</a><br><b>${d.conversation.name}</b><div class="small muted">${d.conversation.phone || ''} ${d.conversation.email || ''}</div></div><div style="display:flex;gap:6px"><button class="btn light sm" id="ar">${d.conversation.archived ? 'Unarchive' : 'Archive'}</button></div></div><div class="msgs" id="msgs"></div><form class="composer" id="rf"><input id="in" placeholder="Reply as ${S('business_name')}…" maxlength="1000" autocomplete="off"><button class="btn gold" aria-label="Send">${icon('send')}</button></form></div>`);
  const box = $('#msgs'); const add = ms => { ms.forEach(m => { box.insertAdjacentHTML('beforeend', bubble(m, m.sender === 'salon' ? 'me' : 'them').s); last = m.id; }); if (ms.length) box.scrollTop = box.scrollHeight; };
  add(d.messages); every(async () => { try { const r = await A(`conversations/${id}?after=${last}`); add(r.messages); } catch (e) { } }, 5000);
  $('#rf').onsubmit = async e => { e.preventDefault(); const i = $('#in'), body = i.value.trim(); if (!body) return; i.value = ''; try { await A(`conversations/${id}/reply`, { method: 'POST', body: { body } }); add((await A(`conversations/${id}?after=${last}`)).messages); list(); } catch (er) { i.value = body; adminAlert(er); } };
  $('#ar').onclick = async () => { await A(`conversations/${id}/archive`, { method: 'POST', body: { archived: !d.conversation.archived } }); go('/admin/messages'); };
}
route('/admin/messages', () => messagesPage(null), { admin: true });
route('/admin/messages/:id', ({ id }) => messagesPage(id), { admin: true });
route('/admin/notifications', async () => { setTitle('Notifications'); await renderNotifications(view()); }, { admin: true });
