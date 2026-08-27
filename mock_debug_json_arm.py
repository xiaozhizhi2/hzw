# -*- coding: utf-8 -*-
"""ARM: test json.loads on cache raw directly."""
import paramiko
import base64

HOST = "172.17.8.148"
PORT = 6188
USER = "cbcadmin"
PASS = "XPCCncn99d"

DEBUG = r'''
import json, traceback
raw = open('/opt/cbc/agent/agent/cache/event_used_data_cache.json').read()
print('len:', len(raw))
try:
    d = json.loads(raw)
    print('json.loads OK, keys:', list(d.keys()))
except Exception as e:
    print('json.loads ERR:', e)
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
