# -*- coding: utf-8 -*-
import paramiko

HOST = '172.17.8.148'
PORT = 6188
USER = 'cbcadmin'
PWD = 'XPCCncn99d'


def run(cmd, timeout=30, sudo=False):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, port=PORT, username=USER, password=PWD, timeout=15)
    if sudo:
        cmd = 'echo "{0}" | sudo -S {1}'.format(PWD, cmd)
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', 'ignore')
    err = stderr.read().decode('utf-8', 'ignore')
    rc = stdout.channel.recv_exit_status()
    ssh.close()
    return rc, out, err


def main():
    cmds = [
        'ps w | grep -iE "ipm|fping" | grep -v grep',
        'cat /opt/cbc/ipm/bin/ipm_keepalive.sh',
        'cat /opt/cbc/ipm/bin/ipm_setup.sh',
        'ls -la /opt/cbc/ipm/var/',
        'find /opt/cbc/ipm -name "*.log" 2>/dev/null',
        'cat /var/log/cbc/ipm/ipm.log 2>/dev/null | tail -20',
        'ls -la /etc/cbc/ipm/',
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
