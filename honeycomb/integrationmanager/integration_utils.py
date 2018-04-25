# -*- coding: utf-8 -*-
"""Honeycomb Integration Manager."""

from __future__ import unicode_literals, absolute_import

import logging
from abc import ABCMeta, abstractmethod

from honeycomb.integrationmanager.exceptions import IntegrationNoMethodImplementationError

logger = logging.getLogger(__name__)


class BaseIntegration(object):
    """Base Output Integration Class.

    Will be overridden by output plugins.
    """

    __metaclass__ = ABCMeta

    def __init__(self, integration_data):
        """__init__."""
        self.integration_data = integration_data
        self.logger = logging.getLogger(__name__)

    @abstractmethod
    def send_event(self, required_alert_fields):
        """Send event."""
        pass

    @abstractmethod
    def format_output_data(self, output_data):
        """format_output_data."""
        pass

    def test_connection(self, data):
        """test_connection."""
        raise IntegrationNoMethodImplementationError()

    def poll_for_updates(self, integration_output_data):
        """poll_for_updates."""
        raise IntegrationNoMethodImplementationError()
