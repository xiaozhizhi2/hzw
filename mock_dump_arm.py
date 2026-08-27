# -*- coding: utf-8 -*-
"""ARM: dump full cache + check script main flow lines."""
import paramiko

HOST = "172.17.8.148"
PORT = 6188
USER = "cbcadmin"
PASS = "XPCCncn99d"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=20)

def run(cmd):
    stdin, stdout, stderr = c.exec_command(cmd)
    out = stdout.read().decode("utf-8", "ignore")
    err = stderr.read().decode("utf-8", "ignore")
    return out, err

print("=== full cache ===")
out, err = run("cat /opt/cbc/agent/agent/cache/event_used_data_cache.json")
print(out, err)

print("=== cache mtime ===")
out, err = run("ls -la /opt/cbc/agent/agent/cache/event_used_data_cache.json")
print(out, err)

print("=== script main flow 280-310 ===")
out, err = run("sed -n '280,310p' /opt/cbc/agent/agent/plugins/enet/10_event_push.py")
print(out, err)

c.close()
print("DONE")
