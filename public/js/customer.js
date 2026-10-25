'use strict';
/* ---------- customer shell ---------- */
const NAV = [['/', 'Home'], ['/services', 'Services'], ['/staff', 'Team'], ['/products', 'Shop'], ['/promotions', 'Promotions'], ['/reviews', 'Reviews'], ['/location', 'Location'], ['/contact', 'Contact']];
function buildCustomerShell() {
  const u = App.user, st = isStaffUser(), bell = st ? '/admin/notifications' : '/account/notifications';
  put($('#app'), html`<header class="topbar"><div class="container"><a class="brand" href="#/" aria-label="${S('business_name')} home"><b>Blonde Majestic</b><span>Ladies Salon</span></a>
    <nav class="nav" aria-label="Main">${NAV.map(([h, l]) => html`<a href="#${h}">${l}</a>`)}</nav>
    ${u ? html`<a class="iconbtn" href="#${bell}" aria-label="Notifications">${icon('bell')}<span class="badge hidden" data-badge="notif">0</span></a>` : ''}
    <a class="btn ghost sm desk" href="#${u ? (st ? '/admin' : '/account') : '/login'}">${u ? (st ? 'Admin panel' : 'My account') : 'Sign in'}</a>
    <a class="btn gold sm desk" href="#/book">Book now</a><button class="iconbtn" id="morebtn" aria-label="Menu">${icon('menu')}</button></div></header>
    <main id="view"></main>
    <footer class="site"><div class="container"><div class="cols"><div><h4>${S('business_name')}</h4><p>${S('area')}<br>${S('address')}</p><p><a href="${telHref(S('phone'))}">${S('phone')}</a></p></div>
    <div><h4>Opening hours</h4>${hoursSummary()}</div><div><h4>We accept</h4><p>${(S('payment_methods') || []).join(' · ')}</p><h4>Amenities</h4><p>${(S('amenities') || []).join(' · ')}</p></div>
    <div><h4>Explore</h4><p>${NAV.slice(1).map(([h, l]) => html`<a href="#${h}">${l}</a><br>`)}<a href="#/about">About us</a><br><a href="#/admin">Staff & owner sign in</a></p></div></div>
    <p class="small" style="margin-top:28px;opacity:.7">© ${new Date().getFullYear()} ${S('business_name')}. ${S('business_type')}.</p></div></footer>
    <nav class="bottomnav" aria-label="App"><a href="#/">${icon('home')}Home</a><a href="#/services">${icon('scissors')}Services</a><a href="#/book" class="book"><span class="orb">${icon('calendar')}</span>Book</a>
    <a href="#/chat">${icon('chat')}Chat<span class="badge hidden" data-badge="chat" style="right:22%">0</span></a><a href="#${u ? (st ? '/admin' : '/account') : '/login'}">${icon('user')}${u ? 'Account' : 'Sign in'}</a></nav>`);
  $('#morebtn').onclick = () => {
    const m = modal('Menu', html`<div style="display:grid;gap:8px">${[...NAV, ['/about', 'About us'], ['/chat', 'Chat']].map(([h, l]) => html`<a class="btn light" href="#${h}" data-close>${l}</a>`)}${u ? html`<a class="btn light" href="#${bell}" data-close>Notifications</a>` : ''}${st ? html`<a class="btn" href="#/admin" data-close>Admin panel</a>` : ''}</div>`);
  };
  pollNotifications(true);
}
function hoursSummary() {
  const h = S('hours') || []; const same = h.length === 7 && h.every(x => !x.closed && x.open === h[0].open && x.close === h[0].close);
  return same ? html`<p>Monday – Sunday<br>${t12(h[0].open)} – ${t12(h[0].close)}</p>` : html`<p>${h.map(x => html`${x.day.slice(0, 3)}: ${x.closed ? 'Closed' : t12(x.open) + ' – ' + t12(x.close)}<br>`)}</p>`;
}
function markNav(path) {
  $$('.nav a,.bottomnav a,.side nav a').forEach(a => { const h = a.getAttribute('href').slice(1); a.classList.toggle('on', h === '/' ? path === '/' : (path === h || path.startsWith(h + '/'))); });
  const m = $('.side'); m && m.classList.remove('open');
  const sc = $('.scrim'); if (sc && !sc.classList.contains('out')) { sc.classList.add('out'); setTimeout(() => sc.remove(), RM() ? 0 : 240); }
}
const wrap = (inner, cls = '') => html`<div class="container ${cls}" style="padding:28px 0 40px">${inner}</div>`;
const emptyBox = (t, m, extra = '') => html`<div class="empty"><b>${t}</b>${m}${extra}</div>`;

