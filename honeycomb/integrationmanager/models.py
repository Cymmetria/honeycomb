# -*- coding: utf-8 -*-
"""Honeycomb integration models."""
from __future__ import unicode_literals, absolute_import


from datetime import datetime, timedelta

from attr import attrs, attrib, Factory

from honeycomb.decoymanager.models import Alert


@attrs
class Integration(object):
    """Integration model."""

    parameters = attrib(type=str)
    display_name = attrib(type=str)
    required_fields = attrib(type=list)
    polling_enabled = attrib(type=bool)
    integration_type = attrib(type=str)
    max_send_retries = attrib(type=int)
    supported_event_types = attrib(type=list)
    test_connection_enabled = attrib(type=bool)

    module = attrib(default=None)
    description = attrib(type=str, default=None)
    polling_duration = attrib(type=timedelta, default=0)

    # TODO: Fix schema differences between custom service and integration config.json
    name = attrib(type=str, init=False, default=Factory(lambda self: self.display_name.lower().replace(" ", "_"),
                                                        takes_self=True))
    label = attrib(type=str, init=False, default=Factory(lambda self: self.description, takes_self=True))


@attrs
class ConfiguredIntegration(object):
    """Configured integration model."""

    name = attrib(type=str)
    path = attrib(type=str)
    integration = attrib(type=Integration)

    data = attrib(type=str, init=False)
    send_muted = attrib(type=bool, default=False)
    created_at = attrib(type=datetime, default=Factory(datetime.now))

    # status = attrib(type=str, init=False)
    # configuring = attrib(type=bool, default=False)


@attrs
class IntegrationAlert(object):
    """Integration alert model."""

    alert = attrib(type=Alert)
    status = attrib(type=str)
    retries = attrib(type=int)
    configured_integration = attrib(type=ConfiguredIntegration)

    send_time = attrib(type=datetime, init=False)
    output_data = attrib(type=str, init=False)
