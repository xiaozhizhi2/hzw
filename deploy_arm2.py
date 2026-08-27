# -*- coding: utf-8 -*-
import base64
import json
import paramiko
import time

HOST = '172.17.8.148'
PORT = 6188
USER = 'cbcadmin'
PWD = 'XPCCncn99d'

LOCAL_FPING = r'd:\cbc\arm-ipm\fping.py'
REMOTE_FPING = '/opt/cbc/ipm/bin/fping.py'
REMOTE_CONF = '/etc/cbc/ipm/ping_conf.json'
TMP_FPING = '/home/cbcadmin/fping_new.py'
TMP_CONF = '/home/cbcadmin/ping_conf_new.json'

CONF_JSON = {
    "debug": False,
    "max_size_of_log": 120,
    "gc_minute_interval": 30,
    "check_interval": 10,
    "targets_size_of_worker": 80,
    "device_id": "b2382ea2-9895-43cc-84b6-e43f51814f82",
    "path": "/usr/bin/fping",
    "targets": [
        {
            "ipm_version": "2",
            "ipm_id": "2cdce256-0fb1-431d-9815-8888a722d54b",
            "ipm_name": "IPM4cbccn-Shanghai-enetlite-chalie-To-cbccn-Shanghai-mxlTest42_U1",
            "target_address": "172.17.9.42",
            "ip_version": 4,
            "end_time": "Infinity",
            "count": 300,
            "consumer_interval": 300,
            "report_interval": 300,
            "request_interval": 1000,
            "source_address": "172.17.8.148",
            "outbound_interface": "wan0",
            "packet_size": None,
            "is_dfset": "false",
            "tos": None,
            "vrf_name": ""
        },
        {
            "ipm_version": "2",
            "ipm_id": "38b86e9f-4dd4-4794-b87d-ff50b5f740f5",
            "ipm_name": "IPM4cbccn-Shanghai-enetlite-chalie-To-cbccn-Shanghai-mxlTest42_A",
            "target_address": "182.12.3.18",
            "ip_version": 4,
            "end_time": "Infinity",
            "count": 300,
            "consumer_interval": 300,
            "report_interval": 300,
            "request_interval": 1000,
            "source_address": "182.12.3.17",
            "outbound_interface": "cbccn-Shanghai-enetlite-chalie-To-cbccn-Shanghai-mxlTest42",
            "packet_size": None,
            "is_dfset": "false",
            "tos": None,
            "vrf_name": ""
        },
        {
            "ipm_version": "2",
            "ipm_id": "5e4ae8c5-be63-41a4-acf4-f77146d3810b",
            "ipm_name": "IPM4cbccn-Shanghai-enetlite-chalie-To-cbccn-mxlTest2_A",
            "target_address": "182.12.3.14",
            "ip_version": 4,
            "end_time": "Infinity",
            "count": 300,
            "consumer_interval": 300,
            "report_interval": 300,
            "request_interval": 1000,
            "source_address": "182.12.3.13",
            "outbound_interface": "cbccn-Shanghai-enetlite-chalie-To-cbccn-mxlTest2",
            "packet_size": None,
            "is_dfset": "false",
            "tos": None,
            "vrf_name": ""
        },
        {
            "ipm_version": "2",
            "ipm_id": "f3dab435-af6c-4033-bd8b-0dc1f1c99d10",
            "ipm_name": "IPM4cbccn-Shanghai-enetlite-chalie-To-cbccn-mxlTest2_U1",
            "target_address": "3.3.3.114",
            "ip_version": 4,
            "end_time": "Infinity",
            "count": 300,
            "consumer_interval": 300,
            "report_interval": 300,
            "request_interval": 1000,
            "source_address": "172.17.8.148",
            "outbound_interface": "wan0",
            "packet_size": None,
            "is_dfset": "false",
            "tos": None,
            "vrf_name": "",
            "is_check_connection_down": True,
            "check_connection_down_threshold": 10
        }
    ]
}


def get_ssh():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, port=PORT, username=USER, password=PWD, timeout=15)
    return ssh


