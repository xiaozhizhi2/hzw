# -*- coding: utf-8 -*-
import paramiko

HOST = '172.17.9.42'
PORT = 6188
USER = 'cbcadmin'
PASSWORD = 'X98kgF2pwW'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=20)

cmds = [
    "python -c \"import json; path='/opt/cbc/ipm/cache/event_used_data_cache.json'; data=json.load(open(path));\nfor item in data.get('last_update_info', []):\n    item['value']='PROBLEM'\n    item['packet_loss_rate']=100\njson.dump(data, open(path,'w'), indent=4)\"",
    "cd /opt/cbc/ipm/bin && python ipm.py restart",
    "sleep 10 ; tail -n 80 /root/cbc/agent/agent/cache/event_push.log 2>/dev/null || true",
    "cat /opt/cbc/ipm/cache/event_used_data_cache.json 2>/dev/null || true",
]

for cmd in cmds:
    wrapped = "echo '{0}' | sudo -S sh -c \"{1}\"".format(PASSWORD, cmd.replace('"', '\\"'))
    stdin, stdout, stderr = ssh.exec_command(wrapped, timeout=240)
    print(stdout.read().decode('utf-8', 'ignore'))
    print(stderr.read().decode('utf-8', 'ignore'))

ssh.close()
