# -*- coding: utf-8 -*-
"""Check ARM device state: script, config, cache, ip route."""
import paramiko
import sys

HOST = "172.17.8.148"
PORT = 6188
USER = "cbcadmin"
PASS = "XPCCncn99d"


def run(cmd):
    stdin, stdout, stderr = c.exec_command(cmd)
    out = stdout.read().decode("utf-8", "ignore")
    err = stderr.read().decode("utf-8", "ignore")
    return out, err


c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=20)
print("=== whoami ===")
print(run("whoami")[0].strip())

print("=== ls config dir ===")
print(run("ls -la /etc/cbc/agent/ 2>&1")[0])

print("=== config content ===")
print(run("cat /etc/cbc/agent/traffic_failover_cellular_check.json 2>&1")[0])

print("=== script path & grep logic ===")
print(run("ls -la /opt/cbc/agent/agent/plugins/enet/10_event_push.py 2>&1")[0])
out, err = run("grep -n traffic.failover.cellular /opt/cbc/agent/agent/plugins/enet/10_event_push.py 2>&1")
print("grep out:", out)
print("grep err:", err)

print("=== cache file ===")
print(run("ls -la /opt/cbc/agent/agent/cache/ 2>&1")[0])
print(run("cat /opt/cbc/agent/agent/cache/event_used_data_cache.json 2>&1")[0])

print("=== ip route ===")
print(run("ip route 2>&1")[0])

print("=== python version ===")
print(run("which python; python --version 2>&1")[0])

c.close()
print("DONE")
