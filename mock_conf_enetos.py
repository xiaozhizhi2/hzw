# -*- coding: utf-8 -*-
import json
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

    # read remote ping_conf.json
    remote_conf = "/opt/cbc/ipm/etc/ping_conf.json"
    exec_cmd(ssh, "sudo cp {0} {0}.bak_connection_down".format(remote_conf))
    with sftp.open(remote_conf, "r") as f:
        conf = json.loads(f.read().decode("utf-8"))

    # backup current targets, modify first target for mock
    target = conf["targets"][0]
    target["is_check_connection_down"] = True
    target["check_connection_down_threshold"] = 10
    target["report_interval"] = 60
    target["count"] = 5
    target["request_interval"] = 1000
    print("mock target: {0}".format(json.dumps(target, indent=2)))

    with sftp.open("/tmp/ping_conf_mock.json", "w") as f:
        f.write(json.dumps(conf, indent=2))
    exec_cmd(ssh, "sudo cp /tmp/ping_conf_mock.json {0}".format(remote_conf))

    # verify
    exec_cmd(ssh, "sudo cat {0} | head -60".format(remote_conf))
    ssh.close()


if __name__ == "__main__":
    main()
