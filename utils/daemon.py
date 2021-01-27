#!/usr/bin/env python

import sys
import os
import time
import traceback

import logging

import shell
import signal

logger = logging.getLogger(__name__)


class Daemon(object):
    """
    A generic daemon class.

    Usage: subclass the Daemon class and override the run() method
    """
    atexit_hooks = []

    def __init__(self, pidfile,
                 stdin='/dev/null',
                 stdout='/dev/null',
                 stderr='/dev/null'):
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self.pidfile = pidfile

    def delpid(self):
        if os.path.exists(self.pidfile):
            os.remove(self.pidfile)

    def get_pid(self):
        pid = None
        pid_context = None
        if os.path.exists(self.pidfile):
            with open(self.pidfile, 'r') as fp:
                pid_context = fp.readline()
        if pid_context:
            pid = int(pid_context.strip())
        return pid

    def start(self):
        """
        Start the daemon
        """
        logger.info("Start Daemon...")
        # Check for a pidfile to see if the daemon already runs
        pid = self.get_pid()
        logger.debug('pidfile is %s' % os.getpid())
        if pid:
            pscmd = shell.call('ps -p %s > /dev/null' % pid)
            if pscmd.return_code == 0:
                message = "Daemon already running, pid is %s\n"
                sys.stderr.write(message % pid)
                sys.exit(0)

        logger.info('current pid :%s' % os.getpid())
        with open(self.pidfile, 'w') as f:
            f.write('%s' % os.getpid())
        try:
            self.run()
        except Exception:
            content = traceback.format_exc()
            logger.error(content)
            sys.exit(1)
        logger.info("Start Daemon Successfully")

    def stop(self):
        """
        Stop the daemon
        """
        # wait 2s for gracefully shutdown, then will force kill
        logger.debug("Stop Daemon...")
        wait_stop = 2

        # Get the pid from the pidfile
        pid = self.get_pid()
        logger.info('pid %s will be killed' % os.getpid())

        # not an error in a restart
        if not pid:
            message = "pidfile %s does not exist. Daemon not running?\n"
            sys.stderr.write(message % self.pidfile)
            return

        # Try killing the daemon process
        start_time = time.time()
        while True:
            if os.path.exists('/proc/' + str(pid)):
                curr_time = time.time()
                if (curr_time - start_time) > wait_stop:
                    os.kill(pid, signal.SIGINT)
                else:
                    os.kill(pid, signal.SIGTERM)
                time.sleep(0.3)
            else:
                self.delpid()
                break
        logger.info("Stop Daemon Successfully")

    def restart(self):
        """
        Restart the daemon
        """
        self.stop()
        self.start()

    def run(self):
        """
        You should override this method when you subclass Daemon.
        It will be called after the process has been
        daemonized by start() or restart().
        """
