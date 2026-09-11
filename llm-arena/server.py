#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LLM 竞技场 —— 本地服务端。

做两件事：
1. 托管 web/ 目录下的静态页面；
2. 代理 /api/act：把当前对局状态拼成提示词发给大模型，解析出固定技能池中的一招。

只用 Python 标准库，无需安装任何第三方包。

启动：python server.py [端口]
"""

from __future__ import annotations

import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(ROOT, "web")
CONFIG_PATH = os.path.join(ROOT, "config.json")

# ---------------------------------------------------------------- 固定技能池
# 模型只能在下面这些招式里选，禁止自创。spd 越大出手越早。
SKILLS = [
    {
        "id": "attack", "name": "普通攻击", "type": "attack", "spd": 50,
        "min": 6, "max": 12, "cd": 0, "uses": None,
        "desc": "造成 6-12 点伤害，无冷却",
    },
    {
        "id": "heavy", "name": "重击", "type": "attack", "spd": 30,
        "min": 14, "max": 22, "cd": 2, "uses": None,
        "desc": "造成 14-22 点伤害，冷却 2 回合，出手很慢",
    },
    {
        "id": "guard", "name": "格挡", "type": "guard", "spd": 90,
        "reduce": 0.6, "cd": 1, "uses": None,
        "desc": "本回合受到的伤害减少 60%，冷却 1 回合，出手最快",
    },
    {
        "id": "dodge", "name": "闪避", "type": "dodge", "spd": 80,
        "chance": 0.55, "cd": 1, "uses": None,
        "desc": "55% 概率完全闪避下一次攻击，冷却 1 回合",
    },
    {
        "id": "heal", "name": "回复", "type": "heal", "spd": 70,
        "min": 15, "max": 22, "cd": 3, "uses": 2,
        "desc": "回复 15-22 点生命，冷却 3 回合，全场最多用 2 次",
    },
    {
        "id": "charge", "name": "蓄力", "type": "charge", "spd": 85,
        "mult": 2, "cd": 2, "uses": None,
        "desc": "使自己下一次攻击伤害翻倍，冷却 2 回合",
    },
    {
        "id": "debuff", "name": "破防", "type": "debuff", "spd": 60,
        "mult": 1.3, "turns": 2, "cd": 3, "uses": None,
        "desc": "让对手接下来 2 回合受到的伤害增加 30%，冷却 3 回合",
    },
    {
        "id": "taunt", "name": "嘲讽", "type": "taunt", "spd": 65,
        "mult": 0.75, "cd": 0, "uses": None,
        "desc": "对手的下一次攻击伤害减少 25%，无冷却",
    },
]

SKILL_BY_ID = {s["id"]: s for s in SKILLS}


# ---------------------------------------------------------------- 配置读取
def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as fp:
        cfg = json.load(fp)
    cfg.setdefault("port", 8000)
    cfg.setdefault("max_hp", 200)
    cfg.setdefault("request_timeout", 90)
    cfg.setdefault("max_tokens", 1200)
    return cfg


def public_config(cfg: dict) -> dict:
    """给前端的配置，不含 api_key。"""
    return {
        "max_hp": cfg["max_hp"],
        "turn_delay_ms": cfg.get("turn_delay_ms", 400),
        "fighters": {
            side: {"name": f["name"], "model": f["model"]}
            for side, f in cfg["fighters"].items()
        },
    }


# ---------------------------------------------------------------- 提示词
SYSTEM_TEMPLATE = """你是 2D 格斗游戏《LLM 竞技场》中的一名选手。
你的擂台名是「{name}」，本体是语言模型 {model}。
你现在的对手是「{opp_name}」（本体是语言模型 {opp_model}）。

这是你死我活的擂台赛，每回合你必须从固定技能池里挑一招出手，并放一句挑衅台词。

技能池（只能从中选择，严禁自创、严禁改动数值）：
{skill_lines}

输出要求：
- 只能选「本回合可用技能」里列出的 id，冷却中的技能不许选；
- line 是一句不超过 20 个字的挑衅台词，凶狠、幽默、贴合你作为语言模型的身份，禁止脏话；
- 只输出一个 JSON 对象，不要 markdown 代码块，不要任何解释文字：

