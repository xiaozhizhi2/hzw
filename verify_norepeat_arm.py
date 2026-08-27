# -*- coding: utf-8 -*-
import json
import paramiko
import time

HOST = '172.17.8.148'
PORT = 6188
USER = 'cbcadmin'
PWD = 'XPCCncn99d'


def run(cmd, timeout=90):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, port=PORT, username=USER, password=PWD, timeout=15)
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', 'ignore')
    err = stderr.read().decode('utf-8', 'ignore')
    rc = stdout.channel.recv_exit_status()
    ssh.close()
    return rc, out, err


def count_events():
    rc, out, err = run('grep -c "eventType.*connection.down" /var/log/cbc/argus-agent/event_push.log 2>/dev/null')
    return out.strip()


def main():
    # 阶段1: 等待 14:31:30，确认第二轮无重复推送
    now_ts = time.time()
    target = None
    import datetime
    t = datetime.datetime.now()
    nxt = t.replace(minute=31, second=30, microsecond=0)
    if nxt <= t:
        nxt = nxt.replace(day=t.day)  # same day
        if nxt <= t:
            nxt = nxt + datetime.timedelta(days=1)
    wait = (nxt - t).total_seconds()
    print('wait {0}s until {1}'.format(int(wait), nxt.strftime('%H:%M:%S')))
    time.sleep(wait)

    print('--- after next cycle (no-repeat check) ---')
    rc, out, err = run('tail -3 /var/log/cbc/argus-agent/event_push.log')
    print(out)
    rc, out, err = run('cat /opt/cbc/ipm/cache/event_used_data_cache.json')
    print('CACHE: {0}'.format(out.strip()))
    print('connection.down event count: {0}'.format(count_events()))


if __name__ == '__main__':
    main()
