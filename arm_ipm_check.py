# -*- coding: utf-8 -*-
"""ARM: check ipm structure, fping.py, cache dir."""
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

print("=== /opt/cbc/ipm ===")
out, err = run("sudo ls -la /opt/cbc/ipm/ 2>&1")
print(out, err)

print("=== /opt/cbc/ipm/bin ===")
out, err = run("sudo ls -la /opt/cbc/ipm/bin/ 2>&1")
print(out, err)

print("=== /opt/cbc/ipm/etc ===")
out, err = run("sudo ls -la /opt/cbc/ipm/etc/ 2>&1")
print(out, err)

print("=== /opt/cbc/ipm/cache ===")
out, err = run("sudo ls -la /opt/cbc/ipm/cache 2>&1")
print(out, err)

print("=== fping.py connection.down grep ===")
out, err = run("sudo grep -n 'connection.down\\|is_check_connection_down' /opt/cbc/ipm/bin/fping.py 2>&1")
print(out, err)

print("=== ping_conf.json ===")
out, err = run("sudo cat /opt/cbc/ipm/etc/ping_conf.json 2>&1")
print(out, err)

c.close()
print("DONE")
