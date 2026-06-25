/**
 * 规则 Agent · 手机端（仅移动 + 放技能，进局/结算请手动操作）
 *
 * VS Code AutoX 运行；识别到血条后自动跟队友、放技能，血条消失后暂停等待。
 */
"auto";

var DESIGN_W = 2400;
var DESIGN_H = 1080;
var GAME_W = Math.max(device.width, device.height);
var GAME_H = Math.min(device.width, device.height);

function scalePt(x, y) {
  return [
    Math.round(x * GAME_W / DESIGN_W),
    Math.round(y * GAME_H / DESIGN_H),
  ];
}

var CFG = {
  delay: 200,
  skill_1: scalePt(1665, 950),
  skill_2: scalePt(1785, 750),
  skill_3: scalePt(2000, 650),
  joystick: scalePt(470, 875),
  move_radius: Math.round(110 * GAME_W / DESIGN_W),
  move_hold_ms: 400,
};

var RULE = {
  lowHpRatio: 0.5,
  skill1IntervalMs: 1000,
  redBarPixels: 90,
  fieldCrop: [0.1, 0.78, 0.12, 0.88],
  ownHpCrop: [0.84, 0.98, 0.01, 0.28],
  bottomHpCrop: [0.82, 0.97, 0.35, 0.72],
  lastSkill1: 0,
  cachedAllies: [],
  lastAllyScan: 0,
  cachedOwn: 1,
  lastOwnScan: 0,
  defaultMove: 8,
  followCloseDist: 15,
};

var ACT_NAME = {
  0: "idle",
  1: "up",
  2: "down",
  3: "left",
  4: "right",
  5: "up-left",
  6: "up-right",
  7: "down-left",
  8: "down-right",
  10: "skill_1",
  11: "skill_2",
  12: "skill_3",
};

var SESSION = { startMs: Date.now(), playNo: 0 };

// 先只做紧密跟随队友，技能逻辑暂时关闭
var ENABLE_SKILLS = false;
var MOVE_INTERVAL_MS = 280;

function dbg(tag, msg) {
  log("[" + tag + "] " + msg);
}

function logConfig() {
  dbg(
    "cfg",
    "joy=" +
      CFG.joystick[0] +
      "," +
      CFG.joystick[1] +
      " r=" +
      CFG.move_radius +
      " sk1=" +
      CFG.skill_1[0] +
      "," +
      CFG.skill_1[1] +
      " sk2=" +
      CFG.skill_2[0] +
      "," +
      CFG.skill_2[1] +
      " sk3=" +
      CFG.skill_3[0] +
      "," +
      CFG.skill_3[1]
  );
  dbg(
    "cfg",
    "field=" +
      RULE.fieldCrop +
      " bottomHp=" +
      RULE.bottomHpCrop +
      " skill1ms=" +
      RULE.skill1IntervalMs +
      " redPx>=" +
      RULE.redBarPixels
  );
}

function alliesSummary(allies) {
  if (!allies || allies.length === 0) {
    return "[]";
  }
  var parts = [];
  for (var i = 0; i < allies.length; i++) {
    parts.push(
      "#" +
        i +
        "(" +
        Math.round(allies[i].cx) +
        "," +
        Math.round(allies[i].cy) +
        ",w" +
        allies[i].bw +
        ")"
    );
  }
  return "[" + parts.join(" ") + "]";
}

function tapBtn(pt, name) {
  click(pt[0], pt[1]);
  log(name + " " + pt[0] + "," + pt[1]);
  sleep(CFG.delay);
}

function moveDir(dx, dy, holdMs) {
  var jx = CFG.joystick[0];
  var jy = CFG.joystick[1];
  var r = CFG.move_radius;
  var tx = jx + dx * r;
  var ty = jy + dy * r;
  var ms = holdMs || CFG.move_hold_ms;
  gesture(ms, [jx, jy], [jx, jy], [tx, ty]);
  sleep(150);
}