/* ---------- home ---------- */
route('/', async () => {
  const hero = S('hero_image'), r = App.rating, owner = S('owner_name');
  const svcCount = App.cats.reduce((a, c) => a + c.service_count, 0);
  put(view(), html`<section class="hero"><div class="container"><div><h1>${S('business_name')}</h1><p class="lead">${S("tagline")} An exclusive ladies beauty salon in ${S("area")}.</p>
    <div class="cta"><a class="btn gold" href="#/book">Book an Appointment</a><a class="btn ghost" href="#/services">Explore Services</a><a class="btn ghost" href="#/contact">Contact Us</a></div>
    <div class="facts"><span><b>${r.average ? r.average.toFixed(1) : '–'} / 5</b> · ${r.total}${r.baseline_count ? '+' : ''} reviews</span><span><b>${S('area')}</b></span><span>${hoursOneLine()}</span></div></div>
    <div class="visual">${hero ? html`<div class="arch"><img src="${img(hero)}" alt="${S('business_name')} salon" fetchpriority="high"></div>` : html`<div class="crest" aria-hidden="true"><div class="ring r1"></div><div class="ring r2"></div><div class="ring r3"></div><div class="ring r4"></div><div class="mono">BM<small>${S('area')}</small></div></div>`}</div></div></section>
    <section class="block" style="padding-top:0"><div class="container"><div class="section-head"><h2>What we do</h2><a class="btn ghost sm" href="#/services">All ${svcCount} services</a></div>
    <div class="grid">${App.cats.map((c, i) => html`<a class="card" href="#/services?category=${c.id}"><div class="cover" style="aspect-ratio:16/9">${pic(c.image || '', c.name, i)}</div><div class="body"><h3>${c.name}</h3><p class="muted small" style="margin:0">${c.service_count} service${c.service_count === 1 ? '' : 's'}</p></div></a>`)}</div></div></section>
    <section class="block" style="padding-top:0"><div class="container"><div class="band" style="display:grid;gap:28px;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));align-items:center"><div><h2>An exclusive ladies’ salon in Al Rigga</h2><p class="muted">${S('description')}</p><a class="btn gold" href="#/about">About us</a></div>
      <div style="display:grid;gap:10px">${(S('amenities') || []).map(a => html`<div style="display:flex;gap:12px;align-items:center">${icon(amenityIcon(a))}<span>${a}</span></div>`)}</div></div></div></section>
    ${App.staff.length ? html`<section class="block" style="padding-top:0"><div class="container"><div class="section-head"><h2>Meet the team</h2><a class="btn ghost sm" href="#/staff">See everyone</a></div><div class="grid" style="grid-template-columns:repeat(auto-fill,minmax(170px,1fr))">${App.staff.map((s, i) => html`<a class="card staffcard" href="#/staff"><div class="arch">${pic(s.image, s.name, i)}</div><h3 style="margin:0">${s.name}</h3><p class="small muted" style="margin:4px 0 0">${s.specialty}</p></a>`)}</div></div></section>` : ''}
    ${App.promos.length ? html`<section class="block" style="padding-top:0"><div class="container"><div class="section-head"><h2>Offers</h2><a class="btn ghost sm" href="#/promotions">All promotions</a></div><div class="grid two">${App.promos.slice(0, 2).map(promoCard)}</div></div></section>` : ''}
    <section class="block" style="padding-top:0"><div class="container"><div class="section-head"><h2>What our guests say</h2><a class="btn ghost sm" href="#/reviews">Read & write reviews</a></div>
      ${App.testimonials.length ? html`<div class="grid">${App.testimonials.slice(0, 6).map(t => html`<div class="card review"><div>${stars(t.rating)}</div><p class="quote">“${t.body}”</p><div class="small muted">— ${t.author_name}${t.service_name ? ' · ' + t.service_name : ''}</div></div>`)}</div>`
        : emptyBox('Share your experience', 'Be among the first to feature here.', html`<p><a class="btn" href="#/reviews?write=1">Write a review</a></p>`)}</div></section>
    ${(S('gallery') || []).length ? html`<section class="block" style="padding-top:0"><div class="container"><h2>Inside the salon</h2><div class="grid" style="grid-template-columns:repeat(auto-fill,minmax(200px,1fr))">${S('gallery').map((g, i) => html`<div class="cover" style="border-radius:var(--r);cursor:zoom-in" data-lb="${i}"><img src="${img(g)}" alt="Salon photo ${i + 1}" loading="lazy"></div>`)}</div></div></section>` : ''}
    <section class="block" style="padding-top:0"><div class="container"><div class="grid two"><div class="card pad"><h3>Visit us</h3><p>${S('address')}</p>${hoursSummary()}<div style="display:flex;gap:10px;flex-wrap:wrap"><a class="btn" href="#/location">View map</a><a class="btn ghost" href="${telHref(S('phone'))}">Call ${S('phone')}</a></div></div>
    <div class="card pad"><h3>We accept</h3><div class="chips" style="flex-wrap:wrap">${(S('payment_methods') || []).map(p => html`<span class="chip">${p}</span>`)}</div><p class="small muted" style="margin-top:14px">${S('appointment_policy')}</p><a class="btn gold" href="#/book">Book an Appointment</a></div></div></div></section>`);
  $$('[data-lb]').forEach(el => el.onclick = () => lightbox(S('gallery'), +el.dataset.lb));
});
function hoursOneLine() { const h = S('hours') || []; return h.length === 7 && h.every(x => !x.closed && x.open === h[0].open && x.close === h[0].close) ? `Open daily ${t12(h[0].open)} – ${t12(h[0].close)}` : 'See opening hours'; }
const promoCard = p => html`<div class="card"><div class="cover" style="aspect-ratio:16/9">${pic(p.image, p.title, 1)}<span class="tag">${p.discount_type === 'percent' ? p.discount_value + '% off' : 'AED ' + p.discount_value + ' off'}</span></div><div class="body"><h3>${p.title}</h3><p class="muted small">${p.description}</p>
  <p class="small muted">${p.start_date || p.end_date ? [p.start_date && 'From ' + dshort(p.start_date), p.end_date && 'Until ' + dshort(p.end_date)].filter(Boolean).join(' · ') : 'Ongoing offer'}</p><a class="btn gold sm" href="#/book?promo=${p.id}">Book with this offer</a></div></div>`;

