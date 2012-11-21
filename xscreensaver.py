#!/usr/bin/env python

import sys, os, time, atexit, signal
import subprocess, copy, re, os.path

class Daemon(object):
    """A generic daemon class.
    Usage: subclass the daemon class and override the run() method."""

    def __init__(self, pidfile):
        self.pidfile = pidfile

    def daemonize(self):
        """Deamonize class. UNIX double fork mechanism."""

        try:
            pid = os.fork()
            if pid > 0:
                # exit first parent
                sys.exit(0)
        except OSError as err:
            sys.stderr.write('fork #1 failed: {0}\n'.format(err))
            sys.exit(1)

        # decouple from parent environment
        os.chdir('/')
        os.setsid()
        os.umask(0)

        # do second fork
        try:
            pid = os.fork()
            if pid > 0:
                # exit from second parent
                sys.exit(0)
        except OSError as err:
            sys.stderr.write('fork #2 failed: {0}\n'.format(err))
            sys.exit(1)

        # redirect standard file descriptors
        sys.stdout.flush()
        sys.stderr.flush()
        si = open(os.devnull, 'r')
        so = open(os.devnull, 'a+')
        se = open(os.devnull, 'a+')

        os.dup2(si.fileno(), sys.stdin.fileno())
        os.dup2(so.fileno(), sys.stdout.fileno())
        os.dup2(se.fileno(), sys.stderr.fileno())

        # write pidfile
        atexit.register(self.delpid)

        pid = str(os.getpid())
        with open(self.pidfile,'w+') as f:
            f.write(pid + '\n')

    def delpid(self):
        os.remove(self.pidfile)

    def start(self):
        """Start the daemon."""

        # Check for a pidfile to see if the daemon already runs
        try:
            with open(self.pidfile,'r') as pf:
                pid = int(pf.read().strip())
        except IOError:
            pid = None

        if pid:
            message = "pidfile {0} already exist. " + \
                "Daemon already running?\n"
            sys.stderr.write(message.format(self.pidfile))
            sys.exit(1)

        # Start the daemon
        self.daemonize()
        self.run()

    def stop(self):
        """Stop the daemon."""

        # Get the pid from the pidfile
        try:
            with open(self.pidfile,'r') as pf:
                pid = int(pf.read().strip())
        except IOError:
            pid = None

        if not pid:
            message = "pidfile {0} does not exist. " + \
                "Daemon not running?\n"
            sys.stderr.write(message.format(self.pidfile))
            return # not an error in a restart

        # Try killing the daemon process
        try:
            while 1:
                os.kill(pid, signal.SIGTERM)
                time.sleep(0.1)
        except OSError as err:
            e = str(err.args)
            if e.find("No such process") > 0:
                if os.path.exists(self.pidfile):
                    os.remove(self.pidfile)
            else:
                print (str(err.args))
                sys.exit(1)

    def restart(self):
        """Restart the daemon."""
        self.stop()
        self.start()

    def run(self):
        """You should override this method when you subclass Daemon.

        It will be called after the process has been daemonized by
        start() or restart()."""


class XLocker(Daemon):
    def start(self):
        if os.path.exists(self.pidfile):
            print("Daemon is still alive! Otherwise try to delete file '%s'" % self.pidfile)
            sys.exit(0)
        self.Xscreensaver = subprocess.Popen(['xscreensaver'])
        self.Xscreencmd = subprocess.Popen(['xscreensaver-command', '-watch'], stdout=subprocess.PIPE)
        self.OriginMap = self.scan_fkeys()[1]
        self.LockMap = [i[:2] + self.OriginMap[6][2:] for i in self.OriginMap]

        ret = super(XLocker, self).start()
        if not ret:
            self.Xscreensaver.terminate()
            self.Xscreencmd.terminate()

        return ret


    def scan_fkeys(self):
        map = subprocess.getoutput(r'xmodmap -pke')
        aro = [i.split() for i in re.compile(r'^(.+=\sF\d+\s.+)$', re.M).findall(map)]

        return map, aro


    def switch_xmodmap(self, aro, encoding):
        p = subprocess.Popen(['xmodmap', '-'], stdin=subprocess.PIPE)
        p.communicate(input='\n'.join([' '.join(i) for i in aro]).encode(encoding))


    def run(self):
        signal.signal(signal.SIGTERM, self.halt)

        while True:
            try:
                line = self.Xscreencmd.stdout.readline()
                print(line)
                if line.startswith(b'LOCK'):
                    self.switch_xmodmap(self.LockMap, 'utf8')
                elif line.startswith(b'UNBLANK'):
                    self.switch_xmodmap(self.OriginMap, 'utf8')
            except:
                break

    def halt(self, signum, frame):
        self.Xscreensaver.terminate()
        self.Xscreencmd.terminate()
        return True

if __name__ == "__main__":
    if len(sys.argv) >= 2:
        if len(sys.argv) == 3:
            daemon = XLocker(sys.argv[2])
        else:
            daemon = XLocker(os.path.expanduser('~/.xscreensaver.py.pid'))
        if 'start' == sys.argv[1]:
            daemon.start()
        elif 'stop' == sys.argv[1]:
            daemon.stop()
        elif 'restart' == sys.argv[1]:
            daemon.restart()
        else:
            print("Unknown command")
            sys.exit(2)
        sys.exit(0)
    else:
        print("usage: %s start|stop|restart" % sys.argv[0])
        sys.exit(2)