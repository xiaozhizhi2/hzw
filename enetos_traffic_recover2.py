# -*- coding: utf-8 -*-
"""enetos: full recover - config eth0 (PROBLEM), del default route -> OK push."""
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

# config eth0
print("=== config eth0 ===")
upload_remote(CFG, json.dumps({"eth0": {"is_check_traffic_failover_cellular": True}}).encode("utf-8"))

# clear cache, run -> PROBLEM
print("=== reset cache, run (PROBLEM) ===")
run("sudo rm -f /root/cbc/agent/agent/cache/event_used_data_cache.json")
run("sudo python3 {0} 2>&1".format(PLUGIN))
out, err = run("sudo python3 -c \"import json; d=json.load(open('/root/cbc/agent/agent/cache/event_used_data_cache.json')); print([i for i in d['last_update_info'] if i['metric']=='traffic.failover.cellular'])\"")
print(out.strip())

# del default route -> recover OK
print("=== del default route ===")
out, err = run("ip route show default")
print("before:", out.strip())
run("sudo ip route del default via 172.17.9.1 dev eth0 metric 20 2>&1")
out, err = run("ip route show default")
print("after:", out.strip())

print("=== run script (OK recover expected) ===")
out, err = run("sudo python3 {0} 2>&1; echo RC=$?".format(PLUGIN))
print("OUT:", out.strip(), "ERR:", err.strip())

print("=== cache ===")
out, err = run("sudo python3 -c \"import json; d=json.load(open('/root/cbc/agent/agent/cache/event_used_data_cache.json')); print(d['last_update_seq'], [i for i in d['last_update_info'] if i['metric']=='traffic.failover.cellular'])\"")
print(out.strip())

print("=== log tail ===")
out, err = run("sudo tail -6 /root/cbc/agent/agent/cache/event_push.log 2>&1")
print(out, err)

# restore default route
print("=== restore default route ===")
run("sudo ip route add default via 172.17.9.1 dev eth0 metric 20 2>&1")
out, err = run("ip route show default")
print("restored:", out.strip())

c.close()
print("DONE")
