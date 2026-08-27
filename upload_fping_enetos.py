# -*- coding: utf-8 -*-
import base64
import paramiko

HOST = "172.17.9.42"
PORT = 6188
USER = "cbcadmin"
PWD = "X98kgF2pwW"
LOCAL_FPING = r"d:\cbc\ipm-v2\ipm_agent\fping.py"


def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, port=PORT, username=USER, password=PWD, timeout=15)
    sftp = ssh.open_sftp()

    with open(LOCAL_FPING, "rb") as f:
        data = f.read()
    b64 = base64.b64encode(data).decode()

    # backup + upload fping.py
    remote = "/opt/cbc/ipm/bin/fping.py"
    cmds = [
        "sudo cp {0} {0}.bak_connection_down 2>&1".format(remote),
        "echo '{0}' | sudo python -c 'import sys,base64;sys.stdin.read()'" + "",
    ]
    # write via sftp to tmp then sudo cp
    tmp = "/tmp/fping_new.py"
    with sftp.open(tmp, "wb") as f:
        f.write(data)
    stdin, stdout, stderr = ssh.exec_command("sudo cp {0} {1} 2>&1 && sudo chmod 755 {1} 2>&1 && ls -la {1}".format(tmp, remote))
    print(stdout.read().decode("utf-8", "replace"))
    print(stderr.read().decode("utf-8", "replace"))

    # stop keepalive & ipm process
    stdin, stdout, stderr = ssh.exec_command(
        "ps -ef | grep -E 'ipm|fping' | grep -v grep 2>&1"
    )
    print("=== running procs ===")
    print(stdout.read().decode("utf-8", "replace"))

    stdin, stdout, stderr = ssh.exec_command(
        "sudo pkill -f ipm_keepalive 2>&1; sudo pkill -f fping.py 2>&1; sleep 1; ps -ef | grep -E 'ipm|fping' | grep -v grep 2>&1; echo DONE"
    )
    print("=== after kill ===")
    print(stdout.read().decode("utf-8", "replace"))
    print(stderr.read().decode("utf-8", "replace"))
    ssh.close()


if __name__ == "__main__":
    main()
