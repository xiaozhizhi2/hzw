# -*- coding: utf-8 -*-
"""ARM device: run script, capture traceback, check cache mtime and log."""
import paramiko

HOST = "172.17.8.148"
PORT = 6188
USER = "cbcadmin"
PASS = "XPCCncn99d"
SCRIPT = "/opt/cbc/agent/agent/plugins/enet/10_event_push.py"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=20)

def run(cmd):
    stdin, stdout, stderr = c.exec_command(cmd)
    out = stdout.read().decode("utf-8", "ignore")
    err = stderr.read().decode("utf-8", "ignore")
    return out, err

print("=== cache mtime before ===")
print(run("ls -la /opt/cbc/agent/agent/cache/event_used_data_cache.json")[0])

print("=== run script with traceback ===")
out, err = run("sudo python {0} 2>&1; echo RC=$?".format(SCRIPT))
print("OUT:", out)
print("ERR:", err)

print("=== cache mtime after ===")
print(run("ls -la /opt/cbc/agent/agent/cache/event_used_data_cache.json")[0])
print(run("cat /opt/cbc/agent/agent/cache/event_used_data_cache.json")[0])

print("=== event_push.log mtime + tail ===")
print(run("ls -la /var/log/cbc/argus-agent/event_push.log")[0])
print(run("tail -5 /var/log/cbc/argus-agent/event_push.log")[0])

c.close()
print("DONE")
