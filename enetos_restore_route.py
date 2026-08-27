# -*- coding: utf-8 -*-
"""enetos: restore original default route nhid 14, verify connectivity."""
import paramiko

HOST = "172.17.9.42"
PORT = 6188
USER = "cbcadmin"
PASS = "X98kgF2pwW"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=20)

def run(cmd):
    stdin, stdout, stderr = c.exec_command(cmd)
    out = stdout.read().decode("utf-8", "ignore")
    err = stderr.read().decode("utf-8", "ignore")
    return out, err

print("=== current default ===")
out, err = run("ip route show default")
print(out.strip())

print("=== restore nhid 14 ===")
out, err = run("sudo ip route replace default nhid 14 via 172.17.9.1 dev eth0 proto static metric 20 2>&1; echo RC=$?")
print(out, err)
out, err = run("ip route show default")
print(out.strip())

print("=== ping test connectivity ===")
out, err = run("ping -c 2 -W 2 172.17.9.1 2>&1")
print(out[-300:] if out else err)

c.close()
print("DONE")
