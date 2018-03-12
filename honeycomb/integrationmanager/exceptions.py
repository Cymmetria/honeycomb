# -*- coding: utf-8 -*-
"""Honeycomb Output Integration Exceptions."""

from __future__ import unicode_literals, absolute_import

from honeycomb.exceptions import PluginError
from honeycomb.integrationmanager import error_messages


class IntegrationSendEventError(PluginError):
    """IntegrationSendEventError."""

    msg_format = error_messages.INTEGRATION_SEND_EVENT_ERROR


class IntegrationMissingRequiredFieldError(PluginError):
    """IntegrationMissingRequiredFieldError."""


class IntegrationPollEventError(PluginError):
    """IntegrationPollEventError."""


class IntegrationOutputFormatError(PluginError):
    """IntegrationOutputFormatError."""


class IntegrationPackageError(PluginError):
    """IntegrationPackageError."""


class IntegrationNoMethodImplementationError(PluginError):
    """IntegrationNoMethodImplementationError."""


class IntegrationNotFound(PluginError):
    """Integration not found."""

    msg_format = error_messages.INTEGRATION_NOT_FOUND_ERROR


class IntegrationTestFailed(PluginError):
    """Integration not found."""

    msg_format = error_messages.INTEGRATION_TEST_FAILED
