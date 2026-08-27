# -*- coding: utf-8 -*-
import paramiko
import time

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
    # 日志位置
    rc, out, err = run('ls -la /var/log/cbc/ipm/')
    print(out)
    rc, out, err = run('tail -30 /var/log/cbc/ipm/fping.log 2>/dev/null || tail -30 /var/log/cbc/ipm/agent.log 2>/dev/null')
    print('LOG:\n{0}'.format(out))
    if err:
        print('ERR: {0}'.format(err))


if __name__ == '__main__':
    main()
