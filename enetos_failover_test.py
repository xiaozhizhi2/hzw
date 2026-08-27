# -*- coding: utf-8 -*-
"""enetos: simulate failover via ip route replace -> wwan0 PROBLEM -> eth0 OK."""
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

def cellular():
    out, _ = run("sudo python3 -c \"import json; d=json.load(open('/root/cbc/agent/agent/cache/event_used_data_cache.json')); print(d['last_update_seq'], [i for i in d['last_update_info'] if i['metric']=='traffic.failover.cellular'])\"")
    return out.strip()

# config wwan0, reset cache
print("=== config wwan0, reset ===")
upload_remote(CFG, json.dumps({"wwan0": {"is_check_traffic_failover_cellular": True}}).encode("utf-8"))
run("sudo rm -f /root/cbc/agent/agent/cache/event_used_data_cache.json")

# replace default to wwan0 -> PROBLEM
print("=== replace default -> wwan0 (PROBLEM) ===")
out, err = run("sudo ip route replace default via 172.17.9.1 dev wwan0 metric 20 2>&1; echo RC=$?")
print(out, err)
out, err = run("ip route show default")
print(out.strip())
run("sudo python3 {0} 2>&1".format(PLUGIN))
print("cache:", cellular())

# replace default back to eth0 -> OK
print("=== replace default -> eth0 (OK recover) ===")
out, err = run("sudo ip route replace default via 172.17.9.1 dev eth0 metric 20 2>&1; echo RC=$?")
print(out, err)
out, err = run("ip route show default")
print(out.strip())
run("sudo python3 {0} 2>&1".format(PLUGIN))
print("cache:", cellular())

# run again -> no change
print("=== run again (no repeat) ===")
run("sudo python3 {0} 2>&1".format(PLUGIN))
print("cache:", cellular())

print("=== cellular log lines ===")
out, err = run("sudo grep 'traffic.failover.cellular' /root/cbc/agent/agent/cache/event_push.log | tail -4")
print(out, err)

c.close()
print("DONE")
