# -*- coding: utf-8 -*-
"""enetos: recover test - config wwan0 (not default) -> OK event, no repeat."""
import paramiko
import json

HOST = "172.17.9.42"
PORT = 6188
USER = "cbcadmin"
PASS = "X98kgF2pwW"
PLUGIN = "/root/cbc/agent/agent/plugins/enet/10_event_push.py"
CFG = "/root/cbc/agent/agent/config/traffic_failover_cellular_check.json"

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
    stdout.read()
    stderr.read()

print("=== ip route default ===")
out, err = run("ip route show default")
print(out.strip())

print("=== change config to wwan0 (recover) ===")
cfg = json.dumps({"wwan0": {"is_check_traffic_failover_cellular": True}})
upload_remote(CFG, cfg.encode("utf-8"))
out, err = run("sudo cat {0}".format(CFG))
print(out.strip())

print("=== run script (OK expected) ===")
out, err = run("sudo python3 {0} 2>&1; echo RC=$?".format(PLUGIN))
print("OUT:", out.strip(), "ERR:", err.strip())

print("=== cache cellular ===")
out, err = run("sudo python3 -c \"import json; d=json.load(open('/root/cbc/agent/agent/cache/event_used_data_cache.json')); print([i for i in d['last_update_info'] if i['metric']=='traffic.failover.cellular'])\"")
print(out, err)

print("=== run again (no repeat) ===")
out, err = run("sudo python3 {0} 2>&1; echo RC=$?".format(PLUGIN))
print("OUT:", out.strip(), "ERR:", err.strip())

print("=== log tail ===")
out, err = run("sudo tail -8 /root/cbc/agent/agent/cache/event_push.log 2>&1")
print(out, err)

c.close()
print("DONE")
