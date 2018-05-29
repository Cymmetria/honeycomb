# -*- coding: utf-8 -*-
"""Honeycomb integration tasks."""

from __future__ import unicode_literals, absolute_import

import os
import json
import logging
import threading
from time import sleep
from datetime import datetime, tzinfo

import click

from honeycomb.defs import ARGS_JSON
from honeycomb.integrationmanager import exceptions
from honeycomb.integrationmanager.defs import (IntegrationTypes, IntegrationAlertStatuses,
                                               SEND_ALERT_DATA_INTERVAL, MAX_SEND_RETRIES)
from honeycomb.integrationmanager.models import IntegrationAlert, ConfiguredIntegration
from honeycomb.integrationmanager.registration import register_integration, get_integration_module

logger = logging.getLogger(__name__)

configured_integrations = list()
polling_integration_alerts = list()


class _UTC(tzinfo):
    def utcoffset(self, dt):
        return datetime.timedelta(0)

    def tzname(self, dt):
        return "UTC"

    def dst(self, dt):
        return datetime.timedelta(0)


def configure_integration(path):
    """Configure and enable an integration."""
    integration = register_integration(path)
    integration_args = {}
    try:
        with open(os.path.join(path, ARGS_JSON)) as f:
            integration_args = json.loads(f.read())
    except Exception as exc:
        logger.debug(str(exc), exc_info=True)
        raise click.ClickException("Cannot load {} integration args, please configure it first."
                                   .format(os.path.basename(path)))

    click.secho("[*] Adding integration {}".format(integration.name))
    logger.debug("Adding integration %s", integration.name,
                 extra={"integration": integration.name, "args": integration_args})
    configured_integration = ConfiguredIntegration(name=integration.name, integration=integration, path=path)
    configured_integration.data = integration_args
    configured_integration.integration.module = get_integration_module(path).IntegrationActionsClass(integration_args)

    configured_integrations.append(configured_integration)


def send_alert_to_subscribed_integrations(alert):
    """Send Alert to relevant integrations."""
    valid_configured_integrations = get_valid_configured_integrations(alert)

    for configured_integration in valid_configured_integrations:
        threading.Thread(target=create_integration_alert_and_call_send, args=(alert, configured_integration)).start()


def get_current_datetime_utc():
    """Return a datetime object localized to UTC."""
    return datetime.utcnow().replace(tzinfo=_UTC())


def get_valid_configured_integrations(alert):
    """Return a list of integrations for alert filtered by alert_type.

    :returns: A list of relevant integrations
    """
    if not configured_integrations:
        return []

    # Collect all integrations that are configured for specific alert_type
    # or have no specific supported_event_types (i.e., all alert types)
    valid_configured_integrations = [
        _ for _ in configured_integrations if _.integration.integration_type == IntegrationTypes.EVENT_OUTPUT.name and
        (not _.integration.supported_event_types or alert.alert_type in _.integration.supported_event_types)
    ]

    return valid_configured_integrations


def create_integration_alert_and_call_send(alert, configured_integration):
    """Create an IntegrationAlert object and send it to Integration."""
    integration_alert = IntegrationAlert(
        alert=alert,
        configured_integration=configured_integration,
        status=IntegrationAlertStatuses.PENDING.name,
        retries=configured_integration.integration.max_send_retries
    )

    send_alert_to_configured_integration(integration_alert)


