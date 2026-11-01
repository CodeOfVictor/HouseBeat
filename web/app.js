let st = null, editing = false, masterDrag = false, masterTimer;

const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
const sec = ms => (ms / 1000).toFixed(2) + ' s';

async function api(path, body) {
  await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) });
  refresh();
}
const set = (target, key, value, name) => api('/api/set', { target, key, value, name });

function card(title, meta, c, target, name, extra) {
  const volMax = target === 'output' ? 150 : 100;
  const vol = Math.round((c.volume ?? 0.5) * 100);
  const trim = c.trim_ms || 0;
  const el = document.createElement('div');
  el.className = 'card' + (c.enabled ? '' : ' off');
  el.innerHTML = `
    <div class="head">
      <div><div class="name">${title}</div><div class="meta">${meta}</div></div>
      <label class="switch"><input type="checkbox" ${c.enabled ? 'checked' : ''}><span></span></label>
    </div>
    ${extra || ''}
    <div class="row"><label>${t('volume')}</label>
      <input type="range" class="vol" min="0" max="${volMax}" value="${vol}">
      <span class="meta volv">${vol} %</span></div>
    <div class="row delrow"><label title="${esc(t('addedTitle'))}">${t('added')}</label>
      <input type="range" class="del" min="0" max="15000" step="10" value="${c.delay_ms}">
      <span><input type="number" class="deln" min="0" max="15000" step="10" value="${c.delay_ms}"> ms</span></div>
    <div class="row trimrow"><label title="${esc(t('trimTitle'))}">${t('trim')}</label>
      <span class="trimsteps">${[-20, -5].map(d => `<button data-t="${d}">${d}</button>`).join('')}
        <b class="trimv ${trim > 0 ? 'late' : trim < 0 ? 'early' : ''}" title="${trim > 0 ? esc(t('soundsLate')) : trim < 0 ? esc(t('soundsEarly')) : ''}">${trim > 0 ? '+' : ''}${trim} ms</b>
        ${[5, 20].map(d => `<button data-t="${d}">+${d}</button>`).join('')}</span></div>
    <div class="steps delsteps">
      ${[-100, -10, 10, 100].map(d => `<button data-d="${d}">${d > 0 ? '+' : ''}${d}</button>`).join('')}
      ${target === 'cast' ? `<button class="recast">${t('reconnect')}</button>` : ''}
    </div>`;
  const q = s => el.querySelector(s);
  q('.switch input').onchange = e => set(target, 'enabled', e.target.checked, name);
  let volTimer;
  q('.vol').oninput = e => {
    q('.volv').textContent = e.target.value + ' %';
    clearTimeout(volTimer);
    volTimer = setTimeout(() => set(target, 'volume', e.target.value / 100, name), 120);
  };
  q('.del').oninput = e => { q('.deln').value = e.target.value; };
  q('.del').onchange = e => set(target, 'delay_ms', +e.target.value, name);
  q('.deln').onchange = e => set(target, 'delay_ms', +e.target.value, name);
  el.querySelectorAll('[data-t]').forEach(b => b.onclick = () => set(target, 'trim_ms', trim + +b.dataset.t, name));
  el.querySelectorAll('[data-d]').forEach(b => b.onclick = () => set(target, 'delay_ms', Math.max(0, c.delay_ms + +b.dataset.d), name));
  if (q('.recast')) q('.recast').onclick = () => api('/api/recast', { name });
  el.addEventListener('pointerdown', () => editing = true);
  el.addEventListener('pointerup', () => setTimeout(() => editing = false, 300));
  return el;
}

function outputCard(dev, o) {
  const label = dev.includes('(') ? dev.slice(dev.indexOf('(') + 1, dev.lastIndexOf(')')) : dev;
  const icon = /headset|headphone|auricular|airpods|buds/i.test(dev) ? '🎧' : '🔈';
  const meta = !o.present ? t('disconnected') : o.direct ? t('directMeta') : (o.main ? t('mainOutput') : t('windowsOutput'));
  const extra = o.main ? '' :
    `<div class="steps" style="justify-content:flex-start"><button class="mkmain" title="${esc(t('makeMainTitle'))}">${t('makeMain')}</button></div>`;
  const el = card(`${icon} ${esc(label)}${o.main ? ' ★' : ''}`, esc(meta), o, 'output', dev, extra);
  const trim = o.trim_ms || 0;
  el.querySelector('.head').insertAdjacentHTML('afterend', `<div class="total">${o.direct ? t('instant') : t('outTotal', {
    total: sec(o.delay_ms + trim), added: sec(o.delay_ms), trim: trim ? t('outTrim', { trim: sec(trim) }) : '',
  })}</div>`);
  if (o.direct) el.querySelectorAll('.delrow, .trimrow, .delsteps').forEach(e => e.hidden = true);
  if (el.querySelector('.mkmain')) el.querySelector('.mkmain').onclick = () => set('output', 'main', true, dev);
  return el;
}

