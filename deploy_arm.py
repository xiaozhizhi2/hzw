# -*- coding: utf-8 -*-
import base64
import json
import paramiko

HOST = '172.17.8.148'
PORT = 6188
USER = 'cbcadmin'
PWD = 'XPCCncn99d'

LOCAL_FPING = r'd:\cbc\arm-ipm\fping.py'
REMOTE_FPING = '/opt/cbc/ipm/bin/fping.py'
REMOTE_CONF = '/etc/cbc/ipm/ping_conf.json'


def run(cmd, timeout=60, sudo=True):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, port=PORT, username=USER, password=PWD, timeout=15)
    if sudo:
        cmd = 'echo "{0}" | sudo -S {1}'.format(PWD, cmd)
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', 'ignore')
    err = stderr.read().decode('utf-8', 'ignore')
    rc = stdout.channel.recv_exit_status()
    ssh.close()
    return rc, out, err


def write_remote_remote(remote_path, content, sudo=True, chunk_size=3000):
    """通过 base64 分块写文件，避免命令行过长"""
    b64 = base64.b64encode(content).decode()
    chunks = [b64[i:i + chunk_size] for i in range(0, len(b64), chunk_size)]
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, port=PORT, username=USER, password=PWD, timeout=15)
    try:
        # 先清空目标文件
        if sudo:
            cmd = 'echo "{0}" | sudo -S sh -c "> {1}"'.format(PWD, remote_path)
        else:
            cmd = 'sh -c "> {0}"'.format(remote_path)
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=60)
        stdout.channel.recv_exit_status()
        for i, chunk in enumerate(chunks):
            if sudo:
                cmd = 'echo "{0}" | sudo -S sh -c "echo {1} | base64 -d >> {2}"'.format(PWD, chunk, remote_path)
            else:
                cmd = 'sh -c "echo {0} | base64 -d >> {1}"'.format(chunk, remote_path)
            stdin, stdout, stderr = ssh.exec_command(cmd, timeout=60)
            stdout.channel.recv_exit_status()
        rc = 0
    except Exception as e:
        rc = 1
        print('write_remote_remote error: {0}'.format(e))
    finally:
        ssh.close()
    return rc, '', ''


def main():
    # 1. 备份
    rc, out, err = run('cp -a {0} {1}.bak_esdwan7925'.format(REMOTE_FPING, REMOTE_FPING))
    print('backup rc={0} out={1} err={2}'.format(rc, out, err))

    # 2. 上传新 fping.py
    with open(LOCAL_FPING, 'rb') as f:
        content = f.read()
    rc, out, err = write_remote_remote(REMOTE_FPING, content)
    print('upload fping.py rc={0} out={1} err={2}'.format(rc, out, err))

    # 3. 修改 ping_conf.json
    rc, out, err = run('cat {0}'.format(REMOTE_CONF))
    conf = json.loads(out)
    changed = False
    for t in conf['targets']:
        if t['target_address'] == '3.3.3.114':
            t['is_check_connection_down'] = True
            t['check_connection_down_threshold'] = 10
            changed = True
    if not changed:
        print('ERROR: target 3.3.3.114 not found')
        return
    new_conf = json.dumps(conf, indent=2, ensure_ascii=False).encode('utf-8')
    rc, out, err = write_remote_remote(REMOTE_CONF, new_conf)
    print('conf update rc={0} err={1}'.format(rc, err))
    rc, out, err = run('cat {0}'.format(REMOTE_CONF))
    print(out)

    # 4. 重启 ipm
    rc, out, err = run('cd /opt/cbc/ipm/bin && python ipm.py restart', timeout=90)
    print('restart rc={0} out={1} err={2}'.format(rc, out, err))


if __name__ == '__main__':
    main()
