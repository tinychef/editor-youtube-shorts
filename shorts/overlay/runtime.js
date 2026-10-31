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
    // damped spring (iOS-like): ~15% overshoot, settles at x = 1
    spring: (x) => (x <= 0 ? 0 : x >= 1 ? 1 : 1 - Math.exp(-6.5 * x) * Math.cos(11 * x)),
  };
  // seeded random numbers (mulberry32): particles look random but every render draws the same ones
  function rng(seed) {
    let a = (seed >>> 0) || 1;
    return () => { a = (a + 0x6D2B79F5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  }
  const FX = [];          // per-component data that kidFrame needs (particles, chart points…), referenced by data-fx
  const fxId = (data) => FX.push(data) - 1;
  let uid = 0;
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
    else if (/^\d+,\d+$/.test(body)) { dp = ','; }      // decimal comma: "1,2k"
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

  // ── motion graphics (iOS / Instagram) ────────────────────────────────────
  const IG = ['#FF7A00', '#FF0069', '#D300C5', '#7638FA'];
  const pct = (v) => { const n = parseFloat(String(v ?? 0).replace(',', '.')); return isNaN(n) ? 0 : n; };
  const HEART = 'M12 21.2c-.4 0-.8-.1-1.1-.4C6.6 17.1 2 13.3 2 8.6 2 5.5 4.4 3 7.4 3c1.9 0 3.6 1 4.6 2.6C13 4 14.7 3 16.6 3 19.6 3 22 5.5 22 8.6c0 4.7-4.6 8.5-8.9 12.2-.3.3-.7.4-1.1.4z';
  const STAR = 'M12 0C12.9 7.6 16.4 11.1 24 12 16.4 12.9 12.9 16.4 12 24 11.1 16.4 7.6 12.9 0 12 7.6 11.1 11.1 7.6 12 0z';

  // iOS notification banner (drops from the top)
  C.notif = (p) => `<div class="notif">${p.logo ? tile(p.logo, 92, 'nt-ico') : ''}<div class="nt-body">` +
    `<div class="nt-top"><b class="nt-title">${esc(p.title || p.app || '')}</b><span class="nt-time">${esc(p.time ?? 'ahora')}</span></div>` +
    `${p.text ? `<div class="nt-text">${esc(p.text)}</div>` : ''}</div></div>`;

  // iMessage thread: «escribiendo…» (three bouncing dots) before every bubble
  C.imessage = (p) => {
    const typing = p.typing ?? 0.75;
    let t = p.t0 ?? 0.3;
    const rows = (p.messages || []).map((m, i) => {
      const me = m.who === 'me' || m.who === 'user';
      const ty = m.typing ?? typing;
      t = m.t ?? (i ? t + 0.55 + ty : t + ty);
      const t1 = Math.max(0, t - ty);       // the dots run until the bubble lands
      const dots = t - t1 > 0.15 ? `<div class="im-typing" ${kid('typing', t1, t - t1)}><i></i><i></i><i></i></div>` : '';
      return `<div class="im-row ${me ? 'me' : 'them'}">${dots}<div class="im-b" ${kid('bubble', t, 0.32, 'data-sfx="bubble"')}>${esc(m.text)}</div></div>`;
    }).join('');
    const head = p.title ? `<div class="im-h">${p.logo ? tile(p.logo, 72, 'im-av') : `<span class="im-av mono-av">${esc(String(p.title).slice(0, 1))}</span>`}<b>${esc(p.title)}</b>${p.sub ? `<span>${esc(p.sub)}</span>` : ''}</div>` : '';
    return `<div class="card imsg" style="${p.color ? `--bubble-me:${p.color};` : ''}">${head}<div class="im-list">${rows}</div></div>`;
  };

  // iOS switches turning on (Settings-style group)
  C.toggle = (p) => {
    const items = p.items || [{ label: p.label, sub: p.sub, logo: p.logo, t: p.on_t }];
    return `<div class="card toggles">${p.title ? `<div class="tg-h">${esc(p.title)}</div>` : ''}` + items.map((x, i) =>
      `<div class="tg-row">${x.logo ? tile(x.logo, 76) : ''}<div class="tg-txt"><div class="tg-l">${esc(x.label || '')}</div>${x.sub ? `<div class="tg-s">${esc(x.sub)}</div>` : ''}</div>` +
      `<div class="switch" ${kid('switch', x.t ?? (p.on_t ?? 0.55) + i * 0.4, 0.3, `data-sfx="haptic" data-on="${esc(x.color || p.color || 'var(--switch-on)')}"`)}><i></i></div></div>`).join('') + '</div>';
  };

  // progress rings that fill (Instagram-gradient strokes)
  C.rings = (p) => {
    const items = (p.items || [p]).slice(0, 3), n = items.length;
    const size = p.size || (n > 1 ? 340 : 300), sw = p.stroke || (n > 1 ? 36 : 40), gap = 8, c = size / 2;
    const t0 = p.t0 ?? 0.3, dur = p.fill_dur ?? 1.1, st = 0.2, id = `rg${uid++}`;
    const stops = [IG, ['#FF0069', '#D300C5'], ['#D300C5', '#7638FA']];
    let svg = `<svg class="rg-svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}"><defs>` +
      stops.map((g, i) => `<linearGradient id="${id}_${i}" x1="0" y1="1" x2="1" y2="0">${g.map((col, j) => `<stop offset="${j / (g.length - 1)}" stop-color="${col}"/>`).join('')}</linearGradient>`).join('') + '</defs>';
    const legend = [];
    items.forEach((x, i) => {
      const r = c - sw / 2 - i * (sw + gap), v = Math.min(1, pct(x.value) / 100), paint = x.color || `url(#${id}_${i})`;
      svg += `<circle cx="${c}" cy="${c}" r="${r}" fill="none" stroke="${paint}" stroke-opacity=".15" stroke-width="${sw}"/>` +
        `<circle class="rg-arc" cx="${c}" cy="${c}" r="${r}" fill="none" stroke="${paint}" stroke-width="${sw}" stroke-linecap="round" pathLength="1" transform="rotate(-90 ${c} ${c})" ${kid('ring', t0 + i * st, dur, `data-to="${v}" data-sfx="haptic"`)}/>`;
      const shown = x.display ?? `${pct(x.value)}%`;
      legend.push(`<div class="rg-it"><i style="background:${x.color || (i ? `linear-gradient(45deg,${stops[i].join(',')})` : 'var(--grad)')}"></i><div><div class="rg-l">${esc(x.label || '')}</div>` +
        `<div class="rg-v" ${kid('count', t0 + i * st, dur, `data-to="${esc(shown)}"`)}>${esc(shown)}</div></div></div>`);
    });
    svg += '</svg>';
    const center = n === 1 ? `<div class="rg-c"><b ${kid('count', t0, dur, `data-to="${esc(items[0].display ?? `${pct(items[0].value)}%`)}"`)}>${esc(items[0].display ?? `${pct(items[0].value)}%`)}</b>${items[0].label ? `<span>${esc(items[0].label)}</span>` : ''}</div>` : '';
    return `<div class="card rings ${n === 1 ? 'one' : ''}">${p.title ? `<div class="rg-t">${esc(p.title)}</div>` : ''}<div class="rg-body"><div class="rg-dial" style="width:${size}px;height:${size}px">${svg}${center}</div>` +
      `${n > 1 ? `<div class="rg-leg">${legend.join('')}</div>` : ''}</div></div>`;
  };

  // bar or line chart that draws itself, with numbers counting up
  C.chart = (p) => {
    const items = p.items || [], n = items.length;
    const vals = items.map((x) => (parseNum(x.value) || { v: 0 }).v);
    const max = p.max ?? Math.max(1e-9, ...vals);
    const hi = p.highlight === undefined ? n - 1 : p.highlight;
    const H = p.height || 360, t0 = p.t0 ?? 0.3, st = p.stagger ?? 0.12, gd = p.grow_dur ?? 0.6;
    const shown = (x) => String(x.display ?? x.value ?? '');
    const head = `${p.title ? `<div class="ch-t">${esc(p.title)}</div>` : ''}${p.sub ? `<div class="ch-s">${esc(p.sub)}</div>` : ''}`;
    if (!n) return `<div class="card chart">${head}</div>`;
    if ((p.kind || 'bar') === 'bar') {
      const cols = items.map((x, i) => `<div class="ch-col ${i === hi ? 'hi' : ''}"><div class="ch-v" ${kid('count', t0 + st * i, gd, `data-to="${esc(shown(x))}" data-hide="1"`)}>${esc(shown(x))}</div>` +
        `<div class="ch-bar" data-h="${Math.round((vals[i] / max) * H)}" ${kid('bar', t0 + st * i, gd, 'data-sfx="haptic"')}></div><div class="ch-l">${esc(x.label || '')}</div></div>`).join('');
      return `<div class="card chart">${head}<div class="ch-bars" style="height:${H + 120}px">${cols}</div></div>`;
    }
    // line: points along the plot, drawn left to right at constant speed so the dots land with the line
    const PW = 852, top = 70, PH = H, pad = 34;
    const pts = vals.map((v, i) => [pad + (n > 1 ? (i * (PW - 2 * pad)) / (n - 1) : (PW - 2 * pad) / 2), top + PH - (v / max) * PH]);
    let L = 0;
    const cum = pts.map((q, i) => (i ? (L += Math.hypot(q[0] - pts[i - 1][0], q[1] - pts[i - 1][1])) : 0));
    const dd = p.draw_dur ?? 1.2, id = `ch${uid++}`;
    const d = pts.map((q, i) => `${i ? 'L' : 'M'}${q[0].toFixed(1)} ${q[1].toFixed(1)}`).join(' ');
    const area = `${d} L${pts[n - 1][0].toFixed(1)} ${top + PH} L${pts[0][0].toFixed(1)} ${top + PH} Z`;
    const tAt = (i) => t0 + dd * (L ? cum[i] / L : 0);
    let svg = `<svg class="ch-svg" width="${PW}" height="${top + PH + 8}"><defs><linearGradient id="${id}a" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#FF0069" stop-opacity=".28"/><stop offset="1" stop-color="#FF0069" stop-opacity="0"/></linearGradient>` +
      `<linearGradient id="${id}s" x1="0" y1="0" x2="1" y2="0">${IG.map((col, j) => `<stop offset="${j / 3}" stop-color="${col}"/>`).join('')}</linearGradient></defs>` +
      `<line x1="0" x2="${PW}" y1="${top + PH}" y2="${top + PH}" class="ch-axis"/>` +
      `<path d="${area}" fill="url(#${id}a)" ${kid('fade', t0 + dd * 0.6, 0.5)}/>` +
      `<path d="${d}" class="ch-line" stroke="url(#${id}s)" pathLength="1" ${kid('draw', t0, dd, 'data-ease="lin" data-sfx="marker"')}/>` +
      pts.map((q, i) => `<circle cx="${q[0].toFixed(1)}" cy="${q[1].toFixed(1)}" r="${i === hi ? 15 : 11}" class="ch-pt ${i === hi ? 'hi' : ''}" style="transform-origin:${q[0].toFixed(1)}px ${q[1].toFixed(1)}px" ${kid('pop', tAt(i), 0.3, i === hi ? 'data-sfx="haptic"' : '')}/>`).join('') + '</svg>';
    const labels = pts.map((q, i) => `<div class="ch-pl ${i === hi ? 'hi' : ''}" style="left:${q[0]}px;top:${q[1] - (i === hi ? 74 : 56)}px" ${kid('count', tAt(i), 0.5, `data-to="${esc(shown(items[i]))}" data-hide="1"`)}>${esc(shown(items[i]))}</div>` +
      `<div class="ch-xl" style="left:${q[0]}px;top:${top + PH + 14}px">${esc(items[i].label || '')}</div>`).join('');
    return `<div class="card chart line">${head}<div class="ch-plot" style="height:${top + PH + 58}px">${svg}${labels}</div></div>`;
  };

  // odometer: each digit rolls on its own wheel, like a mechanical counter
  C.odometer = (p) => {
    const T = parseNum(p.to ?? p.value ?? '0') || { pre: '', v: 0, post: '', sep: ',', dec: 0, dp: '.' };
    const F = parseNum(p.from ?? '0') || { v: 0 };
    const sep = T.sep || (Math.max(Math.abs(F.v), Math.abs(T.v)) >= 10000 ? ',' : '');
    const nd = String(Math.floor(Math.max(Math.abs(F.v), Math.abs(T.v), 1))).length;
    let h = '';
    for (let k = nd - 1; k >= -T.dec; k--) {
      if (k === -1) h += `<span class="od-sep">${esc(T.dp)}</span>`;
      h += `<span class="od-col" data-k="${k}"><span class="od-strip">${[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 0].map((x) => `<span>${x}</span>`).join('')}</span></span>`;
      if (k > 0 && k % 3 === 0 && sep) h += `<span class="od-sep" data-k="${k}">${esc(sep)}</span>`;
    }
    const at = p.roll_t ?? 0.25, dur = p.roll_dur ?? 1.6;
    const end = p.end_sfx === null ? '' : `<i class="od-end" ${kid('fade', at + dur - 0.05, 0.01, `data-sfx="${esc(p.end_sfx || 'cash')}"`)}></i>`;
    return `<div class="${p.card === false ? '' : 'card '}odo-card ${p.color || ''}">${p.label ? `<div class="od-l">${esc(p.label)}</div>` : ''}` +
      `<div class="odo" style="font-size:${p.size || 150}px" ${kid('odo', at, dur, `data-from="${F.v}" data-to="${T.v}" data-sfx="ratchet"`)}>` +
      `${T.pre ? `<span class="od-fix">${esc(T.pre)}</span>` : ''}${h}${T.post ? `<span class="od-fix od-post">${esc(T.post)}</span>` : ''}</div>` +
      `${p.sub ? `<div class="od-s">${esc(p.sub)}</div>` : ''}${end}</div>`;
  };

  // hearts / emojis floating up (Instagram live)
  C.hearts = (p, it) => {
    const dur = Math.min(4, p.burst ?? (it.t1 - it.t0)), n = Math.min(40, p.count ?? 16), R = rng(p.seed ?? 11);
    const x0 = p.x ?? 815, y0 = p.y ?? 1430, rise = p.rise ?? 760, spread = p.spread ?? 80;
    const em = p.emoji ? [].concat(p.emoji) : null, cols = p.colors || ['grad', '#FF0069', '#FF3B30', '#D300C5', '#FF7A00'];
    const parts = [];
    for (let i = 0; i < n; i++) {
      const life = 1.4 + R() * 0.7, size = (p.size || 68) * (0.75 + R() * 0.5);
      parts.push({ d: (i / n) * Math.max(0.1, dur - life) + R() * 0.12, life, size, x: x0 + (R() - 0.5) * spread, amp: 12 + R() * 24,
        f: 0.6 + R() * 0.7, ph: R() * 6.283, rise: rise * (0.8 + R() * 0.35), rot: (R() - 0.5) * 30, c: cols[i % cols.length], e: em ? em[i % em.length] : null });
    }
    const pops = parts.filter((_, i) => i % 4 === 0).map((q) => q.d.toFixed(2)).join(',');
    return `<div class="hearts" style="width:${TL.W}px;height:${TL.H}px" data-fx="${fxId({ parts, y0 })}" ${kid('hearts', 0, dur, `data-sfx="softpop" data-sfx-at="${pops}"`)}>` +
      parts.map((q) => `<div class="hp" style="width:${q.size}px;height:${q.size}px;left:${(q.x - q.size / 2).toFixed(1)}px;top:${(y0 - q.size / 2).toFixed(1)}px">` +
        (q.e ? `<span style="font-size:${(q.size * 0.86).toFixed(0)}px">${esc(q.e)}</span>` : `<svg viewBox="0 0 24 24" width="${q.size}" height="${q.size}"><path d="${HEART}" fill="${q.c === 'grad' ? 'url(#ig-grad)' : q.c}"/></svg>`) + '</div>').join('') + '</div>';
  };

  // confetti or sparkles bursting out of a point (use on «gratis», «$0»)
  C.confetti = (p, it) => {
    const style = p.style || (it.type === 'sparkle' ? 'sparkle' : 'confetti'), R = rng(p.seed ?? 5), S = 1000;
    const cols = p.colors || [...IG, '#34C759', '#FFCC00'];
    const n = Math.min(120, p.count ?? (style === 'sparkle' ? 18 : 70)), parts = [];
    for (let i = 0; i < n; i++) {
      if (style === 'sparkle') {
        const a = R() * 6.283, r = 70 + Math.pow(R(), 0.7) * (p.radius ?? 380);
        parts.push({ x: Math.cos(a) * r, y: Math.sin(a) * r * 0.8, d: R() * 0.45, life: 0.45 + R() * 0.35, size: 34 + R() * 46, rot: R() * 90, c: cols[i % cols.length] });
      } else {
        const a = -Math.PI / 2 + (R() - 0.5) * Math.PI * 1.25, v = (p.power ?? 1) * (650 + R() * 950);
        parts.push({ vx: Math.cos(a) * v, vy: Math.sin(a) * v, d: R() * 0.05, life: 1.2 + R() * 0.5, w: 14 + R() * 14, h: 8 + R() * 8,
          r0: R() * 360, w0: (R() - 0.5) * 1100, fl: 6 + R() * 10, ph: R() * 6.283, c: cols[i % cols.length], round: R() < 0.25 });
      }
    }
    const dur = Math.max(...parts.map((q) => q.d + q.life));
    const body = style === 'sparkle'
      ? `<div class="cf-ring"></div>` + parts.map((q) => `<svg class="cf-p sp" viewBox="0 0 24 24" width="${q.size.toFixed(0)}" height="${q.size.toFixed(0)}" style="left:${(S / 2 - q.size / 2).toFixed(1)}px;top:${(S / 2 - q.size / 2).toFixed(1)}px"><path d="${STAR}" fill="${q.c}"/></svg>`).join('')
      : parts.map((q) => `<i class="cf-p" style="width:${q.w.toFixed(0)}px;height:${q.h.toFixed(0)}px;left:${(S / 2 - q.w / 2).toFixed(1)}px;top:${(S / 2 - q.h / 2).toFixed(1)}px;background:${q.c};${q.round ? 'border-radius:50%;' : ''}"></i>`).join('');
    return `<div class="confetti ${style}" style="width:${S}px;height:${S}px" data-fx="${fxId({ style, parts })}" ${kid(style, 0, dur, 'data-sfx="sparkle"')}>${body}</div>`;
  };

  // «palabra golpe»: one giant word over the whole screen for ~0.6 s
  C.punch = (p, it) => `<div class="punch ${p.style || 'acc'}" style="width:${TL.W}px;height:${TL.H}px"><div class="pw-in" ${kid('slam', 0, it.t1 - it.t0)}>` +
    `<div class="pw fit" style="font-size:${p.size || 300}px">${esc(p.text)}</div>${p.sub ? `<div class="pw-sub">${esc(p.sub)}</div>` : ''}</div></div>`;

  // underline / highlighter drawn under a word
  C.marker = (p) => {
    const words = String(p.text || '').split(/\s+/).filter(Boolean);
    const mark = new Set([].concat(p.mark ?? words.map((_, i) => i)));
    const st = p.style || 'underline', t0 = p.draw_t ?? 0.3, dur = p.draw_dur ?? 0.4;
    let j = 0;
    return `<div class="marker ${p.on_bg ? 'on-bg' : ''}" style="font-size:${p.size || 110}px;${p.color ? `--mk:${p.color};` : ''}">` + words.map((w, i) => {
      if (!mark.has(i)) return `<span>${esc(w)}</span>`;
      const t = t0 + 0.18 * j++;
      const ink = st === 'highlight' ? `<i class="mk-h" ${kid('hl', t, dur, 'data-sfx="marker"')}></i>`
        : `<i class="mk-u" ${kid('underline', t, dur, 'data-sfx="marker"')}></i>`;
      return `<span class="mk ${st}">${ink}<span class="mk-t">${esc(w)}</span></span>`;
    }).join(' ') + '</div>';
  };

  // app icons bouncing into a home-screen grid
  C.homescreen = (p) => {
    const cols = p.cols || 4, size = p.size || 150, st = p.stagger ?? 0.06, t0 = p.t0 ?? 0.1;
    const apps = (p.items || []).map((x, i) => {
      const t = t0 + (Math.floor(i / cols) + (i % cols)) * st;
      return `<div class="hs-app" ${kid('bounce', t, 0.7, 'data-sfx="softpop"')}><div class="hs-ico">${tile(x.logo, size)}` +
        `${x.badge ? `<span class="hs-badge" ${kid('pop', x.badge_t ?? t + 0.45, 0.3, 'data-sfx="haptic"')}>${esc(x.badge)}</span>` : ''}</div>` +
        `${x.label ? `<div class="hs-l">${esc(x.label)}</div>` : ''}</div>`;
    }).join('');
    return `<div class="homescreen ${p.card ? 'card' : ''} ${p.wallpaper ? 'wall' : ''}">${p.title ? `<div class="hs-t">${esc(p.title)}</div>` : ''}` +
      `<div class="hs-grid" style="grid-template-columns:repeat(${cols}, ${size + 40}px)">${apps}</div></div>`;
  };

  // Dynamic Island pill that expands with a fact
  C.island = (p) => {
    const t = p.open_t ?? 0.2, w = p.width || 940;
    return `<div class="isl-wrap" style="width:${Math.max(1000, w + 60)}px"><div class="island" data-w="${w}" ${kid('island', t, 0.6, 'data-sfx="haptic"')}><div class="isl-in" style="width:${w}px;left:50%;right:auto;transform:translateX(-50%)">` +
      `${p.logo ? tile(p.logo, 88, 'isl-ico') : ''}<div class="isl-txt"><div class="isl-t">${esc(p.text || '')}</div>${p.sub ? `<div class="isl-s">${esc(p.sub)}</div>` : ''}</div>` +
      `${p.value ? `<div class="isl-v ${p.color || ''}" ${kid('count', t + 0.3, 0.8, `data-to="${esc(p.value)}"`)}>${esc(p.value)}</div>` : ''}</div></div></div>`;
  };

  // iPhone with a screenshot that scrolls
  C.iphone = (p, it) => {
    const zh = it.zone && it.zone.top ? it.zone.top[1] - it.zone.top[0] : 1000;
    const h = Math.round(p.height || Math.max(560, Math.min(1160, zh))), w = Math.round(h / 2.05);
    const sc = p.scroll === false ? 0 : p.scroll ?? 1;
    const screen = p.src ? `<img src="${p.src}" ${sc ? kid('scroll', p.scroll_t ?? 0.7, p.scroll_dur ?? 2.4, `data-to="${sc}"`) : ''}>` : (p.html || '');
    const icons = `<svg width="${w * 0.2}" height="${w * 0.045}" viewBox="0 0 80 18"><rect x="0" y="11" width="4" height="6" rx="1"/><rect x="6" y="8" width="4" height="9" rx="1"/><rect x="12" y="5" width="4" height="12" rx="1"/><rect x="18" y="2" width="4" height="15" rx="1"/>` +
      `<path d="M36 6.5a12 12 0 0 1 16 0l-2 2a9 9 0 0 0-12 0zM40 10.5a6 6 0 0 1 8 0L44 15z"/><rect x="56" y="3" width="21" height="12" rx="3.5" fill="none" stroke="currentColor" stroke-width="1.6"/><rect x="58.5" y="5.5" width="14" height="7" rx="1.8"/></svg>`;
    return `<div class="iphone" style="width:${w}px;height:${h}px;--pw:${w}px;${p.tilt ? `transform:perspective(1800px) rotateY(${p.tilt}deg);` : ''}"><div class="ip-screen">` +
      `<div class="ip-view ${p.status === false ? 'full' : ''}">${screen}</div>` +
      `${p.status === false ? '' : `<div class="ip-status"><b>${esc(p.time || '9:41')}</b>${icons}</div>`}<div class="ip-island"></div><div class="ip-home"></div></div></div>`;
  };
  C.sparkle = C.confetti;

  C.scrim = (p) => `<div class="scrim ${p.side || 'top'}" style="height:${p.height || 900}px"></div>`;
  C.html = (p) => `${p.css ? `<style>${p.css}</style>` : ''}${p.html || ''}`;

  // ── build ────────────────────────────────────────────────────────────────
  const ITEMS = [];
  stage.insertAdjacentHTML('beforeend', `<svg width="0" height="0" style="position:absolute"><defs><linearGradient id="ig-grad" x1="0" y1="1" x2="1" y2="0">${IG.map((c, j) => `<stop offset="${j / 3}" stop-color="${c}"/>`).join('')}</linearGradient></defs></svg>`);
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
      ease: E[k.dataset.ease], hide: k.dataset.hide === '1', ds: k.dataset, it,
      fx: k.dataset.fx !== undefined ? FX[+k.dataset.fx] : null,
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
      case 'drop': return { o: clamp(p * 3), ty: -(1 - E.back(p, 1.2)) * 320 };
      case 'bounce': return { o: clamp(p * 5), s: E.spring(p), ty: (1 - E.spring(p)) * 50 };
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
    if (k.hide) el.style.visibility = lt >= k.at ? '' : 'hidden';    // '' inherits: stays hidden in the other layer
    switch (k.kind) {
      case 'type': {
        const n = Math.round(p * k.text.length);
        const caret = p < 1 && Math.floor(lt * 2.5) % 2 === 0;
        const html = esc(k.text.slice(0, n)) + (p > 0 && p < 1 ? `<span class="caret" style="opacity:${caret ? 1 : 0}">▍</span>` : '');
        if (el._h !== html) { el.innerHTML = html; el._h = html; }
        el.style.visibility = p > 0 || lt >= k.at ? '' : 'hidden';
        return n + (caret ? 'c' : '');
      }
      case 'count': {
        if (!k.P) return 'x';
        const v = k.P.v * E.out(p);
        const s = p >= 1 ? k.to : fmtNum(k.P, v);      // lands on exactly what the plan says
        if (el._h !== s) { el.textContent = s; el._h = s; }
        return s;
      }
      case 'strike': case 'underline': el.style.setProperty('--p', E.out(p)); return q(p);
      case 'dim': el.style.opacity = 1 - 0.58 * E.inout(p); return q(p);
      case 'out': el.style.opacity = 1 - E.lin(p); return q(p);
      case 'grow': el.style.transform = `scaleX(${E.out(p)})`; el.style.opacity = p > 0 ? 1 : 0; return q(p);
      case 'scroll': {
        const view = el.parentElement.clientHeight, H = el.naturalHeight ? el.clientHeight : 0;
        el.style.transform = `translateY(${-E.inout(p) * (+k.to || 0) * Math.max(0, H - view)}px)`;
        return q(p);
      }
      case 'draw': el.style.strokeDasharray = '1'; el.style.strokeDashoffset = String(1 - (k.ease || E.inout)(p)); el.style.opacity = p > 0 ? 1 : 0; return q(p);
      case 'ripple': el.style.opacity = p > 0 && p < 1 ? 1 - p : 0; el.style.transform = `translate(-50%,-50%) scale(${0.2 + 1.3 * E.out(p)})`; return q(p);
      case 'bubble': {    // message bubble: grows out of its tail
        el.style.opacity = clamp(p * 4);
        el.style.transform = `translateY(${((1 - E.out(p)) * 18).toFixed(1)}px) scale(${(0.35 + 0.65 * E.back(p, 2.0)).toFixed(4)})`;
        return q(p);
      }
      case 'typing': {    // «escribiendo…»: shows during [at, at + dur), dots bounce in a wave
        const on = lt >= k.at && lt < k.at + k.dur, u = lt - k.at;
        if (!on) { el.style.opacity = 0; return 'x'; }
        const a = clamp(u / 0.12) * clamp((k.dur - u) / 0.08);
        el.style.opacity = a;
        el.style.transform = `scale(${(0.6 + 0.4 * E.back(clamp(u / 0.2))).toFixed(3)})`;
        [...el.children].forEach((d, j) => {
          const w = Math.max(0, Math.sin(u * 2.6 * 6.283 - j * 0.95));
          d.style.transform = `translateY(${(-w * 11).toFixed(1)}px)`;
          d.style.opacity = (0.45 + 0.55 * w).toFixed(2);
        });
        return 't' + Math.round(u * 60);
      }
      case 'switch': {
        const e = E.inout(p), kn = el.firstElementChild, wd = 56 + 14 * Math.sin(Math.PI * p);
        kn.style.width = wd.toFixed(1) + 'px';
        kn.style.transform = `translateX(${(e * (40 - (wd - 56))).toFixed(1)}px)`;
        el.style.background = `color-mix(in srgb, ${k.ds.on} ${Math.round(e * 100)}%, #E9E9EA)`;
        return q(p);
      }
      case 'ring': {
        const f = (+k.to || 0) * E.out(p);
        el.style.strokeDasharray = `${f.toFixed(4)} 2`;
        el.style.opacity = f > 0.002 ? 1 : 0;
        return q(p);
      }
      case 'bar': el.style.height = ((+k.ds.h || 0) * E.out(p)).toFixed(1) + 'px'; return q(p);
      case 'hl': el.style.transform = `scaleX(${E.out(p).toFixed(4)})`; el.style.opacity = p > 0 ? 1 : 0; return q(p);
      case 'bounce': {
        const s = E.spring(p);
        el.style.opacity = clamp(p * 5);
        el.style.transform = `translateY(${((1 - s) * 60).toFixed(1)}px) scale(${s.toFixed(4)})`;
        return q(p);
      }
      case 'odo': return odoFrame(k, p);
      case 'hearts': return heartsFrame(k, lt);
      case 'confetti': case 'sparkle': return burstFrame(k, lt);
      case 'slam': {      // palabra golpe: slams in, shakes, then drifts closer
        const hold = Math.min(Math.max(k.dur, 0.2), 1.2);   // continuous drift capped: then the frame repeats
        const s = 1.5 - 0.5 * E.out(clamp(lt / 0.13)) + 0.06 * clamp(lt / hold);
        const sh = lt > 0.13 ? Math.sin(lt * 95) * 7 * clamp(1 - (lt - 0.13) / 0.14) : 0;
        el.style.opacity = clamp(lt / 0.05);
        el.style.transform = `translate(${sh.toFixed(1)}px,0) scale(${s.toFixed(4)})`;
        return 'g' + Math.round(Math.min(lt, hold) * 60);
      }
      case 'island': {    // Dynamic Island: springs open, collapses before the item ends
        const rem = k.it.t1 - k.it.t0 - lt;
        const m = E.spring(p) * E.inout(clamp(rem / 0.35));
        const w = 360 + ((+k.ds.w || 940) - 360) * m, h = 104 + (156 - 104) * Math.min(1, m);
        el.style.width = w.toFixed(1) + 'px';
        el.style.height = h.toFixed(1) + 'px';
        el.firstElementChild.style.opacity = clamp((m - 0.72) / 0.25);
        return 'i' + Math.round(m * 400);
      }
      default: {
        const f = fx(k.kind, p);
        el.style.opacity = f.o ?? 1;
        el.style.transform = `translate(${f.tx || 0}px,${f.ty || 0}px) scale(${f.s ?? 1})`;
        return q(p);
      }
    }
  }

  function odoFrame(k, p) {
    if (!k.cols) {
      k.cols = [...k.el.querySelectorAll('.od-col')].map((c) => ({ k: +c.dataset.k, el: c, strip: c.firstElementChild }));
      k.seps = [...k.el.querySelectorAll('.od-sep[data-k]')].map((c) => ({ k: +c.dataset.k, el: c }));
    }
    const a = +k.ds.from || 0, b = +k.ds.to || 0, done = p >= 1;
    const val = (x) => Math.abs(a + (b - a) * E.out(x));
    const v = val(p), dv = Math.abs(val(clamp(p + 1 / (30 * Math.max(k.dur, 0.1)))) - v);
    const low = Math.min(...k.cols.map((c) => c.k));
    const op = {};
    for (const c of k.cols) {
      const pw = Math.pow(10, c.k), x = v / pw;
      let pos;
      if (done) pos = Math.floor(Math.abs(b) / pw + 1e-9) % 10;
      else if (c.k === low) pos = x % 10;
      else { const r = x - Math.floor(x); pos = (Math.floor(x) % 10) + (r > 0.9 ? (r - 0.9) / 0.1 : 0); }
      const speed = dv / pw, blur = done || p <= 0 ? 0 : Math.min(7, Math.max(0, speed - 0.25) * 2.2);
      c.strip.style.transform = `translateY(${(-pos * 100 / 11).toFixed(3)}%)`;
      c.strip.style.filter = blur > 0.3 ? `blur(${blur.toFixed(1)}px)` : '';
      op[c.k] = c.k <= 0 ? 1 : 0.2 + 0.8 * clamp((x - 0.9) / 0.1);
      c.el.style.opacity = op[c.k].toFixed(3);
    }
    for (const s of k.seps) s.el.style.opacity = (op[s.k] ?? 1).toFixed(3);
    return 'o' + q(p);
  }

  function heartsFrame(k, lt) {
    const D = k.fx;
    if (!k.nodes) k.nodes = [...k.el.children];
    let live = 0;
    D.parts.forEach((q2, i) => {
      const el = k.nodes[i], u = (lt - q2.d) / q2.life;
      if (u < 0 || u >= 1) { el.style.opacity = 0; return; }
      live++;
      const tt = lt - q2.d;
      const y = -q2.rise * (u * 0.85 + 0.15 * E.out(u));
      const x = q2.amp * Math.sin(6.283 * q2.f * tt + q2.ph) * clamp(u * 3);
      const s = 0.25 + 0.75 * E.back(clamp(u * 5), 2.2) - 0.15 * u;
      el.style.opacity = (u < 0.7 ? 1 : 1 - (u - 0.7) / 0.3).toFixed(3);
      el.style.transform = `translate(${x.toFixed(1)}px,${y.toFixed(1)}px) rotate(${(q2.rot * Math.sin(tt * 2.2)).toFixed(1)}deg) scale(${s.toFixed(3)})`;
    });
    return live ? 'h' + Math.round(lt * 60) : 'h-';
  }

  function burstFrame(k, lt) {
    const D = k.fx;
    if (!k.nodes) k.nodes = [...k.el.querySelectorAll('.cf-p')];
    const ring = k.el.querySelector('.cf-ring');
    let live = 0;
    if (ring) {
      const u = clamp(lt / 0.5);
      ring.style.opacity = u > 0 && u < 1 ? (1 - u).toFixed(3) : 0;
      ring.style.transform = `translate(-50%,-50%) scale(${(0.1 + 1.1 * E.out(u)).toFixed(3)})`;
      if (u < 1) live++;
    }
    D.parts.forEach((q2, i) => {
      const el = k.nodes[i], tt = lt - q2.d, u = tt / q2.life;
      if (u < 0 || u >= 1) { el.style.opacity = 0; return; }
      live++;
      if (D.style === 'sparkle') {
        const s = Math.pow(Math.sin(Math.PI * u), 0.8);
        el.style.opacity = 1;
        el.style.transform = `translate(${q2.x.toFixed(1)}px,${q2.y.toFixed(1)}px) rotate(${(q2.rot + 70 * u).toFixed(1)}deg) scale(${s.toFixed(3)})`;
      } else {
        const kd = 2.4, g = 1900, ex = 1 - Math.exp(-kd * tt);
        const x = (q2.vx / kd) * ex, y = ((q2.vy + g / kd) / kd) * ex - (g / kd) * tt;
        el.style.opacity = (u < 0.65 ? 1 : 1 - (u - 0.65) / 0.35).toFixed(3);
        el.style.transform = `translate(${x.toFixed(1)}px,${(-y).toFixed(1)}px) rotate(${(q2.r0 + q2.w0 * tt).toFixed(1)}deg) scaleY(${Math.cos(q2.fl * tt + q2.ph).toFixed(3)})`;
      }
    });
    return live ? 'b' + Math.round(lt * 60) : 'b-';
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
      case 'top': y = 190; break;
      case 'title': y = (it.y ?? Z.title) - h / 2; break;
      case 'cap': y = (it.y ?? Z.cap) - h / 2; break;
      case 'full': x = 0; y = 0; break;
      case 'abs': {
        const [ax, ay] = it.anchor || [0.5, 0.5];
        if (it.attach) {
          const tgt = ITEMS.find((o) => o.id === it.attach);
          // a target that already left (or hasn't come in) still anchors it where it was (pure in t)
          const tb = tgt && (tgt._box || (tgt.w0 !== undefined ? itemBox(tgt, clamp(t, tgt.t0, tgt.t1 - 1e-3)) : null));
          if (tb) {
            const [cx, cy] = it.corner || [1, 0];
            x = tb.x + tb.w * cx - w * ax + (it.dx || 0);
            y = tb.y + tb.h * cy - h * ay + (it.dy || 0);
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
      capEl.innerHTML = ch.words.map((w) => `<span class="w${w.e ? ' em' : ''}${w.m ? ' mk' : ''}">${esc(w.w)}</span>`).join(' ');
      capEl._k = k;
    }
    let ai = -1;
    ch.words.forEach((w, i) => { if (w.t0 <= t) ai = i; });
    if (CAP.style.karaoke) [...capEl.children].forEach((s, i) => s.classList.toggle('on', i === ai));
    let mk = '';         // captions.marker: an underline draws under the word as it's said
    ch.words.forEach((w, i) => {
      if (!w.m) return;
      const pm = clamp((t - w.t0) / 0.28);
      capEl.children[i].style.setProperty('--p', E.out(pm).toFixed(3));
      mk += q(pm);
    });
    const Z = zoneAt(t);
    capEl.className = 'cap ' + (Z.capOn === 'bg' ? 'on-bg' : 'on-sp') + (CAP.style.karaoke ? ' kara' : '');
    const p = clamp((t - ch.t0) / 0.13);
    const s = CAP.style.pop === false ? 1 : 0.84 + 0.16 * E.back(p, 2.2);
    capEl.style.opacity = 1;
    const h = capEl.offsetHeight;
    const cy = ch.y ?? CAP.style.y ?? Z.cap;
    capEl.style.transform = `translate(0px,${cy - h / 2}px) scale(${s})`;
    return `c${k}:${CAP.style.karaoke ? ai : ''}:${q(p)}:${Z.capOn}:${cy}:${mk}`;
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
        const d = k.kind === 'type' || k.kind === 'count' || k.kind === 'odo' ? k.dur : 0;
        const offs = k.ds.sfxAt ? k.ds.sfxAt.split(',').map(Number) : [0];
        for (const o of offs) if (it.t0 + k.at + o < it.t1) ev.push({ t: it.t0 + k.at + o, sfx: k.sfx, dur: d });
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
