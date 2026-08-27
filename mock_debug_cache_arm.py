# -*- coding: utf-8 -*-
"""ARM: debug get_cache_content why returns None."""
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
print('PLUGIN_CACHE_FILE:', m.PLUGIN_CACHE_FILE)
# read raw
try:
    raw = open(m.PLUGIN_CACHE_FILE).read()
    print('raw len:', len(raw))
    print('raw head:', raw[:200])
except Exception as e:
    print('open err:', e)
# call get_cache_content
try:
    res = m.get_cache_content(0)
    print('get_cache_content result:', res if res is None else ('keys=' + str(list(res.keys()))))
except Exception as e:
    print('call err:')
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
