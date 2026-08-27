# -*- coding: utf-8 -*-
import re
import time
import paramiko

DEVICES = [
    {
        'name': 'ARM',
        'host': '172.17.8.148',
        'port': 6188,
        'user': 'cbcadmin',
        'password': 'XPCCncn99d',
        'targets': [
            ('argus-agent', '1.0.1.R4'),
            ('ipm-agent', '1.0.0.R1'),
        ],
    },
    {
        'name': 'ENETOS',
        'host': '172.17.9.42',
        'port': 6188,
        'user': 'cbcadmin',
        'password': 'X98kgF2pwW',
        'targets': [
            ('argus-agent', '2.2.6.R3'),
            ('ipm-agent', '2.1.22.R1'),
        ],
    },
]

TIMEOUT = 1200


def open_ssh(device):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(device['host'], port=device['port'], username=device['user'], password=device['password'], timeout=20)
    return ssh


def run_cmd(ssh, cmd, timeout=120):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', 'ignore')
    err = stderr.read().decode('utf-8', 'ignore')
    rc = stdout.channel.recv_exit_status()
    return rc, out, err


def search_and_select(ssh, password, pkg, version):
    chan = ssh.get_transport().open_session()
    chan.get_pty()
    chan.exec_command('sudo -S depm search {0}'.format(pkg))

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
                chan.send(password + '\n')
                sent_password = True

            if choice is None:
                match = re.search(r'^(\d+)\)\s+%s[-_]%s[^\s]*' % (re.escape(pkg), re.escape(version)), all_out, re.M)
                if match:
                    choice = match.group(1)
                    print('\nAUTO FOUND CHOICE:', choice)

            if choice and (not sent_choice) and ('enter your choice' in lower or 'please select' in lower or 'select a deb' in lower or 'press a to abort' in lower):
                chan.send(choice + '\n')
                sent_choice = True
                print('AUTO SEND CHOICE:', choice)

            if (not sent_confirm) and ('[y/n]' in lower or '[y/n]' in lower or 'do you want to continue' in lower or 'continue?' in lower or 'is this ok' in lower or 'proceed' in lower):
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
            raise TimeoutError('search/select timeout for {0} {1}'.format(pkg, version))

        time.sleep(0.1)

    rc = chan.recv_exit_status()
    return rc, choice, all_out


def verify_pkg(ssh, pkg):
    rc, out, err = run_cmd(ssh, 'dpkg -s {0} 2>/dev/null || opkg info {0} 2>/dev/null || true'.format(pkg), timeout=120)
    print(out)
    if err:
        print(err)
    return out


def main():
    for device in DEVICES:
        print('\n' + '=' * 72)
        print(device['name'], device['host'])
        ssh = open_ssh(device)
        try:
            for pkg, version in device['targets']:
                print('\n--- SEARCH/SELECT INSTALL {0} {1} ---'.format(pkg, version))
                rc, choice, _ = search_and_select(ssh, device['password'], pkg, version)
                print('\nRESULT RC:', rc, 'CHOICE:', choice)
                print('\n--- VERIFY {0} ---'.format(pkg))
                verify_pkg(ssh, pkg)
        finally:
            ssh.close()


if __name__ == '__main__':
    main()
