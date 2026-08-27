# -*- coding: utf-8 -*-
"""enetos: check sudo, /root paths, python3."""
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

print("=== sudo test ===")
out, err = run("sudo -n true 2>&1; echo RC=$?")
print(out, err)

print("=== /root/cbc/agent tree ===")
out, err = run("sudo ls -la /root/cbc/agent/ 2>&1")
print(out, err)
out, err = run("sudo ls -la /root/cbc/agent/agent/plugins/enet/ 2>&1")
print(out, err)
out, err = run("sudo ls -la /root/cbc/agent/agent/config/ 2>&1")
print(out, err)
out, err = run("sudo ls -la /root/cbc/agent/agent/cache/ 2>&1")
print(out, err)

print("=== push_event.py ===")
out, err = run("sudo ls -la /root/cbc/agent/push_event.py 2>&1")
print(out, err)
out, err = run("sudo grep -n 'cellular\\|connection.down' /root/cbc/agent/push_event.py 2>&1")
print(out, err)

print("=== ipm fping ===")
out, err = run("sudo ls -la /root/cbc/ipm/ 2>&1")
print(out, err)

print("=== python3 ===")
out, err = run("which python3; python3 --version 2>&1")
print(out, err)

print("=== event log ===")
out, err = run("sudo ls -la /var/log/cbc/argus-agent/ 2>&1")
print(out, err)

c.close()
print("DONE")
