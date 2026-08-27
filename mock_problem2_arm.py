# -*- coding: utf-8 -*-
"""ARM: re-apply %10 trigger, run, verify PROBLEM + event push."""
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

print("=== check push_event.py category map ===")
out, err = run("grep -n 'cellular' /opt/cbc/agent/push_event.py 2>&1")
print(out, err)

print("=== re-apply %10 ===")
out, err = run("sudo sed -i 's/if now_time % 300 == 0/if now_time % 10 == 0/' {0} 2>&1; echo RC=$?".format(SCRIPT))
print(out, err)
out, err = run("grep -n 'now_time % 10 == 0' {0}".format(SCRIPT))
print(out)

print("=== clear cache to simulate first run ===")
out, err = run("sudo rm -f /opt/cbc/agent/agent/cache/event_used_data_cache.json 2>&1; echo RC=$?")
print(out, err)

print("=== run script (PROBLEM expected) ===")
out, err = run("sudo python {0} 2>&1; echo RC=$?".format(SCRIPT))
print("OUT:", out, "ERR:", err)

print("=== cache cellular ===")
out, err = run("python -c \"import json; d=json.load(open('/opt/cbc/agent/agent/cache/event_used_data_cache.json')); print([i for i in d['last_update_info'] if i['metric']=='traffic.failover.cellular'])\"")
print(out, err)

print("=== event_push.log tail ===")
out, err = run("tail -15 /var/log/cbc/argus-agent/event_push.log 2>&1")
print(out, err)

c.close()
print("DONE")