function executeAction(actionId, holdMs) {
  var ms = holdMs || CFG.move_hold_ms;
  switch (actionId) {
    case 0:
      sleep(100);
      break;
    case 1:
      moveDir(0, -1, ms);
      break;
    case 2:
      moveDir(0, 1, ms);
      break;
    case 3:
      moveDir(-1, 0, ms);
      break;
    case 4:
      moveDir(1, 0, ms);
      break;
    case 5:
      moveDir(-0.7, -0.7, ms);
      break;
    case 6:
      moveDir(0.7, -0.7, ms);
      break;
    case 7:
      moveDir(-0.7, 0.7, ms);
      break;
    case 8:
      moveDir(0.7, 0.7, ms);
      break;
    case 10:
      tapBtn(CFG.skill_1, "skill_1");
      break;
    case 11:
      tapBtn(CFG.skill_2, "skill_2");
      break;
    case 12:
      tapBtn(CFG.skill_3, "skill_3");
      break;
    default:
      log("unknown action " + actionId);
  }
}

function rgbAt(img, x, y) {
  var w = img.getWidth();
  var h = img.getHeight();
  if (x < 0 || y < 0 || x >= w || y >= h) {
    return [0, 0, 0];
  }
  var c = images.pixel(img, x, y);
  if (c < 0) {
    c = c >>> 0;
  }
  return [(c >> 16) & 0xff, (c >> 8) & 0xff, c & 0xff];
}

function rgbToHsv(r, g, b) {
  r /= 255;
  g /= 255;
  b /= 255;
  var max = Math.max(r, g, b);
  var min = Math.min(r, g, b);
  var h = 0;
  var v = max;
  var d = max - min;
  var s = max === 0 ? 0 : d / max;
  if (max !== min) {
    if (max === r) {
      h = (g - b) / d + (g < b ? 6 : 0);
    } else if (max === g) {
      h = (b - r) / d + 2;
    } else {
      h = (r - g) / d + 4;
    }
    h /= 6;
  }
  return [h * 180, s * 255, v * 255];
}

function inHsv(h, s, v, h0, s0, v0, h1, s1, v1) {
  return (
    h >= h0 &&
    h <= h1 &&
    s >= s0 &&
    s <= s1 &&
    v >= v0 &&
    v <= v1
  );
}

function isGreenHp(h, s, v) {
  return inHsv(h, s, v, 35, 50, 50, 88, 255, 255);
}

function isBlueHp(h, s, v) {
  return inHsv(h, s, v, 95, 70, 70, 130, 255, 255);
}

function isRedHp(h, s, v) {
  return (
    inHsv(h, s, v, 0, 70, 70, 12, 255, 255) ||
    inHsv(h, s, v, 168, 70, 70, 180, 255, 255)
  );
}

function matchColor(img, x, y, colorFn) {
  var rgb = rgbAt(img, x, y);
  var hsv = rgbToHsv(rgb[0], rgb[1], rgb[2]);
  return colorFn(hsv[0], hsv[1], hsv[2]);
}

function clipRel(img, box) {
  var W = img.getWidth();
  var H = img.getHeight();
  var y0 = Math.max(0, Math.floor(box[0] * H));
  var y1 = Math.min(H, Math.floor(box[1] * H));
  var x0 = Math.max(0, Math.floor(box[2] * W));
  var x1 = Math.min(W, Math.floor(box[3] * W));
  if (y1 <= y0) {
    y1 = Math.min(H, y0 + 1);
  }
  if (x1 <= x0) {
    x1 = Math.min(W, x0 + 1);
  }
  return images.clip(img, x0, y0, x1 - x0, y1 - y0);
}

function horizontalFillRatio(img, colorFn) {
  var w = img.getWidth();
  var h = img.getHeight();
  var step = Math.max(1, Math.floor(w / 80));
  var filled = 0;
  var total = 0;
  for (var x = 0; x < w; x += step) {
    total++;
    for (var y = 0; y < h; y++) {
      if (matchColor(img, x, y, colorFn)) {
        filled++;
        break;
      }
    }
  }
  return total > 0 ? filled / total : 1;
}

