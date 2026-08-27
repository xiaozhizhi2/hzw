# -*- coding: utf-8 -*-
import paramiko

DEVICES = [
    ('ARM', '172.17.8.148', 6188, 'cbcadmin', 'XPCCncn99d'),
    ('ENETOS', '172.17.9.42', 6188, 'cbcadmin', 'X98kgF2pwW'),
]

CMDS = [
    'depm search argus',
    'depm search ipm',
    'depm search argus-agent',
    'depm search ipm-agent',
]


def run_cmd(host, port, user, pwd, cmd, timeout=120):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, port=port, username=user, password=pwd, timeout=15)
    # run with sudo -S, provide password via stdin
    full = 'echo "{pwd}" | sudo -S {cmd}'.format(pwd=pwd, cmd=cmd)
    stdin, stdout, stderr = ssh.exec_command(full, timeout=timeout)
    out = stdout.read().decode('utf-8', 'ignore')
    err = stderr.read().decode('utf-8', 'ignore')
    rc = stdout.channel.recv_exit_status()
    ssh.close()
    return rc, out, err


def main():
    for name, host, port, user, pwd in DEVICES:
        print('\n' + '='*60)
        print('Device: {0} {1}'.format(name, host))
        for cmd in CMDS:
            print('\nCMD: sudo {0}'.format(cmd))
            try:
                rc, out, err = run_cmd(host, port, user, pwd, cmd)
            except Exception as e:
                print('ERROR running cmd: {0}'.format(e))
                continue
            print('RC: {0}\n'.format(rc))
            if out:
                print('OUT:\n{0}'.format(out))
            if err:
                print('ERR:\n{0}'.format(err))

if __name__ == '__main__':
    main()
