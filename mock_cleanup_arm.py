# -*- coding: utf-8 -*-
"""ARM cleanup: restore %300, del default route, remove mock config, restore scripts."""
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

print("=== restore %10 -> %300 ===")
out, err = run("sudo sed -i '0,/if now_time % 10 == 0:/s//if now_time % 300 == 0:/' {0} 2>&1; echo RC=$?".format(SCRIPT))
print(out, err)
out, err = run("grep -n 'now_time % ' {0}".format(SCRIPT))
print(out)

print("=== del default route ===")
out, err = run("ip route show default")
print("before:", out.strip())
out, err = run("sudo ip route del default via 172.17.8.1 dev wan0 metric 20 2>&1; echo RC=$?")
print(out, err)
out, err = run("ip route show default")
print("after:", out.strip())

print("=== remove mock config ===")
out, err = run("sudo rm -f /etc/cbc/agent/traffic_failover_cellular_check.json 2>&1; echo RC=$?")
print(out, err)
out, err = run("ls -la /etc/cbc/agent/traffic_failover_cellular_check.json 2>&1")
print(out, err)

print("=== verify script trigger & config gone ===")
out, err = run("grep -n 'now_time % 300' {0}".format(SCRIPT))
print(out)
out, err = run("ls /etc/cbc/agent/ 2>&1")
print(out)

c.close()
print("DONE")