function grabScreen() {
  var t0 = Date.now();
  var img = null;
  var via = "";
  try {
    img = captureScreen();
    if (img) {
      via = "captureScreen";
    }
  } catch (e) {
    dbg("grab", "captureScreen异常: " + e);
  }
  if (!img) {
    var path = "/sdcard/wzry_cap.png";
    try {
      shell("screencap -p " + path, true);
      if (files.exists(path)) {
        img = images.read(path);
        via = "screencap";
      }
    } catch (e2) {
      dbg("grab", "screencap异常: " + e2);
    }
  }
  var ms = Date.now() - t0;
  if (img && ms >= 250) {
    dbg(
      "grab",
      via +
        " " +
        img.getWidth() +
        "x" +
        img.getHeight() +
        " ms=" +
        ms
    );
  }
  return img;
}

function countColorInBox(img, box, colorFn, step) {
  var roi = clipRel(img, box);
  var w = roi.getWidth();
  var h = roi.getHeight();
  var n = 0;
  step = step || 10;
  for (var y = 0; y < h; y += step) {
    for (var x = 0; x < w; x += step) {
      if (matchColor(roi, x, y, colorFn)) {
        n++;
      }
    }
  }
  return n;
}

function quickHpSignals(img) {
  return {
    ownPx: countColorInBox(img, RULE.ownHpCrop, isGreenHp, 5),
    bottomPx: countColorInBox(img, RULE.bottomHpCrop, isGreenHp, 5),
    greenPx: countColorInBox(img, RULE.fieldCrop, isGreenHp, 6),
    bluePx: countColorInBox(img, RULE.fieldCrop, isBlueHp, 6),
    bright: Math.round(avgBrightness(img, RULE.fieldCrop)),
    w: img.getWidth(),
    h: img.getHeight(),
  };
}

function avgBrightness(img, box) {
  var roi = clipRel(img, box);
  var w = roi.getWidth();
  var h = roi.getHeight();
  var sum = 0;
  var n = 0;
  var step = Math.max(10, Math.floor(w / 50));
  for (var y = 0; y < h; y += step) {
    for (var x = 0; x < w; x += step) {
      var px = rgbAt(roi, x, y);
      sum += (px[0] + px[1] + px[2]) / 3;
      n++;
    }
  }
  return n > 0 ? sum / n : 0;
}

function bottomHpFill(img) {
  var roi = clipRel(img, RULE.bottomHpCrop);
  return horizontalFillRatio(roi, isGreenHp);
}

function countRedPixelsFast(img) {
  var roi = clipRel(img, RULE.fieldCrop);
  var w = roi.getWidth();
  var h = roi.getHeight();
  var count = 0;
  for (var y = 0; y < h; y += 10) {
    for (var x = 0; x < w; x += 10) {
      if (matchColor(roi, x, y, isRedHp)) {
        count++;
      }
    }
  }
  return count;
}

function cachedBottomHp(img) {
  var now = Date.now();
  if (now - RULE.lastOwnScan >= 500) {
    RULE.cachedOwn = bottomHpFill(img);
    RULE.lastOwnScan = now;
  }
  return RULE.cachedOwn;
}

function scanAllies(img) {
  var now = Date.now();
  if (now - RULE.lastAllyScan >= 900) {
    try {
      RULE.cachedAllies = findAllyBars(img);
    } catch (e) {
      dbg("ally", "scan异常: " + e);
    }
    RULE.lastAllyScan = now;
  }
  return RULE.cachedAllies;
}

function ownHpRatio(img) {
  return bottomHpFill(img);
}

function countRedPixels(img) {
  var roi = clipRel(img, RULE.fieldCrop);
  var w = roi.getWidth();
  var h = roi.getHeight();
  var count = 0;
  for (var y = 0; y < h; y += 4) {
    for (var x = 0; x < w; x += 4) {
      if (matchColor(roi, x, y, isRedHp)) {
        count++;
      }
    }
  }
  return count;
}

