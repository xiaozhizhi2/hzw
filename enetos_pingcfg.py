# -*- coding: utf-8 -*-
"""enetos: find ping_config path in fping.py, check ipm etc."""
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

print("=== ping_config in fping.py ===")
out, err = run("sudo grep -n 'ping_config\\|config.json\\|json.load' /opt/cbc/ipm/bin/fping.py 2>&1")
print(out, err)

print("=== ipm etc ===")
out, err = run("sudo ls -la /opt/cbc/ipm/etc/ 2>&1")
print(out, err)
out, err = run("sudo ls -la /opt/cbc/ipm/var/ 2>&1")
print(out, err)

print("=== find any json in ipm ===")
out, err = run("sudo find /opt/cbc/ipm -name '*.json' 2>/dev/null; echo RC=$?")
print(out, err)

print("=== ARM device ipm? (via check on this box) ===")
out, err = run("sudo ls -la /opt/cbc/ipm/cache 2>&1")
print(out, err)

c.close()
print("DONE")
