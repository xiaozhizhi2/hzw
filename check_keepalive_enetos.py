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
        "sudo cat /opt/cbc/ipm/bin/ipm_keepalive.sh 2>&1",
        "sudo crontab -l 2>&1; echo ---; sudo cat /etc/crontab 2>&1; echo ---; ls /etc/cron.d/ 2>&1",
        "sudo systemctl list-units | grep -i ipm 2>&1; echo ---; sudo ps -ef | grep -i ipm | grep -v grep",
        "sudo cat /opt/cbc/ipm/etc/agent.conf 2>&1",
        "sudo cat /opt/cbc/ipm/bin/ipm.py 2>&1 | head -80",
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
