# -*- coding: utf-8 -*-
import paramiko

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
    rc, out, err = run('cat /etc/cbc/ipm/ping_conf.json')
    print('RC: {0}'.format(rc))
    print(out)
    if err:
        print('ERR: {0}'.format(err))


if __name__ == '__main__':
    main()
