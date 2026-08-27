# -*- coding: utf-8 -*-
"""ARM device mock: tweak trigger to %10, set config to wan0, run, check cache."""
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

print("=== push_event.py category map ===")
out, err = run("grep -n 'connection.down\\|traffic.failover.cellular' /opt/cbc/agent/push_event.py 2>&1")
print(out, err)

print("=== tweak trigger %300 -> %10 ===")
out, err = run("sudo sed -i 's/if now_time % 300 == 0/if now_time % 10 == 0/' {0} 2>&1; echo RC=$?".format(SCRIPT))
print(out, err)
out, err = run("grep -n 'now_time % 10 == 0' {0}".format(SCRIPT))
print(out)

print("=== set config to wan0 ===")
import json
cfg = json.dumps({"wan0": {"is_check_traffic_failover_cellular": True}})
cmd = "sudo sh -c 'cat > /etc/cbc/agent/traffic_failover_cellular_check.json'"
stdin, stdout, stderr = c.exec_command(cmd)
stdin.write(cfg)
stdin.channel.shutdown_write()
out = stdout.read().decode("utf-8", "ignore")
err = stderr.read().decode("utf-8", "ignore")
print(out, err)
out, err = run("cat /etc/cbc/agent/traffic_failover_cellular_check.json")
print(out, err)

print("=== run script ===")
out, err = run("sudo python {0} 2>&1; echo RC=$?".format(SCRIPT))
print(out, err)

print("=== cache after run ===")
out, err = run("cat /opt/cbc/agent/agent/cache/event_used_data_cache.json")
print(out, err)

print("=== event_push.log tail ===")
out, err = run("tail -30 /var/log/cbc/argus-agent/event_push.log 2>&1")
print(out, err)

c.close()
print("DONE")
