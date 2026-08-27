# -*- coding: utf-8 -*-
"""Upload local arm 10_event_push.py to ARM device via sudo, then run check."""
import paramiko

HOST = "172.17.8.148"
PORT = 6188
USER = "cbcadmin"
PASS = "XPCCncn99d"
LOCAL = r"d:\cbc\arm-argus-agent\plugins\enet\10_event_push.py"
REMOTE = "/opt/cbc/agent/agent/plugins/enet/10_event_push.py"
BACKUP = REMOTE + ".bak_0925"

with open(LOCAL, "rb") as f:
    content = f.read()

print("local file size:", len(content))

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=20)

def run(cmd):
    stdin, stdout, stderr = c.exec_command(cmd)
    out = stdout.read().decode("utf-8", "ignore")
    err = stderr.read().decode("utf-8", "ignore")
    return out, err

# backup remote
out, err = run("sudo cp {0} {1} 2>&1; echo RC=$?".format(REMOTE, BACKUP))
print("backup:", out, err)

# upload via sudo tee
cmd = "sudo sh -c 'cat > {0}'".format(REMOTE)
stdin, stdout, stderr = c.exec_command(cmd)
stdin.write(content)
stdin.channel.shutdown_write()
out = stdout.read().decode("utf-8", "ignore")
err = stderr.read().decode("utf-8", "ignore")
print("upload out:", out[:200], "err:", err[:200])

# verify
out, err = run("wc -c {0} 2>&1".format(REMOTE))
print("remote size:", out, err)
out, err = run("head -3 {0}".format(REMOTE))
print("remote head:", out)
out, err = run("grep -n traffic.failover.cellular {0} | head -5".format(REMOTE))
print("grep:", out)
out, err = run("sudo python -m py_compile {0} 2>&1; echo RC=$?".format(REMOTE))
print("compile:", out, err)

c.close()
print("DONE")
