/* 因果律软糖罐 · 试玩版引擎（GitHub Pages 用）
 *
 * 没有后端：把 gateway/candyjar.py 那套规则搬进浏览器，账本存 localStorage。
 * 做法是拦下页面对 /candyjar* 的 fetch，游戏本体一行不用改——这样正式版和试玩版
 * 永远是同一个界面，不会各改各的。
 *
 * 与正式版的差别只有两条：账本在你自己浏览器里（换设备就没了）；没有 AI 那一头。
 */
(function () {
  const KEY = 'candyjar_demo_v1';
  const START_COURAGE = 12, GRACE_MIN = 10;
  const PRICES = { reserve: 5 }, LADDER = [3, 3, 4, 4, 5, 5], ONCE_A_DAY = ['mm_gold'];
  const JAR_NAMES = { 1: '宿命论', 2: '蝴蝶效应', 3: '桃花劫', 4: '薛定谔', 5: '世界线收束' };
  let CAT = null;                                   // 图鉴（页面自己会拉，这里也拉一份）

  const today = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; };
  const blank = () => ({ dex: {}, courage: { user: START_COURAGE, ai: START_COURAGE }, active: [], jar: null,
                         pending: {}, shield: {}, reserve: { user: [], ai: [] }, buys: {}, extras: {}, log: [] });
  function load() { try { return Object.assign(blank(), JSON.parse(localStorage.getItem(KEY) || '{}')); } catch (e) { return blank(); } }
  function save(st) { try { localStorage.setItem(KEY, JSON.stringify(st)); } catch (e) {} }

  // 简易可复现随机数：同一天同一罐摇出同一批糖（后端用 Python 的 Random，这里换成 mulberry32，
  // 结果不同但性质一样——试玩版不需要和正式版逐颗对上）。
  function rng(seed) {
    let h = 1779033703 ^ seed.length;
    for (let i = 0; i < seed.length; i++) { h = Math.imul(h ^ seed.charCodeAt(i), 3432918353); h = (h << 13) | (h >>> 19); }
    let a = h >>> 0;
    return function () { a |= 0; a = (a + 0x6D2B79F5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  }
  const find = id => CAT && CAT.candies.find(c => c.id === id);

  function rollJar(day, n) {
    const pool = CAT.candies.filter(c => (n === 5 ? c.jar > 0 : c.jar === n));
    const mech = CAT.candies.filter(c => c.jar === 0);
    const r = rng(day + '|' + n), pick = arr => arr[Math.floor(r() * arr.length)];
    const nEff = n === 5 ? 26 : 17, nMech = n === 5 ? 5 : 3, ids = [];
    for (let i = 0; i < nEff; i++) ids.push(pick(pool).id);
    for (let i = 0; i < nMech; i++) ids.push(pick(mech).id);
    for (let i = ids.length - 1; i > 0; i--) { const j = Math.floor(r() * (i + 1)); [ids[i], ids[j]] = [ids[j], ids[i]]; }
    return { day, jar: n, name: JAR_NAMES[n], candies: ids.map((id, i) => ({ i, id })) };
  }
  function attachExtras(st, jar) {
    const ids = (st.extras || {})[String(jar.jar)] || [];
    let nxt = jar.candies.reduce((m, x) => Math.max(m, x.i), -1) + 1;
    for (const id of ids) jar.candies.push({ i: nxt++, id, bought: true });
  }
  function ensureJar(st) { const j = st.jar; return (j && j.day === today()) ? j : null; }
  function prune(st) {
    const now = Date.now();
    st.active = (st.active || []).filter(a => new Date(a.expires).getTime() > now);
  }
  function statusList(st) {
    const now = Date.now();
    return (st.active || []).map(a => {
      const c = find(a.candy_id); if (!c) return null;
      return { target: a.target, name: c.name, effect: c.effect, reveal: c.reveal, perform: c.perform,
               minutes_left: Math.max(0, Math.floor((new Date(a.expires).getTime() - now) / 60000)), from: a.from || null };
    }).filter(Boolean);
  }
  function buysToday(st) {
    const d = today(); let b = st.buys || {};
    if (b.day !== d) b = st.buys = { day: d, n: 0, once: {} };
    if (!b.once) b.once = {};
    return b;
  }
  const mysteryPrice = st => LADDER[Math.min(buysToday(st).n, LADDER.length - 1)];
  const onceUsed = st => (buysToday(st).once.user || []).slice();

  function shieldLeft(st, who) {
    const e = (st.shield || {})[who]; if (!e) return 0;
    return Math.max(0, (new Date(e).getTime() - Date.now()) / 60000);
  }
  function apply(st, cid, target, from) {
    const c = find(cid);
    if (c.jar > 0 && shieldLeft(st, target) > 0) {          // 护身符挡下第一颗效果糖
      delete st.shield[target];
      st.dex[cid] = (st.dex[cid] || 0) + 1;
      return { c, mins: -1 };
    }
    const [lo, hi] = c.dur || [0, 0];
    let mins = !hi ? 0 : (lo === hi ? lo : lo + Math.floor(Math.random() * (hi - lo + 1)));
    if (cid === 'mm_white') {                                // 护身符自己不占药效牌
      st.shield = st.shield || {};
      st.shield[target] = new Date(Date.now() + (mins || 10) * 60000).toISOString();
      st.dex[cid] = (st.dex[cid] || 0) + 1;
      return { c, mins: 0 };
    }
    if ((st.pending || {})[target] === 'double' && mins) { mins *= 2; delete st.pending[target]; }
    if (mins) {
      st.active = (st.active || []).filter(a => a.target !== target);   // 新顶旧
      st.active.push({ target, candy_id: cid, from: from || null,
                       expires: new Date(Date.now() + mins * 60000).toISOString() });
    }
    st.dex[cid] = (st.dex[cid] || 0) + 1;
    return { c, mins };
  }

  function eat(body) {
    const st = load(); prune(st);
    const jar = ensureJar(st);
    const target = body.feed ? 'ai' : 'user', who = 'user';
    let cid;
    if (body.source === 'reserve') {
      const res = st.reserve.user || [];
      const k = res.indexOf(body.candy_id);
      if (k < 0) return { ok: true, text: '储藏罐里没有这颗糖。', active: statusList(st), courage: st.courage, reserve: res, dex: st.dex };
      res.splice(k, 1); cid = body.candy_id;
    } else {
      if (!jar) return { ok: true, text: '罐子空了，明天再来。', active: statusList(st), courage: st.courage, reserve: st.reserve.user, dex: st.dex };
      const hit = jar.candies.find(x => x.i === body.index);
      if (!hit) return { ok: true, text: `没有编号 ${body.index} 的糖了。`, active: statusList(st), courage: st.courage, reserve: st.reserve.user, dex: st.dex };
      jar.candies = jar.candies.filter(x => x !== hit); cid = hit.id;
      const ex = (st.extras || {})[String(jar.jar)];
      if (ex) { const k = ex.indexOf(cid); if (k >= 0) ex.splice(k, 1); }
    }
    const line = Date.now() + GRACE_MIN * 60000;
    const had = (st.active || []).some(a => a.target === target && new Date(a.expires).getTime() > line);
    const { c, mins } = apply(st, cid, target, target !== who ? who : null);
    const blocked = mins === -1, real = blocked ? 0 : mins;
    const override = target === who && had && real > 0;
    if (override) st.courage[who] = Math.max(0, (st.courage[who] ?? START_COURAGE) - 2);
    else if (body.source !== 'reserve') st.courage[who] = (st.courage[who] ?? START_COURAGE) + (target === who ? 1 : 0);

    if (c.id === 'mm_red' && target !== who) {              // 回旋镖
      const pool = CAT.candies.filter(x => x.jar > 0);
      apply(st, pool[Math.floor(Math.random() * pool.length)].id, who, '回旋镖');
    } else if (c.id === 'mm_yellow') { st.pending = st.pending || {}; st.pending[target] = 'double'; }
    else if (c.id === 'mm_blue') st.active = st.active.filter(a => a.target !== target);
    else if (c.id === 'mm_gold') st.courage[target] = (st.courage[target] ?? START_COURAGE) + 10;
    else if (c.id === 'mm_hourglass') st.active.forEach(a => {
      if (a.target !== target) return;
      const exp = new Date(a.expires).getTime(), now = Date.now();
      if (exp > now) a.expires = new Date(now + (exp - now) / 2).toISOString();
    });
    else if (c.id === 'mm_swap') { const o = target === 'user' ? 'ai' : 'user';
      st.active.forEach(a => { a.target = a.target === target ? o : (a.target === o ? target : a.target); }); }

    save(st);
    return { ok: true, text: `你吃下了「${c.name}」。`, active: statusList(st),
             courage: st.courage, reserve: st.reserve.user, dex: st.dex };
  }

  function buy(body) {
    const st = load(); prune(st);
    const jar = ensureJar(st), c = find(body.id), dest = body.dest || 'reserve';
    if (!c) return { error: '没有这种糖。' };
    if (dest === 'today' && !jar) return { error: '今天还没开罐，神秘柜的糖没处放。' };
    if (ONCE_A_DAY.includes(body.id) && onceUsed(st).includes(body.id)) return { error: '这颗今天已经买过啦，明天再来。' };
    const price = dest === 'today' ? mysteryPrice(st) : PRICES.reserve;
    const have = st.courage.user ?? START_COURAGE;
    if (have < price) return { error: `勇气不够（有 ${have}，要 ${price}）。` };
    st.courage.user = have - price;
    if (dest === 'today') {
      const nxt = jar.candies.reduce((m, x) => Math.max(m, x.i), -1) + 1;
      jar.candies.push({ i: nxt, id: body.id, bought: true });
      (st.extras[String(jar.jar)] = st.extras[String(jar.jar)] || []).push(body.id);
      buysToday(st).n += 1;
    } else st.reserve.user.push(body.id);
    if (ONCE_A_DAY.includes(body.id)) (buysToday(st).once.user = buysToday(st).once.user || []).push(body.id);
    save(st);
    return { ok: true, courage: st.courage, reserve: st.reserve.user, jar,
             mystery_price: mysteryPrice(st), once_used: onceUsed(st) };
  }

  function view() {
    const st = load(); prune(st);
    const jar = ensureJar(st); save(st);
    const out = { jar, dex: st.dex, courage: st.courage, reserve: st.reserve.user,
                  active: statusList(st), mystery_price: mysteryPrice(st), once_used: onceUsed(st) };
    if (!jar) {
      const day = today(), jars = {};
      let h = 0; for (const ch of day) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
      for (let n = 1; n <= 5; n++) { const j = rollJar(day, n); attachExtras(st, j); jars[String(n)] = j; }
      out.choose = { day, suggest: (h % 5) + 1, jars };
    }
    return out;
  }
  function choose(body) {
    const st = load();
    if (ensureJar(st)) return { error: '今天已经开过罐了，明天零点再选。' };
    const n = parseInt(body.jar, 10);
    if (!JAR_NAMES[n]) return { error: '没有这一罐。' };
    st.jar = rollJar(today(), n); attachExtras(st, st.jar); save(st);
    return { ok: true, jar: st.jar };
  }

  const json = o => new Response(JSON.stringify(o), { status: o && o.error ? 400 : 200,
                                                      headers: { 'Content-Type': 'application/json' } });
  const real = window.fetch.bind(window);
  window.fetch = async function (input, init) {
    const url = typeof input === 'string' ? input : (input && input.url) || '';
    const path = url.split('?')[0].replace(/^https?:\/\/[^/]+/, '');
    // 只认这几个接口，且必须**结尾匹配**：图鉴的 /assets/candyjar/candies.json 路径里也带 candyjar，
    // 早先的宽松写法把它一并拦了，糖果表拿不到、罐子渲染成空的（2026-09-05 自测撞上）。
    if (!/\/candyjar(\/(eat|buy|choose))?$/.test(path) && !/\/state$/.test(path)) return real(input, init);
    if (!CAT) CAT = await real('assets/candyjar/candies.json').then(r => r.json());
    let body = {};
    try { body = init && init.body ? JSON.parse(init.body) : {}; } catch (e) {}
    if (/state$/.test(path)) return json({});
    if (/candyjar$/.test(path)) return json(view());
    if (/choose$/.test(path)) return json(choose(body));
    if (/eat$/.test(path)) return json(eat(body));
    if (/buy$/.test(path)) return json(buy(body));
    return json({ error: '试玩版没有这个接口。' });
  };
})();
