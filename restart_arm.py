# -*- coding: utf-8 -*-
import paramiko

HOST = '172.17.8.148'
PORT = 6188
USER = 'cbcadmin'
PWD = 'XPCCncn99d'


def run(cmd, timeout=90):
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
    # 校验上传的文件是否完整（行数对比本地）
    rc, out, err = run('wc -l /opt/cbc/ipm/bin/fping.py')
    print('remote wc: {0}'.format(out.strip()))
    # 语法检查
    rc, out, err = run('python -m py_compile /opt/cbc/ipm/bin/fping.py && echo SYNTAX_OK')
    print('py_compile rc={0} out={1} err={2}'.format(rc, out.strip(), err.strip()))
    # 确认配置
    rc, out, err = run('python -c "import json;c=json.load(open(\'/etc/cbc/ipm/ping_conf.json\'));[print(t[\'target_address\'], t.get(\'is_check_connection_down\'), t.get(\'check_connection_down_threshold\')) for t in c[\'targets\']]"')
    print('conf check: {0}'.format(out))
    if err:
        print('ERR: {0}'.format(err))
    # 重启
    rc, out, err = run('echo "{0}" | sudo -S sh -c "cd /opt/cbc/ipm/bin && python ipm.py restart"'.format(PWD))
    print('restart rc={0} out={1} err={2}'.format(rc, out.strip(), err.strip()))
    import time
    time.sleep(8)
    rc, out, err = run('ps w | grep -E "fping.py|ipm.py restart" | grep -v grep')
    print('process: {0}'.format(out))


if __name__ == '__main__':
    main()
