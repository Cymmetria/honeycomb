# -*- coding: utf-8 -*-
"""Honeycomb Service Manager Exceptions."""

from __future__ import unicode_literals, absolute_import

import honeycomb.exceptions
from honeycomb.servicemanager import error_messages


class ServiceManagerException(honeycomb.exceptions.PluginError):
    """Generic Service Manager Exception."""


class ServiceNotFound(ServiceManagerException):
    """Specified service does not exist."""

    msg_format = error_messages.SERVICE_NOT_FOUND_ERROR


class UnsupportedOS(ServiceManagerException):
    """Specified service does not exist."""

    msg_format = error_messages.UNSUPPORTED_OS_ERROR
