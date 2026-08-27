# -*- coding: utf-8 -*-
"""enetos: how 10_event_push.py is scheduled, python used."""
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

print("=== crontab ===")
out, err = run("sudo crontab -l 2>&1")
print(out, err)

print("=== ps for argus ===")
out, err = run("ps -ef | grep -E 'argus|event_push|10_event' | grep -v grep 2>&1")
print(out, err)

print("=== /root/cbc/agent/agent ===")
out, err = run("sudo ls -la /root/cbc/agent/agent/ 2>&1")
print(out, err)

print("=== agent scripts ===")
out, err = run("sudo ls -la /root/cbc/agent/agent/*.py 2>&1")
print(out, err)

c.close()
print("DONE")
