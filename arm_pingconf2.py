# -*- coding: utf-8 -*-
"""ARM: dump ping_conf.json, compare fping.py with local ipm-v2."""
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

print("=== /etc/cbc/ipm/ping_conf.json ===")
out, err = run("sudo cat /etc/cbc/ipm/ping_conf.json")
print(out, err)

print("=== fping.py size ===")
out, err = run("sudo wc -c /opt/cbc/ipm/bin/fping.py")
print(out, err)

print("=== fping.py is_check_connection_down ===")
out, err = run("sudo grep -n 'is_check_connection_down\\|connection.down\\|outbound_interface' /opt/cbc/ipm/bin/fping.py 2>&1 | head -20")
print(out, err)

print("=== fping.py conf path line ===")
out, err = run("sudo sed -n '578,588p' /opt/cbc/ipm/bin/fping.py")
print(out, err)

c.close()
print("DONE")
