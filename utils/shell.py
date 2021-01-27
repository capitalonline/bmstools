import subprocess

import logging
import os

logger = logging.getLogger(__name__)


class ShellCmd(object):

    def __init__(self, cmd, workdir=None, logcmd=True):
        self.cmd = cmd
        self.logcmd = logcmd
        self.workdir = workdir
        self.stdout = None
        self.stderr = None
        self.return_code = None

    def debug_error(self):
        err = ['failed to execute shell command: %s' % self.cmd,
               'return code: %s' % self.process.returncode,
               'stdout: %s' % self.stdout,
               'stderr: %s' % self.stderr]
        message = '\n'.join(err)
        logger.debug('execute error %s' % message)

    def __call__(self, is_exception=True, timeout=5):

        self.process = subprocess.Popen(
            self.cmd, bufsize=10000,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            close_fds=True, executable='/bin/bash',
            cwd=self.workdir)

        (self.stdout, self.stderr) = self.process.communicate()
        if self.logcmd:
            logger.debug(self.cmd)
            if self.process.returncode != 0:
                logger.debug('command return error result : %s' % self.stderr)
            else:
                logger.debug('command return ok result : %s' % self.stdout)

        self.return_code = self.process.returncode

        if self.process.stdout:
            self.process.stdout.close()
        if self.process.stderr:
            self.process.stderr.close()
        if self.process.stdin:
            self.process.stdin.close()
        if self.return_code != 0:
            self.debug_error()
        try:
            self.process.kill()
        except OSError:
            pass
        return self


def call(cmd, exception=True, workdir=None, logcmd=True):
    return ShellCmd(cmd, workdir, logcmd=logcmd)(exception)


def run(cmd, workdir=None):
    s = ShellCmd(cmd, workdir)
    s(False)
    return s.return_code

def prepare_pid_dir(path):
    pdir = os.path.dirname(path)
    if not os.path.isdir(pdir):
        os.makedirs(pdir)
