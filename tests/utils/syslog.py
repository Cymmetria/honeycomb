# -*- coding: utf-8 -*-
"""Syslog utility for tests."""

import logging
from six.moves import socketserver

logger = logging.getLogger(__name__)


class SyslogUDPHandler(socketserver.BaseRequestHandler):
    """Syslog UDP dummy handler."""

    outputFile = None

    def handle(self):
        """Handle incoming data by logging to debug and writing to logfie."""
        data = bytes.decode(self.request[0].strip())
        logger.debug(data)
        self.outputFile.write(data)


def runSyslogServer(host, port, logfile):
    """Run a dummy syslog server.

    :param host: IP address to listen
    :param port: Port to listen
    :param logfile: File handle used to write incoming logs
    """
    handler = SyslogUDPHandler
    handler.outputFile = logfile
    syslogd = socketserver.UDPServer((host, port), handler)
    syslogd.serve_forever()
