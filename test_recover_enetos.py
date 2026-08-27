# -*- coding: utf-8 -*-
import json
import time
import paramiko

HOST = "172.17.9.42"
PORT = 6188
USER = "cbcadmin"
PWD = "X98kgF2pwW"


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

    # keep target unreachable (10.255.255.254), raise threshold to 200 so 100% < 200 -> OK
    with sftp.open("/opt/cbc/ipm/etc/ping_conf.json", "r") as f:
        conf = json.loads(f.read().decode("utf-8"))
    conf["targets"][0]["target_address"] = "10.255.255.254"
    conf["targets"][0]["check_connection_down_threshold"] = 200
    with sftp.open("/tmp/ping_conf_mock.json", "w") as f:
        f.write(json.dumps(conf, indent=2))
    exec_cmd(ssh, "sudo cp /tmp/ping_conf_mock.json /opt/cbc/ipm/etc/ping_conf.json")
    print("===== threshold raised to 200, waiting for OK (recover) cycle =====")
    deadline = time.time() + 90
    while time.time() < deadline:
        time.sleep(20)
        exec_cmd(ssh, "date")
        out = exec_cmd(ssh, "sudo grep 'connection.down' /root/cbc/agent/agent/cache/event_push.log 2>&1 | tail -3")
        if '"status": "OK"' in out:
            print("RECOVER PUSHED")
            break
    exec_cmd(ssh, "sudo cat /opt/cbc/ipm/cache/event_used_data_cache.json 2>&1")
    ssh.close()


if __name__ == "__main__":
    main()
