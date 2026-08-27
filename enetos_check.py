# -*- coding: utf-8 -*-
"""enetos device: check state - paths, scripts, configs, route."""
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

print("=== whoami ===")
print(run("whoami")[0].strip())

print("=== argus scripts locations ===")
out, err = run("ls -la /root/cbc/agent/agent/plugins/enet/10_event_push.py 2>&1; ls -la /opt/cbc/agent/agent/plugins/enet/10_event_push.py 2>&1")
print(out, err)

print("=== config dir ===")
out, err = run("ls -la /root/cbc/agent/agent/config/ 2>&1; ls -la /etc/cbc/agent/ 2>&1")
print(out, err)

print("=== push_event.py locations ===")
out, err = run("ls -la /root/cbc/agent/push_event.py 2>&1; ls -la /opt/cbc/agent/push_event.py 2>&1")
print(out, err)

print("=== cache dirs ===")
out, err = run("ls -la /root/cbc/agent/agent/cache/ 2>&1; ls -la /opt/cbc/agent/agent/cache/ 2>&1")
print(out, err)

print("=== ipm fping.py location ===")
out, err = run("ls -la /root/cbc/ipm/fping.py 2>&1; ls -la /opt/cbc/ipm/fping.py 2>&1; ls -la /opt/cbc/ipm/cache 2>&1")
print(out, err)

print("=== ip route ===")
print(run("ip route 2>&1")[0])

print("=== python ===")
print(run("which python; python --version 2>&1")[0])

c.close()
print("DONE")
