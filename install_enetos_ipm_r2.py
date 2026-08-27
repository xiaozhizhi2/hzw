# -*- coding: utf-8 -*-
import re
import time
import paramiko

HOST = '172.17.9.42'
PORT = 6188
USER = 'cbcadmin'
PASSWORD = 'X98kgF2pwW'
PKG = 'ipm-agent'
VERSION = '2.1.22.R2'
TIMEOUT = 1800


def open_ssh():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=20)
    return ssh


def run_cmd(ssh, cmd, timeout=120):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', 'ignore')
    err = stderr.read().decode('utf-8', 'ignore')
    rc = stdout.channel.recv_exit_status()
    return rc, out, err


def depm_search_install(ssh):
    chan = ssh.get_transport().open_session()
    chan.get_pty()
    chan.exec_command('sudo -S depm search {0}'.format(PKG))

    all_out = ''
    sent_password = False
    sent_choice = False
    sent_confirm = False
    choice = None
    start = time.time()

    while True:
        if chan.recv_ready():
            data = chan.recv(4096).decode('utf-8', 'ignore')
            all_out += data
            print(data, end='')
            lower = data.lower()

            if (not sent_password) and ('password' in lower or '密码' in data):
                chan.send(PASSWORD + '\n')
                sent_password = True

            if choice is None:
                match = re.search(r'^(\d+)\)\s+%s[-_]%s[^\s]*' % (re.escape(PKG), re.escape(VERSION)), all_out, re.M)
                if match:
                    choice = match.group(1)
                    print('\nAUTO FOUND CHOICE:', choice)

            if choice and (not sent_choice) and ('enter your choice' in lower or 'please select' in lower or 'select a deb' in lower or 'press a to abort' in lower):
                chan.send(choice + '\n')
                sent_choice = True
                print('AUTO SEND CHOICE:', choice)

            if (not sent_confirm) and ('[y/n]' in lower or 'do you want to continue' in lower or 'continue?' in lower or 'is this ok' in lower or 'proceed' in lower):
                chan.send('y\n')
                sent_confirm = True
                print('AUTO SEND CONFIRM: y')

        if chan.recv_stderr_ready():
            data = chan.recv_stderr(4096).decode('utf-8', 'ignore')
            all_out += data
            print(data, end='')

        if chan.exit_status_ready():
            break

        if time.time() - start > TIMEOUT:
            raise TimeoutError('timeout waiting depm search/install')

        time.sleep(0.1)

    rc = chan.recv_exit_status()
    return rc, choice, all_out


def main():
    ssh = open_ssh()
    try:
        rc, out, err = run_cmd(ssh, 'dpkg --configure -a', timeout=300)
        print('=== dpkg --configure -a ===')
        print(out)
        print(err)

        rc, choice, all_out = depm_search_install(ssh)
        print('\n=== RESULT ===')
        print('RC:', rc)
        print('CHOICE:', choice)

        for cmd in [
            'dpkg -s ipm-agent || true',
            'grep -n "connection.down\|traffic.failover.cellular" /opt/cbc/ipm/bin/fping.py || true',
            'tail -n 80 /root/cbc/agent/agent/cache/event_push.log 2>/dev/null || true',
            'cat /opt/cbc/ipm/cache/event_used_data_cache.json 2>/dev/null || true',
        ]:
            rc, out, err = run_cmd(ssh, cmd, timeout=120)
            print('\n=== CMD ===')
            print(cmd)
            print(out)
            print(err)
    finally:
        ssh.close()


if __name__ == '__main__':
    main()