/* ---------- about ---------- */
route('/about', async () => {
  put(view(), wrap(html`<div class="grid two" style="align-items:center;gap:40px"><div><h1 style="font-size:3rem">About ${S('business_name')}</h1><p class="lead" style="font-size:1.1rem">${S('description')}</p>
    <p>We focus on <b>beauty, hair, nail, lash, brow, skin and body-care</b> services in a comfortable and welcoming environment, exclusively for women, in ${S('area')}.</p>
    <div class="card pad" style="display:flex;gap:16px;align-items:center"><div class="arch" style="width:84px;flex:none;aspect-ratio:3/4">${pic(S('owner_image'), S('owner_name'), 2)}</div><div><b>${S('owner_name')}</b><div class="muted small">${S('owner_title')}</div>${S('owner_bio') ? html`<p class="small" style="margin:6px 0 0">${S('owner_bio')}</p>` : ''}</div></div>
    <p style="margin-top:22px"><a class="btn gold" href="#/book">Book an Appointment</a> <a class="btn ghost" href="#/staff">Meet the team</a></p></div>
    <div>${S('hero_image') ? html`<div class="arch"><img src="${img(S('hero_image'))}" alt="Inside the salon"></div>` : html`<div class="crest" aria-hidden="true"><div class="ring r1"></div><div class="ring r2"></div><div class="ring r3"></div><div class="ring r4"></div><div class="mono">BM</div></div>`}</div></div>
    <h2 style="margin-top:56px">Amenities</h2><div class="grid" style="grid-template-columns:repeat(auto-fill,minmax(210px,1fr))">${(S('amenities') || []).map(a => html`<div class="iconcard">${icon(amenityIcon(a))}<b>${a}</b></div>`)}</div>`));
});

/* ---------- services ---------- */
route('/services', async (_, q, t) => {
  const f = { category: q.category || '', q: '', max: '' };
  put(view(), wrap(html`<h1 style="font-size:2.8rem">Services</h1><div class="chips" id="cats"></div><div class="row" style="margin-top:14px"><label class="fld"><span>Search</span><input id="sq" type="search" placeholder="e.g. keratin, manicure"></label><label class="fld"><span>Maximum price (AED)</span><input id="mx" type="number" min="0" inputmode="numeric"></label></div><div id="list"></div>`));
  const draw = async () => {
    put($('#cats'), html`<button class="chip ${f.category ? '' : 'on'}" data-c="">All</button>${App.cats.map(c => html`<button class="chip ${String(c.id) === String(f.category) ? 'on' : ''}" data-c="${c.id}">${c.name}</button>`)}`);
    const list = await api('/api/services' + qs(f)); if (stale(t)) return;
    put($('#list'), list.length ? html`<div class="grid">${list.map((s, i) => html`<a class="card" href="#/services/${s.id}"><div class="cover">${pic(s.image, s.name, s.category_id)}<span class="tag">${s.category_name}</span></div><div class="body"><h3>${s.name}</h3><div style="display:flex;justify-content:space-between"><span class="price">${money(s.price)}</span><span class="muted small">${s.duration_min} min</span></div><p class="small muted" style="margin:6px 0 0">${s.staff.length ? 'With ' + s.staff.map(x => x.name).join(', ') : 'Contact salon to book'}</p></div></a>`)}</div>` : emptyBox('No services found', 'Try a different search or category.'));
  };
  $('#cats').onclick = e => { const b = e.target.closest('[data-c]'); if (b) { f.category = b.dataset.c; draw(); } };
  $('#sq').oninput = debounce(e => { f.q = e.target.value; draw(); }); $('#mx').oninput = debounce(e => { f.max = e.target.value; draw(); });
  draw();
});
route('/services/:id', async ({ id }) => {
  const s = await api('/api/services/' + id), bookable = s.staff.length > 0;
  put(view(), wrap(html`<a href="#/services" class="small muted">← All services</a><div class="grid two" style="margin-top:14px;gap:34px"><div class="arch" style="aspect-ratio:4/5;max-width:480px;width:100%;margin-inline:auto">${pic(s.image, s.name, s.category_id)}</div>
    <div><span class="pill">${s.category_name}</span><h1 style="font-size:3rem;margin-top:10px">${s.name}</h1><p>${s.description || 'Ask our team for details about this service.'}</p>
    <dl class="kv" style="margin-bottom:20px"><dt>Price</dt><dd class="price">${money(s.price)}</dd><dt>Estimated duration</dt><dd>${s.duration_min} minutes</dd><dt>Available with</dt><dd>${bookable ? s.staff.map(x => x.name).join(', ') : 'Contact the salon'}</dd></dl>
    ${bookable ? html`<a class="btn gold" href="#/book?service=${s.id}">Book this service</a>` : html`<div class="notice">This service can’t be booked online yet. Please chat with us or call ${S('phone')}.</div><a class="btn gold" href="#/chat/salon">Chat with Salon</a> <a class="btn ghost" href="${telHref(S('phone'))}">Call</a>`}</div></div>
    ${s.related.length ? html`<h2 style="margin-top:50px">Related services</h2><div class="grid">${s.related.map(r => html`<a class="card" href="#/services/${r.id}"><div class="body"><h3>${r.name}</h3><span class="price">${money(r.price)}</span> <span class="muted small">· ${r.duration_min} min</span></div></a>`)}</div>` : ''}`));
});

