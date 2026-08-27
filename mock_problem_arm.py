# -*- coding: utf-8 -*-
"""ARM device: add default route -> trigger PROBLEM, verify event push + cache."""
import paramiko

HOST = "172.17.8.148"
PORT = 6188
USER = "cbcadmin"
PASS = "XPCCncn99d"
SCRIPT = "/opt/cbc/agent/agent/plugins/enet/10_event_push.py"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=20)

def run(cmd):
    stdin, stdout, stderr = c.exec_command(cmd)
    out = stdout.read().decode("utf-8", "ignore")
    err = stderr.read().decode("utf-8", "ignore")
    return out, err

print("=== push_event.py location ===")
out, err = run("ls -la /opt/cbc/agent/push_event.py 2>&1")
print(out, err)

print("=== current default routes ===")
out, err = run("ip route show default 2>&1")
print(out, err)

print("=== add default route via wan0 ===")
out, err = run("sudo ip route add default via 172.17.8.1 dev wan0 metric 20 2>&1; echo RC=$?", )
print(out, err)
out, err = run("ip route show default")
print(out, err)

print("=== run script ===")
out, err = run("sudo python {0} 2>&1; echo RC=$?".format(SCRIPT))
print("OUT:", out, "ERR:", err)

print("=== cache traffic.failover.cellular value ===")
out, err = run("python -c \"import json; d=json.load(open('/opt/cbc/agent/agent/cache/event_used_data_cache.json')); print([i for i in d['last_update_info'] if i['metric']=='traffic.failover.cellular'])\"")
print(out, err)

print("=== event_push.log tail ===")
out, err = run("tail -20 /var/log/cbc/argus-agent/event_push.log 2>&1")
print(out, err)

c.close()
print("DONE")
