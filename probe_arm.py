# -*- coding: utf-8 -*-
import paramiko
import sys

HOST = '172.17.8.148'
PORT = 6188
USER = 'cbcadmin'
PWD = 'XPCCncn99d'


def run(cmd, timeout=30):
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
    cmds = [
        'ls -la /opt/cbc/ipm/',
        'ls -la /opt/cbc/ipm/bin/ 2>/dev/null',
        'cat /etc/cbc/ipm/ping_conf.json 2>/dev/null | head -50',
        'ls -la /opt/cbc/ipm/cache/ 2>/dev/null',
        'ls -la /root/cbc/ipm/ 2>/dev/null',
        'ps aux | grep -i ipm | grep -v grep',
        'which python python3 fping; python --version 2>&1; python3 --version 2>&1',
    ]
    for c in cmds:
        rc, out, err = run(c)
        print('=' * 60)
        print('CMD: {0}'.format(c))
        print('RC: {0}'.format(rc))
        if out:
            print('OUT:\n{0}'.format(out))
        if err:
            print('ERR:\n{0}'.format(err))


if __name__ == '__main__':
    main()