/* ---------- team ---------- */
route('/staff', async () => {
  const list = await api('/api/staff');
  put(view(), wrap(html`<h1 style="font-size:2.8rem">Our team</h1><div class="grid" style="grid-template-columns:repeat(auto-fill,minmax(250px,1fr))">${list.map((s, i) => html`<div class="card staffcard"><div class="arch">${pic(s.image, s.name, i)}</div><h3>${s.name}</h3><p class="muted" style="margin-bottom:6px">${s.specialty}</p>${s.rating ? html`<div>${stars(s.rating)} <span class="small muted">${s.rating.toFixed(1)} (${s.review_count})</span></div>` : ''}${s.bio ? html`<p class="small">${s.bio}</p>` : ''}
    <div class="chips" style="flex-wrap:wrap;justify-content:center;margin:10px 0">${s.services.slice(0, 5).map(x => html`<a class="chip" style="min-height:30px;font-size:.8rem" href="#/services/${x.id}">${x.name}</a>`)}</div><a class="btn sm" href="#/book?staff=${s.id}">Book with ${s.name}</a></div>`)}</div>`));
});

/* ---------- products ---------- */
route('/products', async (_, q, t) => {
  const f = { category: '', q: '', max: '' }; const cats = await api('/api/product-categories');
  put(view(), wrap(html`<h1 style="font-size:2.8rem">Beauty shop</h1><p class="muted">Products recommended and stocked by the salon. Ask us in the salon or by chat to purchase.</p><div class="chips" id="cats"></div><div class="row"><label class="fld"><span>Search</span><input id="sq" type="search"></label><label class="fld"><span>Maximum price (AED)</span><input id="mx" type="number" min="0"></label></div><div id="list"></div>`));
  const draw = async () => {
    put($('#cats'), html`<button class="chip ${f.category ? '' : 'on'}" data-c="">All</button>${cats.map(c => html`<button class="chip ${String(c.id) === String(f.category) ? 'on' : ''}" data-c="${c.id}">${c.name}</button>`)}`);
    const list = await api('/api/products' + qs(f)); if (stale(t)) return;
    put($('#list'), list.length ? html`<div class="grid">${list.map((p, i) => html`<a class="card" href="#/products/${p.id}"><div class="cover" style="aspect-ratio:1/1">${pic(p.images[0]?.filename, p.name, i)}${p.images.length > 1 ? html`<span class="count-badge">${p.images.length} photos</span>` : ''}</div><div class="body"><h3>${p.name}</h3><span class="price">${money(p.price)}</span> ${p.stock <= 0 ? html`<span class="pill cancelled">Out of stock</span>` : ''}<div class="small muted">${p.category_name || ''}</div></div></a>`)}</div>` : emptyBox('No products yet', 'The salon hasn’t listed products matching your search.'));
  };
  $('#cats').onclick = e => { const b = e.target.closest('[data-c]'); if (b) { f.category = b.dataset.c; draw(); } };
  $('#sq').oninput = debounce(e => { f.q = e.target.value; draw(); }); $('#mx').oninput = debounce(e => { f.max = e.target.value; draw(); }); draw();
});
route('/products/:id', async ({ id }) => {
  const p = await api('/api/products/' + id);
  put(view(), wrap(html`<a href="#/products" class="small muted">← Shop</a><div class="grid two" style="margin-top:14px;gap:34px"><div style="max-width:560px;width:100%">${gallery(p.images.map(i => i.filename), p.name)}</div><div><span class="pill">${p.category_name || 'Product'}</span><h1 style="font-size:2.8rem;margin-top:10px">${p.name}</h1><p class="price" style="font-size:1.6rem">${money(p.price)}</p>
    <p>${p.stock > 0 ? html`<span class="pill paid">In stock</span>` : html`<span class="pill cancelled">Out of stock</span>`}</p><p>${p.description}</p><a class="btn gold" href="#/chat/salon">Ask the salon</a> <a class="btn ghost" href="${telHref(S('phone'))}">Call ${S('phone')}</a></div></div>`));
});

/* ---------- promotions ---------- */
route('/promotions', async () => {
  const list = await api('/api/promotions');
  put(view(), wrap(html`<h1 style="font-size:2.8rem">Promotions</h1>${list.length ? html`<div class="grid two">${list.map(promoCard)}</div>` : emptyBox('No promotions right now', 'New offers are announced here and by notification.', html`<p><a class="btn" href="#/services">Browse services</a></p>`)}`));
});