function filterBars(bars, minBw) {
  var kept = [];
  var i;
  for (i = 0; i < bars.length; i++) {
    if ((bars[i].bw || 0) >= minBw) {
      kept.push(bars[i]);
    }
  }
  kept.sort(function (a, b) {
    return (b.bw || 0) - (a.bw || 0);
  });
  if (kept.length > 8) {
    kept = kept.slice(0, 8);
  }
  var merged = [];
  for (i = 0; i < kept.length; i++) {
    var dup = false;
    for (var k = 0; k < merged.length; k++) {
      if (
        Math.hypot(kept[i].cx - merged[k].cx, kept[i].cy - merged[k].cy) < 30
      ) {
        dup = true;
        break;
      }
    }
    if (!dup) {
      merged.push(kept[i]);
    }
  }
  if (merged.length > 4) {
    merged = merged.slice(0, 4);
  }
  return merged;
}

function isFieldAllyBar(bar, w, h) {
  if (bar.cy < h * 0.48) {
    return false;
  }
  if (bar.cy > h * 0.8) {
    return false;
  }
  if (bar.cx < w * 0.06) {
    return false;
  }
  if (bar.cx > w * 0.75) {
    return false;
  }
  if (bar.cx < w * 0.14 && bar.cy < h * 0.52) {
    return false;
  }
  return true;
}

function findAllyBars(img) {
  var t0 = Date.now();
  var roi = clipRel(img, RULE.fieldCrop);
  var w = roi.getWidth();
  var h = roi.getHeight();
  var yMin = Math.floor(h * 0.35);
  var yMax = Math.floor(h * 0.78);
  var xMin = Math.floor(w * 0.06);
  var xMax = Math.floor(w * 0.75);
  var step = 8;
  var grid = {};
  var blueHits = 0;
  for (var y = yMin; y < yMax; y += step) {
    for (var x = xMin; x < xMax; x += step) {
      if (!matchColor(roi, x, y, isBlueHp)) {
        continue;
      }
      blueHits++;
      var gx = Math.floor(x / 50);
      var gy = Math.floor(y / 36);
      var key = gx + "_" + gy;
      if (!grid[key]) {
        grid[key] = {
          n: 0,
          sx: 0,
          sy: 0,
          minX: x,
          maxX: x,
          minY: y,
          maxY: y,
        };
      }
      var c = grid[key];
      c.n++;
      c.sx += x;
      c.sy += y;
      if (x < c.minX) {
        c.minX = x;
      }
      if (x > c.maxX) {
        c.maxX = x;
      }
      if (y < c.minY) {
        c.minY = y;
      }
      if (y > c.maxY) {
        c.maxY = y;
      }
    }
  }
  var raw = [];
  for (var key in grid) {
    var cl = grid[key];
    if (cl.n < 3) {
      continue;
    }
    var bw = cl.maxX - cl.minX + step;
    var bh = cl.maxY - cl.minY + step;
    if (bw < 18 || bw > 72) {
      continue;
    }
    if (bh > 22) {
      continue;
    }
    var bar = {
      cx: cl.sx / cl.n,
      cy: cl.sy / cl.n,
      fill: 1,
      bw: Math.round(bw),
    };
    if (!isFieldAllyBar(bar, w, h)) {
      continue;
    }
    raw.push(bar);
  }
  var filtered = filterBars(raw, 18);
  var ms = Date.now() - t0;
  dbg(
    "ally",
    "hits=" +
      blueHits +
      " raw=" +
      raw.length +
      " filtered=" +
      filtered.length +
      " ms=" +
      ms
  );
  if (filtered.length > 0) {
    dbg("ally", "pos=" + alliesSummary(filtered));
  }
  return filtered;
}

function scanHpBar(img) {
  return quickHpSignals(img);
}

function hasHpBar(img) {
  return hasHpBarFromSignals(quickHpSignals(img));
}

