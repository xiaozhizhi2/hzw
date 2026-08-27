# -*- coding: utf-8 -*-
"""ARM: upload push_event.py with category map, verify cellular event category."""
import paramiko

HOST = "172.17.8.148"
PORT = 6188
USER = "cbcadmin"
PASS = "XPCCncn99d"
LOCAL = r"d:\cbc\arm-argus-agent\arm\opt\cbc\agent\push_event.py"
REMOTE = "/opt/cbc/agent/push_event.py"

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

# backup
out, err = run("sudo cp {0} {0}.bak_0925 2>&1; echo RC=$?".format(REMOTE))
print("backup:", out, err)

cmd = "sudo sh -c 'cat > {0}'".format(REMOTE)
stdin, stdout, stderr = c.exec_command(cmd)
stdin.write(content)
stdin.channel.shutdown_write()
out = stdout.read().decode("utf-8", "ignore")
err = stderr.read().decode("utf-8", "ignore")
print("upload:", out[:100], err[:100])

out, err = run("wc -c {0}".format(REMOTE))
print("remote size:", out)
out, err = run("grep -n 'traffic.failover.cellular' {0}".format(REMOTE))
print("grep:", out)
out, err = run("sudo python -m py_compile {0} 2>&1; echo RC=$?".format(REMOTE))
print("compile:", out)

# reset cache so PROBLEM triggers again
out, err = run("sudo rm -f /opt/cbc/agent/agent/cache/event_used_data_cache.json 2>&1; echo RC=$?")
print("rm cache:", out)

# ensure default route still there
out, err = run("ip route show default")
print("default:", out)

# run script
out, err = run("sudo python /opt/cbc/agent/agent/plugins/enet/10_event_push.py 2>&1; echo RC=$?")
print("run OUT:", out, "ERR:", err)

# tail log
out, err = run("tail -6 /var/log/cbc/argus-agent/event_push.log")
print("log tail:\n", out)

c.close()
print("DONE")
