# -*- coding: utf-8 -*-
"""Honeycomb Integration Manager."""

from __future__ import unicode_literals, absolute_import

import logging
from abc import ABCMeta, abstractmethod

from honeycomb.integrationmanager.exceptions import IntegrationNoMethodImplementationError

logger = logging.getLogger(__name__)


class BaseIntegration(object):
    """Base Output Integration Class."""

    __metaclass__ = ABCMeta

    def __init__(self, integration_data):
        """Use :func:`__init__` to set up any prerequisites needed before sending events, validate paramaters, etc.

        :param integration_data: Integration parameters
        :type integration_data: dict
        :raises IntegrationMissingRequiredFieldError: If a required field is missing.
        """
        self.integration_data = integration_data
        self.logger = logging.getLogger(__name__)

    @abstractmethod
    def send_event(self, alert_dict):
        """Send alert event to external integration.

        :param alert_dict: A dictionary with all the alert fields.
        :rtype: tuple(dict(output_data), object(output_file))
        :raises IntegrationSendEventError: If there's a problem sending the event.
        :raises IntegrationMissingRequiredFieldError: If a required field is missing.
        :return: A tuple where the first value is a dictionary with information to display in the UI, and the second is
                 an optional file to be attached. If polling is enabled, the returned output_data will be passed to
                 :func:`poll_for_updates`. If your integration returns nothing, you should return ({}, None).
        """

    @abstractmethod
    def format_output_data(self, output_data):
        """Process and format the output_data returned by :func:`send_event` before display.

        This is currently only relevant for MazeRunner, if you don't return an output this should return output_data
        without change.

        :param output_data: As returned by :func:`send_event`
        :rtype: dict
        :return: MazeRunner compatible UI output.
        :raises .IntegrationOutputFormatError: If there's a problem formatting the output data.
        """

    def test_connection(self, integration_data):
        """Perform a test to ensure the integration is configured correctly.

        This could include testing authentication or performing a test query.

        :param integration_data: Integration arguments.
        :returns: `success`
        :rtype: tuple(bool(success), str(response))
        """
        raise IntegrationNoMethodImplementationError()

    def poll_for_updates(self, integration_output_data):
        """Poll external service for updates.

        If service has enabled polling, this method will be called periodically and should act like :func:`send_event`

        :param integration_output_data: Output data returned by previous :func:`send_event` or :func:`poll_for_updates`
        :return: See :func:`send_event`
        :raises .IntegrationPollEventError: If there's a problem polling for updates.
        """
        raise IntegrationNoMethodImplementationError()
