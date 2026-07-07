"""herdr CLI API client + mock fallback."""
import json
import random
import subprocess
import time
from pathlib import Path


HERDR_BIN = Path(__file__).resolve().parent.parent / "herdr.exe"

# ---------- agent definitions ----------

AGENT_DEFS = [
    {"id": "claude-code", "name": "Claude Code",   "emoji": "🧠"},
    {"id": "codex",       "name": "Codex CLI",     "emoji": "🤖"},
    {"id": "cursor",      "name": "Cursor",        "emoji": "🖱️"},
    {"id": "windsurf",    "name": "Windsurf",      "emoji": "🏄"},
    {"id": "copilot",     "name": "GitHub Copilot","emoji": "👨‍💻"},
    {"id": "claude-ide",  "name": "Claude (IDE)",  "emoji": "⚡"},
]

STATUS_LIST = ["idle", "working", "blocked", "done"]


# ---------- mock ----------

def _mock_agents():
    """Generate mock agent statuses for demo / fallback."""
    now = int(time.time())
    return [
        {
            "id": a["id"],
            "name": a["name"],
            "emoji": a["emoji"],
            "status": STATUS_LIST[i % len(STATUS_LIST)],
            "uptime": random.randint(60, 36000),
            "last_seen": now - random.randint(0, 300),
        }
        for i, a in enumerate(AGENT_DEFS)
    ]


# ---------- herdr CLI ----------

def _herdr_cli(*args):
    """Run herdr CLI command, return parsed JSON or None."""
    if not HERDR_BIN.exists():
        return None
    try:
        r = subprocess.run(
            [str(HERDR_BIN), *args],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0 and r.stdout.strip():
            data = json.loads(r.stdout)
            return data.get("result") or data
    except Exception:
        pass
    return None


HERDR_CONNECTED = False


def _try_herdr_agents():
    """Fetch agents from `herdr agent list`."""
    global HERDR_CONNECTED
    result = _herdr_cli("agent", "list")
    if not result or not isinstance(result, dict):
        return None
    raw = result.get("agents")
    if raw is None:
        return None
    HERDR_CONNECTED = True
    # herdr connected but no real agents running → return mock
    if len(raw) == 0:
        return _mock_agents()
    return _parse_herdr_agents(raw)


def _herdr_pane_list():
    """Fallback to `herdr pane list`."""
    global HERDR_CONNECTED
    result = _herdr_cli("pane", "list")
    if not result:
        return None
    raw = result.get("panes")
    if raw is None:
        return None
    HERDR_CONNECTED = True
    parsed = _parse_herdr_panes(raw)
    if parsed:
        return parsed
    return _mock_agents()


def _herdr_session_snapshot():
    """Try to send session_snapshot request via herdr raw socket."""
    # herdr's socket is a Unix socket; on Windows requires pywin32 for AF_UNIX
    try:
        HERDR_SOCKET = Path.home() / "AppData" / "Roaming" / "herdr" / "herdr.sock"
        if not HERDR_SOCKET.exists():
            return None

        import socket as sock
        s = sock.socket(sock.AF_UNIX, sock.SOCK_STREAM)
        s.settimeout(3)
        s.connect(str(HERDR_SOCKET))
        req = json.dumps({
            "id": "dashboard:session:snapshot",
            "request": "session_snapshot",
        }).encode()
        s.sendall(req)
        resp = b""
        while True:
            chunk = s.recv(65536)
            if not chunk:
                break
            resp += chunk
        s.close()
        data = json.loads(resp.decode())
        snap = data.get("result") or data
        agents = snap.get("agents")
        if agents is not None:
            return _parse_herdr_agents(agents)
    except Exception:
        pass
    return None


# ---------- parsers ----------

def _parse_herdr_agents(raw):
    """Map herdr API agent list to uniform format."""
    now = int(time.time())
    agents = []
    seen = set()
    for a in raw:
        # herdr agent list returns "agent" field, not "agent_id"
        agent_id = a.get("agent") or a.get("agent_id") or a.get("id", "")
        if agent_id in seen:
            continue
        seen.add(agent_id)

        label = a.get("agent_label") or a.get("label") or a.get("name", agent_id)
        # match to known defs
        defn = _match_agent(agent_id, label)
        status = _map_status(a.get("agent_status", a.get("status", "")))

        agents.append({
            "id": agent_id,
            "name": defn["name"] if defn else label,
            "emoji": defn["emoji"] if defn else "🤔",
            "status": status,
            "uptime": a.get("uptime", 0),
            "last_seen": now,
        })
    return agents if agents else None


def _parse_herdr_panes(raw):
    """Map herdr pane list to uniform format."""
    now = int(time.time())
    agents = []
    seen = set()
    for p in raw:
        agent_id = p.get("pane_id", "")
        if agent_id in seen:
            continue
        seen.add(agent_id)

        title = p.get("title", "")
        proc = (p.get("process") or p.get("process_info") or {}).get("name", "")
        defn = _match_agent(agent_id, f"{title} {proc}")
        status = _map_status(p.get("agent_status", ""))

        agents.append({
            "id": agent_id,
            "name": defn["name"] if defn else title,
            "emoji": defn["emoji"] if defn else "🤔",
            "status": status,
            "uptime": p.get("uptime", 0),
            "last_seen": now,
        })
    return agents if agents else None


def _match_agent(agent_id, label):
    """Match agent id or label to known definitions."""
    text = f"{agent_id} {label}".lower()
    for a in AGENT_DEFS:
        # herdr returns short names like "claude", "codex" — match against known defs
        if a["id"] in text or a["name"].lower() in text:
            return a
        # also check if short name (from herdr) matches known def prefix
        short = agent_id.lower()
        if short and (a["id"].startswith(short) or a["name"].lower().startswith(short)):
            return a
    return None


def _map_status(s):
    s = (s or "").lower()
    if s in ("blocked",):
        return "blocked"
    if s in ("working", "running"):
        return "working"
    if s in ("done", "completed"):
        return "done"
    return "idle"


# ---------- public API ----------

def get_agents():
    """Return list of agents with status. Falls back to mock."""
    # Try: herdr agent list
    agents = _try_herdr_agents()
    if agents:
        return agents

    # Try: herdr pane list
    agents = _herdr_pane_list()
    if agents:
        return agents

    # Try: socket session_snapshot
    agents = _herdr_session_snapshot()
    if agents:
        return agents

    # Fallback to mock
    return _mock_agents()