/* ---------- reviews ---------- */
route('/reviews', async (_, q, t) => {
  const f = { rating: '', service_id: '', staff_id: '' }; let off = 0;
  const [first, svcs] = await Promise.all([api('/api/reviews'), api('/api/services')]);
  const sum = first.summary, dist = sum.distribution, rt = Object.values(dist).reduce((a, b) => a + b, 0);
  put(view(), wrap(html`<div class="section-head"><h1 style="font-size:2.8rem;margin:0">Reviews</h1><button class="btn gold" id="write">Write a review</button></div>
    <div class="card pad" style="display:grid;gap:24px;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));margin-bottom:22px"><div><div style="font:600 3.6rem var(--display)">${sum.average.toFixed(1)}<span class="muted" style="font-size:1.4rem"> / 5</span></div>${stars(sum.average)}<div class="muted small">${sum.total}${sum.baseline_count ? '+' : ''} reviews</div></div>
    <div>${[5, 4, 3, 2, 1].map(n => html`<div style="display:grid;grid-template-columns:28px 1fr 34px;gap:8px;align-items:center;font-size:.85rem"><span>${n}★</span><div class="bar"><i style="width:${rt ? 100 * dist[n] / rt : 0}%"></i></div><span class="muted">${dist[n]}</span></div>`)}<div class="small muted" style="margin-top:6px">${rt ? `Distribution of ${rt} review${rt === 1 ? '' : 's'} submitted on this site.` : 'Distribution appears once reviews are submitted on this site.'}</div></div></div>
    <div class="row"><label class="fld"><span>Rating</span><select id="fr"><option value="">All ratings</option>${[5, 4, 3, 2, 1].map(n => html`<option value="${n}">${n} stars</option>`)}</select></label>
    <label class="fld"><span>Service</span><select id="fs"><option value="">All services</option>${svcs.map(s => html`<option value="${s.id}">${s.name}</option>`)}</select></label><label class="fld"><span>Stylist</span><select id="ft"><option value="">Everyone</option>${App.staff.map(s => html`<option value="${s.id}">${s.name}</option>`)}</select></label></div>
    <div id="list" class="grid"></div><p class="center"><button class="btn ghost hidden" id="more">Load more</button></p>`));
  const draw = async (append) => {
    if (!append) off = 0; const r = await api('/api/reviews' + qs({ ...f, offset: off })); if (stale(t)) return;
    const cards = r.reviews.map(x => html`<div class="card review"><div class="who"><b>${x.author_name}${x.verified ? html` <span class="pill paid" title="Has a completed visit">Verified visit</span>` : ''}</b><span class="small muted">${dshort(x.created.slice(0, 10))}</span></div>${stars(x.rating)}<p style="margin:8px 0 4px">${x.body}</p><div class="small muted">${[x.service_name, x.staff_name && 'with ' + x.staff_name].filter(Boolean).join(' · ')}</div>${x.image ? html`<img class="rimg" src="${img(x.image)}" alt="Review photo" loading="lazy">` : ''}</div>`);
    const L = $('#list'); append ? L.insertAdjacentHTML('beforeend', cards.map(c => c.s).join('')) : put(L, cards.length ? cards : emptyBox('No reviews match', 'Be the first to share your experience.'));
    off += r.reviews.length; $('#more').classList.toggle('hidden', r.reviews.length < 12);
  };
  $('#fr').onchange = e => { f.rating = e.target.value; draw(); }; $('#fs').onchange = e => { f.service_id = e.target.value; draw(); }; $('#ft').onchange = e => { f.staff_id = e.target.value; draw(); }; $('#more').onclick = () => draw(true);
  $('#write').onclick = () => writeReview(svcs, draw);
  draw(); if (q.write) { if (App.user) writeReview(svcs, draw); else go('/login?next=' + encodeURIComponent('/reviews?write=1')); }
});
function writeReview(svcs, after) {
  if (!App.user) return go('/login?next=' + encodeURIComponent('/reviews?write=1'));
  const m = modal('Rate your experience', html`<form id="rf"><div id="err"></div><fieldset style="border:0;padding:0;margin:0 0 14px"><legend class="small" style="font-weight:500;margin-bottom:6px">Your rating *</legend><div style="display:flex;gap:6px" id="starpick">${[1, 2, 3, 4, 5].map(n => html`<label style="font-size:2.2rem;cursor:pointer;color:#D9CDBB;line-height:1"><input type="radio" name="rating" value="${n}" class="sr">★</label>`)}</div></fieldset>
    <label class="fld"><span>Your review *</span><textarea name="body" maxlength="1000" required></textarea></label><div class="row"><label class="fld"><span>Service reviewed</span><select name="service_id"><option value="">Not specified</option>${svcs.map(s => html`<option value="${s.id}">${s.name}</option>`)}</select></label>
    <label class="fld"><span>Stylist reviewed</span><select name="staff_id"><option value="">Not specified</option>${App.staff.map(s => html`<option value="${s.id}">${s.name}</option>`)}</select></label></div>
    <label class="fld"><span>Photo <small>(optional, JPG/PNG/WEBP up to 5 MB)</small></span><input type="file" name="image" accept="image/jpeg,image/png,image/webp,image/gif"></label><button class="btn gold block">Submit review</button></form>`);
  const paint = () => { const v = +($('input:checked', m.el)?.value || 0); $$('#starpick label', m.el).forEach((l, i) => l.style.color = i < v ? 'var(--gold)' : '#D9CDBB'); };
  $('#starpick', m.el).onchange = paint;
  $('#rf', m.el).onsubmit = async e => {
    e.preventDefault(); const fd = new FormData(e.target); if (!fd.get('rating')) return put($('#err', m.el), html`<div class="form-error">Please choose a star rating.</div>`);
    if (!fd.get('image') || !fd.get('image').size) fd.delete('image');
    const b = $('button.btn', e.target); b.disabled = true; b.classList.add('busy');
    try { await api('/api/reviews', { method: 'POST', form: fd }); m.close(); toast('Thank you for your review!', 'ok'); const p = await api('/api/public'); Object.assign(App, { rating: p.rating, testimonials: p.testimonials }); after && after(); }
    catch (er) { b.disabled = false; b.classList.remove('busy'); put($('#err', m.el), html`<div class="form-error">${er.message}</div>`); }
  };
}

