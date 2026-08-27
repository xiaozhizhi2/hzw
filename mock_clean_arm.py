# -*- coding: utf-8 -*-
"""ARM clean experiment: PROBLEM -> recover OK, watch seq + push each step."""
import paramiko

HOST = "172.17.8.148"
PORT = 6188
USER = "cbcadmin"
PASS = "XPCCncn99d"
SCRIPT = "/opt/cbc/agent/agent/plugins/enet/10_event_push.py"
CACHE = "/opt/cbc/agent/agent/cache/event_used_data_cache.json"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=20)

def run(cmd):
    stdin, stdout, stderr = c.exec_command(cmd)
    out = stdout.read().decode("utf-8", "ignore")
    err = stderr.read().decode("utf-8", "ignore")
    return out, err

def cellular(cache_path=CACHE):
    out, _ = run("python -c \"import json; d=json.load(open('{0}')); print(d['last_update_seq'], [i for i in d['last_update_info'] if i['metric']=='traffic.failover.cellular'])\"".format(cache_path))
    return out.strip()

# step 1: clean cache, add default -> PROBLEM
print("=== STEP1: reset -> PROBLEM ===")
run("sudo rm -f {0}".format(CACHE))
run("sudo ip route add default via 172.17.8.1 dev wan0 metric 20 2>&1")
out, _ = run("ip route show default")
print("default:", out.strip())
run("sudo python {0} 2>&1".format(SCRIPT))
print("cache:", cellular())

# step 2: remove default -> recover OK
print("=== STEP2: remove default -> recover ===")
run("sudo ip route del default via 172.17.8.1 dev wan0 metric 20 2>&1")
out, _ = run("ip route show default")
print("default after del:", out.strip())
run("sudo python {0} 2>&1".format(SCRIPT))
print("cache:", cellular())
out, _ = run("grep -c 'traffic.failover.cellular' /var/log/cbc/argus-agent/event_push.log")
print("total cellular push count:", out.strip())
out, _ = run("grep 'traffic.failover.cellular' /var/log/cbc/argus-agent/event_push.log")
print(out)

c.close()
print("DONE")
