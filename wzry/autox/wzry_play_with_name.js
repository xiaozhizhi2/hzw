/**
 * 规则 Agent · 手机端（紧密跟随队友，支持OCR识别名字）
 *
 * 支持两种模式：
 * 1. 只跟随蓝色血条（快速）
 * 2. OCR识别队友名字 + 蓝色血条（精准）
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

// ============== 配置区 ==============
var CFG = {
  delay: 200,
  joystick: scalePt(470, 875),
  move_radius: Math.round(110 * GAME_W / DESIGN_W),
  move_hold_ms: 500,
};

var RULE = {
  fieldCrop: [0.1, 0.78, 0.12, 0.88],
  ownHpCrop: [0.84, 0.98, 0.01, 0.28],
  bottomHpCrop: [0.82, 0.97, 0.35, 0.72],
  nameCrop: [0.08, 0.78, 0.02, 0.98],  // OCR名字识别区域
  cachedAllies: [],
  lastAllyScan: 0,
  cachedOwn: 1,
  lastOwnScan: 0,
  followCloseDist: 50,
  followMaxDistRatio: 0.6,
  allyBarHMin: Math.round(33 * (GAME_H / DESIGN_H)),
  allyBarHMax: Math.round(36 * (GAME_H / DESIGN_H)),
  allyBarWidthRatio: 3,
  blueHsv: [90, 50, 50, 130, 255, 255],
  morphKernel: 5,
  maskStep: 3,
  allyScanMs: 1500,  // 扫描间隔
  useOcr: true,      // 是否使用OCR识别名字
  ocrMinScore: 0.5,  // OCR最低匹配分数
  nameBelowOffset: 48,  // 名字在血条上方多少
  useMorph: false,
};

// ============== 队友名字配置 ==============
// 在这里填写你要跟随的队友名字（支持多个）
var TEAMMATE_NAMES = ["泥石流", "怎么说", "花球", "小青龙", "五里", "倾雨", "吃火锅"];

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
};

var SESSION = { startMs: Date.now(), playNo: 0 };
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
      CFG.move_radius
  );
  dbg(
    "cfg",
    "field=" +
      RULE.fieldCrop +
      " bottomHp=" +
      RULE.bottomHpCrop +
      " followMax=" +
      RULE.followMaxDistRatio +
      " barH=" +
      RULE.allyBarHMin +
      "-" +
      RULE.allyBarHMax
  );
  dbg("cfg", "队友名字=" + TEAMMATE_NAMES.join(","));
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
        Math.round(allies[i].x) +
        "," +
        Math.round(allies[i].y) +
        "," +
        allies[i].bw +
        "x" +
        (allies[i].bh != null ? allies[i].bh : "?") +
        (allies[i].name ? " name=" + allies[i].name : "") +
        (allies[i].score ? " score=" + allies[i].score.toFixed(2) : "") +
        " c=" +
        Math.round(allies[i].cx) +
        "," +
        Math.round(allies[i].cy) +
        ")"
    );
  }
  return "[" + parts.join(" ") + "]";
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
  var b = RULE.blueHsv;
  return inHsv(h, s, v, b[0], b[1], b[2], b[3], b[4], b[5]);
}

function isAllyBarShape(bw, bh) {
  return (
    bh >= RULE.allyBarHMin &&
    bh <= RULE.allyBarHMax &&
    bw > RULE.allyBarWidthRatio * bh
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

function cachedBottomHp(img) {
  var now = Date.now();
  if (now - RULE.lastOwnScan >= 500) {
    RULE.cachedOwn = bottomHpFill(img);
    RULE.lastOwnScan = now;
  }
  return RULE.cachedOwn;
}

// ============== OCR名字识别功能 ==============

function cleanText(text) {
  return text.replace(/\s+/g, "");
}

function nameScore(text, target) {
  text = cleanText(text);
  target = target;
  if (!text || !target) return 0;
  
  // 完全包含的话直接给满分
  if (text.indexOf(target) !== -1) {
    return 1.0;
  }
  
  // 简单匹配度计算
  var matches = 0;
  for (var i = 0; i < Math.min(text.length, target.length); i++) {
    if (text[i] === target[i]) {
      matches++;
    }
  }
  return matches / Math.max(text.length, target.length, 1);
}

function ocrNames(img) {
  var t0 = Date.now();
  var result = [];
  
  try {
    var roi = clipRel(img, RULE.nameCrop);
    
    // 使用AutoJS的OCR功能
    // 注意：需要设备支持OCR，或者使用百度OCR等插件
    if (typeof ocr !== "undefined") {
      // 尝试使用系统OCR
      var ocrResult = ocr.recognize(roi);
      if (ocrResult && ocrResult.length > 0) {
        for (var i = 0; i < ocrResult.length; i++) {
          var item = ocrResult[i];
          var text = item.text;
          var bounds = item.bounds;
          
          // 检查是否匹配我们要找的名字
          var bestScore = 0;
          var bestName = "";
          
          for (var j = 0; j < TEAMMATE_NAMES.length; j++) {
            var score = nameScore(text, TEAMMATE_NAMES[j]);
            if (score > bestScore && score >= RULE.ocrMinScore) {
              bestScore = score;
              bestName = TEAMMATE_NAMES[j];
            }
          }
          
          if (bestName) {
            result.push({
              x: bounds.left,
              y: bounds.top,
              w: bounds.width(),
              h: bounds.height(),
              cx: bounds.centerX(),
              cy: bounds.centerY(),
              text: text,
              name: bestName,
              score: bestScore
            });
          }
        }
      }
    } else {
      // 如果没有OCR功能，只使用蓝色血条
      dbg("ocr", "未检测到OCR功能，使用蓝色血条模式");
    }
  } catch (e) {
    dbg("ocr", "OCR识别异常: " + e);
  }
  
  var ms = Date.now() - t0;
  if (result.length > 0) {
    dbg("ocr", "找到" + result.length + "个队友 ms=" + ms);
  }
  return result;
}

// ============== 蓝色血条检测 ==============

function fieldRoiMeta(img) {
  var W = img.getWidth();
  var H = img.getHeight();
  return {
    roi: clipRel(img, RULE.fieldCrop),
    ox: Math.floor(RULE.fieldCrop[2] * W),
    oy: Math.floor(RULE.fieldCrop[0] * H),
  };
}

function offsetBars(bars, ox, oy) {
  for (var i = 0; i < bars.length; i++) {
    bars[i].x += ox;
    bars[i].y += oy;
    bars[i].cx += ox;
    bars[i].cy += oy;
  }
  return bars;
}

function findAllyBarsGrid(roi) {
  var w = roi.getWidth();
  var h = roi.getHeight();
  var step = RULE.maskStep;
  var grid = {};
  
  for (var y = 0; y < h; y += step) {
    for (var x = 0; x < w; x += step) {
      if (!matchColor(roi, x, y, isBlueHp)) {
        continue;
      }
      var gx = Math.floor(x / 48);
      var gy = Math.floor(y / 20);
      var key = gx + "_" + gy;
      if (!grid[key]) {
        grid[key] = {
          n: 0,
          minX: x,
          maxX: x + step,
          minY: y,
          maxY: y + step,
        };
      }
      var c = grid[key];
      c.n++;
      if (x < c.minX) c.minX = x;
      if (x + step > c.maxX) c.maxX = x + step;
      if (y < c.minY) c.minY = y;
      if (y + step > c.maxY) c.maxY = y + step;
    }
  }
  
  var boxes = [];
  for (var key in grid) {
    var cl = grid[key];
    if (cl.n < 3) continue;
    var bw = cl.maxX - cl.minX;
    var bh = cl.maxY - cl.minY;
    boxes.push({
      x: cl.minX,
      y: cl.minY,
      bw: bw,
      bh: bh,
      cx: cl.minX + bw / 2,
      cy: cl.minY + bh / 2,
      fill: 1,
    });
  }
  return boxes;
}

function filterBars(bars, minBw) {
  var kept = [];
  for (var i = 0; i < bars.length; i++) {
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

function findAllyBars(img) {
  var t0 = Date.now();
  var fm = fieldRoiMeta(img);
  var roi = fm.roi;
  
  var raw = findAllyBarsGrid(roi);
  var bars = [];
  for (var i = 0; i < raw.length; i++) {
    if (isAllyBarShape(raw[i].bw, raw[i].bh)) {
      bars.push(raw[i]);
    }
  }
  
  var filtered = filterBars(bars, 0);
  offsetBars(filtered, fm.ox, fm.oy);
  
  var ms = Date.now() - t0;
  if (filtered.length > 0) {
    dbg("ally", "找到" + filtered.length + "个蓝条 ms=" + ms);
  }
  return filtered;
}

// ============== 混合识别（OCR + 蓝条） ==============

function scanAlliesWithOcr(img) {
  var now = Date.now();
  if (now - RULE.lastAllyScan >= RULE.allyScanMs) {
    try {
      var allies = [];
      
      if (RULE.useOcr) {
        // 先尝试OCR识别名字
        var namedAllies = ocrNames(img);
        allies = allies.concat(namedAllies);
      }
      
      // 再识别蓝色血条
      var blueBars = findAllyBars(img);
      
      // 合并结果：如果OCR找到了，就优先用OCR的
      // 如果没有OCR结果，就用蓝条
      if (allies.length === 0) {
        allies = blueBars;
      } else {
        // 对于有名字的，标记一下
        for (var i = 0; i < allies.length; i++) {
          allies[i].hasName = true;
        }
        // 也可以把蓝条加进来（可选）
      }
      
      RULE.cachedAllies = allies;
    } catch (e) {
      dbg("ally", "scan异常: " + e);
    }
    RULE.lastAllyScan = now;
  }
  return RULE.cachedAllies;
}

function scanAllies(img) {
  return scanAlliesWithOcr(img);
}

// ============== 其他辅助函数 ==============

function ownHpRatio(img) {
  return bottomHpFill(img);
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
  info.allyCount = allies.length;

  var W = img.getWidth();
  var H = img.getHeight();
  var playerX = W * 0.5;
  var playerY = H * 0.55;
  var maxFollow = Math.min(W, H) * RULE.followMaxDistRatio;
  info.player = Math.round(playerX) + "," + Math.round(playerY);
  info.maxFollow = Math.round(maxFollow);

  if (allies.length === 0) {
    info.rule = "idle";
    info.reason = "no_ally";
    info.decideMs = Date.now() - t0;
    return { actionId: 0, info: info };
  }

  // 优先选择有名字的队友
  var best = null;
  var bestDist = 1e9;
  
  // 第一轮：优先找有名字的
  for (var j = 0; j < allies.length; j++) {
    if (!allies[j].hasName) continue;
    var dist = Math.hypot(allies[j].cx - playerX, allies[j].cy - playerY);
    if (dist > maxFollow) continue;
    if (dist < bestDist) {
      bestDist = dist;
      best = allies[j];
    }
  }
  
  // 第二轮：如果没有有名字的，就找最近的蓝条
  if (!best) {
    for (j = 0; j < allies.length; j++) {
      dist = Math.hypot(allies[j].cx - playerX, allies[j].cy - playerY);
      if (dist > maxFollow) continue;
      if (dist < bestDist) {
        bestDist = dist;
        best = allies[j];
      }
    }
  }

  if (!best) {
    info.rule = "idle";
    info.reason =
      "no_valid_ally n=" + allies.length + " maxDist=" + info.maxFollow;
    info.decideMs = Date.now() - t0;
    return { actionId: 0, info: info };
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
      Math.round(best.x) +
      "," +
      Math.round(best.y) +
      " " +
      best.bw +
      "x" +
      best.bh;
    if (best.name) {
      info.target += " name=" + best.name;
    }
    info.reason = "near_ally dist=" + info.followDist;
    info.decideMs = Date.now() - t0;
    return { actionId: closeAct, info: info };
  }
  var act = vectorToMove(best.cx - playerX, best.cy - playerY);
  info.rule = "follow";
  info.followDist = Math.round(bestDist);
  info.target =
    Math.round(best.x) +
    "," +
    Math.round(best.y) +
    " " +
    best.bw +
    "x" +
    best.bh;
  if (best.name) {
    info.target += " name=" + best.name;
  }
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
    " n=" +
    (i.allyCount != null ? i.allyCount : "-") +
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
  var lastImg = null;
  var plan = { actionId: 0, info: { rule: "idle" } };
  SESSION.playNo++;
  dbg("play", "进入对战循环 playNo=" + SESSION.playNo + " OCR模式=" + RULE.useOcr);
  RULE.lastAllyScan = 0;
  RULE.cachedAllies = [];
  lastVision = 0;
  lastHpCheck = Date.now();
  lastMove = Date.now();
  while (true) {
    var now = Date.now();
    var needGrab = !lastImg;
    if (now - lastVision >= RULE.allyScanMs) {
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
    if (now - lastVision >= RULE.allyScanMs) {
      try {
        plan = decide(img);
        steps++;
        dbg("vision", "step=" + steps + " " + formatPlan(plan));
      } catch (decideErr) {
        dbg("vision", "decide异常: " + decideErr);
      }
      lastVision = Date.now();
    }
    if (now - lastMove >= MOVE_INTERVAL_MS) {
      var rule = plan.info.rule;
      if (rule === "follow" || rule === "follow_close") {
        var moveId = plan.actionId;
        if (moveId >= 1 && moveId <= 8) {
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
                rule +
                " tgt=" +
                (plan.info.target || "-")
            );
          }
          executeAction(moveId, CFG.move_hold_ms);
        }
      }
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
