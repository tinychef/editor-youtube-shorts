// Deterministic overlay timeline, rendered by headless Chromium one frame at a time.
//   window.__frame(t)  → applies the state for time t and returns a signature string; equal signatures
//                        mean identical pixels, so the renderer reuses the previous screenshot.
//   window.__events()  → sound cues [{t, sfx, dur}] declared by items and their animated children.
// Every animation is a pure function of t (no CSS transitions), so any frame renders on its own.
(function () {
  'use strict';
  const TL = window.TL;
  const LAYER = TL.layer;
  const stage = document.getElementById('stage');
  const clamp = (x, a = 0, b = 1) => (x < a ? a : x > b ? b : x);
  const E = {
    lin: clamp,
    out: (x) => 1 - Math.pow(1 - clamp(x), 3),
    in: (x) => Math.pow(clamp(x), 3),
    inout: (x) => { x = clamp(x); return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; },
    back: (x, s = 1.7) => { x = clamp(x) - 1; return 1 + (s + 1) * x * x * x + s * x * x; },
  };
  const q = (x) => Math.round(x * 500) / 500;
  const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const num = (x, d) => (x === undefined || x === null || x === '' ? d : +x);

  // ── logos ──────────────────────────────────────────────────────────────────
  function tile(L, size = 96, cls = '') {
    if (!L) return '';
    const r = Math.round(size * 0.24);
    const box = `width:${size}px;height:${size}px;border-radius:${r}px`;
    if (L.kind === 'svg') {
      return `<div class="logo ${cls}" style="${box};background:${L.bg}"><svg viewBox="0 0 24 24" style="width:${size * 0.56}px;height:${size * 0.56}px"><path fill="${L.fg}" d="${L.path}"/></svg></div>`;
    }
    if (L.kind === 'img') {
      const s = L.fill ? size : Math.round(size * 0.74);
      return `<div class="logo img ${cls}" style="${box};background:${L.bg || '#fff'}"><img src="${L.src}" style="width:${s}px;height:${s}px;object-fit:${L.fill ? 'cover' : 'contain'}"></div>`;
    }
    return `<div class="logo mono ${cls}" style="${box};background:${L.bg};color:${L.fg};font-size:${Math.round(size * (String(L.text).length > 2 ? 0.3 : 0.4))}px">${esc(L.text)}</div>`;
  }

  window.__tile = tile;

  // ── number formatting for count-ups: "$59,523" "4.9" "+103" "12 h" ──────────
  function parseNum(s) {
    const m = String(s).match(/^(\D*?)(\d[\d.,]*)(.*)$/);
    if (!m) return null;
    let body = m[2], sep = '', dec = 0, dp = '.';
    if (/^\d{1,3}(,\d{3})+(\.\d+)?$/.test(body)) { sep = ','; }
    else if (/^\d{1,3}(\.\d{3})+(,\d+)?$/.test(body)) { sep = '.'; dp = ','; }
    const norm = sep === ',' ? body.replace(/,/g, '') : sep === '.' ? body.replace(/\./g, '').replace(',', '.') : body.replace(',', '.');
    const di = norm.indexOf('.');
    if (di >= 0) dec = norm.length - di - 1;
    return { pre: m[1], v: parseFloat(norm), post: m[3], sep, dec, dp };
  }
  function fmtNum(P, v) {
    let s = v.toFixed(P.dec);
    let [a, b] = s.split('.');
    if (P.sep) a = a.replace(/\B(?=(\d{3})+(?!\d))/g, P.sep);
    return P.pre + a + (b ? P.dp + b : '') + P.post;
  }

  // ── components: return HTML; [data-in] children animate on their own ────────
  const C = {};
  const kid = (kind, at, dur, extra = '') => `data-in="${kind}" data-at="${(+at).toFixed(3)}"${dur !== undefined ? ` data-dur="${(+dur).toFixed(3)}"` : ''} ${extra}`;

  C.hook = (p) => {
    const lines = p.lines || [p.text || ''];
    const acc = new Set(p.accent ?? [lines.length - 1]);
    let k = 0;
    const st = p.stagger ?? 0.06;
    const body = lines.map((ln, i) => `<div class="hook-line ${acc.has(i) ? 'acc' : ''}">` +
      String(ln).split(/\s+/).map((w) => `<span class="hw" ${kid('pop', st * k++, 0.3)}>${esc(w)}</span>`).join(' ') + '</div>').join('');
    return `<div class="hook ${p.style === 'box' ? 'box' : ''}" style="${p.size ? `--hs:${p.size}px` : ''}">${body}</div>`;
  };

  C.title = (p) => `<div class="title ${p.style || ''}" style="${p.size ? `--ts:${p.size}px;` : ''}${p.color ? `color:${p.color};` : ''}">` +
    `${(p.lines || [p.text]).map((l, i) => `<div class="${(p.accent || []).includes(i) ? 'acc' : ''}">${esc(l)}</div>`).join('')}` +
    `${p.sub ? `<div class="title-sub">${esc(p.sub)}</div>` : ''}</div>`;

  C.section = (p) => p.style === 'big'
    ? `<div class="sec-big"><span class="sec-n">${esc(p.n)}</span><span class="sec-dot">·</span>${esc(p.title || p.label || '')}</div>`
    : `<div class="sec-chip"><span class="sec-num">${esc(p.n)}</span><span class="sec-txt">${p.of ? `de ${esc(p.of)}` : ''}${p.label ? `${p.of ? ' · ' : ''}${esc(p.label)}` : ''}</span>` +
      `${p.right ? `<span class="pill dark sm sec-right">${esc(p.right)}</span>` : ''}</div>`;

  C.app = (p) => {
    const st = p.states || [];
    const cancel = st.find((s) => s.state === 'cancelado' || s.state === 'cancel');
    const free = st.find((s) => s.state === 'gratis' || s.state === 'free');
    const strike = cancel || free;
    return `<div class="card app ${p.dark ? 'dark' : ''}">` +
      `<div class="app-l" ${cancel ? kid('dim', cancel.t, 0.35) : ''}>${tile(p.logo, 112)}<div class="app-mid"><div class="app-name">${esc(p.name)}</div>` +
      `${p.sub ? `<div class="app-sub">${esc(p.sub)}</div>` : ''}` +
      `${cancel ? `<span class="pill danger sm app-tag" ${kid('pop', cancel.t + 0.1, 0.3, 'data-sfx="buzz"')}>${esc(cancel.label || 'cancelado')}</span>` : ''}</div></div>` +
      `<div class="app-r"><div class="app-price ${strike ? 'strike' : ''}" ${strike ? kid('strike', strike.t, 0.3) : ''}>${esc(p.price || '')}</div>` +
      `${p.per ? `<div class="app-per">${esc(p.per)}</div>` : ''}` +
      `${free ? `<span class="pill acc big app-free" ${kid('pop', free.t + 0.25, 0.35, 'data-sfx="cash"')}>${esc(free.label || p.free || '$0')}</span>` : ''}</div></div>`;
  };

  C.logos = (p) => {
    const st = p.stagger ?? 0.12, size = p.size || 124;
    return `<div class="logos ${p.card ? 'card' : ''}">${p.title ? `<div class="logos-title">${esc(p.title)}</div>` : ''}<div class="logos-row">` +
      (p.items || []).map((x, i) => `<div class="lg" ${kid('pop', (p.at0 ?? 0) + st * i, 0.32, 'data-sfx="pop"')}>${tile(x.logo, size)}${x.label ? `<div class="lg-l">${esc(x.label)}</div>` : ''}</div>`).join('') +
      `</div></div>`;
  };

  C.logo = (p) => `<div class="logo-big">${tile(p.logo, p.size || 230)}${p.name ? `<div class="lb-name">${esc(p.name)}</div>` : ''}${p.sub ? `<div class="lb-sub">${esc(p.sub)}</div>` : ''}</div>`;

  C.list = (p) => {
    const S = p.strike_t, n = (p.rows || []).length, step = 0.12;
    const rows = (p.rows || []).map((r, i) => `<div class="lr" ${kid('up', 0.12 + i * 0.09, 0.3)}><span class="lr-i">${i + 1}</span>${r.logo ? tile(r.logo, 56) : ''}<span class="lr-n" ${S != null ? kid('dim', S + i * step, 0.3) : ''}>${esc(r.name)}</span>` +
      `<span class="lr-v ${S != null ? 'strike' : ''}" ${S != null ? kid('strike', S + i * step, 0.25) : ''}>${esc(r.value || '')}</span>` +
      `${S != null ? `<span class="pill acc sm lr-free" ${kid('pop', S + i * step + 0.12, 0.3, 'data-sfx="pop"')}>${esc(p.free || '$0')}</span>` : ''}</div>`).join('');
    const tot = p.total ? `<div class="lt"><span class="lt-l">${esc(p.total.label || 'TOTAL')}</span><span class="lt-v"><span class="lt-a" ${S != null ? kid('out', S + n * step + 0.1, 0.2) : ''}>${esc(p.total.value)}</span>` +
      `${S != null ? `<span class="lt-b" ${kid('pop', S + n * step + 0.2, 0.3)}>${esc(p.total.free || p.free || '$0')}</span>` : ''}</span>` +
      `${p.savings ? `<span class="pill dark lt-s" ${kid('pop', (S ?? 0) + n * step + 0.45, 0.35, 'data-sfx="cash"')}>${esc(p.savings.label || '')} <b>${esc(p.savings.value)}</b></span>` : ''}</div>` : '';
    return `<div class="card list ${p.dark ? 'dark' : ''}"><div class="list-h"><b>${esc(p.title || '')}</b>${p.badge ? `<span class="pill acc xs">${esc(p.badge)}</span>` : ''}<span class="list-u">${esc(p.unit || '')}</span></div>${rows}${tot}</div>`;
  };

  C.repo = (p) => {
    const [owner, name] = String(p.repo || '').includes('/') ? p.repo.split('/') : ['', p.repo || ''];
    return `<div class="card repo ${p.dark === false ? '' : 'dark'}"><div class="repo-top">${tile(p.logo, 88)}<div class="repo-id"><div class="repo-name">${owner ? `<span class="repo-o">${esc(owner)}/</span>` : ''}${esc(name)}</div>` +
      `${p.desc ? `<div class="repo-desc">${esc(p.desc)}</div>` : ''}</div>` +
      `${p.badge ? `<span class="pill acc big repo-badge" ${kid('pop', p.badge_t ?? 0.55, 0.35, 'data-sfx="pop"')}>${esc(p.badge)}</span>` : ''}</div>` +
      `<div class="repo-meta">${p.stars ? `<span>★ <b ${kid('count', 0.2, p.count_dur ?? 1.0, `data-to="${esc(p.stars)}" data-sfx="tick"`)}>${esc(p.stars)}</b></span>` : ''}` +
      `${p.forks ? `<span>⑂ ${esc(p.forks)}</span>` : ''}${p.license ? `<span>⚖ ${esc(p.license)}</span>` : ''}` +
      `${p.lang ? `<span><i class="dot" style="background:${p.lang_color || '#3178c6'}"></i>${esc(p.lang)}</span>` : ''}</div></div>`;
  };

  C.browser = (p) => `<div class="card browser"><div class="bar"><i></i><i></i><i></i><div class="tab">${esc(p.title || p.url || '')}</div></div>` +
    `${p.url ? `<div class="url">🔒&nbsp;${esc(p.url)}</div>` : ''}` +
    `<div class="view" style="height:${p.height || 700}px"><img src="${p.image}" ${p.scroll ? kid('scroll', p.scroll_t ?? 0.8, p.scroll_dur ?? 3.0, `data-to="${p.scroll}"`) : ''}>` +
    `${(p.marks || []).map((m) => `<div class="mark" style="left:${m.x}%;top:${m.y}%;width:${m.w}%;height:${m.h}%" ${kid('grow', m.t ?? 1.0, 0.35)}></div>`).join('')}</div>` +
    `${(p.chips || []).map((c, i) => `<span class="pill dark br-chip" style="${i % 2 ? 'right' : 'left'}:26px;bottom:${26 + Math.floor(i / 2) * 64}px" ${kid('pop', c.t ?? 1.0 + 0.35 * i, 0.3, 'data-sfx="pop"')}>${esc(c.text ?? c)}</span>`).join('')}</div>`;

  C.terminal = (p) => {
    let t = p.t0 ?? 0.35, h = '';
    const cps = p.cps || 30;
    for (const ln of p.lines || []) {
      if (ln.cmd) {
        const d = ln.cmd.length / cps;
        h += `<div class="tl"><span class="pr">$</span> <span class="ty" ${kid('type', t, d, `data-text="${esc(ln.cmd)}" data-sfx="type"`)}>${esc(ln.cmd)}</span></div>`;
        t += d + 0.3;
      }
      for (const o of ln.out || []) {
        h += `<div class="to ${/^(✓|✔|ok)/i.test(o) ? 'ok' : ''}" ${kid('fade', t, 0.12)}>${esc(o)}</div>`;
        t += 0.2;
      }
    }
    return `<div class="card term dark"><div class="bar"><i></i><i></i><i></i><div class="tab mono">${esc(p.title || 'terminal')}</div></div><div class="term-b mono">${h}</div></div>`;
  };

  C.search = (p) => {
    const d = String(p.query || '').length / (p.cps || 22);
    return `<div class="card search"><div class="s-box">${p.logo ? tile(p.logo, 54) : '<span class="s-ico">⌕</span>'}` +
      `<span class="mono s-q ty" ${kid('type', p.t0 ?? 0.3, d, `data-text="${esc(p.query)}" data-sfx="type"`)}>${esc(p.query)}</span></div>` +
      `${p.hint ? `<div class="s-hint mono">⠿ ${esc(p.hint)}</div>` : ''}</div>`;
  };

  C.checklist = (p) => `<div class="card check ${p.dark ? 'dark' : ''}">${p.title ? `<div class="ck-t mono">${esc(p.title)}</div>` : ''}` +
    (p.items || []).map((x, i) => `<div class="ck" ${kid('up', (p.t0 ?? 0.25) + i * (p.every ?? 0.45), 0.25, 'data-sfx="tick"')}><span class="ck-b">✓</span><span>${esc(x)}</span></div>`).join('') + '</div>';

  C.stat = (p) => {
    const items = p.items || [p];
    return `<div class="stats">` + items.map((s, i) => `<div class="card stat ${s.dark ?? p.dark ? 'dark' : ''}"><div class="st-l">${esc(s.label || '')}</div>` +
      `<div class="st-v"><span ${kid('count', (p.t0 ?? 0.15) + i * 0.25, s.count_dur ?? 0.9, `data-to="${esc(s.value)}" data-sfx="tick"`)}>${esc(s.value)}</span>${s.unit ? `<span class="st-u">${esc(s.unit)}</span>` : ''}</div>` +
      `${s.sub ? `<div class="st-s">${esc(s.sub)}</div>` : ''}</div>`).join('') + '</div>';
  };

  C.badge = (p) => `<div class="pill badge ${p.color || 'acc'}" style="font-size:${p.size || 46}px;transform:rotate(${num(p.tilt, -6)}deg)">${esc(p.text)}</div>`;

  C.stamp = (p) => `<div class="stamp" style="--c:${p.color || 'var(--danger)'};font-size:${p.size || 100}px;transform:rotate(${num(p.tilt, -8)}deg)">${esc(p.text)}</div>`;

  C.compare = (p) => `<div class="card cmp">${tile(p.logo, 104)}<div class="cmp-n">${esc(p.name || '')}${p.per ? `<div class="cmp-per">${esc(p.per)}</div>` : ''}</div>` +
    `<span class="cmp-from strike" ${kid('strike', p.strike_t ?? 0.55, 0.3, 'data-sfx="cash"')}>${esc(p.from)}</span>` +
    `<span class="pill acc cmp-to" ${kid('pop', (p.strike_t ?? 0.55) + 0.25, 0.35)}>${esc(p.to ?? '$0')}</span></div>`;

  C.chat = (p) => `<div class="card chat">${p.title ? `<div class="chat-h">${p.logo ? tile(p.logo, 46) : ''}<b>${esc(p.title)}</b></div>` : ''}` +
    (p.messages || []).map((m, i) => `<div class="msg ${m.who === 'user' ? 'me' : 'ai'}" ${kid('up', m.t ?? 0.3 + i * 0.8, 0.25, 'data-sfx="pop"')}>${esc(m.text)}</div>`).join('') + '</div>';

  C.image = (p) => `<div class="card img-card" style="width:${p.w || 920}px">${p.title ? `<div class="img-t">${esc(p.title)}</div>` : ''}<img src="${p.src}" style="${p.h ? `height:${p.h}px;object-fit:cover;` : ''}">${p.caption ? `<div class="img-c">${esc(p.caption)}</div>` : ''}</div>`;

  C.cta = (p) => `<div class="card cta"><div class="cta-1">${esc(p.lead || 'Comenta')}</div><div class="cta-kw" ${kid('pop', 0.3, 0.4, 'data-sfx="ding"')}>${esc(p.keyword)}</div>` +
    `<div class="cta-2">${esc(p.text || 'y te lo mando por DM')}</div>${p.sub ? `<div class="cta-3">${esc(p.sub)}</div>` : ''}<div class="cta-arrow" ${kid('down', 0.8, 0.35)}>↓</div></div>`;

  C.cursor = (p) => `<div class="cursor"><svg viewBox="0 0 64 64" width="${p.size || 120}" height="${p.size || 120}"><path d="M22 6c-3 0-5 2-5 5v26l-4-4c-2-2-6-2-8 0s-2 5 0 7l14 15c3 3 7 5 11 5h9c9 0 16-7 16-16V31c0-3-2-5-5-5s-5 2-5 5v-3c0-3-2-5-5-5s-5 2-5 5v-2c0-3-2-5-5-5-1 0-2 0-3 1V11c0-3-2-5-5-5z" fill="#fff" stroke="#111" stroke-width="3" stroke-linejoin="round"/></svg>` +
    `<div class="ripple" ${kid('ripple', p.click_t ?? 0.45, 0.5, 'data-sfx="click"')}></div></div>`;

  C.arrow = (p) => {
    const [x1, y1] = p.from, [x2, y2] = p.to;
    const mx = (x1 + x2) / 2 + (y2 - y1) * (p.curve ?? 0.25), my = (y1 + y2) / 2 - (x2 - x1) * (p.curve ?? 0.25);
    const a = Math.atan2(y2 - my, x2 - mx), L = 34;
    const h1 = [x2 - L * Math.cos(a - 0.5), y2 - L * Math.sin(a - 0.5)], h2 = [x2 - L * Math.cos(a + 0.5), y2 - L * Math.sin(a + 0.5)];
    const col = p.color || 'var(--danger)';
    return `<svg class="arrow" width="${TL.W}" height="${TL.H}" viewBox="0 0 ${TL.W} ${TL.H}"><path d="M${x1} ${y1} Q${mx} ${my} ${x2} ${y2}" pathLength="1" stroke="${col}" ${kid('draw', 0, p.dur ?? 0.45)}/>` +
      `<path d="M${h1[0]} ${h1[1]} L${x2} ${y2} L${h2[0]} ${h2[1]}" pathLength="1" stroke="${col}" ${kid('draw', (p.dur ?? 0.45) - 0.05, 0.15)}/></svg>` +
      `${p.label ? `<div class="arrow-l" style="left:${x1}px;top:${y1}px">${esc(p.label)}</div>` : ''}`;
  };

  C.scrim = (p) => `<div class="scrim ${p.side || 'top'}" style="height:${p.height || 900}px"></div>`;
  C.html = (p) => `${p.css ? `<style>${p.css}</style>` : ''}${p.html || ''}`;

  // ── build ────────────────────────────────────────────────────────────────
  const ITEMS = [];
  TL.items.forEach((it, order) => {
    const el = document.createElement('div');
    el.className = `item it-${it.type} ${it.cls || ''}`;
    if (it.w) el.style.width = it.w + 'px';
    el.innerHTML = (C[it.type] || C.html)(it.props || {}, it);
    if (it.layer !== LAYER) el.style.visibility = 'hidden';
    stage.appendChild(el);
    it.el = el;
    it.order = order;
    it.kids = [...el.querySelectorAll('[data-in]')].map((k) => ({
      el: k, kind: k.dataset.in, at: +k.dataset.at || 0, dur: num(k.dataset.dur, 0.3), sfx: k.dataset.sfx,
      text: k.dataset.text, to: k.dataset.to, P: k.dataset.in === 'count' ? parseNum(k.dataset.to) : null,
    }));
    ITEMS.push(it);
  });
  const capEl = document.createElement('div');
  capEl.className = 'cap';
  stage.appendChild(capEl);
  if (LAYER !== 'over') capEl.style.visibility = 'hidden';

  // ── animation kinds (p: 0 → 1 = hidden → shown) ──────────────────────────
  function fx(kind, p) {
    switch (kind) {
      case 'none': return {};
      case 'fade': return { o: E.lin(p) };
      case 'pop': return { o: clamp(p * 4), s: 0.5 + 0.5 * E.back(p) };
      case 'up': return { o: clamp(p * 2.2), ty: (1 - E.out(p)) * 70 };
      case 'down': return { o: clamp(p * 2.2), ty: -(1 - E.out(p)) * 70 };
      case 'left': return { o: clamp(p * 2.2), tx: -(1 - E.out(p)) * 120 };
      case 'right': return { o: clamp(p * 2.2), tx: (1 - E.out(p)) * 120 };
      case 'zoom': return { o: clamp(p * 2), s: 1.3 - 0.3 * E.out(p) };
      case 'stamp': return { o: clamp(p * 3), s: 2.2 - 1.2 * E.out(p) };
      case 'rise': return { o: clamp(p * 2), ty: (1 - E.out(p)) * 520 };
      default: return { o: E.lin(p) };
    }
  }
  function applyBox(el, a, b) {
    const o = (a.o ?? 1) * (b.o ?? 1), s = (a.s ?? 1) * (b.s ?? 1);
    const tx = (a.tx || 0) + (b.tx || 0), ty = (a.ty || 0) + (b.ty || 0);
    el.style.opacity = o;
    return [o, s, tx, ty];
  }

  function kidFrame(k, lt) {
    const p = clamp((lt - k.at) / Math.max(k.dur, 1e-3));
    const el = k.el;
    switch (k.kind) {
      case 'type': {
        const n = Math.round(p * k.text.length);
        const caret = p < 1 && Math.floor(lt * 2.5) % 2 === 0;
        const html = esc(k.text.slice(0, n)) + (p > 0 && p < 1 ? `<span class="caret" style="opacity:${caret ? 1 : 0}">▍</span>` : '');
        if (el._h !== html) { el.innerHTML = html; el._h = html; }
        el.style.visibility = p > 0 || lt >= k.at ? 'visible' : 'hidden';
        return n + (caret ? 'c' : '');
      }
      case 'count': {
        if (!k.P) return 'x';
        const v = k.P.v * E.out(p);
        const s = fmtNum(k.P, p >= 1 ? k.P.v : v);
        if (el._h !== s) { el.textContent = s; el._h = s; }
        return s;
      }
      case 'strike': el.style.setProperty('--p', E.out(p)); return q(p);
      case 'dim': el.style.opacity = 1 - 0.58 * E.inout(p); return q(p);
      case 'out': el.style.opacity = 1 - E.lin(p); return q(p);
      case 'grow': el.style.transform = `scaleX(${E.out(p)})`; el.style.opacity = p > 0 ? 1 : 0; return q(p);
      case 'scroll': {
        const view = el.parentElement.clientHeight, H = el.naturalHeight ? el.clientHeight : 0;
        el.style.transform = `translateY(${-E.inout(p) * (+k.to || 0) * Math.max(0, H - view)}px)`;
        return q(p);
      }
      case 'draw': el.style.strokeDasharray = '1'; el.style.strokeDashoffset = String(1 - E.inout(p)); el.style.opacity = p > 0 ? 1 : 0; return q(p);
      case 'ripple': el.style.opacity = p > 0 && p < 1 ? 1 - p : 0; el.style.transform = `translate(-50%,-50%) scale(${0.2 + 1.3 * E.out(p)})`; return q(p);
      default: {
        const f = fx(k.kind, p);
        el.style.opacity = f.o ?? 1;
        el.style.transform = `translate(${f.tx || 0}px,${f.ty || 0}px) scale(${f.s ?? 1})`;
        return q(p);
      }
    }
  }

  // ── placement ──────────────────────────────────────────────────────────
  const REFLOW = 0.35, GAP = 26;
  const CHANGES = [...new Set(ITEMS.filter((i) => i.place === 'stack' || i.place === 'header').flatMap((i) => [i.t0, i.t1]))].sort((a, b) => a - b);
  const posCache = new Map();
  function stackAt(t) {
    const key = q(t);
    if (posCache.has(key)) return posCache.get(key);
    const groups = {};
    for (const it of ITEMS) if (it.place === 'stack' && t >= it.t0 && t < it.t1) (groups[it.zid] ||= []).push(it);
    const pos = new Map();
    for (const zid in groups) {
      const g = groups[zid].sort((a, b) => a.t0 - b.t0 || a.order - b.order);
      const Z = g[0].zone;
      const hdr = ITEMS.find((h) => h.place === 'header' && h.zid === g[0].zid && t >= h.t0 && t < h.t1);
      const top = Z.top[0] + (hdr ? hdr.h + 34 : 0), bot = Z.top[1];
      const total = g.reduce((s, it) => s + it.h, 0) + GAP * (g.length - 1);
      let y = Z.align === 'top' || total > bot - top ? top : top + (bot - top - total) / 2;
      for (const it of g) { pos.set(it.id, y); y += it.h + GAP; }
    }
    posCache.set(key, pos);
    return pos;
  }
  function stackY(it, t) {
    const now = stackAt(t).get(it.id);
    let tc = -1;
    for (const c of CHANGES) { if (c <= t + 1e-9) tc = c; else break; }
    if (tc < 0 || t - tc >= REFLOW || tc <= it.t0 + 1e-6) return now;
    const before = stackAt(tc - 1e-3).get(it.id);
    if (before === undefined) return now;
    return before + (now - before) * E.inout((t - tc) / REFLOW);
  }
  function itemBox(it, t) {
    const Z = it.zone, w = it.w0, h = it.h;
    let x = (TL.W - w) / 2 + (it.dx || 0), y = 0;
    switch (it.place) {
      case 'stack': y = stackY(it, t); break;
      case 'header': y = Z.top[0]; break;
      case 'title': y = (it.y ?? Z.title) - h / 2; break;
      case 'cap': y = (it.y ?? Z.cap) - h / 2; break;
      case 'full': x = 0; y = 0; break;
      case 'abs': {
        const [ax, ay] = it.anchor || [0.5, 0.5];
        if (it.attach) {
          const tgt = ITEMS.find((o) => o.id === it.attach);
          if (tgt && tgt._box) {
            const [cx, cy] = it.corner || [1, 0];
            x = tgt._box.x + tgt._box.w * cx - w * ax + (it.dx || 0);
            y = tgt._box.y + tgt._box.h * cy - h * ay + (it.dy || 0);
            break;
          }
        }
        x = (it.x ?? TL.W / 2) - w * ax;
        y = (it.y ?? TL.H / 2) - h * ay;
        break;
      }
    }
    if (it.y !== undefined && it.place !== 'abs' && it.place !== 'title' && it.place !== 'cap') y = it.y;
    return { x, y, w, h };
  }

  // ── captions ────────────────────────────────────────────────────────────
  const CAP = TL.captions || { chunks: [], mute: [] };
  function zoneAt(t) {
    for (const s of TL.layout) if (t >= s.t0 && t < s.t1) return s.zone;
    return TL.layout.length ? TL.layout[TL.layout.length - 1].zone : { cap: TL.H * 0.75, capOn: 'speaker' };
  }
  function capFrame(t) {
    const hide = () => { capEl.style.opacity = 0; return 'c-'; };
    if (!CAP.chunks.length || LAYER !== 'over') return hide();
    if ((CAP.mute || []).some(([a, b]) => t >= a && t < b)) return hide();
    let lo = 0, hi = CAP.chunks.length - 1, k = -1;
    while (lo <= hi) { const m = (lo + hi) >> 1; if (CAP.chunks[m].t0 <= t) { k = m; lo = m + 1; } else hi = m - 1; }
    if (k < 0 || t >= CAP.chunks[k].t1) return hide();
    const ch = CAP.chunks[k];
    if (capEl._k !== k) {
      capEl.innerHTML = ch.words.map((w) => `<span class="w${w.e ? ' em' : ''}">${esc(w.w)}</span>`).join(' ');
      capEl._k = k;
    }
    let ai = -1;
    ch.words.forEach((w, i) => { if (w.t0 <= t) ai = i; });
    if (CAP.style.karaoke) [...capEl.children].forEach((s, i) => s.classList.toggle('on', i === ai));
    const Z = zoneAt(t);
    capEl.className = 'cap ' + (Z.capOn === 'bg' ? 'on-bg' : 'on-sp') + (CAP.style.karaoke ? ' kara' : '');
    const p = clamp((t - ch.t0) / 0.13);
    const s = CAP.style.pop === false ? 1 : 0.84 + 0.16 * E.back(p, 2.2);
    capEl.style.opacity = 1;
    const h = capEl.offsetHeight;
    const cy = ch.y ?? CAP.style.y ?? Z.cap;
    capEl.style.transform = `translate(0px,${cy - h / 2}px) scale(${s})`;
    return `c${k}:${CAP.style.karaoke ? ai : ''}:${q(p)}:${Z.capOn}:${cy}`;
  }

  // ── frame ───────────────────────────────────────────────────────────────
  window.__frame = function (t) {
    const sig = [];
    for (const it of ITEMS) {
      const on = t >= it.t0 && t < it.t1;
      if (!on) {
        if (it.el.style.display !== 'none') it.el.style.display = 'none';
        it._box = null;
        continue;
      }
      if (it.el.style.display === 'none') it.el.style.display = '';
      const lt = t - it.t0;
      const pin = it.in[1] > 0 ? clamp(lt / it.in[1]) : 1, pout = it.out[1] > 0 ? clamp((it.t1 - t) / it.out[1]) : 1;
      const b = itemBox(it, t);
      it._box = b;
      const [o, s, tx, ty] = applyBox(it.el, fx(it.in[0], pin), fx(it.out[0], pout));
      it.el.style.transform = `translate(${Math.round((b.x + tx) * 10) / 10}px,${Math.round((b.y + ty) * 10) / 10}px) scale(${s})`;
      let ks = '';
      for (const k of it.kids) ks += kidFrame(k, lt) + ',';
      if (it.layer === LAYER || it.attachSig) sig.push(`${it.id}:${q(o)}:${q(s)}:${Math.round(b.x + tx)}:${Math.round(b.y + ty)}:${ks}`);
    }
    sig.push(capFrame(t));
    const visible = sig.filter((x) => x !== 'c-');
    return visible.length ? sig.join('|') : '';
  };

  window.__events = function () {
    const ev = [];
    for (const it of ITEMS) {
      if (it.sfx) ev.push({ t: it.t0, sfx: it.sfx });
      for (const k of it.kids) {
        if (!k.sfx || it.t0 + k.at >= it.t1) continue;
        const d = k.kind === 'type' || k.kind === 'count' ? k.dur : 0;
        ev.push({ t: it.t0 + k.at, sfx: k.sfx, dur: d });
      }
    }
    return ev.sort((a, b) => a.t - b.t);
  };

  // measure once fonts and images are ready
  window.__ready = (async () => {
    await document.fonts.ready;
    await Promise.all([...document.images].map((im) => (im.complete ? 0 : new Promise((r) => { im.onload = im.onerror = r; }))));
    for (const it of ITEMS) {
      it.el.style.display = '';
      it.el.style.transform = 'none';
      // titles never wrap mid-phrase: shrink a line until it fits the safe width
      for (const ln of it.el.querySelectorAll('.hook-line, .fit')) {
        let fs = parseFloat(getComputedStyle(ln).fontSize);
        while (ln.scrollWidth > ln.clientWidth + 1 && fs > 30) { fs -= 2; ln.style.fontSize = fs + 'px'; }
      }
      it.w0 = it.el.offsetWidth;
      it.h = it.el.offsetHeight;
      it.el.style.display = 'none';
    }
    return ITEMS.map((it) => ({ id: it.id, w: it.w0, h: it.h }));
  })();
})();
