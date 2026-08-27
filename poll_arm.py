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
    total = 0
    while total < 15 * 60:
        rc, out, err = run('date "+%H:%M:%S"; cat /opt/cbc/ipm/cache/event_used_data_cache.json 2>/dev/null; echo ---; ls -la /opt/cbc/ipm/cache/ 2>/dev/null; echo ---; tail -5 /var/log/cbc/ipm/ping.log')
        print('[{0}]'.format(out.strip()))
        print('=' * 40)
        if 'last_update_time' in out:
            print('CACHE EXISTS, stopping poll')
            break
        time.sleep(30)
        total += 30


if __name__ == '__main__':
    main()
