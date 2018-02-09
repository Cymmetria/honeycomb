# -*- coding: utf-8 -*-

import logging
from six.moves import socketserver

logger = logging.getLogger(__name__)


class SyslogUDPHandler(socketserver.BaseRequestHandler):
    outputFile = None

    def handle(self):
        data = bytes.decode(self.request[0].strip())
        logger.debug(data)
        self.outputFile.write(data)


def runSyslogServer(HOST, PORT, logfile):
    handler = SyslogUDPHandler
    handler.outputFile = logfile
    syslogd = socketserver.UDPServer((HOST, PORT), handler)
    syslogd.serve_forever()
