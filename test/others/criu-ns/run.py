#!/usr/bin/env python

import os
import pty
import shutil
import subprocess
import sys
import time
import fcntl, termios

CRIU_BIN = "../../../criu/criu"
CRIU_NS = "../../../scripts/criu-ns"

os.chdir(os.getcwd())

def check_dumpdir():
    if os.path.isdir("dumpdir"):
        shutil.rmtree("dumpdir")
    os.mkdir("dumpdir", 0o755)


def create_pty():
    fd_m, fd_s = pty.openpty()
    return (os.fdopen(fd_m, "wb"), os.fdopen(fd_s, "wb"))


def test_dump_and_restore_with_shell_job():
    check_dumpdir()

    open("running", "w").close()
    m, s = create_pty()
    p = os.pipe()
    pr = os.fdopen(p[0], "r")
    pw = os.fdopen(p[1], "w")

    pid = os.fork()
    if pid == 0:
        m.close()
        os.setsid()
        os.dup2(s.fileno(), 0)
        os.dup2(s.fileno(), 1)
        os.dup2(s.fileno(), 2)
        fcntl.ioctl(s.fileno(), termios.TIOCSCTTY, 1)
        pr.close()
        pw.close()
        while True:
            if not os.access("running", os.F_OK):
                sys.exit(0)
            time.sleep(1)
        sys.exit(1)

    pw.close()
    pr.read(1)
    cmd = [CRIU_NS, "dump", "-D", "dumpdir", "-v", "--shell-job",
           "-t", str(pid), "--criu-binary", CRIU_BIN]
    ret = subprocess.Popen(cmd).wait()
    if ret != 0:
        sys.exit(ret)

    os.unlink("running")
    fd_m, fd_s = create_pty()
    pid = os.fork()
    if pid == 0:
        os.setsid()
        fcntl.ioctl(fd_m.fileno(), termios.TIOCSCTTY, 1)
        cmd = [CRIU_NS, "restore", "-D", "dumpdir", "-v",
               "--shell-job", "--criu-binary", CRIU_BIN]
        ret = subprocess.Popen(cmd).wait()
        if ret != 0:
            sys.exit(ret)
        os._exit(0)

    os.waitpid(pid, 0)


def test_dump_and_restore_without_shell_job(restore_detached=False):
    check_dumpdir()

    open("running", "w").close()
    fd_m, fd_s = create_pty()
    pid = os.fork()
    if pid == 0:
        os.setsid()
        os.dup2(fd_s.fileno(), 0)
        os.dup2(fd_s.fileno(), 1)
        os.dup2(fd_s.fileno(), 2)
        while True:
            if not os.access("running", os.F_OK):
                sys.exit(0)
            time.sleep(1)

    cmd = [CRIU_NS, "dump", "-D", "dumpdir", "-v", "-t", str(pid),
           "--criu-binary", CRIU_BIN]
    ret = subprocess.Popen(cmd).wait()
    if ret != 0:
        sys.exit(ret)

    os.unlink("running")
    fd_m, fd_s = create_pty()
    pid = os.fork()
    if pid == 0:
        if restore_detached:
            cmd = [CRIU_NS, "restore", "-D", "dumpdir", "-v",
                   "--restore-detached", "--criu-binary",
                   CRIU_BIN]
        else:
            cmd = [CRIU_NS, "restore", "-D", "dumpdir", "-v",
                   "--criu-binary", CRIU_BIN]

        ret = subprocess.Popen(cmd, start_new_session=True).wait()
        if ret != 0:
            sys.exit(ret)
        os._exit(0)

    os.waitpid(pid, 0)


if __name__ == "__main__":
    test_dump_and_restore_with_shell_job()
    #test_dump_and_restore_without_shell_job()
    #test_dump_and_restore_without_shell_job(restore_detached=True)
    sys.exit(0)
