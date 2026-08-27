# -*- coding: utf-8 -*-
"""ARM device: inline debug, python decodes base64 and execs."""
import paramiko
import base64

HOST = "172.17.8.148"
PORT = 6188
USER = "cbcadmin"
PASS = "XPCCncn99d"

DEBUG = r'''
import os, re, json, subprocess
print('=== cfg exists ===')
print(os.path.exists('/etc/cbc/agent/traffic_failover_cellular_check.json'))
with open('/etc/cbc/agent/traffic_failover_cellular_check.json') as f:
    cfg = json.load(f)
print('cfg:', cfg)
print('=== ip route stdout/stderr ===')
obj = subprocess.Popen('ip route', shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
so, se = obj.communicate()
print('stdout:', so.decode())
print('stderr:', se.decode())
default_interface = ''
for line in so.decode().splitlines():
    line = line.strip()
    if not line.startswith('default '):
        continue
    m = re.search(r'\bdev\s+(\S+)', line)
    if m:
        default_interface = m.group(1)
    break
print('default_interface:', repr(default_interface))
for iface, icfg in cfg.items():
    print('iface:', iface, 'check:', icfg.get('is_check_traffic_failover_cellular'))
    print('match:', default_interface == iface)
'''

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=20)

def run(cmd):
    stdin, stdout, stderr = c.exec_command(cmd)
    out = stdout.read().decode("utf-8", "ignore")
    err = stderr.read().decode("utf-8", "ignore")
    return out, err

b64 = base64.b64encode(DEBUG.encode("utf-8")).decode("ascii")
cmd = "sudo python -c \"import base64;exec(base64.b64decode('{0}'))\"".format(b64)
out, err = run(cmd)
print("OUT:\n", out)
print("ERR:\n", err)

c.close()
print("DONE")
