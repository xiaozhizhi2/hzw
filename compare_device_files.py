# -*- coding: utf-8 -*-
import paramiko

DEVICES = [
    ('ARM', '172.17.8.148', 6188, 'cbcadmin', 'XPCCncn99d', [
        '/opt/cbc/agent/push_event.py',
        '/opt/cbc/ipm/bin/fping.py',
    ]),
    ('ENETOS', '172.17.9.42', 6188, 'cbcadmin', 'X98kgF2pwW', [
        '/root/cbc/agent/push_event.py',
        '/opt/cbc/ipm/bin/fping.py',
    ]),
]


def run(ssh, pwd, cmd):
    stdin, stdout, stderr = ssh.exec_command('echo "{0}" | sudo -S {1}'.format(pwd, cmd), timeout=60)
    out = stdout.read().decode('utf-8', 'ignore')
    err = stderr.read().decode('utf-8', 'ignore')
    rc = stdout.channel.recv_exit_status()
    return rc, out, err


def main():
    for name, host, port, user, pwd, files in DEVICES:
        print('\n' + '=' * 60)
        print(name, host)
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(host, port=port, username=user, password=pwd, timeout=15)
        try:
            for f in files:
                print('\n---', f, '---')
                rc, out, err = run(ssh, pwd, 'grep -n -E "connection.down|traffic.failover.cellular|EVENT_LOG_FILE|build_connection_down_status|compare_connection_down_events|handle_connection_down_events" {0} || true'.format(f))
                print(out)
                if err:
                    print('ERR:', err)
        finally:
            ssh.close()

if __name__ == '__main__':
    main()
