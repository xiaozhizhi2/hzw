# -*- coding: utf-8 -*-
"""ARM: find ping_conf.json, check fping.py conf path."""
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

print("=== find ping_conf.json ===")
out, err = run("sudo find / -name 'ping_conf.json' 2>/dev/null; echo RC=$?")
print(out, err)

print("=== fping.py config path grep ===")
out, err = run("sudo grep -n 'ping_conf\\|config_path' /opt/cbc/ipm/bin/fping.py 2>&1 | head -10")
print(out, err)

print("=== fping.py json.load grep ===")
out, err = run("sudo grep -n 'json.load\\|config' /opt/cbc/ipm/bin/fping.py 2>&1 | head -20")
print(out, err)

print("=== var dir ===")
out, err = run("sudo ls -laR /opt/cbc/ipm/var/ 2>&1")
print(out, err)

c.close()
print("DONE")
