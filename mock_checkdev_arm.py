# -*- coding: utf-8 -*-
"""ARM: check device script get_cache_content line + encoding param."""
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

print("=== device get_cache_content ===")
out, err = run("grep -n -A6 'def get_cache_content' /opt/cbc/agent/agent/plugins/enet/10_event_push.py")
print(out, err)

print("=== device json.loads/dumps lines ===")
out, err = run("grep -n 'json.loads\\|json.dumps' /opt/cbc/agent/agent/plugins/enet/10_event_push.py")
print(out, err)

print("=== device script size ===")
out, err = run("wc -c /opt/cbc/agent/agent/plugins/enet/10_event_push.py")
print(out, err)

c.close()
print("DONE")
