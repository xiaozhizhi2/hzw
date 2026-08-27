# -*- coding: utf-8 -*-
"""ARM: upload fixed script, apply %10, full PROBLEM->recover test."""
import paramiko

HOST = "172.17.8.148"
PORT = 6188
USER = "cbcadmin"
PASS = "XPCCncn99d"
LOCAL = r"d:\cbc\arm-argus-agent\plugins\enet\10_event_push.py"
REMOTE = "/opt/cbc/agent/agent/plugins/enet/10_event_push.py"
CACHE = "/opt/cbc/agent/agent/cache/event_used_data_cache.json"

with open(LOCAL, "rb") as f:
    content = f.read()
print("local size:", len(content))

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=20)

def run(cmd):
    stdin, stdout, stderr = c.exec_command(cmd)
    out = stdout.read().decode("utf-8", "ignore")
    err = stderr.read().decode("utf-8", "ignore")
    return out, err

def cellular():
    out, _ = run("python -c \"import json; d=json.load(open('{0}')); print(d['last_update_seq'], [i for i in d['last_update_info'] if i['metric']=='traffic.failover.cellular'])\"".format(CACHE))
    return out.strip()

cmd = "sudo sh -c 'cat > {0}'".format(REMOTE)
stdin, stdout, stderr = c.exec_command(cmd)
stdin.write(content)
stdin.channel.shutdown_write()
out = stdout.read().decode("utf-8", "ignore")
err = stderr.read().decode("utf-8", "ignore")
print("upload:", out[:100], err[:100])

out, _ = run("wc -c {0}".format(REMOTE))
print("remote size:", out.strip())
out, _ = run("grep -n 'json.loads(f.read()' {0}".format(REMOTE))
print("loads fix:", out.strip())
out, _ = run("grep -n 'json.dumps(info' {0}".format(REMOTE))
print("dumps fix:", out.strip())

# apply %10
out, _ = run("sudo sed -i 's/if now_time % 300 == 0/if now_time % 10 == 0/' {0}".format(REMOTE))
out, _ = run("grep -n 'now_time % 10 == 0' {0}".format(REMOTE))
print("trigger:", out.strip())

# compile
out, _ = run("sudo python -m py_compile {0} 2>&1; echo RC=$?".format(REMOTE))
print("compile:", out.strip())

# STEP1 PROBLEM
print("=== STEP1: PROBLEM ===")
run("sudo rm -f {0}".format(CACHE))
run("sudo ip route del default via 172.17.8.1 dev wan0 metric 20 2>&1")
run("sudo ip route add default via 172.17.8.1 dev wan0 metric 20 2>&1")
run("sudo python {0} 2>&1".format(REMOTE))
print("cache:", cellular())
out, _ = run("grep -c 'traffic.failover.cellular' /var/log/cbc/argus-agent/event_push.log")
print("cellular push count:", out.strip())

# STEP2 recover
print("=== STEP2: recover OK ===")
run("sudo ip route del default via 172.17.8.1 dev wan0 metric 20 2>&1")
run("sudo python {0} 2>&1".format(REMOTE))
print("cache:", cellular())
out, _ = run("grep -c 'traffic.failover.cellular' /var/log/cbc/argus-agent/event_push.log")
print("cellular push count:", out.strip())

# STEP3 no change, should not push again
print("=== STEP3: no change ===")
run("sudo python {0} 2>&1".format(REMOTE))
out, _ = run("grep -c 'traffic.failover.cellular' /var/log/cbc/argus-agent/event_push.log")
print("cellular push count:", out.strip())

print("=== cellular log lines ===")
out, _ = run("grep 'traffic.failover.cellular' /var/log/cbc/argus-agent/event_push.log")
print(out)

c.close()
print("DONE")
