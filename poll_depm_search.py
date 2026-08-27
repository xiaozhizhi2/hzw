# -*- coding: utf-8 -*-
import paramiko
import time
import re
from datetime import datetime

DEVICES = [
    ('ARM', '172.17.8.148', 6188, 'cbcadmin', 'XPCCncn99d', ['argus-agent', 'ipm-agent']),
    ('ENETOS', '172.17.9.42', 6188, 'cbcadmin', 'X98kgF2pwW', ['argus-agent', 'ipm-agent']),
]

TARGETS = {
    'ARM': {
        'argus-agent': '1.0.1.R4',
        'ipm-agent': '1.0.0.R1',
    },
    'ENETOS': {
        'argus-agent': '2.2.6.R3',
        'ipm-agent': '2.1.22.R1',
    },
}


def connect(host, port, user, pwd):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, port=port, username=user, password=pwd, timeout=15)
    return ssh


def run_interactive(ssh, password, cmd, timeout=300):
    chan = ssh.get_transport().open_session()
    chan.get_pty()
    chan.exec_command('sudo -S ' + cmd)
    out = ''
    err = ''
    sent_pwd = False
    sent_choice = False
    start = time.time()
    while True:
        if chan.recv_ready():
            data = chan.recv(4096).decode('utf-8', 'ignore')
            out += data
            if not sent_pwd and ('password' in data.lower() or '[sudo]' in data.lower()):
                chan.send(password + '\n')
                sent_pwd = True
            if ('Enter your choice' in data or 'Please select' in data or '选择' in data) and not sent_choice:
                chan.send('A\n')
                sent_choice = True
        if chan.recv_stderr_ready():
            err += chan.recv_stderr(4096).decode('utf-8', 'ignore')
        if chan.exit_status_ready():
            break
        if time.time() - start > timeout:
            try:
                chan.close()
            except Exception:
                pass
            return 1, out, err + '\nTIMEOUT'
        time.sleep(0.1)
    rc = chan.recv_exit_status()
    return rc, out, err


def main():
    start = time.time()
    while True:
        print('\n' + '=' * 80)
        print('POLL TIME:', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        all_found = True
        for name, host, port, user, pwd, pkgs in DEVICES:
            print('\nDEVICE:', name, host)
            ssh = connect(host, port, user, pwd)
            try:
                for pkg in pkgs:
                    target = TARGETS[name][pkg]
                    rc, out, err = run_interactive(ssh, pwd, 'depm search {0}'.format(pkg), timeout=300)
                    found = target in out
                    print('  PKG:', pkg, 'TARGET:', target, 'FOUND:', found, 'RC:', rc)
                    if found:
                        m = re.search(r'(^.*' + re.escape(target) + r'.*$)', out, re.M)
                        if m:
                            print('   MATCH:', m.group(1))
                    else:
                        all_found = False
            finally:
                ssh.close()
        if all_found:
            print('\nALL TARGET PACKAGES FOUND')
            break
        if time.time() - start > 3600:
            print('\nPOLL TIMEOUT 1h')
            break
        time.sleep(120)

if __name__ == '__main__':
    main()
