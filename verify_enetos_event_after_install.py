# -*- coding: utf-8 -*-
import json
import time
import paramiko

HOST = '172.17.9.42'
PORT = 6188
USER = 'cbcadmin'
PASSWORD = 'X98kgF2pwW'


def open_ssh():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=20)
    return ssh


def sudo_cmd(ssh, cmd, timeout=120):
    wrapped = "echo '{0}' | sudo -S sh -c \"{1}\"".format(PASSWORD.replace("'", "'\"'\"'"), cmd.replace('"', '\\"'))
    stdin, stdout, stderr = ssh.exec_command(wrapped, timeout=timeout)
    out = stdout.read().decode('utf-8', 'ignore')
    err = stderr.read().decode('utf-8', 'ignore')
    rc = stdout.channel.recv_exit_status()
    return rc, out, err


def main():
    ssh = open_ssh()
    try:
        cmds = [
            "grep -n \"connection.down\\|traffic.failover.cellular\" /root/cbc/agent/push_event.py || true",
            "tail -n 50 /root/cbc/agent/agent/cache/event_push.log 2>/dev/null || true",
            "cat /opt/cbc/ipm/cache/event_used_data_cache.json 2>/dev/null || true",
            "python - <<'PY'\nimport json\npath='/opt/cbc/ipm/etc/ping_conf.json'\nwith open(path,'r') as f:\n    data=json.load(f)\nfor item in data.get('target',[]):\n    item['is_check_connection_down']=True\n    item['check_connection_down_threshold']=10\n    item['packet_loss']=100\nwith open(path,'w') as f:\n    json.dump(data,f,indent=4)\nPY",
            "cd /opt/cbc/ipm/bin && python ipm.py restart",
            "sleep 15 ; tail -n 100 /root/cbc/agent/agent/cache/event_push.log 2>/dev/null || true",
            "cat /opt/cbc/ipm/cache/event_used_data_cache.json 2>/dev/null || true",
        ]
        for cmd in cmds:
            rc, out, err = sudo_cmd(ssh, cmd, timeout=240)
            print('\n=== CMD ===')
            print(cmd)
            print(out)
            print(err)
            time.sleep(1)
    finally:
        ssh.close()


if __name__ == '__main__':
    main()
