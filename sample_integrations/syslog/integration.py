# -*- coding: utf-8 -*-
"""Honeycomb Syslog integration."""
from __future__ import unicode_literals, absolute_import

import ssl
import socket
import logging.handlers

import six
import certifi
from cefevent import CEFEvent
from attr import attrs, attrib

from honeycomb import __version__
from decoymanager.models import Alert
from integrationmanager.exceptions import IntegrationSendEventError
from integrationmanager.integration_utils import BaseIntegration


@attrs
class CEFField(object):
    """Generic CEF Field."""

    field_name = attrib(type=str)


@attrs
class CEFCustomString(CEFField):
    """Custom CEF Field."""

    field_label = attrib(type=str)
    field_label_text = attrib(type=str)


cef_dict = {
    "id": CEFField("externalId"),
    "timestamp": CEFField("start"),
    "event_type": CEFField("act"),
    "alert_type": CEFField("app"),
    "event_description": CEFField("msg"),

    "request": CEFField("request"),
    "dest_ip": CEFField("dst"),
    "dest_port": CEFField("dpt"),
    "originating_ip": CEFField("src"),
    "originating_port": CEFField("spt"),
    "transport_protocol": CEFField("proto"),
    "originating_hostname": CEFField("shost"),
    "originating_mac_address": CEFField("smac"),

    "manufacturer": CEFField("sourceServiceName"),

    "domain": CEFField("deviceDnsDomain"),
    "username": CEFField("duser"),
    "password": CEFField("dpassword"),

    "image_path": CEFField("filePath"),
    "image_sha256": CEFField("fileHash"),
    "file_accessed": CEFField("filePath"),

    "cmd": CEFField("destinationServiceName"),
    "pid": CEFField("spid"),
    "uid": CEFField("duid"),
    "MD5": CEFCustomString("cs1", "cs1Label", "MD5"),
    "ppid": CEFCustomString("cs2", "cs2Label", "PPID"),

    # Extra fields:
    "additional_fields": CEFCustomString("cs4", "cs4Label", "Additional Fields"),
}


class SyslogIntegration(BaseIntegration):
    """Honeycomb Syslog integration."""

    def get_formatted_alert_as_cef(self, result_fields):
        """Format message as CEFEvent."""
        cef_event = CEFEvent()
        timestamp = result_fields['timestamp'].isoformat() if result_fields['timestamp'] else None
        hostname = socket.getfqdn()
        for field_name, field_value in [("deviceVendor", "Cymmetria"),
                                        ("deviceProduct", "Honeycomb"),
                                        ("deviceVersion", six.text_type(__version__))]:
            cef_event.set_field(field_name, field_value)

        result = None

        for field_name, field_value in six.iteritems(result_fields):
            if field_name not in cef_dict:
                continue

            cef_field_name = cef_dict[field_name].field_name
            if isinstance(cef_field_name, CEFCustomString):
                result = cef_event.set_field(
                    six.text_type(cef_field_name.field_name), six.text_type(field_value))
                cef_event.set_field(
                    six.text_type(cef_field_name.field_label), six.text_type(cef_field_name.field_label_text))
            else:
                result = cef_event.set_field(
                    six.text_type(cef_field_name), six.text_type(field_value))

            if not result:
                self.logger.warning("cef field {} didn't defined well to cef to alert_id {}".format(
                    field_name, result_fields['id']))

        entry = "{timestamp} {host} {cef_message}".format(
            timestamp=timestamp,
            host=hostname,
            cef_message=cef_event.build_cef())

        return entry

    def get_formatted_alert_as_syslog(self, result_fields):
        """Convert alert to syslog record."""
        timestamp = result_fields['timestamp'].isoformat() if result_fields['timestamp'] else None
        application = "Honeycomb"
        hostname = socket.getfqdn()
        data = ' '.join(['{}="{}"'.format(x, result_fields[x])
                         for x in six.iterkeys(result_fields)])

        syslog_entry = "{timestamp} {host} {application}: {data}".format(
            timestamp=timestamp,
            host=hostname,
            application=application,
            data=data
        )

        return syslog_entry

    def send_event(self, required_alert_fields):
        """Send syslog event."""
        logger_to_external = logging.getLogger("syslog")
        logger_to_external.setLevel(logging.DEBUG)
        logger_to_external.propagate = False

        for handler in logger_to_external.handlers[:]:
            logger_to_external.removeHandler(handler)

        protocol = self.integration_data['protocol']
        address = self.integration_data['address']
        port = self.integration_data['port']
        cef_output_format = self.integration_data['cef_output_format']
        syslog_ssl_enabled = self.integration_data['syslog_ssl_enabled']
        is_tcp = protocol == 'tcp'

        syslog_handler = MySysLogHandler(
            address=(address, port),
            socktype=socket.SOCK_STREAM if is_tcp else socket.SOCK_DGRAM,
            ssl_enabled=(is_tcp and syslog_ssl_enabled)
        )
        logger_to_external.addHandler(syslog_handler)

        try:
            message = self.get_formatted_alert_as_cef(required_alert_fields) if cef_output_format \
                else self.get_formatted_alert_as_syslog(required_alert_fields)
            is_critical = (required_alert_fields["status"] == Alert.STATUS_ALERT)

            if is_critical:
                logger_to_external.critical(message)
            else:
                logger_to_external.warning(message)

            return {}, None

        except Exception as e:
            raise IntegrationSendEventError(e)

    def format_output_data(self, output_data):
        """No special formatting required."""
        return output_data


class MySysLogHandler(logging.handlers.SysLogHandler):
    r"""Custom Syslog logging handler that includes CEFEvent.

    For some reason python SysLogHandler appends \x00 byte to every record sent,
    This fixes it and replaces it with \n.
    """

    def __init__(self,
                 address,
                 facility=logging.handlers.SysLogHandler.LOG_USER,
                 socktype=socket.SOCK_DGRAM,
                 ssl_enabled=False):
        """Code from logging.handlers.SysLogHandler."""
        logging.Handler.__init__(self)

        self.address = address
        self.facility = facility
        self.socktype = socktype
        self.ssl_enabled = ssl_enabled

        self.socket = socket.socket(socket.AF_INET, socktype)
        if socktype == socket.SOCK_STREAM and ssl_enabled:
            self.ssl_socket = ssl.wrap_socket(
                self.socket,
                ca_certs=certifi.where(),
                cert_reqs=ssl.CERT_REQUIRED)
            self.ssl_socket.connect(address)
        elif socktype == socket.SOCK_STREAM:
            self.socket.connect(address)
        self.socktype = socktype
        self.formatter = None
        self.ssl_enabled = ssl_enabled

    def close(self):
        """Close the socket."""
        if self.socket:
            self.socket.close()

    def emit(self, record):
        """
        Emit a record.

        The record is formatted, and then sent to the syslog server. If
        exception information is present, it is NOT sent to the server.
        """
        msg = self.format(record) + '\n'

        # We need to convert record level to lowercase, maybe this will
        # change in the future.

        prio = b'<%d>' % self.encodePriority(self.facility,
                                             self.mapPriority(record.levelname))
        # Message is a string. Convert to bytes as required by RFC 5424
        if type(msg) is six.text_type:
            msg = msg.encode('utf-8')
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


IntegrationActionsClass = SyslogIntegration
