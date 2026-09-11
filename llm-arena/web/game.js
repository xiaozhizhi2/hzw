/* LLM 竞技场 —— 前端回合引擎 + Canvas 2D 战斗演出
 *
 * 流程：点击开始 -> 每回合并行请求两个大模型出招（技能只能来自固定技能池）
 *      -> 按技能速度排序结算 -> 血条与画面同步 -> 任一方血量为 0 判定 KO 并停止。
 */
(function () {
  'use strict';

  const API_ACT = '/api/act';
  const API_SKILLS = '/api/skills';
  const API_CONFIG = '/api/config';

  const GROUND_RATIO = 0.80;
  const MONO = '"Cascadia Mono", "JetBrains Mono", Consolas, monospace';

  const PALETTES = {
    left: { body: '#1e6379', body2: '#12414f', accent: '#38e1ff', glow: '#cdf7ff' },
    right: { body: '#4a3282', body2: '#2f2058', accent: '#b48bff', glow: '#e8dcff' }
  };

  // ---------------------------------------------------------------- DOM 引用
  const $ = (sel, root) => (root || document).querySelector(sel);

  const dom = {
    subtitle: $('#subtitle'),
    canvas: $('#arena'),
    roundBadge: $('#roundBadge'),
    result: $('#result'),
    btnStart: $('#btnStart'),
    btnStop: $('#btnStop'),
    btnReset: $('#btnReset'),
    status: $('#status'),
    skillPool: $('#skillPool'),
    log: $('#log'),
    btnClearLog: $('#btnClearLog')
  };

  const cardEls = { left: $('#cardLeft'), right: $('#cardRight') };
  const ui = {};
  ['left', 'right'].forEach(function (side) {
    const card = cardEls[side];
    ui[side] = {
      fill: $('[data-role="fill"]', card),
      hp: $('[data-role="hp"]', card),
      name: $('[data-role="name"]', card),
      model: $('[data-role="model"]', card),
      statuses: $('[data-role="statuses"]', card)
    };
  });

  // ---------------------------------------------------------------- 运行时状态
  let SKILLS = [];
  let SKILL_BY_ID = {};
  let CONFIG = null;

  const state = {
    running: false,
    over: false,
    round: 0,
    token: 0,
    recent: [],
    ac: null
  };

  const fighters = { left: null, right: null };
  const fx = [];
  const particles = [];
  const floaters = [];
  let shake = { mag: 0, start: 0, dur: 0 };
  let lastFrame = 0;

  // ---------------------------------------------------------------- 小工具
  const rnd = (a, b) => a + Math.floor(Math.random() * (b - a + 1));
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const other = (side) => (side === 'left' ? 'right' : 'left');
  const clamp = (v, a, b) => (v < a ? a : v > b ? b : v);
  const ease = (t) => t * t * (3 - 2 * t);
  const nowMs = () => performance.now();

  function rrPath(x, y, w, h, r) {
    const rr = Math.min(r, w / 2, h / 2);
    ctx.beginPath();
    ctx.moveTo(x + rr, y);
    ctx.lineTo(x + w - rr, y);
    ctx.arcTo(x + w, y, x + w, y + rr, rr);
    ctx.lineTo(x + w, y + h - rr);
    ctx.arcTo(x + w, y + h, x + w - rr, y + h, rr);
    ctx.lineTo(x + rr, y + h);
    ctx.arcTo(x, y + h, x, y + h - rr, rr);
    ctx.lineTo(x, y + rr);
    ctx.arcTo(x, y, x + rr, y, rr);
    ctx.closePath();
  }

  // ---------------------------------------------------------------- 画布
  const canvas = dom.canvas;
  const ctx = canvas.getContext('2d');
  let W = 0;
  let H = 0;

  function resize() {
    const rect = canvas.getBoundingClientRect();
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    W = Math.max(320, Math.round(rect.width));
    H = Math.max(220, Math.round(rect.height));
    canvas.width = Math.round(W * dpr);
    canvas.height = Math.round(H * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  const figScale = () => clamp(H / 340, 0.7, 2.6);
  const fightX = (side) => W * (side === 'left' ? 0.30 : 0.70);
  const chestY = () => H * GROUND_RATIO - 100 * figScale();
  const pointOf = (side) => ({ x: fightX(side), y: chestY() });

  // ---------------------------------------------------------------- 选手对象
  function createFighter(side) {
    const c = CONFIG.fighters[side];
    return {
      side: side,
      name: c.name,
      model: c.model,
      hp: CONFIG.max_hp,
      maxHp: CONFIG.max_hp,
      cooldowns: {},
      uses: {},
      guard: false,
      dodge: false,
      charge: false,
      vuln: 0,
      weak: false,
      palette: PALETTES[side],
      anim: { kind: 'idle', start: -1e9, dur: 0 },
      phase: Math.random() * Math.PI * 2
    };
  }

  function play(f, kind, dur) {
    f.anim = { kind: kind, start: nowMs(), dur: dur };
  }

  function animOf(f) {
    const a = f.anim;
    const t = a.dur > 0 ? (nowMs() - a.start) / a.dur : 1;
    if (t >= 1) return { kind: 'idle', t: 0 };
    return { kind: a.kind, t: t < 0 ? 0 : t };
  }

  // ---------------------------------------------------------------- 技能可用性
  function availableFor(f) {
    return SKILLS.filter(function (s) {
      if (f.cooldowns[s.id] > 0) return false;
      if (s.uses != null && (f.uses[s.id] || 0) >= s.uses) return false;
      return true;
    }).map(function (s) { return s.id; });
  }

  function unavailableNames(f) {
    return SKILLS.filter(function (s) {
      if (f.cooldowns[s.id] > 0) return true;
      return s.uses != null && (f.uses[s.id] || 0) >= s.uses;
    }).map(function (s) { return s.name; });
  }

  function statusChips(f) {
    const out = [];
    if (f.guard) out.push({ text: '格挡', kind: 'buff' });
    if (f.dodge) out.push({ text: '闪避', kind: 'buff' });
    if (f.charge) out.push({ text: '蓄力', kind: 'buff' });
    if (f.vuln > 0) out.push({ text: '破防 ' + f.vuln, kind: 'debuff' });
    if (f.weak) out.push({ text: '被嘲讽', kind: 'debuff' });
    return out;
  }

  // ---------------------------------------------------------------- 请求模型
  function snapshot(f) {
    return {
      hp: f.hp,
      maxHp: f.maxHp,
      statuses: statusChips(f).map(function (c) { return c.text; })
    };
  }

  async function ask(side, signal) {
    const me = fighters[side];
    const foe = fighters[other(side)];
    const body = {
      side: side,
      round: state.round,
      available: availableFor(me),
      cooling: unavailableNames(me),
      recent: state.recent.slice(0, 6),
      self: snapshot(me),
      opponent: snapshot(foe)
    };

    try {
      const resp = await fetch(API_ACT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: signal
      });
      const data = await resp.json();
      if (!data.action) throw new Error(data.error || 'HTTP ' + resp.status);
      data.side = side;
      return data;
    } catch (err) {
      const pool = availableFor(me);
      return {
        side: side,
        action: pool[rnd(0, pool.length - 1)] || 'attack',
        line: '',
        reasoning: '',
        raw: '',
        latency_ms: 0,
        fallback: true,
        error: String((err && err.message) || err)
      };
    }
  }

  // ---------------------------------------------------------------- 结算
  function applyAction(act) {
    const me = fighters[act.side];
    const foe = fighters[other(act.side)];
    const sk = SKILL_BY_ID[act.action];
    const res = { side: act.side, skill: sk, dmg: 0, heal: 0, dodged: false, notes: [], act: act };

    if (sk.cd > 0) me.cooldowns[sk.id] = sk.cd + 1;
    if (sk.uses != null) me.uses[sk.id] = (me.uses[sk.id] || 0) + 1;

    switch (sk.type) {
      case 'guard':
        me.guard = true;
        break;

      case 'dodge':
        me.dodge = true;
        break;

      case 'charge':
        me.charge = true;
        res.notes.push('下次攻击伤害翻倍');
        break;

      case 'heal': {
        const before = me.hp;
        me.hp = Math.min(me.maxHp, me.hp + rnd(sk.min, sk.max));
        res.heal = me.hp - before;
        if (res.heal <= 0) res.notes.push('生命已满，回复落空');
        break;
      }

      case 'debuff':
        foe.vuln = Math.max(foe.vuln, sk.turns);
        res.notes.push('对手接下来 2 回合受到伤害 +30%');
        break;

      case 'taunt':
        foe.weak = true;
        res.notes.push('对手下次攻击伤害 -25%');
        break;

      case 'attack': {
        let mult = 1;
        if (me.charge) { mult *= 2; me.charge = false; res.notes.push('蓄力生效，伤害翻倍'); }
        if (me.weak) { mult *= SKILL_BY_ID.taunt.mult; me.weak = false; res.notes.push('被嘲讽，伤害 -25%'); }
        if (foe.vuln > 0) { mult *= SKILL_BY_ID.debuff.mult; res.notes.push('对手破防中，伤害 +30%'); }

        let dodged = false;
        if (foe.dodge) {
          foe.dodge = false;
          if (Math.random() < SKILL_BY_ID.dodge.chance) dodged = true;
        }

        if (dodged) {
          res.dodged = true;
          res.notes.push('对手闪避成功，攻击落空');
        } else {
          if (foe.guard) { mult *= 1 - SKILL_BY_ID.guard.reduce; res.notes.push('对手格挡，伤害 -60%'); }
          res.dmg = Math.max(1, Math.round(rnd(sk.min, sk.max) * mult));
          foe.hp = Math.max(0, foe.hp - res.dmg);
        }
        break;
      }
    }
    return res;
  }

  function endOfRound() {
    ['left', 'right'].forEach(function (side) {
      const f = fighters[side];
      Object.keys(f.cooldowns).forEach(function (id) {
        if (f.cooldowns[id] > 0) f.cooldowns[id] -= 1;
      });
      if (f.vuln > 0) f.vuln -= 1;
      f.guard = false;
      f.dodge = false;
    });
  }

  function checkKO() {
    const left = fighters.left;
    const right = fighters.right;
    if (left.hp > 0 && right.hp > 0) return false;

    state.over = true;
    state.running = false;

    play(left, left.hp <= 0 ? 'ko' : 'idle', 900);
    play(right, right.hp <= 0 ? 'ko' : 'idle', 900);
    shakeIt(10, 520);

    const winner = right.hp <= 0 ? left : right;
    const loser = right.hp <= 0 ? right : left;
    const both = left.hp <= 0 && right.hp <= 0;

    const text = both ? '同时倒下' : winner.name + ' 获胜';
    const desc = both ? '双方血量同时归零，平局。' :
      loser.name + '（' + loser.model + '）血量归零，判定落败。';

    dom.result.hidden = false;
    dom.result.innerHTML = '';
    const w = document.createElement('div');
    w.className = 'win';
    w.textContent = text;
    const d = document.createElement('div');
    d.className = 'desc';
    d.textContent = desc;
    dom.result.appendChild(w);
    dom.result.appendChild(d);

    dom.roundBadge.hidden = true;
    setStatus('对决结束：' + text, false);
    addEntry({
      kind: 'ko',
      title: 'KO',
      who: both ? '双方' : winner.name,
      note: desc + ' 共进行 ' + state.round + ' 回合。'
    });
    setButtons();
    return true;
  }

  function shakeIt(mag, dur) {
    shake = { mag: mag, start: nowMs(), dur: dur };
  }

  // ---------------------------------------------------------------- 特效
  function spawnSpark(side, big) {
    const p = pointOf(side);
    const pal = fighters[side].palette;
    const n = big ? 22 : 12;
    for (let i = 0; i < n; i++) {
      const ang = Math.random() * Math.PI * 2;
      const sp = (big ? 190 : 120) * (0.35 + Math.random());
      particles.push({
        x: p.x, y: p.y,
        vx: Math.cos(ang) * sp, vy: Math.sin(ang) * sp - 30,
        life: 1, decay: 1.7 + Math.random(), size: big ? 3.4 : 2.3,
        color: Math.random() < 0.45 ? pal.accent : pal.glow
      });
    }
    fx.push({ type: 'spark', x: p.x, y: p.y, start: nowMs(), dur: big ? 420 : 300, color: pal.accent, big: big });
  }

  function spawnRing(side, color, dur) {
    const p = pointOf(side);
    fx.push({ type: 'ring', x: p.x, y: p.y, start: nowMs(), dur: dur || 620, color: color });
  }

  function spawnBolt(fromSide, toSide) {
    const a = pointOf(fromSide);
    const b = pointOf(toSide);
    fx.push({
      type: 'bolt', start: nowMs(), dur: 520,
      ax: a.x, ay: a.y, bx: b.x, by: b.y,
      color: fighters[fromSide].palette.accent
    });
  }

  function spawnHeal(side) {
    const p = pointOf(side);
    for (let i = 0; i < 16; i++) {
      particles.push({
        x: p.x + (Math.random() * 2 - 1) * 46,
        y: p.y + 30 + Math.random() * 40,
        vx: (Math.random() * 2 - 1) * 14,
        vy: -60 - Math.random() * 70,
        life: 1, decay: 1.1 + Math.random(),
        size: 2.4, color: '#4ade80'
      });
    }
    fx.push({ type: 'ring', x: p.x, y: p.y, start: nowMs(), dur: 620, color: '#4ade80' });
  }

  function spawnFloater(side, text, color) {
    const p = pointOf(side);
    floaters.push({
      text: text, color: color, start: nowMs(), dur: 950,
      x: p.x + (Math.random() * 2 - 1) * 22,
      y: p.y - 46
    });
  }

  function playAnims(res) {
    const me = fighters[res.side];
    const foeSide = other(res.side);
    const foe = fighters[foeSide];
    const sk = res.skill;

    switch (sk.type) {
      case 'attack': {
        play(me, sk.id === 'heavy' ? 'heavy' : 'attack', sk.id === 'heavy' ? 760 : 620);
        if (sk.id === 'heavy') shakeIt(6, 340);
        setTimeout(function () {
          if (res.dodged) {
            play(foe, 'dodge', 480);
            spawnFloater(foeSide, 'MISS', '#7d8ba3');
          } else {
            play(foe, 'hit', 420);
            spawnSpark(foeSide, sk.id === 'heavy');
            spawnFloater(foeSide, '-' + res.dmg, '#ff5f6d');
            if (sk.id === 'heavy') shakeIt(9, 420);
          }
        }, sk.id === 'heavy' ? 340 : 260);
        break;
      }
      case 'guard':
        play(me, 'guard', 700);
        spawnRing(res.side, me.palette.accent, 700);
        break;

      case 'dodge':
        play(me, 'dodge', 620);
        break;

      case 'charge':
        play(me, 'charge', 700);
        spawnRing(res.side, me.palette.accent, 700);
        spawnFloater(res.side, '蓄力', '#4ade80');
        break;

      case 'heal':
        play(me, 'heal', 700);
        spawnHeal(res.side);
        if (res.heal > 0) spawnFloater(res.side, '+' + res.heal, '#4ade80');
        break;

      case 'debuff':
        play(me, 'debuff', 560);
        spawnBolt(res.side, foeSide);
        setTimeout(function () {
          play(foe, 'hit', 380);
          spawnFloater(foeSide, '破防', '#ff8fb1');
        }, 340);
        break;

      case 'taunt':
        play(me, 'taunt', 620);
        spawnRing(foeSide, foe.palette.accent, 560);
        spawnFloater(foeSide, '被嘲讽', '#ff8fb1');
        break;
    }
  }

  // ---------------------------------------------------------------- 战报
  function scrollLog() {
    dom.log.scrollTop = dom.log.scrollHeight;
  }

  function clearLogEmpty() {
    dom.log.innerHTML = '';
    const p = document.createElement('p');
    p.className = 'log-empty';
    p.textContent = '点「开始对打」，两个模型会自己决定每回合出什么招。';
    dom.log.appendChild(p);
  }

  function entryHead(round, name, skillName, skillId) {
    const head = document.createElement('div');
    head.className = 'entry-head';

    const r = document.createElement('span');
    r.className = 'rnd';
    r.textContent = 'R' + round;
    head.appendChild(r);

    const who = document.createElement('span');
    who.className = 'who';
    who.textContent = name;
    head.appendChild(who);

    const sk = document.createElement('span');
    sk.className = 'skill';
    sk.textContent = skillName;
    if (skillId) {
      const code = document.createElement('code');
      code.textContent = skillId;
      code.style.marginLeft = '5px';
      code.style.fontFamily = MONO;
      code.style.fontSize = '10px';
      code.style.color = '#7d8ba3';
      sk.appendChild(code);
    }
    head.appendChild(sk);
    return head;
  }

  function addEntry(opt) {
    const el = document.createElement('div');
    el.className = 'entry ' + (opt.kind || 'system');

    const head = document.createElement('div');
    head.className = 'entry-head';
    const tag = document.createElement('span');
    tag.className = 'rnd';
    tag.textContent = opt.title || '系统';
    head.appendChild(tag);
    const who = document.createElement('span');
    who.className = 'who';
    who.textContent = opt.who || '';
    head.appendChild(who);
    el.appendChild(head);

    if (opt.note) {
      const note = document.createElement('div');
      note.className = 'note';
      note.textContent = opt.note;
      el.appendChild(note);
    }
    dom.log.appendChild(el);
    scrollLog();
  }

  function renderEntry(res) {
    const act = res.act;
    const f = fighters[res.side];
    const el = document.createElement('div');
    el.className = 'entry ' + res.side;

    const head = entryHead(state.round, f.name, res.skill.name, res.skill.id);

    const dmg = document.createElement('span');
    dmg.className = 'dmg';
    if (res.dmg > 0) {
      dmg.textContent = '-' + res.dmg;
    } else if (res.heal > 0) {
      dmg.className = 'dmg heal';
      dmg.textContent = '+' + res.heal;
    } else if (res.dodged) {
      dmg.className = 'dmg zero';
      dmg.textContent = '落空';
    } else {
      dmg.className = 'dmg zero';
      dmg.textContent = '生效';
    }
    head.appendChild(dmg);
    el.appendChild(head);

    if (act.line) {
      const line = document.createElement('div');
      line.className = 'line';
      line.textContent = '「' + act.line + '」';
      el.appendChild(line);
    }

    const notes = [];
    if (res.notes.length) notes.push(res.notes.join('；'));
    if (act.fallback) notes.push('模型没按格式出招，已随机补招');
    if (act.error) notes.push(act.error);
    notes.push(act.latency_ms + ' ms');
    const note = document.createElement('div');
    note.className = 'note';
    note.textContent = notes.join(' · ');
    el.appendChild(note);

    const detailText = (act.reasoning ? '【思考】\n' + act.reasoning + '\n\n' : '') +
      (act.raw ? '【输出】\n' + act.raw : '');
    if (detailText) {
      const details = document.createElement('details');
      const summary = document.createElement('summary');
      summary.textContent = '模型原始输出';
      const pre = document.createElement('p');
      pre.textContent = detailText;
      details.appendChild(summary);
      details.appendChild(pre);
      el.appendChild(details);
    }

    dom.log.appendChild(el);
    scrollLog();

    const brief = f.name + ' 使用「' + res.skill.name + '」' +
      (res.dmg > 0 ? '，造成 ' + res.dmg + ' 点伤害' :
        res.dodged ? '，被对手闪避' :
          res.heal > 0 ? '，回复 ' + res.heal + ' 点生命' : '，生效');
    state.recent.unshift(brief);
    if (state.recent.length > 8) state.recent.length = 8;
  }

  // ---------------------------------------------------------------- 界面同步
  function syncCards() {
    ['left', 'right'].forEach(function (side) {
      const f = fighters[side];
      const el = ui[side];
      const pct = clamp((f.hp / f.maxHp) * 100, 0, 100);
      el.fill.style.width = pct + '%';
      el.fill.className = 'hp-fill' + (pct <= 30 ? ' low' : '');
      el.hp.textContent = f.hp + ' / ' + f.maxHp;
      el.name.textContent = f.name;
      el.model.textContent = f.model;
      el.statuses.innerHTML = '';
      statusChips(f).forEach(function (c) {
        const chip = document.createElement('span');
        chip.className = 'chip ' + c.kind;
        chip.textContent = c.text;
        el.statuses.appendChild(chip);
      });
    });
  }

  function setStatus(text, thinking) {
    dom.status.textContent = text;
    dom.status.className = thinking ? 'status thinking' : 'status';
  }

  function setButtons() {
    dom.btnStart.disabled = state.running;
    dom.btnStop.disabled = !state.running;
    dom.btnStart.textContent = state.over ? '再打一局' : (state.running ? '对打中…' : '开始对打');
  }

  // ---------------------------------------------------------------- 回合循环
  async function runRound(myToken) {
    state.round += 1;
    dom.roundBadge.hidden = false;
    dom.roundBadge.textContent = 'ROUND ' + state.round;
    setStatus('第 ' + state.round + ' 回合：双方思考中…', true);

    state.ac = new AbortController();
    const acts = await Promise.all([
      ask('left', state.ac.signal),
      ask('right', state.ac.signal)
    ]);
    if (state.token !== myToken || !state.running || state.over) return;

    const order = acts.slice().sort(function (a, b) {
      const sa = SKILL_BY_ID[a.action].spd;
      const sb = SKILL_BY_ID[b.action].spd;
      if (sa !== sb) return sb - sa;
      return a.side === 'left' ? -1 : 1;
    });

    for (let i = 0; i < order.length; i++) {
      if (state.token !== myToken || !state.running || state.over) return;
      const res = applyAction(order[i]);
      renderEntry(res);
      playAnims(res);
      syncCards();
      setStatus('第 ' + state.round + ' 回合：结算中…', true);
      await sleep(880);
      if (checkKO()) return;
    }

    endOfRound();
    syncCards();
  }

  async function loop() {
    const myToken = state.token;
    while (state.running && state.token === myToken && !state.over) {
      await runRound(myToken);
      if (state.token !== myToken || !state.running || state.over) break;
      setStatus('双方喘口气…', false);
      await sleep((CONFIG && CONFIG.turn_delay_ms) || 400);
    }
    if (state.token !== myToken) return;
    if (!state.running && !state.over) setStatus('已停止', false);
    setButtons();
  }

  // ---------------------------------------------------------------- 控制
  function start() {
    if (state.running) return;
    if (state.over) reset();
    state.running = true;
    state.over = false;
    state.token += 1;
    dom.result.hidden = true;
    setButtons();
    setStatus('双方入场…', true);
    loop();
  }

  function stop() {
    if (!state.running) return;
    state.running = false;
    state.token += 1;
    if (state.ac) state.ac.abort();
    setStatus('已停止（可点开始继续）', false);
    setButtons();
  }

  function reset() {
    state.running = false;
    state.over = false;
    state.token += 1;
    state.round = 0;
    state.recent = [];
    if (state.ac) state.ac.abort();
    fighters.left = createFighter('left');
    fighters.right = createFighter('right');
    fx.length = 0;
    particles.length = 0;
    floaters.length = 0;
    dom.roundBadge.hidden = true;
    dom.result.hidden = true;
    clearLogEmpty();
    addEntry({
      kind: 'system',
      title: '就绪',
      who: fighters.left.name + ' VS ' + fighters.right.name,
      note: '双方各 ' + CONFIG.max_hp + ' 点生命。出手的技能由两个大模型自己从固定技能池里挑。'
    });
    syncCards();
    setStatus('等待开始', false);
    setButtons();
  }

  function renderSkillPool() {
    dom.skillPool.innerHTML = '';
    SKILLS.forEach(function (s) {
      const item = document.createElement('div');
      item.className = 'skill-item';

      const n = document.createElement('div');
      n.className = 'n';
      n.textContent = s.name;
      const code = document.createElement('code');
      code.textContent = s.id;
      n.appendChild(code);
      item.appendChild(n);

      const d = document.createElement('div');
      d.className = 'd';
      d.textContent = s.desc;
      item.appendChild(d);

      dom.skillPool.appendChild(item);
    });
  }

  // ---------------------------------------------------------------- 绘制：场景
  function drawBackground() {
    const g = ctx.createRadialGradient(W / 2, H * 0.35, H * 0.05, W / 2, H * 0.5, H * 1.05);
    g.addColorStop(0, '#16233a');
    g.addColorStop(0.55, '#0b1220');
    g.addColorStop(1, '#05080e');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, W, H);

    const gy = H * GROUND_RATIO;
    const beam = ctx.createLinearGradient(0, 0, 0, gy);
    beam.addColorStop(0, 'rgba(56,225,255,0.05)');
    beam.addColorStop(1, 'rgba(180,139,255,0.02)');
    ctx.fillStyle = beam;
    ctx.fillRect(0, 0, W, gy);

    // 远景立柱
    ctx.save();
    ctx.strokeStyle = 'rgba(120,160,220,0.09)';
    ctx.lineWidth = 1;
    for (let i = 1; i < 8; i++) {
      const x = (W / 8) * i;
      ctx.beginPath();
      ctx.moveTo(x, gy);
      ctx.lineTo(W / 2 + (x - W / 2) * 0.25, H * 0.12);
      ctx.stroke();
    }
    const horizon = ctx.createLinearGradient(0, H * 0.5, 0, gy);
    horizon.addColorStop(0, 'rgba(56,225,255,0)');
    horizon.addColorStop(1, 'rgba(56,225,255,0.07)');
    ctx.fillStyle = horizon;
    ctx.fillRect(0, H * 0.5, W, gy - H * 0.5);
    ctx.restore();
  }

  function drawFloor() {
    const gy = H * GROUND_RATIO;
    const g = ctx.createLinearGradient(0, gy, 0, H);
    g.addColorStop(0, '#0f1826');
    g.addColorStop(1, '#070b12');
    ctx.fillStyle = g;
    ctx.fillRect(0, gy, W, H - gy);

    ctx.save();
    ctx.strokeStyle = 'rgba(56,225,255,0.5)';
    ctx.lineWidth = 1.4;
    ctx.shadowColor = 'rgba(56,225,255,0.75)';
    ctx.shadowBlur = 14;
    ctx.beginPath();
    ctx.moveTo(0, gy);
    ctx.lineTo(W, gy);
    ctx.stroke();
    ctx.restore();

    ctx.save();
    ctx.strokeStyle = 'rgba(90,130,190,0.13)';
    ctx.lineWidth = 1;
    for (let i = 1; i <= 6; i++) {
      const y = gy + Math.pow(i / 6, 1.7) * (H - gy);
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(W, y);
      ctx.stroke();
    }
    for (let i = -6; i <= 6; i++) {
      ctx.beginPath();
      ctx.moveTo(W / 2 + i * (W / 12), gy);
      ctx.lineTo(W / 2 + i * (W / 4), H);
      ctx.stroke();
    }
    ctx.restore();
  }

  // ---------------------------------------------------------------- 绘制：粒子与特效
  function stepParticles(dt) {
    for (let i = particles.length - 1; i >= 0; i--) {
      const p = particles[i];
      p.x += p.vx * dt;
      p.y += p.vy * dt;
      p.vy += 240 * dt;
      p.life -= p.decay * dt;
      if (p.life <= 0) particles.splice(i, 1);
    }
    for (let i = floaters.length - 1; i >= 0; i--) {
      if (nowMs() - floaters[i].start > floaters[i].dur) floaters.splice(i, 1);
    }
    for (let i = fx.length - 1; i >= 0; i--) {
      if (nowMs() - fx[i].start > fx[i].dur) fx.splice(i, 1);
    }
  }

  function drawParticles() {
    ctx.save();
    ctx.globalCompositeOperation = 'lighter';
    particles.forEach(function (p) {
      ctx.globalAlpha = clamp(p.life, 0, 1) * 0.9;
      ctx.fillStyle = p.color;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
      ctx.fill();
    });
    ctx.restore();
  }

  function drawFx(now) {
    ctx.save();
    ctx.globalCompositeOperation = 'lighter';
    fx.forEach(function (f) {
      const t = clamp((now - f.start) / f.dur, 0, 1);
      const k = 1 - t;

      if (f.type === 'spark') {
        ctx.globalAlpha = k;
        ctx.strokeStyle = f.color;
        ctx.lineWidth = f.big ? 3 : 2;
        ctx.shadowColor = f.color;
        ctx.shadowBlur = 18;
        const r = (f.big ? 62 : 40) * ease(t);
        ctx.beginPath();
        ctx.arc(f.x, f.y, r, 0, Math.PI * 2);
        ctx.stroke();
      } else if (f.type === 'ring') {
        ctx.globalAlpha = k * 0.85;
        ctx.strokeStyle = f.color;
        ctx.lineWidth = 2.4;
        ctx.shadowColor = f.color;
        ctx.shadowBlur = 20;
        const r = 26 + 52 * ease(t);
        ctx.beginPath();
        ctx.arc(f.x, f.y, r, 0, Math.PI * 2);
        ctx.stroke();
      } else if (f.type === 'bolt') {
        const p = ease(t);
        const x = f.ax + (f.bx - f.ax) * p;
        const y = f.ay + (f.by - f.ay) * p - Math.sin(Math.PI * p) * 34;
        ctx.globalAlpha = 0.35 * k;
        ctx.strokeStyle = f.color;
        ctx.lineWidth = 8;
        ctx.beginPath();
        ctx.moveTo(f.ax, f.ay);
        ctx.lineTo(x, y);
        ctx.stroke();

        ctx.globalAlpha = 1;
        ctx.fillStyle = f.color;
        ctx.shadowColor = f.color;
        ctx.shadowBlur = 24;
        ctx.beginPath();
        ctx.arc(x, y, 9 * (1 - p * 0.3), 0, Math.PI * 2);
        ctx.fill();
      }
    });
    ctx.restore();
  }

  function drawFloaters(now) {
    ctx.save();
    ctx.textAlign = 'center';
    ctx.font = '700 20px ' + MONO;
    floaters.forEach(function (fl) {
      const t = clamp((now - fl.start) / fl.dur, 0, 1);
      ctx.globalAlpha = 1 - t * t;
      ctx.fillStyle = fl.color;
      ctx.shadowColor = fl.color;
      ctx.shadowBlur = 12;
      ctx.fillText(fl.text, fl.x, fl.y - 42 * ease(t));
    });
    ctx.restore();
  }

  // ---------------------------------------------------------------- 绘制：选手
  const IDLE_ARM = { ex: 12, ey: -84, hx: 16, hy: -62 };
  const lerp = (a, b, t) => a + (b - a) * t;

  function armPose(kind) {
    switch (kind) {
      case 'attack': return { ex: 22, ey: -96, hx: 52, hy: -100 };
      case 'heavy': return { ex: 18, ey: -92, hx: 60, hy: -88 };
      case 'guard': return { ex: 15, ey: -104, hx: 5, hy: -126 };
      case 'charge': return { ex: 10, ey: -118, hx: 2, hy: -146 };
      case 'heal': return { ex: 15, ey: -92, hx: 12, hy: -68 };
      case 'hit': return { ex: -8, ey: -96, hx: -30, hy: -86 };
      case 'taunt': return { ex: 16, ey: -108, hx: 30, hy: -134 };
      case 'debuff': return { ex: 20, ey: -104, hx: 46, hy: -110 };
      default: return IDLE_ARM;
    }
  }

  function drawLimb(x0, y0, x1, y1, x2, y2, color, width) {
    ctx.strokeStyle = color;
    ctx.lineWidth = width;
    ctx.beginPath();
    ctx.moveTo(x0, y0);
    ctx.lineTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.stroke();
  }

  function drawFighter(f, now) {
    const scale = figScale();
    const gy = H * GROUND_RATIO;
    const x = fightX(f.side);
    const facing = f.side === 'left' ? 1 : -1;
    const a = animOf(f);
    const kind = a.kind;
    const t = a.t;
    const k = Math.sin(Math.PI * t);
    const kk = kind === 'idle' ? 0 : kind === 'ko' ? 1 : k;
    const p = f.palette;

    let dx = 0, dy = 0, rot = 0, crouch = 0;
    const bob = kind === 'idle' ? Math.sin(now / 640 + f.phase) * 2.2 : 0;

    switch (kind) {
      case 'attack': dx = 52 * k; rot = -0.10 * k; break;
      case 'heavy': dx = 76 * k; rot = -0.17 * k; break;
      case 'hit': dx = -28 * k; rot = 0.17 * k; break;
      case 'dodge': dx = -54 * k; rot = 0.07 * k; break;
      case 'guard': crouch = 8 * k; break;
      case 'charge': dy = -6 * k; break;
      case 'heal': dy = -4 * k; break;
      case 'taunt': rot = -0.06 * k; break;
      case 'debuff': rot = -0.09 * k; break;
      case 'ko': rot = -(Math.PI / 2) * ease(Math.min(1, t / 0.7)); dy = 8 * ease(Math.min(1, t / 0.7)); break;
      default: break;
    }

    // 地面投影
    ctx.save();
    ctx.globalAlpha = 0.42;
    ctx.fillStyle = '#000';
    ctx.beginPath();
    ctx.ellipse(x + dx, gy + 4, 36 * scale, 9 * scale, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();

    ctx.save();
    ctx.translate(x + dx, gy + dy + crouch - bob);
    ctx.scale(facing * scale, scale);
    if (rot) ctx.rotate(rot);

    const hip = -50, sh = -100, headY = -118, headR = 16;
    const pose = armPose(kind);
    const ex = lerp(IDLE_ARM.ex, pose.ex, kk);
    const ey = lerp(IDLE_ARM.ey, pose.ey, kk);
    const hx = lerp(IDLE_ARM.hx, pose.hx, kk);
    const hy = lerp(IDLE_ARM.hy, pose.hy, kk);

    ctx.lineCap = 'round';

    // 闪避残影
    if (kind === 'dodge') {
      ctx.save();
      ctx.globalAlpha = 0.55 * k;
      ctx.strokeStyle = p.accent;
      ctx.lineWidth = 2;
      for (let i = 0; i < 3; i++) {
        const yy = -34 - i * 26;
        ctx.beginPath();
        ctx.moveTo(-26 - i * 6, yy);
        ctx.lineTo(-64 - i * 16, yy);
        ctx.stroke();
      }
      ctx.restore();
    }

    // 后臂
    drawLimb(-8, sh + 8, ex * 0.5 - 10, ey + 12, hx * 0.5 - 14, hy + 18, p.body2, 9);
    // 腿
    drawLimb(-5, hip, -9, -22, -12, 0, p.body2, 11);
    drawLimb(5, hip, 9, -22, 13, 0, p.body, 11);

    // 躯干
    const tg = ctx.createLinearGradient(-17, sh, 17, hip);
    tg.addColorStop(0, p.body);
    tg.addColorStop(1, p.body2);
    ctx.fillStyle = tg;
    ctx.shadowColor = p.accent;
    ctx.shadowBlur = 16;
    ctx.beginPath();
    ctx.moveTo(-17, sh + 6);
    ctx.quadraticCurveTo(0, sh - 5, 17, sh + 6);
    ctx.lineTo(12, hip);
    ctx.quadraticCurveTo(0, hip + 8, -12, hip);
    ctx.closePath();
    ctx.fill();
    ctx.shadowBlur = 0;

    // 胸口能量核
    ctx.fillStyle = p.accent;
    ctx.shadowColor = p.glow;
    ctx.shadowBlur = 14 + 6 * Math.sin(now / 380 + f.phase);
    ctx.beginPath();
    ctx.arc(4, sh + 30, 5.2, 0, Math.PI * 2);
    ctx.fill();
    ctx.shadowBlur = 0;

    // 头
    ctx.fillStyle = p.body;
    ctx.beginPath();
    ctx.arc(3, headY, headR, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = p.accent;
    ctx.shadowColor = p.glow;
    ctx.shadowBlur = 18;
    rrPath(4, headY - 7, 15, 8, 3);
    ctx.fill();
    ctx.shadowBlur = 0;

    // 天线指示灯
    ctx.strokeStyle = p.accent;
    ctx.lineWidth = 2.4;
    ctx.beginPath();
    ctx.moveTo(1, headY - headR);
    ctx.lineTo(-3, headY - headR - 14);
    ctx.stroke();
    ctx.globalAlpha = 0.45 + 0.55 * (0.5 + 0.5 * Math.sin(now / 240 + f.phase));
    ctx.fillStyle = p.glow;
    ctx.beginPath();
    ctx.arc(-3, headY - headR - 16, 3.3, 0, Math.PI * 2);
    ctx.fill();
    ctx.globalAlpha = 1;

    // 前臂
    drawLimb(8, sh + 8, ex, ey, hx, hy, p.body, 10);

    // 格挡护盾
    if (f.guard) {
      ctx.save();
      ctx.globalAlpha = 0.85;
      ctx.strokeStyle = p.accent;
      ctx.lineWidth = 3;
      ctx.shadowColor = p.glow;
      ctx.shadowBlur = 20;
      ctx.beginPath();
      ctx.arc(6, sh + 16, 44, -Math.PI * 0.62, Math.PI * 0.62);
      ctx.stroke();
      ctx.restore();
    }

    // 蓄力光环
    if (f.charge) {
      ctx.save();
      ctx.globalAlpha = 0.7;
      ctx.strokeStyle = p.glow;
      ctx.lineWidth = 2;
      ctx.shadowColor = p.accent;
      ctx.shadowBlur = 18;
      for (let i = 0; i < 2; i++) {
        const r = 30 + i * 12 + Math.sin(now / 200 + i) * 3;
        ctx.beginPath();
        ctx.arc(4, sh + 24, r, 0, Math.PI * 2);
        ctx.stroke();
      }
      ctx.restore();
    }

    ctx.restore();
  }

  // ---------------------------------------------------------------- 主循环
  function frame(ts) {
    requestAnimationFrame(frame);
    const now = ts || nowMs();
    const dt = lastFrame ? Math.min(0.05, (now - lastFrame) / 1000) : 0.016;
    lastFrame = now;
    if (!W || !H || !fighters.left || !fighters.right) return;

    ctx.clearRect(0, 0, W, H);
    ctx.save();
    if (shake.mag > 0) {
      const decay = 1 - clamp((now - shake.start) / shake.dur, 0, 1);
      if (decay <= 0) {
        shake.mag = 0;
      } else {
        ctx.translate((Math.random() * 2 - 1) * shake.mag * decay,
          (Math.random() * 2 - 1) * shake.mag * decay);
      }
    }

    drawBackground();
    drawFloor();
    stepParticles(dt);
    drawFighter(fighters.left, now);
    drawFighter(fighters.right, now);
    drawParticles();
    drawFx(now);
    drawFloaters(now);

    ctx.restore();
  }

  // ---------------------------------------------------------------- 启动
  async function init() {
    resize();
    window.addEventListener('resize', resize);

    try {
      const res = await Promise.all([
        fetch(API_SKILLS).then(function (r) { return r.json(); }),
        fetch(API_CONFIG).then(function (r) { return r.json(); })
      ]);
      SKILLS = res[0].skills || [];
      CONFIG = res[1];
    } catch (err) {
      dom.subtitle.textContent = '加载失败：' + ((err && err.message) || err);
      setStatus('无法连接本地服务', false);
      return;
    }

    SKILL_BY_ID = {};
    SKILLS.forEach(function (s) { SKILL_BY_ID[s.id] = s; });

    renderSkillPool();
    dom.subtitle.textContent =
      CONFIG.fighters.left.name + '（' + CONFIG.fighters.left.model + '） VS ' +
      CONFIG.fighters.right.name + '（' + CONFIG.fighters.right.model + '）· 每回合出什么招由模型自己决定';

    reset();
    requestAnimationFrame(frame);
  }

  dom.btnStart.addEventListener('click', start);
  dom.btnStop.addEventListener('click', stop);
  dom.btnReset.addEventListener('click', function () { reset(); });
  dom.btnClearLog.addEventListener('click', function () { clearLogEmpty(); });

  init();
})();