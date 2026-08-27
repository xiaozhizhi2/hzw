# -*- coding: utf-8 -*-
import paramiko
import time
import select

DEVICES = [
    ('ARM', '172.17.8.148', 6188, 'cbcadmin', 'XPCCncn99d'),
    ('ENETOS', '172.17.9.42', 6188, 'cbcadmin', 'X98kgF2pwW'),
]
PKGS_BY_DEVICE = {
    'ARM': ['argus-agent', 'ipm-agent'],
    'ENETOS': ['argus-agent', 'ipm-agent'],
}

READ_TIMEOUT = 1.0
COMMAND_TIMEOUT = 600


def run_interactive(ssh, cmd, password, timeout=COMMAND_TIMEOUT):
    chan = ssh.get_transport().open_session()
    chan.get_pty()
    chan.exec_command(cmd)
    out = ''
    err = ''
    start = time.time()
    while True:
        if chan.recv_ready():
            data = chan.recv(4096).decode(errors='ignore')
            out += data
            print(data, end='')
            # detect sudo password prompt
            if 'password' in data.lower() or '密码' in data:
                chan.send(password + '\n')
            # detect interactive selection prompts -> send 1 or y
            if ('select' in data.lower() and 'package' in data.lower()) or '请输入' in data or '选择' in data or 'enter choice' in data.lower() or 'please select' in data.lower():
                chan.send('1\n')
            if 'y/N' in data or '[Y/n]' in data or 'do you want' in data.lower():
                chan.send('y\n')
        if chan.recv_stderr_ready():
            err_chunk = chan.recv_stderr(4096).decode(errors='ignore')
            err += err_chunk
            print(err_chunk, end='')
        if chan.exit_status_ready():
            break
        if time.time() - start > timeout:
            try:
                chan.close()
            except Exception:
                pass
            raise TimeoutError('Command timeout')
        time.sleep(0.1)
    rc = chan.recv_exit_status()
    return rc, out, err


def deploy_and_test_device(name, host, port, user, pwd):
    print('\n' + '='*60)
    print('Device:', name, host)
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, port=port, username=user, password=pwd, timeout=15)

    pkgs = PKGS_BY_DEVICE.get(name, [])
    results = []
    for pkg in pkgs:
        try:
            print('\n-- SEARCH', pkg)
            rc, out, err = run_interactive(ssh, 'sudo -S depm search {0}'.format(pkg), pwd)
            print('\nsearch rc=', rc)
            time.sleep(1)
            print('\n-- INSTALL', pkg)
            rc, out, err = run_interactive(ssh, 'sudo -S depm install {0}'.format(pkg), pwd)
            print('\ninstall rc=', rc)
            results.append((pkg, rc, out, err))
        except Exception as e:
            results.append((pkg, 'error', str(e), ''))
    # smoke tests
    print('\n-- SMOKE CHECKS')
    checks = {}
    # check argus-agent log
    rc, out, err = run_interactive(ssh, 'sudo -S ls -la /var/log/cbc/argus-agent || true', pwd)
    checks['argus-log-list'] = out
    rc, out, err = run_interactive(ssh, 'sudo -S tail -n 30 /var/log/cbc/argus-agent/event_push.log || true', pwd)
    checks['event_push_tail'] = out
    # check ipm cache
    rc, out, err = run_interactive(ssh, 'sudo -S cat /opt/cbc/ipm/cache/event_used_data_cache.json || true', pwd)
    checks['ipm_cache'] = out
    # check processes
    rc, out, err = run_interactive(ssh, "sudo -S ps w | grep -E 'argus-agent|ipm.py|fping.py' | grep -v grep || true", pwd)
    checks['processes'] = out

    ssh.close()
    return results, checks


def main():
    summary = {}
    for name, host, port, user, pwd in DEVICES:
        res, checks = deploy_and_test_device(name, host, port, user, pwd)
        summary[name] = {'results': res, 'checks': checks}
    print('\n' + '='*60)
    print('SUMMARY')
    for name, info in summary.items():
        print('\nDevice:', name)
        for pkg_result in info['results']:
            print('PKG:', pkg_result[0], 'RC:', pkg_result[1])
        print('--- checks ---')
        for k, v in info['checks'].items():
            print('CHECK:', k)
            print(v[:1000])

if __name__ == '__main__':
    main()