function hasHpBarFromSignals(q) {
  if (q.bright < 5) {
    return false;
  }
  return (
    q.ownPx >= 5 ||
    q.bottomPx >= 5 ||
    q.greenPx >= 8 ||
    q.bluePx >= 8
  );
}

function inGameFast(img) {
  var bottom = countColorInBox(img, RULE.bottomHpCrop, isGreenHp, 14);
  if (bottom >= 4) {
    return { ok: true, bottom: bottom, blue: 0 };
  }
  var blue = countColorInBox(img, RULE.fieldCrop, isBlueHp, 20);
  return { ok: blue >= 6, bottom: bottom, blue: blue };
}

function vectorToMove(dx, dy) {
  if (Math.abs(dx) < 8 && Math.abs(dy) < 8) {
    return 0;
  }
  var sector = Math.round(Math.atan2(dy, dx) / (Math.PI / 4));
  while (sector < 0) {
    sector += 8;
  }
  return [4, 8, 2, 7, 3, 6, 1, 5][sector % 8];
}

function decide(img) {
  var t0 = Date.now();
  var info = {};
  var own = cachedBottomHp(img);
  info.ownHp = own.toFixed(2);

  var allies = scanAllies(img);
  info.allies = alliesSummary(allies);
  var minAlly = 1;
  if (allies.length > 0) {
    minAlly = allies[0].fill;
    for (var i = 1; i < allies.length; i++) {
      if (allies[i].fill < minAlly) {
        minAlly = allies[i].fill;
      }
    }
    info.minAllyHp = minAlly.toFixed(2);
    info.allyCount = allies.length;
  } else {
    info.allyCount = 0;
  }

  /* 技能暂时关闭，专注跟随
  if (
    (own > 0.05 && own < RULE.lowHpRatio) ||
    (allies.length > 0 && minAlly < RULE.lowHpRatio)
  ) {
    info.rule = "skill_3";
    info.reason = "low_hp own=" + info.ownHp + " minAlly=" + info.minAllyHp;
    info.decideMs = Date.now() - t0;
    return { actionId: 12, info: info };
  }

  var redPx = countRedPixelsFast(img);
  info.redPx = redPx;
  if (redPx >= RULE.redBarPixels) {
    info.rule = "skill_2";
    info.reason = "redPx=" + redPx + ">=" + RULE.redBarPixels;
    info.decideMs = Date.now() - t0;
    return { actionId: 11, info: info };
  }
  */

  var roi = clipRel(img, RULE.fieldCrop);
  var rw = roi.getWidth();
  var rh = roi.getHeight();
  var playerX = rw * 0.5;
  var playerY = rh * 0.55;
  info.player = Math.round(playerX) + "," + Math.round(playerY);
  var best = null;
  var bestDist = 1e9;
  for (var j = 0; j < allies.length; j++) {
    var dist = Math.hypot(allies[j].cx - playerX, allies[j].cy - playerY);
    if (dist < bestDist) {
      bestDist = dist;
      best = allies[j];
    }
  }
  if (!best) {
    info.rule = "move_default";
    info.reason =
      "no_field_target n=" +
      allies.length +
      " player=" +
      info.player;
    info.decideMs = Date.now() - t0;
    return { actionId: RULE.defaultMove, info: info };
  }
  if (bestDist < RULE.followCloseDist) {
    var cdx = best.cx - playerX;
    var cdy = best.cy - playerY;
    if (Math.abs(cdx) < 8 && Math.abs(cdy) < 8) {
      cdx = cdx >= 0 ? 12 : -12;
      cdy = cdy >= 0 ? 12 : -12;
    }
    var closeAct = vectorToMove(cdx, cdy);
    info.rule = "follow_close";
    info.followDist = Math.round(bestDist);
    info.target =
      Math.round(best.cx) + "," + Math.round(best.cy) + " w" + best.bw;
    info.reason = "near_ally dist=" + info.followDist;
    info.decideMs = Date.now() - t0;
    return { actionId: closeAct, info: info };
  }
  var dx = best.cx - playerX;
  var dy = best.cy - playerY;
  var act = vectorToMove(dx, dy);
  info.rule = "follow";
  info.followDist = Math.round(bestDist);
  info.followMode = "field_nearest";
  info.target =
    Math.round(best.cx) + "," + Math.round(best.cy) + " w" + best.bw;
  info.reason =
    "dx=" +
    Math.round(best.cx - playerX) +
    " dy=" +
    Math.round(best.cy - playerY) +
    " dist=" +
    info.followDist;
  info.decideMs = Date.now() - t0;
  return { actionId: act, info: info };
}