def run(cmd, timeout=60, sudo=False):
    ssh = get_ssh()
    if sudo:
        cmd = 'echo "{0}" | sudo -S {1}'.format(PWD, cmd)
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', 'ignore')
    err = stderr.read().decode('utf-8', 'ignore')
    rc = stdout.channel.recv_exit_status()
    ssh.close()
    return rc, out, err


def write_tmp_via_python(remote_path, content, chunk_size=2000):
    """分块写入 /tmp（无 sudo，python base64 解码），返回 0 表示成功"""
    b64 = base64.b64encode(content).decode()
    chunks = [b64[i:i + chunk_size] for i in range(0, len(b64), chunk_size)]
    ssh = get_ssh()
    try:
        # 清空
        stdin, stdout, stderr = ssh.exec_command('> {0}'.format(remote_path), timeout=30)
        stdout.channel.recv_exit_status()
        for chunk in chunks:
            # echo <b64> | python -c "写文件"
            cmd = (
                'echo {0} | python -c "import sys,base64;'
                'data=base64.b64decode(sys.stdin.read().strip());'
                'f=open(sys.argv[1],\'ab\');f.write(data);f.close()" {1}'
            ).format(chunk, remote_path)
            stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
            rc = stdout.channel.recv_exit_status()
            if rc != 0:
                err = stderr.read().decode('utf-8', 'ignore')
                print('chunk write fail rc={0} err={1}'.format(rc, err))
                return 1
        return 0
    except Exception as e:
        print('write_tmp error: {0}'.format(e))
        return 1
    finally:
        ssh.close()


def main():
    # 1. 写 fping.py 到 /tmp，再 sudo cp
    with open(LOCAL_FPING, 'rb') as f:
        content = f.read()
    rc = write_tmp_via_python(TMP_FPING, content)
    print('write tmp fping rc={0}'.format(rc))
    rc, out, err = run('wc -c {0}'.format(TMP_FPING))
    print('tmp fping size: {0}'.format(out.strip()))
    rc, out, err = run('cp {0} {1} && chmod 755 {1} && echo COPY_OK'.format(TMP_FPING, REMOTE_FPING), sudo=True)
    print('sudo cp fping rc={0} out={1} err={2}'.format(rc, out.strip(), err.strip()))

    # 2. 写 ping_conf.json
    conf_bytes = json.dumps(CONF_JSON, indent=2, ensure_ascii=False).encode('utf-8')
    rc = write_tmp_via_python(TMP_CONF, conf_bytes)
    print('write tmp conf rc={0}'.format(rc))
    rc, out, err = run('cp {0} {1} && chmod 644 {1} && echo COPY_OK'.format(TMP_CONF, REMOTE_CONF), sudo=True)
    print('sudo cp conf rc={0} out={1} err={2}'.format(rc, out.strip(), err.strip()))

    # 3. 校验
    rc, out, err = run('wc -c {0}'.format(REMOTE_FPING))
    print('remote fping size: {0}'.format(out.strip()))
    rc, out, err = run('python -c "import ast;ast.parse(open(\'/opt/cbc/ipm/bin/fping.py\').read());print(\'SYNTAX_OK\')"')
    print('syntax rc={0} out={1} err={2}'.format(rc, out.strip(), err.strip()))
    rc, out, err = run('python -c "import json;c=json.load(open(\'/etc/cbc/ipm/ping_conf.json\'));print(len(c[\'targets\']))"')
    print('conf targets count: {0}'.format(out.strip()))
    if err:
        print('conf ERR: {0}'.format(err.strip()))

    # 4. 重启
    rc, out, err = run('sh -c "cd /opt/cbc/ipm/bin && python ipm.py restart"', timeout=90, sudo=True)
    print('restart rc={0} out={1} err={2}'.format(rc, out.strip(), err.strip()))
    time.sleep(10)
    rc, out, err = run('ps w | grep -E "fping.py|ipm.py" | grep -v grep')
    print('process: {0}'.format(out))


if __name__ == '__main__':
    main()
