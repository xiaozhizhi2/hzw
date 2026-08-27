# -*- coding: utf-8 -*-
import paramiko

HOST = '172.17.8.148'
PORT = 6188
USER = 'cbcadmin'
PWD = 'XPCCncn99d'


def run(cmd, timeout=60):
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
        'ls -la /var/log/cbc/agent/ 2>/dev/null | head -20',
        'ls -la /var/log/cbc/ 2>/dev/null',
        'grep -ri "connection.down" /var/log/cbc/agent/ 2>/dev/null | tail -10',
        'grep -ri "connection.down" /var/log/cbc/ 2>/dev/null | tail -20',
        'cat /opt/cbc/agent/push_event.py 2>/dev/null | head -30',
        'ps w | grep -i argus | grep -v grep',
    ]
    for c in cmds:
        rc, out, err = run(c)
        print('=' * 50)
        print('CMD: {0}'.format(c))
        if out:
            print(out.strip())
        if err:
            print('ERR: {0}'.format(err.strip()))


if __name__ == '__main__':
    main()
