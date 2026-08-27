# -*- coding: utf-8 -*-
import paramiko

HOST = "172.17.9.42"
PORT = 6188
USER = "cbcadmin"
PWD = "X98kgF2pwW"


def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, port=PORT, username=USER, password=PWD, timeout=15)
    cmds = [
        "date",
        "sudo cat /opt/cbc/ipm/cache/event_used_data_cache.json 2>&1",
        "ps -ef | grep -E 'ipm|fping' | grep -v grep",
        "sudo grep -E 'connection.down' /root/cbc/agent/agent/cache/event_push.log 2>&1 | tail -5",
    ]
    for c in cmds:
        stdin, stdout, stderr = ssh.exec_command(c)
        out = stdout.read().decode("utf-8", "replace")
        err = stderr.read().decode("utf-8", "replace")
        print("=== {0} ===".format(c))
        if out:
            print(out)
        if err:
            print("STDERR: {0}".format(err))
    ssh.close()


if __name__ == "__main__":
    main()
