# -*- coding: utf-8 -*-
"""enetos: dump ping_conf.json, grep fping.py for conf path + target parse."""
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

print("=== ping_conf.json ===")
out, err = run("sudo cat /opt/cbc/ipm/etc/ping_conf.json")
print(out, err)

print("=== fping.py conf path grep ===")
out, err = run("sudo grep -n 'ping_conf\\|etc/' /opt/cbc/ipm/bin/fping.py 2>&1")
print(out, err)

print("=== fping.py target outbound_interface grep ===")
out, err = run("sudo grep -n 'outbound_interface\\|target\\|is_check' /opt/cbc/ipm/bin/fping.py 2>&1 | head -20")
print(out, err)

c.close()
print("DONE")
