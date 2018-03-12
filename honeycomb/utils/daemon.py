# -*- coding: utf-8 -*-
"""Honeycomb DaemonRunner utility."""

from __future__ import unicode_literals, absolute_import

import sys

import daemon.runner
import daemon.daemon


class myRunner(daemon.runner.DaemonRunner):
    """Overriding default runner behaviour to be simpler."""

    def __init__(self, app, pidfile=None, stdout=sys.stdout, stderr=sys.stderr, stdin=open("/dev/null", "rt")):
        """
        Override init to fit honeycomb needs.

        We initialize app with default stdout/stderr from sys instead of file path
        and remove the use of parse_args() since it's not actually a standalone runner
        """
        self.app = app
        self.daemon_context = daemon.daemon.DaemonContext()
        self.daemon_context.stdin = stdin
        self.daemon_context.stdout = stdout
        self.daemon_context.stderr = stderr
        self.app.pidfile_path = pidfile
        self.pidfile = None
        if self.app.pidfile_path is not None:
            self.pidfile = daemon.runner.make_pidlockfile(self.app.pidfile_path, 3)
        self.daemon_context.pidfile = self.pidfile
