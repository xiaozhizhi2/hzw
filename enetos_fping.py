# -*- coding: utf-8 -*-
"""enetos: inspect fping.py, ping_config, ipm bin."""
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

print("=== /opt/cbc/ipm ===")
out, err = run("sudo ls -la /opt/cbc/ipm/ 2>&1")
print(out, err)

print("=== /opt/cbc/ipm/bin ===")
out, err = run("sudo ls -la /opt/cbc/ipm/bin/ 2>&1")
print(out, err)

print("=== fping.py grep is_check_connection_down ===")
out, err = run("sudo grep -n 'is_check_connection_down\\|check_connection_down_threshold\\|connection.down' /opt/cbc/ipm/bin/fping.py 2>&1")
print(out, err)

print("=== ping_config search again ===")
out, err = run("sudo find /opt /etc /root -name '*ping*config*' 2>/dev/null; echo RC=$?")
print(out, err)

print("=== fping.py header ===")
out, err = run("sudo sed -n '1,60p' /opt/cbc/ipm/bin/fping.py 2>&1")
print(out, err)

c.close()
print("DONE")
