# -*- coding: utf-8 -*-
"""enetos: upload argus-agent scripts + config, run traffic.failover.cellular test."""
import paramiko
import json

HOST = "172.17.9.42"
PORT = 6188
USER = "cbcadmin"
PASS = "X98kgF2pwW"
REMOTE_PLUGIN = "/root/cbc/agent/agent/plugins/enet/10_event_push.py"
REMOTE_PUSH = "/root/cbc/agent/push_event.py"
REMOTE_CFG = "/root/cbc/agent/agent/config/traffic_failover_cellular_check.json"

with open(r"d:\cbc\argus-agent\plugins\enet\10_event_push.py", "rb") as f:
    plugin = f.read()
with open(r"d:\cbc\argus-agent\argus_x86\root\cbc\agent\push_event.py", "rb") as f:
    push = f.read()

print("plugin local size:", len(plugin))
print("push local size:", len(push))

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=20)

def run(cmd):
    stdin, stdout, stderr = c.exec_command(cmd)
    out = stdout.read().decode("utf-8", "ignore")
    err = stderr.read().decode("utf-8", "ignore")
    return out, err

def upload_remote(path, content):
    cmd = "sudo sh -c 'cat > {0}'".format(path)
    stdin, stdout, stderr = c.exec_command(cmd)
    stdin.write(content)
    stdin.channel.shutdown_write()
    out = stdout.read().decode("utf-8", "ignore")
    err = stderr.read().decode("utf-8", "ignore")
    return out, err

# backup
print("=== backup ===")
out, err = run("sudo cp {0} {0}.bak_0925 2>&1; sudo cp {1} {1}.bak_0925 2>&1; echo RC=$?".format(REMOTE_PLUGIN, REMOTE_PUSH))
print(out, err)

# upload plugin
print("=== upload plugin ===")
out, err = upload_remote(REMOTE_PLUGIN, plugin)
print(out[:100], err[:100])
out, err = run("sudo wc -c {0}".format(REMOTE_PLUGIN))
print("plugin remote size:", out.strip())
out, err = run("sudo grep -n 'traffic.failover.cellular\\|TRAFFIC_FAILOVER' {0}".format(REMOTE_PLUGIN))
print("grep:", out.strip())
out, err = run("sudo python3 -m py_compile {0} 2>&1; echo RC=$?".format(REMOTE_PLUGIN))
print("compile:", out.strip())

# upload push_event.py
print("=== upload push_event.py ===")
out, err = upload_remote(REMOTE_PUSH, push)
print(out[:100], err[:100])
out, err = run("sudo grep -n 'traffic.failover.cellular\\|connection.down' {0}".format(REMOTE_PUSH))
print("grep:", out.strip())

# write config eth0 (default route is eth0 -> PROBLEM triggers)
print("=== write config eth0 ===")
cfg = json.dumps({"eth0": {"is_check_traffic_failover_cellular": True}})
out, err = upload_remote(REMOTE_CFG, cfg.encode("utf-8"))
print(out[:100], err[:100])
out, err = run("sudo cat {0}".format(REMOTE_CFG))
print(out.strip())

# apply %10 trigger
print("=== apply %10 trigger ===")
out, err = run("sudo sed -i 's/if now_time % 300 == 0/if now_time % 10 == 0/' {0} 2>&1; echo RC=$?".format(REMOTE_PLUGIN))
print(out, err)
out, err = run("sudo grep -n 'now_time % 10 == 0' {0}".format(REMOTE_PLUGIN))
print(out.strip())

# clear cache & run
print("=== clear cache, run script ===")
out, err = run("sudo rm -f /root/cbc/agent/agent/cache/event_used_data_cache.json 2>&1")
print(out, err)
out, err = run("sudo python3 {0} 2>&1; echo RC=$?".format(REMOTE_PLUGIN))
print("run OUT:", out.strip(), "ERR:", err.strip())

print("=== cache cellular ===")
out, err = run("sudo python3 -c \"import json; d=json.load(open('/root/cbc/agent/agent/cache/event_used_data_cache.json')); print([i for i in d['last_update_info'] if i['metric']=='traffic.failover.cellular'])\"")
print(out, err)

print("=== log tail ===")
out, err = run("sudo tail -8 /root/cbc/agent/agent/cache/event_push.log 2>&1")
print(out, err)

c.close()
print("DONE")
