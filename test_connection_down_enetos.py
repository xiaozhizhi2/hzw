# -*- coding: utf-8 -*-
import json
import time
import paramiko

HOST = "172.17.9.42"
PORT = 6188
USER = "cbcadmin"
PWD = "X98kgF2pwW"
LOCAL_FPING = r"d:\cbc\ipm-v2\ipm_agent\fping.py"


def exec_cmd(ssh, cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    print("=== {0} ===".format(cmd))
    if out:
        print(out)
    if err:
        print("STDERR: {0}".format(err))
    return out


def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, port=PORT, username=USER, password=PWD, timeout=15)
    sftp = ssh.open_sftp()

    # upload new fping.py
    with open(LOCAL_FPING, "rb") as f:
        data = f.read()
    with sftp.open("/tmp/fping_new.py", "wb") as f:
        f.write(data)
    exec_cmd(ssh, "sudo cp /tmp/fping_new.py /opt/cbc/ipm/bin/fping.py && sudo chmod 755 /opt/cbc/ipm/bin/fping.py && sudo ls -la /opt/cbc/ipm/bin/fping.py")

    # keep target unreachable
    with sftp.open("/opt/cbc/ipm/etc/ping_conf.json", "r") as f:
        conf = json.loads(f.read().decode("utf-8"))
    conf["targets"][0]["target_address"] = "10.255.255.254"
    with sftp.open("/tmp/ping_conf_mock.json", "w") as f:
        f.write(json.dumps(conf, indent=2))
    exec_cmd(ssh, "sudo cp /tmp/ping_conf_mock.json /opt/cbc/ipm/etc/ping_conf.json")

    # reset ipm cache
    exec_cmd(ssh, "sudo rm -rf /opt/cbc/ipm/cache /tmp/fping_mock.log")

    # restart fping (kill ipm+keepalive so no auto-restart interference)
    exec_cmd(ssh, "sudo pkill -9 -f ipm_keepalive; sudo pkill -9 -f 'ipm.py'; sudo pkill -9 -f fping.py; sudo pkill -9 -f py_curl.py; sleep 2; sudo rm -f /tmp/fping.py.lock")
    exec_cmd(ssh, "sudo nohup python /opt/cbc/ipm/bin/fping.py >> /tmp/fping_mock.log 2>&1 & echo started")

    # poll for cache up to 150s
    deadline = time.time() + 150
    found = False
    while time.time() < deadline:
        time.sleep(20)
        out = exec_cmd(ssh, "sudo cat /opt/cbc/ipm/cache/event_used_data_cache.json 2>&1")
        if "last_update_time" in out:
            print("CACHE FOUND")
            found = True
            break
    if not found:
        print("NO CACHE within 150s")
    exec_cmd(ssh, "sudo tail -30 /tmp/fping_mock.log 2>&1")
    exec_cmd(ssh, "sudo grep 'connection.down' /root/cbc/agent/agent/cache/event_push.log 2>&1 | tail -10")
    ssh.close()


if __name__ == "__main__":
    main()
