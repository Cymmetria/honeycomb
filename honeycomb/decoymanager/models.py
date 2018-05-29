# -*- coding: utf-8 -*-
"""Honeycomb defs and constants."""

from __future__ import unicode_literals, absolute_import

import platform
from uuid import uuid4

from attr import attrs, attrib, validators, Factory
from datetime import datetime

from honeycomb.servicemanager.models import ServiceType


@attrs(slots=True)
class AlertType(object):
    """Alert Type."""

    name = attrib(type=str)
    label = attrib(type=str)
    service_type = attrib(type=ServiceType)


@attrs(slots=True)
class Alert(object):
    """Alert object."""

    STATUS_IGNORED = 0
    STATUS_MUTED = 1
    STATUS_ALERT = 2
    ALERT_STATUS = (
        (STATUS_IGNORED, "Ignore"),  # == Generate alert in logs but don't send to integrations
        (STATUS_MUTED, "Mute"),  # Generate alert but send only to integrations that accept muted alerts
        (STATUS_ALERT, "Alert")  # Generate alert and send to all integrations
    )

    alert_type = attrib(type=AlertType)

    id = attrib(type=str, default=Factory(uuid4))
    status = attrib(type=int, default=STATUS_ALERT, validator=validators.in_([_[0] for _ in ALERT_STATUS]))
    timestamp = attrib(type=datetime, default=Factory(datetime.now))

    event_type = attrib(init=False, type=str)
    manufacturer = attrib(init=False, type=str)
    event_description = attrib(init=False, type=str, default=Factory(lambda self: self.alert_type.label,
                                                                     takes_self=True))

    request = attrib(init=False, type=str)
    dest_ip = attrib(init=False)
    dest_port = attrib(init=False)
    file_accessed = attrib(init=False)
    originating_ip = attrib(init=False)
    originating_port = attrib(init=False)
    transport_protocol = attrib(init=False)
    originating_hostname = attrib(init=False)
    originating_mac_address = attrib(init=False)

    domain = attrib(init=False)
    username = attrib(init=False)
    password = attrib(init=False)
    image_md5 = attrib(init=False)
    image_path = attrib(init=False)
    image_file = attrib(init=False)
    image_sha256 = attrib(init=False)

    cmd = attrib(init=False)
    pid = attrib(init=False)
    uid = attrib(init=False)
    ppid = attrib(init=False)
    address = attrib(init=False)
    end_timestamp = attrib(init=False)

    # decoy (service) fields:
    decoy_os = attrib(init=False, default=Factory(platform.system))
    decoy_ipv4 = attrib(init=False)
    decoy_name = attrib(init=False)
    decoy_hostname = attrib(init=False)

    # Extra fields:
    additional_fields = attrib(init=False)
