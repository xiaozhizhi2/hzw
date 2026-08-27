# -*- coding: utf-8 -*-
import paramiko
import time

DEVICES = [
    ('ARM', '172.17.8.148', 6188, 'cbcadmin', 'XPCCncn99d', {
        'argus_log': '/var/log/cbc/argus-agent/event_push.log',
        'cache': '/opt/cbc/ipm/cache/event_used_data_cache.json',
        'push_event': '/opt/cbc/agent/push_event.py',
        'argus_pkg': 'argus-agent',
        'ipm_pkg': 'ipm-agent',
    }),
    ('ENETOS', '172.17.9.42', 6188, 'cbcadmin', 'X98kgF2pwW', {
        'argus_log': '/root/cbc/agent/agent/cache/event_push.log',
        'cache': '/opt/cbc/ipm/cache/event_used_data_cache.json',
        'push_event': '/root/cbc/agent/push_event.py',
        'argus_pkg': 'argus-agent',
        'ipm_pkg': 'ipm-agent',
    }),
]


def run_sudo(ssh, password, cmd, timeout=180):
    chan = ssh.get_transport().open_session()
    chan.get_pty()
    chan.exec_command('sudo -S sh -c ' + repr(cmd))
    time.sleep(0.5)
    try:
        chan.send(password + '\n')
    except Exception:
        pass
    out = ''
    err = ''
    start = time.time()
    while True:
        if chan.recv_ready():
            out += chan.recv(4096).decode('utf-8', 'ignore')
        if chan.recv_stderr_ready():
            err += chan.recv_stderr(4096).decode('utf-8', 'ignore')
        if chan.exit_status_ready():
            break
        if time.time() - start > timeout:
            chan.close()
            raise RuntimeError('timeout: ' + cmd)
        time.sleep(0.1)
    rc = chan.recv_exit_status()
    return rc, out, err


def connect(host, port, user, pwd):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, port=port, username=user, password=pwd, timeout=15)
    return ssh


def main():
    for name, host, port, user, pwd, cfg in DEVICES:
        print('\n' + '=' * 70)
        print(name, host)
        ssh = connect(host, port, user, pwd)
        try:
            cmds = [
                ('pkg_argus', 'depm info {0} || opkg info {0} || dpkg -s {0}'.format(cfg['argus_pkg'])),
                ('pkg_ipm', 'depm info {0} || opkg info {0} || dpkg -s {0}'.format(cfg['ipm_pkg'])),
                ('push_event_header', 'sed -n "1,40p" {0}'.format(cfg['push_event'])),
                ('argus_log_tail', 'tail -n 20 {0} 2>/dev/null || true'.format(cfg['argus_log'])),
                ('ipm_cache', 'cat {0} 2>/dev/null || true'.format(cfg['cache'])),
                ('processes', "ps w | grep -E 'argus-agent|ipm.py|fping.py' | grep -v grep || true"),
            ]
            for label, cmd in cmds:
                print('\n---', label, '---')
                rc, out, err = run_sudo(ssh, pwd, cmd, timeout=180)
                print('RC:', rc)
                if out:
                    print(out[:4000])
                if err:
                    print('ERR:', err[:2000])
        finally:
            ssh.close()

if __name__ == '__main__':
    main()
