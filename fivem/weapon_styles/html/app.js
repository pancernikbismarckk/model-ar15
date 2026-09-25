// weapon_styles menu: categories as tabs, a card per style, click = wear it right away.
const resource = typeof GetParentResourceName === 'function' ? GetParentResourceName() : 'weapon_styles';
const menu = document.getElementById('menu');
const tabs = document.getElementById('tabs');
const cards = document.getElementById('cards');
const hint = document.getElementById('hint');
const mode = document.getElementById('mode');

let categories = [];
let prefs = {};
let current = null;

function post(name, body) {
  return fetch(`https://${resource}/${name}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json; charset=UTF-8' },
    body: JSON.stringify(body || {}),
  }).then((r) => r.json()).catch(() => null);
}

function labelOf(cat, id) {
  const st = cat.styles.find((s) => s.id === id);
  return st ? st.label : '';
}

function renderTabs() {
  tabs.innerHTML = '';
  for (const cat of categories) {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'tab' + (cat.key === current ? ' active' : '');
    b.setAttribute('role', 'tab');
    b.textContent = cat.label;
    const s = document.createElement('small');
    s.textContent = labelOf(cat, prefs[cat.key]);
    b.appendChild(s);
    b.onclick = () => { current = cat.key; render(); };
    tabs.appendChild(b);
  }
}

function renderCards() {
  const cat = categories.find((c) => c.key === current);
  cards.innerHTML = '';
  if (!cat) return;
  hint.textContent = cat.hint ? `Dotyczy: ${cat.hint}` : '';
  for (const st of cat.styles) {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'card' + (prefs[cat.key] === st.id ? ' selected' : '') + (st.disabled ? ' disabled' : '');
    b.setAttribute('role', 'option');
    b.setAttribute('aria-selected', prefs[cat.key] === st.id ? 'true' : 'false');

    const img = document.createElement('div');
    img.className = 'img';
    if (st.img) {
      img.style.backgroundImage = `url("${st.img}")`;
      if (st.img.endsWith('.png')) img.classList.add('contain');
    } else {
      img.textContent = st.id === 'default' ? 'GTA' : st.label;
    }
    const check = document.createElement('span');
    check.className = 'check';
    check.textContent = '✓';

    const body = document.createElement('div');
    body.className = 'body';
    const name = document.createElement('div');
    name.className = 'name';
    name.textContent = st.label;
    const variant = document.createElement('div');
    variant.className = 'variant';
    variant.textContent = st.variant || '';
    const desc = document.createElement('div');
    desc.className = 'desc';
    desc.textContent = st.disabled ? (st.why || '') : (st.desc || '');
    body.append(name, variant, desc);
    b.append(img, check, body);

    b.onclick = async () => {
      if (st.disabled || prefs[cat.key] === st.id) return;
      prefs[cat.key] = st.id;
      render();
      const res = await post('select', { category: cat.key, id: st.id });
      if (res && res.prefs) { prefs = res.prefs; render(); }
    };
    cards.appendChild(b);
  }
}

function render() {
  renderTabs();
  renderCards();
}

function open(data) {
  categories = data.categories || [];
  prefs = data.prefs || {};
  if (!current || !categories.some((c) => c.key === current)) current = categories.length ? categories[0].key : null;
  mode.textContent = data.mode === 'native'
    ? 'Tryb natywny: gra odtwarza styl sama (chód, bieg, przejścia do celowania).'
    : 'Tryb skryptowy: styl nakładany na górną część ciała.';
  render();
  menu.classList.remove('hidden');
  menu.setAttribute('aria-hidden', 'false');
}

function close() {
  menu.classList.add('hidden');
  menu.setAttribute('aria-hidden', 'true');
}

window.addEventListener('message', (e) => {
  const d = e.data || {};
  if (d.action === 'open') open(d);
  else if (d.action === 'close') close();
});

document.getElementById('close').onclick = () => { close(); post('close'); };

window.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && !menu.classList.contains('hidden')) {
    close();
    post('close');
  }
});
