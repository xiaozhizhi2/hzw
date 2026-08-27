# -*- coding: utf-8 -*-
import paramiko
import sys

DEVICES = [
    ('ARM', '172.17.8.148', 6188, 'cbcadmin', 'XPCCncn99d'),
    ('ENETOS', '172.17.9.42', 6188, 'cbcadmin', 'X98kgF2pwW'),
]

COMMANDS = [
    'depm search argus',
    'depm search ipm',
    'depm search argus-agent',
    'depm search ipm-agent',
]


def run_cmd(host, port, user, pwd, cmd, timeout=60):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, port=port, username=user, password=pwd, timeout=15)
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', 'ignore')
    err = stderr.read().decode('utf-8', 'ignore')
    rc = stdout.channel.recv_exit_status()
    ssh.close()
    return rc, out, err


def main():
    for name, host, port, user, pwd in DEVICES:
        print('\n' + '='*40)
        print('Device: {0} {1}'.format(name, host))
        for cmd in COMMANDS:
            try:
                rc, out, err = run_cmd(host, port, user, pwd, cmd)
            except Exception as e:
                print('CMD: {0}\nERROR: {1}'.format(cmd, e))
                continue
            print('\nCMD: {0}\nRC: {1}'.format(cmd, rc))
            if out:
                print('OUT:\n{0}'.format(out))
            if err:
                print('ERR:\n{0}'.format(err))

if __name__ == '__main__':
    main()