/* ---------- location & contact ---------- */
const dirUrl = () => 'https://www.google.com/maps/dir/?api=1&destination=' + encodeURIComponent(S('address'));
function mapSrc() {
  const lat = +S('map_lat'), lng = +S('map_lng'), key = S('google_maps_key');
  if (key) return 'https://www.google.com/maps/embed/v1/place?key=' + encodeURIComponent(key) + '&q=' + encodeURIComponent(S('address'));
  const d = 0.006; return `https://www.openstreetmap.org/export/embed.html?bbox=${lng - d},${lat - d / 1.6},${lng + d},${lat + d / 1.6}&layer=mapnik&marker=${lat},${lng}`;
}
route('/location', async () => {
  put(view(), wrap(html`<h1 style="font-size:2.8rem">Find us</h1><div class="grid two" style="align-items:start"><div><iframe class="mapframe" title="Map showing ${S('business_name')}" src="${mapSrc()}" loading="lazy" referrerpolicy="no-referrer-when-downgrade" allowfullscreen></iframe><p class="small muted" style="margin-top:8px">${S('google_maps_key') ? 'Google Maps' : 'Map © OpenStreetMap contributors. The owner can switch to Google Maps in Settings.'}</p></div>
    <div class="card pad"><h3>${S('business_name')}</h3><p>${S('address')}</p><p><a href="${telHref(S('phone'))}">${S('phone')}</a></p>${hoursSummary()}<div style="display:flex;gap:10px;flex-wrap:wrap"><a class="btn gold" href="${dirUrl()}" target="_blank" rel="noopener">Get directions</a><a class="btn ghost" href="${telHref(S('phone'))}">Call</a><a class="btn ghost" href="#/contact">Contact</a></div></div></div>`));
});
route('/contact', async () => {
  const c = [['phone', 'Call us', S('phone'), telHref(S('phone'))], ['pin', 'Open map', S('address'), '#/location'], ['chat', 'Message us', 'Chat with the salon team', '#/chat/salon']];
  if (S('website')) c.push(['globe', 'Website', S('website'), safeUrl(S('website')), 1]); if (S('facebook_url')) c.push(['facebook', 'Facebook', 'Official Facebook page', safeUrl(S('facebook_url')), 1]); if (S('email')) c.push(['msg', 'Email', S('email'), 'mailto:' + S('email')]);
  put(view(), wrap(html`<h1 style="font-size:2.8rem">Contact</h1><div class="grid" style="grid-template-columns:repeat(auto-fill,minmax(280px,1fr))">${c.map(([i, t, s, h, ext]) => html`<a class="iconcard" href="${h}" ${ext ? raw('target="_blank" rel="noopener"') : ''}>${icon(i)}<span><b>${t}</b><span class="small muted">${s}</span></span></a>`)}</div>
    <div class="grid two" style="margin-top:28px"><div class="card pad"><h3>Opening hours</h3>${hoursSummary()}<p class="small muted">${S('appointment_policy')}</p></div><div class="card pad"><h3>Amenities</h3><div class="chips" style="flex-wrap:wrap">${(S('amenities') || []).map(a => html`<span class="chip">${icon(amenityIcon(a))}${a}</span>`)}</div><h3 style="margin-top:20px">Payment methods</h3><div class="chips" style="flex-wrap:wrap">${(S('payment_methods') || []).map(p => html`<span class="chip">${icon('card')}${p}</span>`)}</div></div></div>`));
});

/* ---------- booking page ---------- */
route('/book', async (_, q) => {
  const v = view(); put(v, wrap(html`<div id="bk" style="max-width:760px;margin:auto"></div>`)); const box = document.createElement('div'); $('#bk').appendChild(box);
  await bookingWizard(box, { preset: q });
});

