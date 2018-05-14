# -*- coding: utf-8 -*-
"""Syslog utility for tests."""

import logging
import threading

from six.moves import socketserver

logger = logging.getLogger(__name__)


class SyslogUDPHandler(socketserver.BaseRequestHandler):
    """Syslog UDP dummy handler."""

    outputHandle = None

    def handle(self):
        """Handle incoming data by logging to debug and writing to logfile."""
        data = bytes.decode(self.request[0].strip())
        logger.debug(data)
        self.outputHandle.write(data)
        self.outputHandle.flush()


def runSyslogServer(host, port, logfile):
    """Run a dummy syslog server.

    :param host: IP address to listen
    :param port: Port to listen
    :param logfile: File handle used to write incoming logs
    """
    logfilehandle = open(logfile, "w+")
    handler = SyslogUDPHandler
    handler.outputHandle = logfilehandle
    syslogd = socketserver.UDPServer((host, port), handler)

    def serve():
        syslogd.serve_forever()

    thread = threading.Thread(target=serve)
    thread.start()
    return syslogd