function formatPlan(plan) {
  var i = plan.info;
  return (
    "rule=" +
    i.rule +
    " act=" +
    plan.actionId +
    "(" +
    (ACT_NAME[plan.actionId] || "?") +
    ")" +
    " own=" +
    (i.ownHp || "-") +
    " ally=" +
    (i.minAllyHp || "-") +
    " n=" +
    (i.allyCount != null ? i.allyCount : "-") +
    " red=" +
    (i.redPx != null ? i.redPx : "-") +
    (i.followDist != null ? " dist=" + i.followDist : "") +
    (i.target ? " tgt=" + i.target : "") +
    (i.reason ? " why=" + i.reason : "") +
    (i.decideMs != null ? " ms=" + i.decideMs : "") +
    (i.allies ? " allies=" + i.allies : "")
  );
}

function waitHpBar() {
  dbg("wait", "等待血条（请手动进局）");
  toast("等待血条，请手动进局");
  var ticks = 0;
  var nullCaptures = 0;
  while (true) {
    ticks++;
    var t0 = Date.now();
    var img = grabScreen();
    var grabMs = Date.now() - t0;
    if (!img) {
      nullCaptures++;
      dbg(
        "wait",
        "截图失败 x" +
          nullCaptures +
          " grabMs=" +
          grabMs +
          "（请授权截图并保持游戏在前台）"
      );
      sleep(600);
      continue;
    }
    if (ticks === 1) {
      dbg("wait", "截图OK " + img.getWidth() + "x" + img.getHeight());
    }
    var s = scanHpBar(img);
    if (hasHpBar(img)) {
      RULE.lastSkill1 = Date.now();
      dbg(
        "wait",
        "识别到血条 ownPx=" +
          s.ownPx +
          " bottom=" +
          s.bottomPx +
          " green=" +
          s.greenPx +
          " blue=" +
          s.bluePx +
          " bright=" +
          s.bright +
          " ticks=" +
          ticks
      );
      toast("已开始");
      return;
    }
    dbg(
      "wait",
      "tick=" +
        ticks +
        " ownPx=" +
        s.ownPx +
        " bottom=" +
        s.bottomPx +
        " green=" +
        s.greenPx +
        " blue=" +
        s.bluePx +
        " bright=" +
        s.bright +
        " grabMs=" +
        grabMs +
        (s.bright < 5 ? " [画面偏黑]" : "")
    );
    if (ticks === 4) {
      try {
        images.save(img, "/sdcard/wzry_debug.png");
        dbg("wait", "已保存调试图 /sdcard/wzry_debug.png");
      } catch (saveErr) {
        dbg("wait", "保存调试图失败: " + saveErr);
      }
    }
    sleep(500);
  }
}

