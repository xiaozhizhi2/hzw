# -*- coding: utf-8 -*-
import base64
import json
import paramiko
import time
import datetime

HOST = '172.17.8.148'
PORT = 6188
USER = 'cbcadmin'
PWD = 'XPCCncn99d'
REMOTE_CONF = '/etc/cbc/ipm/ping_conf.json'


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


def main():
    # 1. 改 threshold 200（丢包100% < 200 → OK）
    rc, out, err = run('cat {0}'.format(REMOTE_CONF))
    conf = json.loads(out)
    for t in conf['targets']:
        if t['target_address'] == '3.3.3.114':
            t['check_connection_down_threshold'] = 200
    new_conf = json.dumps(conf, indent=2, ensure_ascii=False).encode('utf-8')
    b64 = base64.b64encode(new_conf).decode()
    chunks = [b64[i:i + 2000] for i in range(0, len(b64), 2000)]
    rc, out, err = run('> /home/cbcadmin/ping_conf_new.json')
    for i, chunk in enumerate(chunks):
        cmd = (
            'echo {0} | python -c "import sys,base64;'
            'data=base64.b64decode(sys.stdin.read().strip());'
            'f=open(sys.argv[1],\'ab\');f.write(data);f.close()" /home/cbcadmin/ping_conf_new.json'
        ).format(chunk)
        rc, out, err = run(cmd)
    rc, out, err = run('echo "{0}" | sudo -S cp -f /home/cbcadmin/ping_conf_new.json {1} && echo OK'.format(PWD, REMOTE_CONF), timeout=30)
    print('conf update rc={0} out={1} err={2}'.format(rc, out.strip(), err.strip()))
    rc, out, err = run('python -c "import json;c=json.load(open(\'{0}\'));t=[x for x in c[\'targets\'] if x[\'target_address\']==\'3.3.3.114\'][0];print(t[\'check_connection_down_threshold\'])"'.format(REMOTE_CONF))
    print('threshold now: {0}'.format(out.strip()))

    # 2. 重启（需 sudo）
    rc, out, err = run('echo "{0}" | sudo -S sh -c "cd /opt/cbc/ipm/bin && python ipm.py restart"'.format(PWD), timeout=90)
    print('restart rc={0} err={1}'.format(rc, err.strip()))
    time.sleep(10)
    rc, out, err = run('ps w | grep fping.py | grep -v grep')
    print('fping proc: {0}'.format(out.strip()))
    if not out.strip():
        # keepalive 未拉起则手动重启
        rc, out, err = run('echo "{0}" | sudo -S sh -c "cd /opt/cbc/ipm/bin && python ipm.py restart"'.format(PWD), timeout=90)
        print('manual restart rc={0} err={1}'.format(rc, err.strip()))
        time.sleep(10)
        rc, out, err = run('ps w | grep fping.py | grep -v grep')
        print('fping proc after: {0}'.format(out.strip()))

    # 3. 等到 14:51:30 检查 OK 恢复事件
    t = datetime.datetime.now()
    nxt = t.replace(minute=51, second=30, microsecond=0)
    if nxt <= t:
        nxt = nxt + datetime.timedelta(minutes=5)
    wait = (nxt - t).total_seconds()
    print('wait {0}s until {1}'.format(int(wait), nxt.strftime('%H:%M:%S')))
    time.sleep(wait)

    rc, out, err = run('tail -5 /var/log/cbc/argus-agent/event_push.log')
    print('EVENT LOG:\n{0}'.format(out))
    rc, out, err = run('cat /opt/cbc/ipm/cache/event_used_data_cache.json')
    print('CACHE:\n{0}'.format(out))
    rc, out, err = run('grep -c "eventType.*connection.down" /var/log/cbc/argus-agent/event_push.log 2>/dev/null')
    print('total connection.down events: {0}'.format(out.strip()))


if __name__ == '__main__':
    main()
