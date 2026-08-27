# -*- coding: utf-8 -*-
"""ARM: debug compare logic for recover (PROBLEM->OK)."""
import paramiko
import base64

HOST = "172.17.8.148"
PORT = 6188
USER = "cbcadmin"
PASS = "XPCCncn99d"

DEBUG = r'''
import json
cache = json.load(open('/opt/cbc/agent/agent/cache/event_used_data_cache.json'))
last_update_info = cache['last_update_info']
print('cache seq:', cache['last_update_seq'])
print('cached cellular:', [i for i in last_update_info if i['metric']=='traffic.failover.cellular'])

current_list = []
current_list.append({'metric': 'traffic.failover.cellular', 'tags': 'outgoing_interface=wan0', 'value': 'OK'})

need_push_events = []
for new_index, new_value in enumerate(current_list):
    matched = 0
    for cached_index, cached_value in enumerate(last_update_info):
        if new_value["tags"] == cached_value["tags"] and new_value["metric"] == cached_value["metric"]:
            if new_value["value"] != cached_value["value"]:
                print('VALUE CHANGED:', new_value['value'], '->', cached_value['value'])
                np = dict(new_value)
                np.update({"before_value": cached_value["value"]})
                need_push_events.append(np)
            matched = 1
            break
print('need_push_events:', need_push_events)
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
