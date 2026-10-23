'use strict';
(async function () {
  try { await loadBoot(); }
  catch (e) { put($('#app'), html`<div class="container" style="padding:80px 0"><div class="empty"><b>We can’t reach the salon system</b>${e.message}<p><button class="btn" onclick="location.reload()">Try again</button></p></div></div>`); return; }
  window.addEventListener('hashchange', render);
  if (App.user) every(() => pollNotifications(), 20000);
  render();
  setInterval(() => { if (App.user) pollNotifications(); }, 20000);
})();