{{"action":"技能id","line":"台词"}}"""


def build_skill_lines(skill_ids):
    lines = []
    for sid in skill_ids:
        s = SKILL_BY_ID.get(sid)
        if s:
            lines.append(f"- {s['id']}（{s['name']}）：{s['desc']}")
    return "\n".join(lines)


def fmt_status(f):
    tags = list(f.get("statuses") or [])
    return "、".join(tags) if tags else "正常"


def build_user_prompt(payload):
    me = payload.get("self") or {}
    opp = payload.get("opponent") or {}
    round_no = payload.get("round", 1)
    recent = payload.get("recent") or []
    cooling = payload.get("cooling") or []

    lines = [
        f"第 {round_no} 回合",
        f"你：{me.get('hp', 0)}/{me.get('maxHp', 0)} 点生命，状态：{fmt_status(me)}",
        f"对手：{opp.get('hp', 0)}/{opp.get('maxHp', 0)} 点生命，状态：{fmt_status(opp)}",
    ]
    if cooling:
        lines.append("你正在冷却中、本回合不能用的技能：" + "、".join(cooling))
    if recent:
        lines.append("最近战报（新 -> 旧）：")
        lines.extend(f"- {r}" for r in recent)
    return "\n".join(lines)


# ---------------------------------------------------------------- 回复解析
FENCE_RE = re.compile(r"```(?:json)?", re.I)


def extract_text(message: dict):
    """返回 (content, reasoning)。"""
    content = message.get("content") or ""
    reasoning = message.get("reasoning_content") or message.get("reasoning") or ""
    if isinstance(content, list):  # 少数网关会返回分段结构
        content = "".join(
            part.get("text", "") for part in content if isinstance(part, dict)
        )
    return str(content), str(reasoning)


def parse_action(text, available):
    """从模型回复里抠出技能 id，失败返回 None。"""
    if not text:
        return None
    cleaned = FENCE_RE.sub(" ", text).strip()
    for match in re.finditer(r"\{[^{}]*\}", cleaned, re.S):
        try:
            obj = json.loads(match.group(0))
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            action = str(obj.get("action", "")).strip()
            line = str(obj.get("line", "")).strip()
            if action in available:
                return action, line
    # 退一步：文本里直接出现了合法技能 id 或技能名
    for sid in available:
        if re.search(r"\b" + re.escape(sid) + r"\b", cleaned):
            return sid, ""
    for sid in available:
        if SKILL_BY_ID[sid]["name"] in cleaned:
            return sid, ""
    return None


# ---------------------------------------------------------------- 模型调用
def call_model(fighter, system_prompt, user_prompt, timeout, max_tokens):
    body = json.dumps(
        {
            "model": fighter["model"],
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": 1.0,
            "stream": False,
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        fighter["base_url"],
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + fighter["api_key"],
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    message = (data.get("choices") or [{}])[0].get("message") or {}
    return extract_text(message)


# ---------------------------------------------------------------- HTTP 服务
class ArenaHandler(SimpleHTTPRequestHandler):
    server_version = "LLMArena/1.0"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    # --- 工具 ---
    def send_json(self, obj, status=200):
        blob = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(blob)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(blob)

    def log_message(self, fmt, *args):
        sys.stderr.write("[%s] %s\n" % (time.strftime("%H:%M:%S"), fmt % args))

    # --- 路由 ---
    def do_GET(self):
        if self.path.split("?")[0] == "/api/skills":
            self.send_json({"skills": SKILLS})
            return
        if self.path.split("?")[0] == "/api/config":
            self.send_json(public_config(self.server.arena_cfg))
            return
        super().do_GET()

    def do_POST(self):
        if self.path.split("?")[0] != "/api/act":
            self.send_json({"ok": False, "error": "not found"}, 404)
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except (ValueError, json.JSONDecodeError):
            self.send_json({"ok": False, "error": "请求体不是合法 JSON"}, 400)
            return

        cfg = self.server.arena_cfg
        side = payload.get("side")
        fighter_cfg = (cfg.get("fighters") or {}).get(side)
        if not fighter_cfg:
            self.send_json({"ok": False, "error": "未知的选手方位: %s" % side}, 400)
            return

        available = [s for s in (payload.get("available") or []) if s in SKILL_BY_ID]
        if not available:
            available = ["attack"]

        opp_side = "right" if side == "left" else "left"
        opp_cfg = cfg["fighters"][opp_side]
        system_prompt = SYSTEM_TEMPLATE.format(
            name=fighter_cfg["name"],
            model=fighter_cfg["model"],
            opp_name=opp_cfg["name"],
            opp_model=opp_cfg["model"],
            skill_lines=build_skill_lines(available),
        )
        user_prompt = build_user_prompt(payload)

        started = time.time()
        content, reasoning, error = "", "", ""
        try:
            content, reasoning = call_model(
                fighter_cfg,
                system_prompt,
                user_prompt,
                float(cfg["request_timeout"]),
                int(cfg["max_tokens"]),
            )
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", "ignore")[:300]
            except Exception:  # noqa: BLE001 - 读取失败不影响主流程
                pass
            error = "HTTP %s %s" % (exc.code, detail)
        except Exception as exc:  # noqa: BLE001 - 统一转成前端可读的错误
            error = "%s: %s" % (type(exc).__name__, exc)

        latency_ms = int((time.time() - started) * 1000)
        parsed = parse_action(content, available) or parse_action(reasoning, available)

        if parsed:
            action, line = parsed
            fallback = False
        else:
            action = random.choice(available)
            line = ""
            fallback = True
            if not error:
                error = "模型没按格式出招，已随机补一招"

        self.send_json(
            {
                "ok": not error or bool(parsed),
                "side": side,
                "model": fighter_cfg["model"],
                "action": action,
                "line": line,
                "reasoning": reasoning.strip(),
                "raw": content.strip(),
                "latency_ms": latency_ms,
                "fallback": fallback,
                "error": error,
            }
        )


def main():
    cfg = load_config()
    port = int(sys.argv[1]) if len(sys.argv) > 1 else int(cfg["port"])

    if not os.path.isdir(WEB_DIR):
        raise SystemExit("找不到页面目录: %s" % WEB_DIR)

    httpd = ThreadingHTTPServer(("127.0.0.1", port), ArenaHandler)
    httpd.arena_cfg = cfg
    httpd.daemon_threads = True

    left, right = cfg["fighters"]["left"], cfg["fighters"]["right"]
    print("LLM 竞技场已启动: http://127.0.0.1:%d" % port)
    print("  左侧: %s (%s)" % (left["name"], left["model"]))
    print("  右侧: %s (%s)" % (right["name"], right["model"]))
    print("  Ctrl+C 退出")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已退出")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