/* ---------- auth ---------- */
async function afterAuth(user, next) {
  App.user = user; App.mode = null; await pollNotifications(true); every(() => pollNotifications(), 20000);
  const st = user.role !== 'customer'; go(next && (st || !next.startsWith('/admin')) ? next : st ? '/admin' : '/account');
}
route('/login', async (_, q) => {
  if (App.user) return go(q.next || '/account'); let mode = q.mode === 'register' ? 'register' : 'login';
  const draw = () => {
    put(view(), wrap(html`<div style="max-width:460px;margin:auto"><h1 style="font-size:2.6rem">${mode === 'login' ? 'Welcome back' : 'Create your account'}</h1><div class="tabs"><button class="${mode === 'login' ? 'on' : ''}" data-m="login">Sign in</button><button class="${mode === 'register' ? 'on' : ''}" data-m="register">Create account</button></div><div id="err"></div>
      <form id="af" class="card pad" novalidate>${mode === 'register' ? html`<label class="fld"><span>Full name</span><input name="name" autocomplete="name" required></label><label class="fld"><span>Mobile number</span><input name="phone" type="tel" autocomplete="tel" placeholder="+971 5X XXX XXXX" required></label>` : ''}
      <label class="fld"><span>Email</span><input name="email" type="email" autocomplete="email" required></label><label class="fld"><span>Password ${mode === 'register' ? html`<small>(at least 8 characters)</small>` : ''}</span><input name="password" type="password" autocomplete="${mode === 'login' ? 'current-password' : 'new-password'}" required></label><button class="btn gold block">${mode === 'login' ? 'Sign in' : 'Create account'}</button></form>
      <p class="small muted center" style="margin-top:14px">Salon owner or staff? Sign in here too — you’ll be taken to the admin panel.</p></div>`));
    $('.tabs').onclick = e => { const b = e.target.closest('[data-m]'); if (b) { mode = b.dataset.m; draw(); } };
    $('#af').onsubmit = async e => {
      e.preventDefault(); const body = Object.fromEntries(new FormData(e.target)); const btn = $('button.btn', e.target); btn.disabled = true; btn.classList.add('busy');
      try { const r = await api('/api/auth/' + mode, { method: 'POST', body }); await afterAuth(r.user, q.next); } catch (er) { btn.disabled = false; btn.classList.remove('busy'); put($('#err'), html`<div class="form-error">${er.message}</div>`); }
    };
  }; draw();
});
async function logout() { try { await api('/api/auth/logout', { method: 'POST', body: {} }); } catch (e) { } App.user = null; App.unread = 0; App.mode = null; go('/'); render(); }

