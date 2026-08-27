# -*- coding: utf-8 -*-
"""ARM device: inline debug get_traffic_failover_cellular_status."""
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

debug = """
import sys, os, re, json, subprocess, time
sys.path.insert(0, '/opt/cbc/agent/agent/plugins/enet')
import importlib.util
spec = importlib.util.spec_from_file_location('ep', '/opt/cbc/agent/agent/plugins/enet/10_event_push.py')
# just replicate logic instead of importing module (module runs main on import? no, has __main__ guard)
os.environ['PYTHONPATH']='/opt/cbc/agent/agent/plugins/enet'

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
    m = re.search(r'\\bdev\\s+(\\S+)', line)
    if m:
        default_interface = m.group(1)
    break
print('default_interface:', repr(default_interface))

for iface, icfg in cfg.items():
    print('iface:', iface, 'check:', icfg.get('is_check_traffic_failover_cellular'))
    print('match:', default_interface == iface)
"""

out, err = run("sudo python -c " + repr(debug))
print("OUT:\n", out)
print("ERR:\n", err)

c.close()
print("DONE")
