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

TIMEOUT = 900


def wait_output(chan, timeout=TIMEOUT):
    out = ''
    start = time.time()
    while True:
        if chan.recv_ready():
            data = chan.recv(4096).decode('utf-8', 'ignore')
            out += data
            print(data, end='')
        if chan.recv_stderr_ready():
            data = chan.recv_stderr(4096).decode('utf-8', 'ignore')
            out += data
            print(data, end='')
        if chan.exit_status_ready():
            break
        if time.time() - start > timeout:
            raise TimeoutError('command timeout')
        time.sleep(0.1)
    rc = chan.recv_exit_status()
    return rc, out


def open_ssh(device):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(
        device['host'],
        port=device['port'],
        username=device['user'],
        password=device['password'],
        timeout=20,
    )
    return ssh


def run_cmd(ssh, cmd, timeout=TIMEOUT):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', 'ignore')
    err = stderr.read().decode('utf-8', 'ignore')
    rc = stdout.channel.recv_exit_status()
    return rc, out, err


def search_package(ssh, password, pkg):
    chan = ssh.get_transport().open_session()
    chan.get_pty()
    chan.exec_command('sudo -S depm search {0}'.format(pkg))
    out = ''
    sent_password = False
    start = time.time()
    while True:
        if chan.recv_ready():
            data = chan.recv(4096).decode('utf-8', 'ignore')
            out += data
            print(data, end='')
            lower = data.lower()
            if (not sent_password) and ('password' in lower or '密码' in data):
                chan.send(password + '\n')
                sent_password = True
        if chan.recv_stderr_ready():
            data = chan.recv_stderr(4096).decode('utf-8', 'ignore')
            out += data
            print(data, end='')
        if chan.exit_status_ready():
            break
        if time.time() - start > TIMEOUT:
            raise TimeoutError('search timeout')
        time.sleep(0.1)
    rc = chan.recv_exit_status()
    return rc, out


def find_choice(search_output, pkg, version):
    pattern = re.compile(r'^(\d+)\)\s+%s[-_]%s[^\s]*' % (re.escape(pkg), re.escape(version)), re.M)
    match = pattern.search(search_output)
    if not match:
        raise RuntimeError('cannot find choice for {0} {1}'.format(pkg, version))
    return match.group(1)


def install_package(ssh, password, pkg, choice):
    chan = ssh.get_transport().open_session()
    chan.get_pty()
    chan.exec_command('sudo -S depm install {0}'.format(pkg))
    out = ''
    sent_password = False
    sent_choice = False
    sent_confirm = False
    start = time.time()
    while True:
        if chan.recv_ready():
            data = chan.recv(4096).decode('utf-8', 'ignore')
            out += data
            print(data, end='')
            lower = data.lower()
            if (not sent_password) and ('password' in lower or '密码' in data):
                chan.send(password + '\n')
                sent_password = True
            if (not sent_choice) and ('enter your choice' in lower or 'please select' in lower or 'select a deb' in lower or 'press a to abort' in lower):
                chan.send(str(choice) + '\n')
                sent_choice = True
                print('AUTO CHOICE:', choice)
            if (not sent_confirm) and ('[y/n]' in lower or '[y/n]' in lower or 'do you want to continue' in lower or 'continue?' in lower or 'proceed' in lower or 'is this ok' in lower):
                chan.send('y\n')
                sent_confirm = True
                print('AUTO CONFIRM: y')
        if chan.recv_stderr_ready():
            data = chan.recv_stderr(4096).decode('utf-8', 'ignore')
            out += data
            print(data, end='')
        if chan.exit_status_ready():
            break
        if time.time() - start > TIMEOUT:
            raise TimeoutError('install timeout')
        time.sleep(0.1)
    rc = chan.recv_exit_status()
    return rc, out


def verify(ssh, pkg):
    rc, out, err = run_cmd(ssh, 'dpkg -s {0} 2>/dev/null || opkg info {0} 2>/dev/null || true'.format(pkg))
    print(out)
    if err:
        print(err)
    return out


def main():
    for device in DEVICES:
        print('\n' + '=' * 70)
        print(device['name'], device['host'])
        ssh = open_ssh(device)
        try:
            for pkg, version in device['targets']:
                print('\n--- SEARCH {0} {1} ---'.format(pkg, version))
                rc, out = search_package(ssh, device['password'], pkg)
                print('SEARCH RC:', rc)
                choice = find_choice(out, pkg, version)
                print('CHOICE:', choice)

                print('\n--- INSTALL {0} {1} ---'.format(pkg, version))
                rc, install_out = install_package(ssh, device['password'], pkg, choice)
                print('INSTALL RC:', rc)

                print('\n--- VERIFY {0} ---'.format(pkg))
                verify(ssh, pkg)
        finally:
            ssh.close()


if __name__ == '__main__':
    main()
