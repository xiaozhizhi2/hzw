# -*- coding: utf-8 -*-
"""ARM device: init logger then call funcs, inspect current_list."""
import paramiko
import base64

HOST = "172.17.8.148"
PORT = 6188
USER = "cbcadmin"
PASS = "XPCCncn99d"

DEBUG = r'''
import importlib.util, traceback
spec = importlib.util.spec_from_file_location('ep', '/opt/cbc/agent/agent/plugins/enet/10_event_push.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
m.logger = m.create_logger()
print('logger ok')
m.current_list = []
try:
    m.get_traffic_failover_cellular_status()
    print('cellular current_list:', m.current_list)
except Exception:
    print('CELLULAR ERROR:')
    traceback.print_exc()
try:
    m.get_interface_info()
    print('interface current_list len:', len(m.current_list))
    print(m.current_list[:5])
except Exception:
    print('INTERFACE ERROR:')
    traceback.print_exc()
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