def send_alert_to_configured_integration(integration_alert):
    """Send IntegrationAlert to configured integration."""
    try:
        alert = integration_alert.alert
        configured_integration = integration_alert.configured_integration
        integration = configured_integration.integration
        integration_actions_instance = configured_integration.integration.module

        alert_fields = dict()
        if integration.required_fields:
            if not all([hasattr(alert, _) for _ in integration.required_fields]):
                logger.debug("Alert does not have all required_fields (%s) for integration %s, skipping",
                             integration.required_fields,
                             integration.name)
                return

        exclude_fields = ["alert_type", "service_type"]
        alert_fields = {}
        for field in alert.__slots__:
            if hasattr(alert, field) and field not in exclude_fields:
                alert_fields[field] = getattr(alert, field)

        logger.debug("Sending alert %s to %s", alert_fields, integration.name)
        output_data, output_file_content = integration_actions_instance.send_event(alert_fields)

        if integration.polling_enabled:
            integration_alert.status = IntegrationAlertStatuses.POLLING.name
            polling_integration_alerts.append(integration_alert)
        else:
            integration_alert.status = IntegrationAlertStatuses.DONE.name

        integration_alert.send_time = get_current_datetime_utc()
        integration_alert.output_data = json.dumps(output_data)
        # TODO: do something with successfully handled alerts? They are all written to debug log file

    except exceptions.IntegrationMissingRequiredFieldError as exc:
        logger.exception("Send response formatting for integration alert %s failed. Missing required fields",
                         integration_alert,
                         exc.message)

        integration_alert.status = IntegrationAlertStatuses.ERROR_MISSING_SEND_FIELDS.name

    except exceptions.IntegrationOutputFormatError:
        logger.exception("Send response formatting for integration alert %s failed", integration_alert)

        integration_alert.status = IntegrationAlertStatuses.ERROR_SENDING_FORMATTING.name

    except exceptions.IntegrationSendEventError as exc:
        integration_send_retries = integration_alert.retries if integration_alert.retries <= MAX_SEND_RETRIES \
            else MAX_SEND_RETRIES  # making sure we do not exceed celery max retries
        send_retries_left = integration_send_retries - 1
        integration_alert.retries = send_retries_left

        logger.error("Sending integration alert %s failed. Message: %s. Retries left: %s",
                     integration_alert,
                     exc.message,
                     send_retries_left)

        if send_retries_left == 0:
            integration_alert.status = IntegrationAlertStatuses.ERROR_SENDING.name

        if send_retries_left > 0:
            sleep(SEND_ALERT_DATA_INTERVAL)
            send_alert_to_configured_integration(integration_alert)


def poll_integration_information_for_waiting_integration_alerts():
    """poll_integration_information_for_waiting_integration_alerts."""
    if not polling_integration_alerts:
        return

    logger.debug("Polling information for waiting integration alerts")

    for integration_alert in polling_integration_alerts:
        configured_integration = integration_alert.configured_integration
        integration = configured_integration.integration
        polling_duration = integration.polling_duration

        if get_current_datetime_utc() - integration_alert.send_time > polling_duration:
            logger.debug("Polling duration expired for integration alert %s", integration_alert)
            integration_alert.status = IntegrationAlertStatuses.ERROR_POLLING.name
        else:
            integration_alert.status = IntegrationAlertStatuses.IN_POLLING.name

            poll_integration_alert_data(integration_alert)


def poll_integration_alert_data(integration_alert):
    """Poll for updates on waiting IntegrationAlerts."""
    logger.info("Polling information for integration alert %s", integration_alert)
    try:
        configured_integration = integration_alert.configured_integration
        integration_actions_instance = configured_integration.integration.module

        output_data, output_file_content = integration_actions_instance.poll_for_updates(
            json.loads(integration_alert.output_data)
        )

        integration_alert.status = IntegrationAlertStatuses.DONE.name
        integration_alert.output_data = json.dumps(output_data)
        polling_integration_alerts.remove(integration_alert)

    except exceptions.IntegrationNoMethodImplementationError:
        logger.error("No poll_for_updates function found for integration alert %s", integration_alert)

        integration_alert.status = IntegrationAlertStatuses.ERROR_POLLING.name

    except exceptions.IntegrationPollEventError:
        # This does not always indicate an error, this is also raised when need to try again later
        logger.debug("Polling for integration alert %s failed", integration_alert)

    except exceptions.IntegrationOutputFormatError:
        logger.error("Integration alert %s formatting error", integration_alert)

        integration_alert.status = IntegrationAlertStatuses.ERROR_POLLING_FORMATTING.name

    except Exception:
        logger.exception("Error polling integration alert %s", integration_alert)

        integration_alert.status = IntegrationAlertStatuses.ERROR_POLLING.name
