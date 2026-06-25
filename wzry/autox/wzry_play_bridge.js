/**
 * AutoJS + PC 桥接：截图发 PC，PC OpenCV 识别队友蓝条，手机只执行移动。
 * 触控逻辑与 wzry_play.js 相同，请勿修改 joystick/gesture 参数。
 *
 * 1. PC 运行: python run_bridge.py
 * 2. 下方 PC_HOST 改成电脑 IP（与手机同一 WiFi）
 * 3. AutoX 运行本脚本
 */
"auto";

// ========== 改成你电脑的 IP（run_bridge.py 启动时会打印）==========
var PC_HOST = "172.17.8.78";
var BRIDGE_PORT = 9330;
// =================================================================

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
  joystick: scalePt(470, 875),
  move_radius: Math.round(110 * GAME_W / DESIGN_W),
  move_hold_ms: 400,
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
};

var BRIDGE_URL = "http://" + PC_HOST + ":" + BRIDGE_PORT + "/step";
var VISION_INTERVAL_MS = 800;
var MOVE_INTERVAL_MS = 280;
var HP_CHECK_MS = 3000;

function dbg(tag, msg) {
  log("[" + tag + "] " + msg);
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
      sleep(80);
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
      dbg("exec", "unknown action " + actionId);
  }
}

function grabScreen() {
  var img = null;
  try {
    img = captureScreen();
  } catch (e) {
    dbg("grab", "captureScreen: " + e);
  }
  if (!img) {
    var path = "/sdcard/wzry_cap.png";
    try {
      shell("screencap -p " + path, true);
      if (files.exists(path)) {
        img = images.read(path);
      }
    } catch (e2) {
      dbg("grab", "screencap: " + e2);
    }
  }
  return img;
}

function imgToBase64(img) {
  var path = "/sdcard/wzry_bridge.png";
  images.save(img, path, "png");
  var bytes = files.readBytes(path);
  importClass(android.util.Base64);
  return android.util.Base64.encodeToString(
    bytes,
    android.util.Base64.NO_WRAP
  );
}

function postStep(phase, img) {
  var t0 = Date.now();
  var payload = { phase: phase };
  if (img) {
    payload.image = imgToBase64(img);
  }
  var resp = http.postJson(BRIDGE_URL, payload, {
    headers: { "Content-Type": "application/json" },
    timeout: 15000,
  });
  var ms = Date.now() - t0;
  if (!resp || resp.statusCode !== 200) {
    var code = resp ? resp.statusCode : "null";
    throw new Error("bridge HTTP " + code);
  }
  var body = resp.body.string();
  var data = JSON.parse(body);
  if (data.error) {
    throw new Error(data.error);
  }
  dbg("bridge", phase + " ms=" + ms + " rule=" + (data.rule || data.ready) +
    (data.ally_count != null ? " n=" + data.ally_count : ""));
  return data;
}

function waitHpBar() {
  dbg("wait", "等待血条，PC=" + PC_HOST);
  toast("等待血条（PC识别）");
  var ticks = 0;
  while (true) {
    ticks++;
    var img = grabScreen();
    if (!img) {
      sleep(600);
      continue;
    }
    try {
      var resp = postStep("wait", img);
      if (resp.ready) {
        dbg("wait", "进局 ticks=" + ticks);
        toast("已开始");
        return;
      }
    } catch (e) {
      dbg("wait", "请求失败: " + e + " 检查 PC 是否运行 run_bridge.py");
    }
    sleep(500);
  }
}

function playWhileInGame() {
  var steps = 0;
  var moveCount = 0;
  var miss = 0;
  var lastVision = 0;
  var lastMove = 0;
  var lastHpCheck = 0;
  var plan = {
    action_id: 0,
    rule: "idle",
    hold_ms: CFG.move_hold_ms,
    in_game: true,
  };
  dbg("play", "对战循环 vision=" + VISION_INTERVAL_MS + "ms move=" + MOVE_INTERVAL_MS + "ms");
  lastVision = 0;
  lastMove = Date.now();
  lastHpCheck = Date.now();
  while (true) {
    var now = Date.now();
    if (now - lastVision >= VISION_INTERVAL_MS) {
      var img = grabScreen();
      if (!img) {
        sleep(200);
        continue;
      }
      try {
        plan = postStep("play", img);
        steps++;
        if (steps <= 5 || steps % 6 === 0) {
          dbg(
            "vision",
            "step=" +
              steps +
              " rule=" +
              (plan.rule || "idle") +
              " act=" +
              (plan.action_id || 0) +
              " n=" +
              (plan.ally_count != null ? plan.ally_count : "-")
          );
        }
      } catch (e) {
        dbg("play", "请求失败: " + e);
        sleep(500);
        continue;
      }
      lastVision = Date.now();
    }
    if (now - lastHpCheck >= HP_CHECK_MS) {
      if (plan.in_game === false) {
        miss++;
        dbg("hp", "未检测到血条 miss=" + miss + "/3");
        if (miss >= 3) {
          toast("已暂停，进局后继续");
          return;
        }
      } else {
        miss = 0;
      }
      lastHpCheck = Date.now();
    }
    if (now - lastMove >= MOVE_INTERVAL_MS) {
      var rule = plan.rule || "idle";
      if (
        (rule === "follow" || rule === "follow_close" || rule === "sticky") &&
        plan.action_id >= 1 &&
        plan.action_id <= 8
      ) {
        moveCount++;
        if (moveCount <= 8 || moveCount % 8 === 0) {
          dbg(
            "move",
            "#" +
              moveCount +
              " " +
              ACT_NAME[plan.action_id] +
              "(" +
              plan.action_id +
              ") plan=" +
              rule
          );
        }
        executeAction(plan.action_id, plan.hold_ms || CFG.move_hold_ms);
      }
      lastMove = Date.now();
    }
    sleep(30);
  }
}

if (!requestScreenCapture(true)) {
  toast("请授予截图权限");
  exit();
}
sleep(1000);

dbg("init", "桥接模式 PC=" + PC_HOST + ":" + BRIDGE_PORT);
dbg("init", "设备 " + device.width + "x" + device.height + " joy=" + CFG.joystick);
toast("桥接就绪，请先 PC 运行 run_bridge.py");

while (true) {
  try {
    waitHpBar();
    playWhileInGame();
  } catch (e) {
    dbg("error", String(e));
    toast("异常: " + e);
    sleep(2000);
  }
}
