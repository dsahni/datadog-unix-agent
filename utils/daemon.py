# Unless explicitly stated otherwise all files in this repository are licensed
# under the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2018 Datadog, Inc.
#
# This file is licensed under CreativeCommons Share-Alike 3.0 license terms

"""
    ***
    Modified generic daemon class
    ***

    Author:     http://www.jejik.com/articles/2007/02/a_simple_unix_linux_daemon_in_python/
                www.boxedice.com
                www.datadoghq.com

    License:    http://creativecommons.org/licenses/by-sa/3.0/
"""

# Core modules
import atexit
import errno
import logging
import os
import signal
import sys

# project
from .process import is_my_process

log = logging.getLogger(__name__)


class Daemon(object):
    """
    A generic daemon class.

    Usage: subclass the Daemon class and override the run() method
    """
    def __init__(self, pidfile, stdin=os.devnull, stdout=os.devnull, stderr=os.devnull):
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self.pidfile = pidfile

    def daemonize(self):
        """
        Do the UNIX double-fork magic, see Stevens' "Advanced
        Programming in the UNIX Environment" for details (ISBN 0201563177)
        http://www.erlenstar.demon.co.uk/unix/faq_2.html#SEC16
        """
        try:
            pid = os.fork()
            if pid > 0:
                # Exit first parent
                sys.exit(0)
        except OSError as e:
            msg = "fork #1 failed: %d (%s)" % (e.errno, e.strerror)
            log.error(msg)
            sys.stderr.write(msg + "\n")
            sys.exit(1)

        log.debug("Fork 1 ok")

        # Decouple from parent environment
        os.chdir("/")
        os.setsid()

        # Do second fork
        try:
            pid = os.fork()
            if pid > 0:
                # Exit from second parent
                sys.exit(0)
        except OSError as e:
            msg = "fork #2 failed: %d (%s)" % (e.errno, e.strerror)
            logging.error(msg)
            sys.stderr.write(msg + "\n")
            sys.exit(1)

        if sys.platform != 'darwin':  # This block breaks on OS X
            # Redirect standard file descriptors
            sys.stdout.flush()
            sys.stderr.flush()
            si = file(self.stdin, 'r')
            so = file(self.stdout, 'a+')
            se = file(self.stderr, 'a+', 0)
            os.dup2(si.fileno(), sys.stdin.fileno())
            os.dup2(so.fileno(), sys.stdout.fileno())
            os.dup2(se.fileno(), sys.stderr.fileno())

        log.info("Daemon started")

    def start(self, foreground=False):
        log.info("Starting...")

        pid = self.pid()

        if pid:
            # Check if the pid in the pidfile corresponds to a running process
            # and if psutil is installed, check if it's a datadog-agent one
            if is_my_process(pid):
                log.error("Not starting, another instance is already running"
                          " (using pidfile {0})".format(self.pidfile))
                sys.exit(1)
            else:
                log.warn("pidfile doesn't contain the pid of an agent process."
                         " Starting normally...")

        if not foreground:
            self.daemonize()
        self.write_pidfile()

        self.run()

    def stop(self):
        log.info("Stopping daemon")
        pid = self.pid()

        # Clear the pid file
        if os.path.exists(self.pidfile):
            os.remove(self.pidfile)

        if pid > 1:
            try:
                os.kill(pid, signal.SIGTERM)
                log.info("Daemon is stopped")
            except OSError as err:
                if str(err).find("No such process") <= 0:
                    log.exception("Cannot kill Agent daemon at pid %s" % pid)
                    sys.stderr.write(str(err) + "\n")
        else:
            message = "Pidfile %s does not exist. Not running?\n" % self.pidfile
            log.info(message)
            sys.stderr.write(message)

            # A ValueError might occur if the PID file is empty but does actually exist
            if os.path.exists(self.pidfile):
                os.remove(self.pidfile)

            return  # Not an error in a restart

    def restart(self):
        "Restart the daemon"
        self.stop()
        self.start()

    def run(self):
        """
        You should override this method when you subclass Daemon. It will be called after the process has been
        daemonized by start() or restart().
        """
        raise NotImplementedError

    @classmethod
    def info(cls):
        """
        You should override this method when you subclass Daemon. It will be
        called to provide information about the status of the process
        """
        raise NotImplementedError

    def status(self):
        """
        Get the status of the daemon. Exits with 0 if running, 1 if not.
        """
        pid = self.pid()

        if pid < 0:
            message = '%s is not running' % self.__class__.__name__
            exit_code = 1
        else:
            # Check for the existence of a process with the pid
            try:
                # os.kill(pid, 0) will raise an OSError exception if the process
                # does not exist, or if access to the process is denied (access denied will be an EPERM error).
                # If we get an OSError that isn't an EPERM error, the process
                # does not exist.
                # (from http://stackoverflow.com/questions/568271/check-if-pid-is-not-in-use-in-python,
                #  Giampaolo's answer)
                os.kill(pid, 0)
            except OSError as e:
                if e.errno != errno.EPERM:
                    message = '%s pidfile contains pid %s, but no running process could be found' % \
                        (self.__class__.__name__, pid)
                else:
                    message = 'You do not have sufficient permissions'
                exit_code = 1

            else:
                message = '%s is running with pid %s' % (self.__class__.__name__, pid)
                exit_code = 0

        log.info(message)
        sys.stdout.write(message + "\n")
        sys.exit(exit_code)

    def pid(self):
        # Get the pid from the pidfile
        try:
            pf = file(self.pidfile, 'r')
            pid = int(pf.read().strip())
            pf.close()
            return pid
        except IOError:
            return None
        except ValueError:
            return None

    def write_pidfile(self):
        # Write pidfile
        atexit.register(self.delpid)  # Make sure pid file is removed if we quit
        pid = str(os.getpid())
        try:
            fp = open(self.pidfile, 'w+')
            fp.write(str(pid))
            fp.close()
            os.chmod(self.pidfile, 0644)
        except Exception:
            msg = "Unable to write pidfile: %s" % self.pidfile
            log.exception(msg)
            sys.stderr.write(msg + "\n")
            sys.exit(1)

    def delpid(self):
        try:
            os.remove(self.pidfile)
        except OSError:
            pass