/* ---------- account ---------- */
const TABS = [['profile', 'Profile'], ['appointments', 'Appointments'], ['reviews', 'My reviews'], ['messages', 'Messages'], ['notifications', 'Notifications'], ['settings', 'Settings']];
route('/account', () => go('/account/appointments'), { auth: true });
route('/account/:tab', async ({ tab }, q, t) => {
  if (isStaffUser()) return go('/admin');
  put(view(), wrap(html`<h1 style="font-size:2.6rem">Hello, ${App.user.name.split(' ')[0]}</h1><div class="tabs">${TABS.map(([k, l]) => html`<a href="#/account/${k}" class="${k === tab ? 'on' : ''}">${l}</a>`)}</div><div id="tab"></div>`), 'x');
  const box = $('#tab');
  if (tab === 'profile') {
    put(box, html`<form id="pf" class="card pad" style="max-width:520px"><div id="err"></div><label class="fld"><span>Name</span><input name="name" value="${App.user.name}" required></label><label class="fld"><span>Mobile</span><input name="phone" type="tel" value="${App.user.phone || ''}" required></label><label class="fld"><span>Email</span><input name="email" type="email" value="${App.user.email}" required></label><button class="btn gold">Save changes</button></form>`);
    $('#pf').onsubmit = async e => { e.preventDefault(); const b = $('button.btn', e.target); b.disabled = true; b.classList.add('busy'); try { const r = await api('/api/auth/me', { method: 'PUT', body: Object.fromEntries(new FormData(e.target)) }); App.user = r.user; b.disabled = false; b.classList.remove('busy'); toast('Profile updated.', 'ok'); } catch (er) { b.disabled = false; b.classList.remove('busy'); put($('#err'), html`<div class="form-error">${er.message}</div>`); } };
  } else if (tab === 'appointments') {
    const d = await api('/api/my/appointments'); if (stale(t)) return; let sub = 'upcoming'; const td = todayIso();
    const part = a => a.status === 'cancelled' ? 'cancelled' : (['pending', 'confirmed', 'in_progress'].includes(a.status) && a.date >= td) ? 'upcoming' : 'past';
    const draw = () => {
      const L = d.appointments.filter(a => part(a) === sub).sort((a, b) => sub === 'upcoming' ? (a.date + a.start_time).localeCompare(b.date + b.start_time) : 0);
      put(box, html`<div class="tabs">${['upcoming', 'past', 'cancelled'].map(k => html`<button class="${k === sub ? 'on' : ''}" data-s="${k}">${k[0].toUpperCase() + k.slice(1)} (${d.appointments.filter(a => part(a) === k).length})</button>`)}</div>
        ${L.length ? html`<div class="grid two">${L.map(a => html`<div class="card pad"><div style="display:flex;justify-content:space-between;gap:8px"><b>${dshort(a.date)} · ${t12(a.start_time)}</b>${pill(a.status)}</div><p class="small muted" style="margin:2px 0 10px">Ref ${a.ref}</p>
          ${a.items.map(i => html`<div style="display:flex;justify-content:space-between;gap:10px"><span>${i.service_name}<span class="small muted"> · ${i.staff_name || 'Our team'}</span></span><span class="muted small">${t12(i.start_time)}</span></div>`)}
          ${a.estimated_total != null ? html`<p class="small" style="margin:10px 0 0">Estimated total: <b>${aed(a.estimated_total)}</b></p>` : ''}${a.customer_notes ? html`<p class="small muted">Your note: ${a.customer_notes}</p>` : ''}
          ${a.status === 'pending' || a.status === 'confirmed' ? (a.can_change ? html`<div style="display:flex;gap:8px;margin-top:12px"><button class="btn ghost sm" data-re="${a.id}">Reschedule</button><button class="btn ghost sm" data-ca="${a.id}">Cancel</button></div>` : html`<p class="small muted" style="margin-top:12px">${d.cutoff_hours ? `Changes must be made at least ${d.cutoff_hours} hours ahead.` : ''} To change this appointment please <a href="#/chat/salon">message the salon</a>.</p>`) : ''}
          ${a.status === 'completed' ? html`<a class="btn ghost sm" style="margin-top:12px" href="#/reviews?write=1">Review this visit</a>` : ''}</div>`)}</div>` : emptyBox('Nothing here', sub === 'upcoming' ? 'You have no upcoming appointments.' : 'No ' + sub + ' appointments.', sub === 'upcoming' ? html`<p><a class="btn gold" href="#/book">Book an appointment</a></p>` : '')}`);
    };
    draw(); box.onclick = async e => {
      const s = e.target.closest('[data-s]'), re = e.target.closest('[data-re]'), ca = e.target.closest('[data-ca]');
      if (s) { sub = s.dataset.s; draw(); } else if (re) rescheduleDialog(d.appointments.find(a => a.id == re.dataset.re), { onDone: render });
      else if (ca && await confirmBox('Cancel appointment?', 'This will free up your time slot.', 'Yes, cancel', true)) { try { await api(`/api/my/appointments/${ca.dataset.ca}/cancel`, { method: 'POST', body: {} }); toast('Appointment cancelled.'); render(); } catch (er) { toast(er.message, 'err'); } }
    };
  } else if (tab === 'reviews') {
    const L = await api('/api/my/reviews'); put(box, html`<p><a class="btn gold sm" href="#/reviews?write=1">Write a review</a></p>${L.length ? html`<div class="grid">${L.map(x => html`<div class="card review">${stars(x.rating)}<p>${x.body}</p><div class="small muted">${dshort(x.created.slice(0, 10))} ${x.visible ? '' : '· hidden by salon'}</div></div>`)}</div>` : emptyBox('No reviews yet', 'Tell us about your visit.')}`);
  } else if (tab === 'messages') {
    put(box, html`<div class="card pad"><h3>Messages</h3><p>Chat directly with the salon team, or ask our AI assistant a quick question.</p><a class="btn gold" href="#/chat/salon">Open salon chat ${raw('<span class="dot hidden" data-badge="chat">0</span>')}</a> <a class="btn ghost" href="#/chat/ai">Chat with AI</a></div>`); pollNotifications();
  } else if (tab === 'notifications') renderNotifications(box);
  else if (tab === 'settings') {
    put(box, html`<div class="grid two"><form id="pw" class="card pad"><h3>Change password</h3><div id="err"></div><label class="fld"><span>Current password</span><input type="password" name="current" autocomplete="current-password" required></label><label class="fld"><span>New password</span><input type="password" name="new" autocomplete="new-password" minlength="8" required></label><button class="btn">Update password</button></form>
      <div class="card pad"><h3>Sign out</h3><p class="muted">You’ll need to sign in again to manage appointments.</p><button class="btn ghost" id="lo">Sign out</button></div></div>`);
    $('#pw').onsubmit = async e => { e.preventDefault(); const b = $('button.btn', e.target); b.disabled = true; b.classList.add('busy'); try { await api('/api/auth/password', { method: 'POST', body: Object.fromEntries(new FormData(e.target)) }); e.target.reset(); b.disabled = false; b.classList.remove('busy'); toast('Password updated.', 'ok'); } catch (er) { b.disabled = false; b.classList.remove('busy'); put($('#err'), html`<div class="form-error">${er.message}</div>`); } };
    $('#lo').onclick = logout;
  }
}, { auth: true });
async function renderNotifications(box) {
  const d = await api('/api/notifications'); App.unread = d.unread;
  put(box, html`<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px"><span class="muted">${d.unread} unread</span><button class="btn ghost sm" id="mar" ${d.unread ? '' : 'disabled'}>Mark all as read</button></div>
    ${d.notifications.length ? html`<div class="card">${d.notifications.map(n => html`<a class="conv" href="${n.link || '#'}" data-n="${n.id}" style="${n.is_read ? '' : 'background:#FFFCF5'}"><b><span>${n.is_read ? '' : raw('<span class="dot" style="min-width:10px;height:10px;padding:0"></span> ')}${n.title}</span><span class="small muted" style="font-weight:400">${dtshort(n.created)}</span></b><p style="white-space:normal">${n.body}</p></a>`)}</div>` : emptyBox('No notifications yet', 'Booking updates and replies will appear here.')}`);
  $('#mar') && ($('#mar').onclick = async () => { await api('/api/notifications/read', { method: 'POST', body: {} }); renderNotifications(box); pollNotifications(); });
  box.onclick = async e => { const a = e.target.closest('[data-n]'); if (a) { api('/api/notifications/read', { method: 'POST', body: { ids: [+a.dataset.n] } }).then(() => pollNotifications()); } };
}
route('/__404__', () => { put(view(), wrap(emptyBox('Page not found', 'That page doesn’t exist.', html`<p><a class="btn" href="#/">Back home</a></p>`))); }, { notFound: true });
