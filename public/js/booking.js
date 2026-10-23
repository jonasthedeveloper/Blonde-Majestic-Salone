'use strict';
/* Booking wizard — used by customers (#/book) and by the admin "New booking" dialog. */
async function bookingWizard(root, opt = {}) {
  const admin = !!opt.admin;
  const services = await api('/api/services');
  const W = { sel: new Map(), date: '', time: '', staffPicks: [], promo_id: '', d: { name: App.user && App.user.role === 'customer' ? App.user.name : '', phone: App.user?.role === 'customer' ? (App.user.phone || '') : '', email: App.user?.role === 'customer' ? (App.user.email || '') : '', notes: '', confirmed: true }, step: 1, slots: null, busy: false };
  const preset = opt.preset || {};
  if (preset.service) { const s = services.find(x => x.id == preset.service); if (s && s.staff.length) W.sel.set(s.id, preset.staff && s.staff.some(t => t.id == preset.staff) ? +preset.staff : ''); }
  if (preset.staff) services.forEach(s => { if (W.sel.has(s.id) && s.staff.some(t => t.id == preset.staff)) W.sel.set(s.id, +preset.staff); });
  if (preset.promo) W.promo_id = String(preset.promo);
  const chosen = () => services.filter(s => W.sel.has(s.id));
  const items = () => chosen().map(s => ({ service_id: s.id, staff_id: W.sel.get(s.id) || null }));
  const totalMin = () => chosen().reduce((a, s) => a + (s.duration_min || +S('default_duration') || 60), 0);
  const estimate = () => { const c = chosen(); if (!c.length || c.some(s => s.price == null)) return null; return c.reduce((a, s) => a + s.price, 0); };
  const promosFor = () => (App.promos || []).filter(p => {
    const ids = p.service_ids ? (typeof p.service_ids === 'string' ? JSON.parse(p.service_ids) : p.service_ids) : []; const sel = chosen().map(s => s.id);
    if (W.date && ((p.start_date && W.date < p.start_date) || (p.end_date && W.date > p.end_date))) return false;
    return !ids.length || (p.requires_all ? ids.every(i => sel.includes(i)) : ids.some(i => sel.includes(i)));
  });
  const discount = () => {
    const p = promosFor().find(x => String(x.id) === W.promo_id); const est = estimate(); if (!p || est == null) return 0;
    const ids = typeof p.service_ids === 'string' ? JSON.parse(p.service_ids || '[]') : (p.service_ids || []);
    const base = chosen().filter(s => !ids.length || ids.includes(s.id)).reduce((a, s) => a + s.price, 0);
    return Math.min(base, p.discount_type === 'percent' ? base * p.discount_value / 100 : p.discount_value);
  };
  const bar = () => html`<div class="steps" aria-label="Step ${W.step} of 4">${[1, 2, 3, 4].map(i => html`<i class="${i <= W.step ? 'on' : ''}"></i>`)}</div>`;
  const policy = () => admin ? '' : html`<div class="notice"><b>Appointments recommended.</b> ${S('appointment_policy')}</div>`;
  let lastStep = 0;
  const draw = t => { put(root, t); root.classList.remove('step-fwd', 'step-back'); if (W.step !== lastStep) { const fwd = W.step > lastStep; lastStep = W.step; if (!RM()) { void root.offsetWidth; root.classList.add(fwd ? 'step-fwd' : 'step-back'); } } };

  function step1() {
    W.step = 1; const est = estimate(); const cats = App.cats;
    draw(html`${bar()}${policy()}<h2 style="font-size:2rem">Choose your services</h2>
      ${cats.map(c => { const list = services.filter(s => s.category_id === c.id); return list.length ? html`<h4 style="margin:22px 0 10px">${c.name}</h4>${list.map(s => {
        const on = W.sel.has(s.id), no = !s.staff.length; return html`<div class="svcrow ${on ? 'on' : ''} ${no ? 'off' : ''}" data-svc="${s.id}" role="checkbox" aria-checked="${on}" tabindex="0">
          <input type="checkbox" ${on ? 'checked' : ''} ${no ? 'disabled' : ''} tabindex="-1" aria-hidden="true"><div class="grow"><b>${s.name}</b><div class="small muted">${s.duration_min || S('default_duration')} min${no ? ' · Not bookable online yet — please chat with the salon' : ''}</div>
          ${on ? html`<label class="small" style="display:block;margin-top:8px" data-stop>Stylist <select data-staff="${s.id}" style="min-height:38px;padding:4px 10px"><option value="">Any available</option>${s.staff.map(t => html`<option value="${t.id}" ${W.sel.get(s.id) === t.id ? 'selected' : ''}>${t.name}</option>`)}</select></label>` : ''}</div>
          <span class="price">${money(s.price)}</span></div>`; })}` : ''; })}
      <div class="stickybar"><div><b>${W.sel.size} selected</b><div class="small muted">${W.sel.size ? totalMin() + ' min' + (est != null ? ' · ' + money(est) : '') : 'Pick at least one service'}</div></div><button class="btn gold" id="next" ${W.sel.size ? '' : 'disabled'}>Choose date & time</button></div>`);
    $('#next', root).onclick = step2;
  }
  root.addEventListener('click', e => {
    const row = e.target.closest('[data-svc]'); if (!row || e.target.closest('[data-stop]') || W.step !== 1) return;
    const id = +row.dataset.svc, s = services.find(x => x.id === id); if (!s.staff.length) return toast('This service can’t be booked online yet. Please chat with the salon or call us.');
    W.sel.has(id) ? W.sel.delete(id) : W.sel.set(id, ''); const y = scrollY; step1(); scrollTo(0, y);
  });
  root.addEventListener('keydown', e => { if ((e.key === ' ' || e.key === 'Enter') && e.target.matches('[data-svc]')) { e.preventDefault(); e.target.click(); } });
  root.addEventListener('change', e => { if (e.target.matches('[data-staff]')) { W.sel.set(+e.target.dataset.staff, e.target.value ? +e.target.value : ''); W.time = ''; } });

  async function loadSlots() {
    const box = $('#slots', root); if (!box) return; if (!W.date) { put(box, html`<p class="muted">Choose a date to see available times.</p>`); return; }
    put(box, html`<p class="muted">Checking availability…</p>`);
    try {
      const r = await api('/api/availability', { method: 'POST', body: { date: W.date, items: items() } }); W.slots = r;
      if (r.closed) return put(box, html`<div class="empty"><b>Unavailable</b>${r.reason || 'The salon is closed on this day.'}</div>`);
      if (!r.slots.length) return put(box, html`<div class="empty"><b>Fully booked</b>No times left for this combination on this day. Try another date, or a different stylist.</div>`);
      put(box, html`<p class="small muted">Total time: ${r.duration} min. All times are Dubai time.</p><div class="slots">${r.slots.map(s => html`<button class="slot ${W.time === s.time ? 'on' : ''}" data-time="${s.time}">${s.label}</button>`)}</div>`);
    } catch (e) { put(box, html`<div class="form-error">${e.message}</div>`); }
  }
  function step2() {
    W.step = 2; const days = []; const base = new Date(); for (let i = 0; i < 21; i++) { const d = new Date(base.getFullYear(), base.getMonth(), base.getDate() + i); days.push(d); }
    const hrs = S('hours') || []; const closedDay = d => hrs[(d.getDay() + 6) % 7]?.closed;
    draw(html`${bar()}<h2 style="font-size:2rem">Pick a date & time</h2>
      <div class="days" role="listbox" aria-label="Dates">${days.map(d => html`<button class="day ${iso(d) === W.date ? 'on' : ''} ${closedDay(d) ? 'closed' : ''}" data-date="${iso(d)}"><span>${d.toLocaleDateString('en-GB', { weekday: 'short' })}</span><b>${d.getDate()}</b><span>${d.toLocaleDateString('en-GB', { month: 'short' })}</span></button>`)}</div>
      <label class="fld" style="max-width:240px"><span>Or choose another date</span><input type="date" id="pickdate" min="${todayIso()}" value="${W.date}"></label>
      <div id="slots"></div>
      <div style="display:flex;gap:10px;margin-top:22px"><button class="btn ghost" id="back">Back</button><button class="btn gold" id="next" ${W.time ? '' : 'disabled'}>Continue</button></div>`);
    $('#back', root).onclick = step1; $('#next', root).onclick = step3; loadSlots();
    $('.days', root).onclick = e => { const b = e.target.closest('[data-date]'); if (!b) return; W.date = b.dataset.date; W.time = ''; $$('.day', root).forEach(x => x.classList.toggle('on', x === b)); $('#pickdate', root).value = W.date; $('#next', root).disabled = true; loadSlots(); };
    $('#pickdate', root).onchange = e => { W.date = e.target.value; W.time = ''; $$('.day', root).forEach(x => x.classList.toggle('on', x.dataset.date === W.date)); $('#next', root).disabled = true; loadSlots(); };
    $('#slots', root).onclick = e => { const b = e.target.closest('[data-time]'); if (!b) return; W.time = b.dataset.time; W.staffPicks = W.slots.slots.find(s => s.time === W.time).staff; $$('.slot', root).forEach(x => x.classList.toggle('on', x === b)); $('#next', root).disabled = false; };
  }
  function step3() {
    W.step = 3; const ps = promosFor(); if (W.promo_id && !ps.some(p => String(p.id) === W.promo_id)) W.promo_id = '';
    draw(html`${bar()}<h2 style="font-size:2rem">Your details</h2>${policy()}
      <div id="err"></div><form id="f" novalidate>
      <div class="row"><label class="fld"><span>Full name *</span><input name="name" autocomplete="name" value="${W.d.name}" required></label>
      <label class="fld"><span>Mobile number *</span><input name="phone" type="tel" inputmode="tel" autocomplete="tel" value="${W.d.phone}" placeholder="+971 5X XXX XXXX" required></label></div>
      <label class="fld"><span>Email <small>(optional — for confirmation)</small></span><input name="email" type="email" autocomplete="email" value="${W.d.email}"></label>
      <label class="fld"><span>Notes for the salon <small>(optional)</small></span><textarea name="notes" maxlength="500">${W.d.notes}</textarea></label>
      ${ps.length ? html`<label class="fld"><span>Promotion</span><select name="promo"><option value="">No promotion</option>${ps.map(p => html`<option value="${p.id}" ${String(p.id) === W.promo_id ? 'selected' : ''}>${p.title} (${p.discount_type === 'percent' ? p.discount_value + '% off' : 'AED ' + p.discount_value + ' off'})</option>`)}</select></label>` : ''}
      ${admin ? html`<label class="check"><input type="checkbox" name="confirmed" ${W.d.confirmed ? 'checked' : ''}> Mark as confirmed</label>` : ''}
      ${!admin && !App.user ? html`<p class="small muted">Have an account? <a href="#/login?next=${encodeURIComponent('/book')}">Sign in</a> to manage this booking later.</p>` : ''}
      <div style="display:flex;gap:10px"><button type="button" class="btn ghost" id="back">Back</button><button class="btn gold">Review booking</button></div></form>`);
    $('#back', root).onclick = step2;
    $('#f', root).onsubmit = e => {
      e.preventDefault(); const f = new FormData(e.target); Object.assign(W.d, { name: f.get('name').trim(), phone: f.get('phone').trim(), email: f.get('email').trim(), notes: f.get('notes').trim(), confirmed: !!f.get('confirmed') }); W.promo_id = f.get('promo') || '';
      const err = !W.d.name || W.d.name.length < 2 ? 'Please enter your full name.' : !/^[+\d\s()\-]{7,25}$/.test(W.d.phone) ? 'Please enter a valid mobile number.' : W.d.email && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(W.d.email) ? 'Please enter a valid email address.' : '';
      if (err) return put($('#err', root), html`<div class="form-error">${err}</div>`); step4();
    };
  }
  function step4() {
    W.step = 4; const est = estimate(), dis = discount(); let t = W.time; const ch = chosen();
    const stf = ch.map((s, i) => W.sel.get(s.id) ? s.staff.find(x => x.id === W.sel.get(s.id)).name : (s.staff.find(x => x.id === W.staffPicks[i])?.name || 'Any available'));
    draw(html`${bar()}<h2 style="font-size:2rem">Review & confirm</h2><div id="err"></div>
      <div class="summary"><div class="ln"><span class="muted">Date</span><b>${dshort(W.date)}</b></div><div class="ln"><span class="muted">Starts</span><b>${t12(W.time)}</b></div>
      ${ch.map((s, i) => html`<div class="ln"><span>${s.name}<div class="small muted">with ${stf[i]} · ${s.duration_min || S('default_duration')} min</div></span><b>${money(s.price)}</b></div>`)}
      ${dis ? html`<div class="ln"><span>Promotion discount</span><b>− AED ${dis.toFixed(2)}</b></div>` : ''}
      <div class="ln"><span class="muted">${est == null ? 'Total' : 'Estimated total'}</span><b>${est == null ? 'Confirmed by the salon' : aed(est - dis)}</b></div>
      <div class="ln"><span class="muted">Name</span><span>${W.d.name} · ${W.d.phone}</span></div></div>
      <p class="small muted" style="margin-top:12px">No online payment is taken. You pay at the salon after your service (${(S('payment_methods') || []).join(', ')}).</p>
      ${policy()}<div style="display:flex;gap:10px"><button class="btn ghost" id="back">Back</button><button class="btn gold" id="ok">Confirm appointment</button></div>`);
    $('#back', root).onclick = step3;
    $('#ok', root).onclick = async e => {
      const b = e.currentTarget; b.disabled = true; b.classList.add('busy'); b.textContent = 'Booking…';
      try {
        const body = { customer_name: W.d.name, customer_phone: W.d.phone, customer_email: W.d.email, customer_notes: W.d.notes, date: W.date, time: W.time, items: items(), promo_id: W.promo_id || null };
        if (admin && W.d.confirmed) body.status = 'confirmed';
        const r = await api(admin ? '/api/admin/appointments' : '/api/book', { method: 'POST', body }); done(r.appointment);
      } catch (er) { b.disabled = false; b.classList.remove('busy'); b.textContent = 'Confirm appointment'; put($('#err', root), html`<div class="form-error">${er.message}</div>`); if (er.status === 409) { W.time = ''; $('#back', root).onclick = step2; toast('Please pick another time.', 'err'); } }
    };
  }
  function done(a) {
    if (opt.onDone) opt.onDone(a);
    draw(html`<div class="center" style="padding:20px 0"><div class="ok-pop" style="width:72px;height:72px;border-radius:50%;background:var(--gold-soft);color:var(--gold);display:grid;place-items:center;margin:0 auto 16px">${icon('check')}</div>
      <h2>${a.status === 'confirmed' ? 'You’re booked!' : 'Request received!'}</h2><p>Reference <b>${a.ref}</b></p>
      <p class="muted">${dshort(a.date)} at ${t12(a.start_time)}<br>${a.items.map(i => i.service_name + ' with ' + (i.staff_name || 'our team')).join(' · ')}</p>
      <p>${a.status === 'confirmed' ? 'Your appointment is confirmed.' : 'The salon will confirm your appointment shortly. We’ll notify you here' + (App.smsReady ? ' and by SMS' : '') + '.'}</p>
      ${admin ? '' : html`<div style="display:flex;gap:10px;justify-content:center;flex-wrap:wrap"><a class="btn" href="${App.user ? '#/account/appointments' : '#/'}">${App.user ? 'View my appointments' : 'Back to home'}</a><a class="btn ghost" href="#/location">Get directions</a></div>`}</div>`);
  }
  step1();
}

