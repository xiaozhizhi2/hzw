# -*- coding: utf-8 -*-
import paramiko
import time

DEVICES = [
    ('ARM', '172.17.8.148', 6188, 'cbcadmin', 'XPCCncn99d', ['argus-agent', 'ipm-agent']),
    ('ENETOS', '172.17.9.42', 6188, 'cbcadmin', 'X98kgF2pwW', ['argus-agent', 'ipm-agent']),
]


def connect(host, port, user, pwd):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, port=port, username=user, password=pwd, timeout=15)
    return ssh


def run_interactive(ssh, password, cmd, timeout=600):
    chan = ssh.get_transport().open_session()
    chan.get_pty()
    chan.exec_command('sudo -S ' + cmd)
    out = ''
    err = ''
    sent_pwd = False
    sent_choice = False
    sent_yes = False
    start = time.time()
    while True:
        if chan.recv_ready():
            data = chan.recv(4096).decode('utf-8', 'ignore')
            out += data
            if not sent_pwd and ('password' in data.lower() or '[sudo]' in data.lower()):
                chan.send(password + '\n')
                sent_pwd = True
            if ('Enter your choice' in data or 'Please select' in data or '选择' in data) and not sent_choice:
                chan.send('1\n')
                sent_choice = True
            if ('[Y/n]' in data or 'y/N' in data or 'Do you want' in data or 'continue?' in data.lower()) and not sent_yes:
                chan.send('y\n')
                sent_yes = True
        if chan.recv_stderr_ready():
            err += chan.recv_stderr(4096).decode('utf-8', 'ignore')
        if chan.exit_status_ready():
            break
        if time.time() - start > timeout:
            chan.close()
            raise RuntimeError('timeout: ' + cmd + '\nOUT:\n' + out[-2000:])
        time.sleep(0.1)
    rc = chan.recv_exit_status()
    return rc, out, err


def main():
    for name, host, port, user, pwd, pkgs in DEVICES:
        print('\n' + '=' * 70)
        print(name, host)
        ssh = connect(host, port, user, pwd)
        try:
            for pkg in pkgs:
                print('\n--- depm install', pkg, '---')
                rc, out, err = run_interactive(ssh, pwd, 'depm install {0}'.format(pkg), timeout=900)
                print('RC:', rc)
                print(out[:8000])
                if err:
                    print('ERR:', err[:3000])
            print('\n--- depm list ---')
            rc, out, err = run_interactive(ssh, pwd, 'depm list', timeout=180)
            print(out[:5000])
        finally:
            ssh.close()

if __name__ == '__main__':
    main()