function castCard(name, c) {
  const icon = /nest|home|mini|speaker|audio/i.test(c.model) ? '🔊' : '📺';
  const fmt = c.format || 'mp3';
  const extra = `<div class="row"><label title="${esc(t('formatTitle'))}">${t('format')}</label>
    <select class="fmt" style="grid-column: span 2">
      <option value="mp3" ${fmt === 'mp3' ? 'selected' : ''}>${t('mp3')}</option>
      <option value="wav" ${fmt === 'wav' ? 'selected' : ''}>${t('wav')}</option></select></div>`;
  const el = card(`${icon} ${esc(name)}`, c.online ? `${esc(c.model)} · ${esc(c.host)}` : t('notFound'), c, 'cast', name, extra);
  el.querySelector('.head').insertAdjacentHTML('afterend', `<div class="total">${c.latency_ms != null
    ? t('castTotal', { total: sec(c.latency_ms), device: sec(Math.max(0, c.latency_ms - c.delay_ms)), added: sec(c.delay_ms) })
    : (c.enabled && st.active ? t('measuring') : t('off'))}</div>`);
  el.querySelector('.fmt').onchange = e => set('cast', 'format', e.target.value, name);
  return el;
}

function render() {
  $('version').textContent = 'v' + st.version;
  const act = $('active');
  act.textContent = st.active ? t('allOn') : t('allOff');
  act.className = st.active ? 'on' : '';
  $('click').className = st.click ? 'on' : '';
  $('sync').className = st.mode === 'sync' ? 'on' : '';
  $('direct').className = st.mode === 'direct' ? 'on' : '';
  $('sync').disabled = !st.virtual_device;
  $('offBanner').hidden = st.active;
  $('noVirtual').hidden = !!st.virtual_device;
  if (!masterDrag) {
    $('master').value = Math.round(st.master * 100);
    $('masterv').textContent = Math.round(st.master * 100) + ' %';
  }
  const cards = $('cards');
  cards.classList.toggle('dim', !st.active);
  cards.innerHTML = '';
  for (const [dev, o] of Object.entries(st.outputs)) cards.appendChild(outputCard(dev, o));
  for (const [name, c] of Object.entries(st.casts)) cards.appendChild(castCard(name, c));
  $('log').textContent = st.log.map(tLog).join('\n');
}

async function refresh() {
  st = await (await fetch('/api/state')).json();
  if (!editing) render();
}

function setupPrefs() {
  $('theme').value = localStorage.getItem('hb-theme') || 'auto';
  $('theme').onchange = e => {
    localStorage.setItem('hb-theme', e.target.value);
    const dark = e.target.value === 'dark' || (e.target.value === 'auto' && matchMedia('(prefers-color-scheme: dark)').matches);
    document.documentElement.dataset.theme = dark ? 'dark' : 'light';
  };
  matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    if (($('theme').value) === 'auto') $('theme').onchange({ target: $('theme') });
  });
  $('lang').value = localStorage.getItem('hb-lang') || 'auto';
  $('lang').onchange = e => {
    if (e.target.value === 'auto') localStorage.removeItem('hb-lang');
    else localStorage.setItem('hb-lang', e.target.value);
    LANG = pickLang();
    applyStaticTexts();
    if (st) render();
  };
}

$('click').onclick = () => api('/api/click');
$('master').onpointerdown = () => masterDrag = true;
$('master').onpointerup = () => setTimeout(() => masterDrag = false, 500);
$('master').oninput = e => {
  $('masterv').textContent = e.target.value + ' %';
  clearTimeout(masterTimer);
  masterTimer = setTimeout(() => set('master', null, e.target.value / 100), 120);
};
$('active').onclick = () => set('active', null, !st.active);
$('autosync').onclick = () => api('/api/autosync');
$('discover').onclick = () => api('/api/discover');
$('sync').onclick = () => api('/api/mode', { mode: 'sync' });
$('direct').onclick = () => api('/api/mode', { mode: 'direct' });
$('quit').onclick = async () => {
  await fetch('/api/quit', { method: 'POST', body: '{}' });
  document.body.innerHTML = `<h1>${t('closedTitle')}</h1><div class="sub">${t('closedText')}</div>`;
};

setupPrefs();
applyStaticTexts();
refresh();
setInterval(refresh, 3000);