/* Date + slot picker used for rescheduling (customer & admin) */
function rescheduleDialog(a, { admin = false, onDone }) {
  const m = modal('Reschedule ' + a.ref, html`<p class="muted">Currently ${dshort(a.date)} at ${t12(a.start_time)}</p><label class="fld"><span>New date</span><input type="date" id="rd" min="${todayIso()}"></label><div id="rs"></div><div id="err"></div><button class="btn gold block" id="go" disabled>Move appointment</button>`);
  let time = '';
  $('#rd', m.el).onchange = async e => {
    time = ''; $('#go', m.el).disabled = true; const box = $('#rs', m.el); put(box, html`<p class="muted">Checking availability…</p>`);
    try {
      const r = await api('/api/availability', { method: 'POST', body: { date: e.target.value, items: a.items.filter(i => i.service_id).map(i => ({ service_id: i.service_id, staff_id: i.staff_id })), exclude_appointment_id: a.id } });
      put(box, r.closed ? html`<div class="empty">${r.reason}</div>` : r.slots.length ? html`<div class="slots">${r.slots.map(s => html`<button class="slot" data-time="${s.time}">${s.label}</button>`)}</div>` : html`<div class="empty">No times available this day.</div>`);
    } catch (er) { put(box, html`<div class="form-error">${er.message}</div>`); }
  };
  $('#rs', m.el).onclick = e => { const b = e.target.closest('[data-time]'); if (!b) return; time = b.dataset.time; $$('.slot', m.el).forEach(x => x.classList.toggle('on', x === b)); $('#go', m.el).disabled = false; };
  $('#go', m.el).onclick = async () => {
    const g = $('#go', m.el); if (g.disabled) return; g.disabled = true; g.classList.add('busy');
    try { await api(admin ? `/api/admin/appointments/${a.id}/reschedule` : `/api/my/appointments/${a.id}/reschedule`, { method: 'POST', body: { date: $('#rd', m.el).value, time } }); m.close(); toast('Appointment moved.', 'ok'); onDone && onDone(); }
    catch (er) { g.disabled = false; g.classList.remove('busy'); put($('#err', m.el), html`<div class="form-error">${er.message}</div>`); }
  };
}