function playWhileInGame() {
  var steps = 0;
  var miss = 0;
  var lastHpCheck = 0;
  var lastVision = 0;
  var lastMove = 0;
  var lastImgAt = 0;
  var moveCount = 0;
  var skill1Count = 0;
  var lastImg = null;
  var plan = { actionId: RULE.defaultMove, info: { rule: "move_default" } };
  SESSION.playNo++;
  dbg("play", "进入对战循环 playNo=" + SESSION.playNo + " 仅跟随(技能已关)");
  RULE.lastSkill1 = Date.now();
  RULE.lastAllyScan = 0;
  RULE.cachedAllies = [];
  lastVision = Date.now();
  lastHpCheck = Date.now();
  lastMove = Date.now();
  while (true) {
    var now = Date.now();
    var needGrab = !lastImg;
    if (now - lastVision >= 900) {
      needGrab = true;
    }
    if (now - lastHpCheck >= 3000) {
      needGrab = true;
    }
    if (needGrab) {
      var g0 = Date.now();
      lastImg = grabScreen();
      lastImgAt = Date.now();
      var gms = Date.now() - g0;
      if (gms >= 80) {
        dbg("grab", "ms=" + gms);
      }
      if (!lastImg) {
        sleep(50);
        continue;
      }
    }
    var img = lastImg;
    if (now - lastHpCheck >= 3000) {
      var hp = inGameFast(img);
      if (!hp.ok) {
        miss++;
        dbg(
          "hp",
          "未检测到血条 miss=" +
            miss +
            "/3 bottom=" +
            hp.bottom +
            " blue=" +
            hp.blue
        );
        if (miss >= 3) {
          dbg("play", "血条消失，暂停（请手动结算/进下一局）");
          toast("已暂停，进局后继续");
          return;
        }
      } else {
        if (miss > 0) {
          dbg("hp", "血条恢复 miss清零");
        }
        miss = 0;
      }
      lastHpCheck = Date.now();
    }
    if (now - lastVision >= 900) {
      try {
        plan = decide(img);
        steps++;
        dbg("vision", "step=" + steps + " " + formatPlan(plan));
        /* 技能暂时关闭
        if (plan.actionId === 11 || plan.actionId === 12) {
          dbg(
            "exec",
            "即时技能 " +
              ACT_NAME[plan.actionId] +
              " id=" +
              plan.actionId
          );
          executeAction(plan.actionId, CFG.move_hold_ms);
        }
        */
      } catch (decideErr) {
        dbg("vision", "decide异常: " + decideErr);
      }
      lastVision = Date.now();
    }
    /* 1 技能暂时关闭
    if (now - RULE.lastSkill1 >= RULE.skill1IntervalMs) {
      var gap = now - RULE.lastSkill1;
      RULE.lastSkill1 = Date.now();
      skill1Count++;
      dbg(
        "skill1",
        "#" + skill1Count + " 间隔=" + gap + "ms plan=" + plan.info.rule
      );
      executeAction(10, CFG.move_hold_ms);
    }
    */
    if (now - lastMove >= MOVE_INTERVAL_MS) {
      var moveId = RULE.defaultMove;
      if (plan.actionId >= 1 && plan.actionId <= 8) {
        moveId = plan.actionId;
      }
      moveCount++;
      if (moveCount <= 8 || moveCount % 8 === 0) {
        dbg(
          "move",
          "#" +
            moveCount +
            " " +
            ACT_NAME[moveId] +
            "(" +
            moveId +
            ") plan=" +
            plan.info.rule
        );
      }
      executeAction(moveId, CFG.move_hold_ms);
      lastMove = Date.now();
    }
    sleep(20);
  }
}

if (!requestScreenCapture(true)) {
  toast("请授予截图权限");
  exit();
}
sleep(1000);

var probe = grabScreen();
if (probe) {
  dbg("init", "截图测试OK " + probe.getWidth() + "x" + probe.getHeight());
} else {
  dbg("init", "截图测试失败，请点「立即开始」授权截图");
}

dbg(
  "init",
  "设备 " +
    device.width +
    "x" +
    device.height +
    " 游戏区约 " +
    GAME_W +
    "x" +
    GAME_H
);
logConfig();
toast("脚本就绪，手动进局后自动开始");

while (true) {
  try {
    waitHpBar();
    playWhileInGame();
  } catch (e) {
    dbg("error", String(e));
    if (e && e.javaException) {
      dbg("error", "java: " + e.javaException);
    }
    toast("异常: " + e);
    sleep(2000);
  }
}
