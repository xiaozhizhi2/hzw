# -*- coding: utf-8 -*-
"""ARM cleanup fix: restore line 291 to %300."""
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

print("=== line 291 before ===")
out, err = run("sed -n '291p' {0}".format(SCRIPT))
print(out, err)

print("=== restore %300 ===")
out, err = run("sudo sed -i '291s/if now_time % 10 == 0/if now_time % 300 == 0/' {0} 2>&1; echo RC=$?".format(SCRIPT))
print(out, err)

print("=== lines 290-295 after ===")
out, err = run("sed -n '290,295p' {0}".format(SCRIPT))
print(out, err)

c.close()
print("DONE")
