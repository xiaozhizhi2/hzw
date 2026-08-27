# -*- coding: utf-8 -*-
"""ARM device: import module, call funcs, inspect current_list scope."""
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
try:
    spec.loader.exec_module(m)
    print('module loaded OK')
    print('has current_list global:', hasattr(m, 'current_list'))
    print('has get_traffic_failover_cellular_status:', hasattr(m, 'get_traffic_failover_cellular_status'))
    # set global current_list
    m.current_list = []
    try:
        m.get_traffic_failover_cellular_status()
        print('after call current_list:', m.current_list)
    except Exception:
        print('CALL ERROR:')
        traceback.print_exc()
except Exception:
    print('LOAD ERROR:')
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
