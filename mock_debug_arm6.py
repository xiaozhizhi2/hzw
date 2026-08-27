# -*- coding: utf-8 -*-
"""ARM device: verify json.dumps encoding bug in python3, check backup version."""
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

print("=== python3 json.dumps with encoding ===")
print(run("sudo python -c \"import json; json.dumps({'a':1}, indent=4, encoding='utf-8')\" 2>&1; echo RC=$?")[0])

print("=== backup script json lines ===")
print(run("grep -n 'json.dumps\\|json.loads' /opt/cbc/agent/agent/plugins/enet/10_event_push.py.bak_0925 2>&1")[0])

c.close()
print("DONE")
