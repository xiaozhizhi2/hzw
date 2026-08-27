# -*- coding: utf-8 -*-
"""enetos: check 10_event_push.py cellular logic, fping.py location, event log."""
import paramiko

HOST = "172.17.9.42"
PORT = 6188
USER = "cbcadmin"
PASS = "X98kgF2pwW"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=20)

def run(cmd):
    stdin, stdout, stderr = c.exec_command(cmd)
    out = stdout.read().decode("utf-8", "ignore")
    err = stderr.read().decode("utf-8", "ignore")
    return out, err

print("=== 10_event_push.py cellular grep ===")
out, err = run("sudo grep -n 'traffic.failover.cellular\\|TRAFFIC_FAILOVER\\|is_check_traffic_failover' /root/cbc/agent/agent/plugins/enet/10_event_push.py 2>&1")
print(out, err)

print("=== 10_event_push.py json lines ===")
out, err = run("sudo grep -n 'json.loads\\|json.dumps' /root/cbc/agent/agent/plugins/enet/10_event_push.py 2>&1")
print(out, err)

print("=== 10_event_push.py header/paths ===")
out, err = run("sudo sed -n '1,30p' /root/cbc/agent/agent/plugins/enet/10_event_push.py 2>&1")
print(out, err)

print("=== fping.py search ===")
out, err = run("sudo find / -name 'fping.py' 2>/dev/null; echo RC=$?")
print(out, err)

print("=== ping_config.json search ===")
out, err = run("sudo find / -name 'ping_config.json' 2>/dev/null; echo RC=$?")
print(out, err)

print("=== ipm dirs ===")
out, err = run("sudo ls -la /root/cbc/ 2>&1")
print(out, err)

print("=== event log tail ===")
out, err = run("sudo tail -5 /root/cbc/agent/agent/cache/event_push.log 2>&1")
print(out, err)

c.close()
print("DONE")
