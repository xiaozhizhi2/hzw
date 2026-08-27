# -*- coding: utf-8 -*-
"""ARM: check OK event pushed in log."""
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

print("=== count cellular events in log ===")
out, err = run("grep -c 'traffic.failover.cellular' /var/log/cbc/argus-agent/event_push.log")
print(out, err)

print("=== all cellular push lines ===")
out, err = run("grep 'traffic.failover.cellular' /var/log/cbc/argus-agent/event_push.log")
print(out)

c.close()
print("DONE")
