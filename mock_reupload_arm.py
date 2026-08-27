# -*- coding: utf-8 -*-
"""Re-upload fixed arm 10_event_push.py and run, verify cache write."""
import paramiko

HOST = "172.17.8.148"
PORT = 6188
USER = "cbcadmin"
PASS = "XPCCncn99d"
LOCAL = r"d:\cbc\arm-argus-agent\plugins\enet\10_event_push.py"
REMOTE = "/opt/cbc/agent/agent/plugins/enet/10_event_push.py"

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

cmd = "sudo sh -c 'cat > {0}'".format(REMOTE)
stdin, stdout, stderr = c.exec_command(cmd)
stdin.write(content)
stdin.channel.shutdown_write()
out = stdout.read().decode("utf-8", "ignore")
err = stderr.read().decode("utf-8", "ignore")
print("upload:", out[:100], err[:100])

out, err = run("wc -c {0}".format(REMOTE))
print("remote size:", out)
out, err = run("grep -n 'json.dumps(info' {0}".format(REMOTE))
print("check:", out)
out, err = run("sudo python -m py_compile {0} 2>&1; echo RC=$?".format(REMOTE))
print("compile:", out)

print("=== run script ===")
out, err = run("sudo python {0} 2>&1; echo RC=$?".format(REMOTE))
print("OUT:", out, "ERR:", err)

print("=== cache after ===")
out, err = run("cat /opt/cbc/agent/agent/cache/event_used_data_cache.json")
print(out, err)

c.close()
print("DONE")
