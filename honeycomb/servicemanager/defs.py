# -*- coding: utf-8 -*-
"""Honeycomb services definitions and constants."""

from __future__ import unicode_literals, absolute_import

import six

from honeycomb.defs import (ConfigField, NAME, LABEL, DEFAULT, VALUE,
                            TYPE, FIELD_LABEL, HELP_TEXT, REQUIRED, TEXT_TYPE, INTEGER_TYPE, BOOLEAN_TYPE, FILE_TYPE)
from honeycomb.utils import config_utils
from honeycomb.error_messages import FIELD_MISSING, CONFIG_FIELD_TYPE_ERROR
from honeycomb.decoymanager.models import Alert
from honeycomb.servicemanager.models import OSFamilies

EVENT_TYPE = "event_type"
SERVICE_CONFIG_SECTION_KEY = "service"
ALERT_CONFIG_SECTION_KEY = "event_types"
SERVICE_ALERT_QUEUE_SIZE = 1000

LOGS_DIR = "logs"
STDOUTLOG = "stdout.log"
STDERRLOG = "stderr.log"

"""Service section."""
PORT = "port"
PORTS = "ports"
FIELDS = "fields"
POLICY = "policy"
WILDCARD_PORT = "*"
PROTOCOL = "protocol"
ALLOW_MANY = "allow_many"
ALERT_TYPES = "alert_types"
CONFLICTS_WITH = "conflicts_with"
SUPPORTED_OS_FAMILIES = "supported_os_families"

TCP = "TCP"
UDP = "UDP"
ALLOWED_PROTOCOLS = [TCP, UDP]


"""Parameters."""
SERVICE_ALLOWED_PARAMTER_KEYS = [VALUE, DEFAULT, TYPE, FIELD_LABEL, HELP_TEXT, REQUIRED]
SERVICE_ALLOWED_PARAMTER_TYPES = [TEXT_TYPE, INTEGER_TYPE, BOOLEAN_TYPE, FILE_TYPE]

SERVICE_FIELDS_TO_CREATE_OBJECT = [NAME, PORTS, LABEL, ALLOW_MANY, ALERT_TYPES, SUPPORTED_OS_FAMILIES]


SERVICE_ALERT_VALIDATE_FIELDS = {
    SERVICE_CONFIG_SECTION_KEY: ConfigField(
        lambda field: True,
        lambda: FIELD_MISSING.format(SERVICE_CONFIG_SECTION_KEY)
    ),
    ALERT_CONFIG_SECTION_KEY: ConfigField(
        lambda field: True,
        lambda: FIELD_MISSING.format(ALERT_CONFIG_SECTION_KEY)
    ),
}

SERVICE_CONFIG_VALIDATE_FIELDS = {
    ALLOW_MANY: config_utils.config_field_type(ALLOW_MANY, bool),
    SUPPORTED_OS_FAMILIES: ConfigField(
        lambda family: family in OSFamilies.all_names(),
        lambda: "Operating system family must be one of the following: {}".format(
            ",".join(OSFamilies.all_names()))
    ),
    PORTS: ConfigField(
        lambda ports: isinstance(ports, list) and all(
            [port.get(PROTOCOL, False) in ALLOWED_PROTOCOLS and
             (isinstance(port.get(PORT, False), int) or
             port.get(PORT, "") == WILDCARD_PORT) for port in ports]),
        lambda: "Ports configuration invalid, please consult docs."
    ),
    NAME: config_utils.config_field_type(NAME, six.string_types),

    LABEL: config_utils.config_field_type(LABEL, six.string_types),

    CONFLICTS_WITH: ConfigField(
        lambda conflicts_with: (isinstance(conflicts_with, list) and
                                all([isinstance(_, six.string_types) for _ in conflicts_with])),
        lambda: CONFIG_FIELD_TYPE_ERROR.format(CONFLICTS_WITH, "list of strings")
    ),

}

ALERT_CONFIG_VALIDATE_FIELDS = {
    NAME: ConfigField(
        lambda name: isinstance(name, six.string_types),
        lambda: "Alert name already used"
    ),
    LABEL: ConfigField(
        lambda label: isinstance(label, six.string_types),
        lambda: "Alert label already used"
    ),
    POLICY: ConfigField(
        lambda policy: isinstance(policy, six.string_types) and policy in [alert_status[1]
                                                                           for alert_status in Alert.ALERT_STATUS],
        lambda: "Alert policy must be one of the following: {}".format([_[1] for _ in Alert.ALERT_STATUS])
    ),
    FIELDS: ConfigField(
        lambda fields: isinstance(fields, list) and all([field in Alert.__slots__ for field in fields]),
        lambda: "Alert fields must be one of the following: {}".format([Alert.__slots___])
    ),
}
