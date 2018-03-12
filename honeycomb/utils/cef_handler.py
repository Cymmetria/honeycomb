# -*- coding: utf-8 -*-
"""CEF Syslog Handler."""

from __future__ import unicode_literals, absolute_import

import socket
import logging
import logging.handlers
from datetime import datetime

import six
from cefevent import CEFEvent

from honeycomb import __version__
from honeycomb.defs import CEFCustomString, AlertFields

logger = logging.getLogger(__name__)


class CEFSyslogHandler(logging.handlers.SysLogHandler):
    r"""Override SysLogHandler to include CEF formatted logs and minor fixes.

    For some reason python SysLogHandler appends \x00 byte to every record sent,
    This fixes it by replacing it with \n, and implemeting CEF format
    """

    def __init__(self,
                 address,
                 facility=logging.handlers.SysLogHandler.LOG_USER,
                 socktype=socket.SOCK_DGRAM):
        """See class docstring."""
        # Copied the code from logging.handlers.SysLogHandler
        logging.Handler.__init__(self)

        self.address = address
        self.facility = facility
        self.socktype = socktype

        self.socket = socket.socket(socket.AF_INET, socktype)
        if socktype == socket.SOCK_STREAM:
            self.socket.connect(address)
        self.socktype = socktype
        self.formatter = None

    def close(self):
        """Close syslog socket on cleanup."""
        if self.socket:
            self.socket.close()

    def emit(self, record):
        """Emit a record.

        The record is formatted, and then sent to the syslog server. If
        exception information is present, it is NOT sent to the server.
        """
        msg = self.format(record) + "\n"

        # We need to convert record level to lowercase, maybe this will
        # change in the future.

        prio = b"<%d>" % self.encodePriority(self.facility,
                                             self.mapPriority(record.levelname))
        # Message is a string. Convert to bytes as required by RFC 5424
        if type(msg) is six.text_type:
            msg = msg.encode("utf-8")
        msg = prio + msg
        try:
            if self.socktype == socket.SOCK_DGRAM:
                self.socket.sendto(msg, self.address)
            else:
                if self.ssl_enabled:
                    self.ssl_socket.sendall(msg)
                else:
                    self.socket.sendall(msg)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            self.handleError(record)

    def format(self, record):
        """Format syslog string with CEF."""
        cef_event = CEFEvent()
        timestamp = datetime.fromtimestamp(record.created).isoformat() if record.created else None
        hostname = socket.getfqdn()
        for field_name, field_value in [("deviceVendor", "Honeycomb"),
                                        ("deviceProduct", "Honeycomb"),
                                        ("deviceVersion", six.text_type(__version__))]:
            cef_event.set_field(field_name, field_value)

        for field_name, field_value in six.iteritems(record.msg):
            cef_field_name = AlertFields.get_value_by_other_value("name", field_name, "cef_field_name")
            if isinstance(cef_field_name, CEFCustomString):
                result = cef_event.set_field(
                    six.text_type(cef_field_name.field_name), six.text_type(field_value))
                cef_event.set_field(
                    six.text_type(cef_field_name.field_label), six.text_type(cef_field_name.field_label_text))
            else:
                result = cef_event.set_field(
                    six.text_type(cef_field_name), six.text_type(field_value))

            if not result:
                logger.warning("cef field {} didn't defined well to cef".format(field_name))

        entry = "{timestamp} {host} {cef_message}".format(
            timestamp=timestamp,
            host=hostname,
            cef_message=cef_event.build_cef())

        return entry
