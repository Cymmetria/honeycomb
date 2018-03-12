# -*- coding: utf-8 -*-
"""Honeycomb integrations definitions and constants."""

from __future__ import unicode_literals, absolute_import

import six

from honeycomb import defs
from honeycomb.utils import config_utils
from honeycomb.error_messages import CONFIG_FIELD_TYPE_ERROR

ACTIONS_FILE_NAME = "integration.py"

SEND_ALERT_DATA_INTERVAL = 5
MAX_SEND_RETRIES = 5

SUPPORTED_FIELD_TYPES = [defs.PASSWORD_TYPE, defs.BOOLEAN_TYPE, defs.INTEGER_TYPE, defs.STRING_TYPE, defs.SELECT_TYPE]

DISPLAY_NAME = "display_name"
INTEGRATION_TYPE = "integration_type"
REQUIRED_FIELDS = "required_fields"
MAX_SEND_RETRIES = "max_send_retries"
POLLING_ENABLED = "polling_enabled"
POLLING_DURATION = "polling_duration"
SUPPORTED_EVENT_TYPES = "supported_event_types"
TEST_CONNECTION_ENABLED = "test_connection_enabled"

INTEGRATION_FIELDS_TO_CREATE_OBJECT = [DISPLAY_NAME, defs.DESCRIPTION, MAX_SEND_RETRIES,
                                       defs.PARAMETERS, INTEGRATION_TYPE, REQUIRED_FIELDS,
                                       POLLING_ENABLED, SUPPORTED_EVENT_TYPES, TEST_CONNECTION_ENABLED]

INTEGRATION_PARAMETERS_ALLOWED_KEYS = [defs.VALUE, defs.LABEL, defs.DEFAULT, defs.TYPE,
                                       defs.HELP_TEXT, defs.REQUIRED, defs.MIN, defs.MAX, defs.VALIDATOR, defs.ITEMS]

INTEGRATION_PARAMETERS_ALLOWED_TYPES = [defs.STRING_TYPE, defs.INTEGER_TYPE, defs.BOOLEAN_TYPE, defs.SELECT_TYPE]


class IntegrationTypes(defs.IBaseType):
    """Integration types.

    Currently only output event is supported.
    """

    EVENT_OUTPUT = defs.BaseNameLabel("event_output", "Event output")


class IntegrationAlertStatuses(defs.IBaseType):
    """Provides information about the alert status in queue."""

    PENDING = defs.BaseNameLabel("pending", "Pending")
    POLLING = defs.BaseNameLabel("polling", "Polling")
    IN_POLLING = defs.BaseNameLabel("in_polling", "Polling")
    DONE = defs.BaseNameLabel("done", "Done")
    ERROR_MISSING_SEND_FIELDS = defs.BaseNameLabel("error_missing", "Error. Missing required alert data.")
    ERROR_SENDING = defs.BaseNameLabel("error_sending", "Error sending")
    ERROR_POLLING = defs.BaseNameLabel("error_polling", "Error polling")
    ERROR_SENDING_FORMATTING = defs.BaseNameLabel("error_sending_formatting",
                                                  "Error sending. Result format not recognized.")
    ERROR_POLLING_FORMATTING = defs.BaseNameLabel("error_polling_formatting",
                                                  "Error polling. Result format not recognized.")


VALID_INTEGRATION_ALERT_OUTPUT_STATUSES = [IntegrationAlertStatuses.POLLING.name,
                                           IntegrationAlertStatuses.DONE.name,
                                           IntegrationAlertStatuses.ERROR_POLLING.name,
                                           IntegrationAlertStatuses.ERROR_POLLING_FORMATTING.name]

INTEGRATION_VALIDATE_CONFIG_FIELDS = {
    DISPLAY_NAME: config_utils.config_field_type(DISPLAY_NAME, six.string_types),
    INTEGRATION_TYPE: defs.ConfigField(
        lambda value: value in IntegrationTypes.all_names(),
        lambda: "Invalid {} must be one of: {}".format(INTEGRATION_TYPE, IntegrationTypes.all_names())
    ),
    SUPPORTED_EVENT_TYPES: defs.ConfigField(
        lambda event_types: (isinstance(event_types, list) and
                             all([isinstance(_, six.string_types) for _ in event_types])),
        lambda: CONFIG_FIELD_TYPE_ERROR.format(SUPPORTED_EVENT_TYPES, "list of strings")
    ),
    REQUIRED_FIELDS: defs.ConfigField(
        lambda required_fields: (isinstance(required_fields, list) and
                                 all([isinstance(_, six.string_types) for _ in required_fields])),
        lambda: CONFIG_FIELD_TYPE_ERROR.format(SUPPORTED_EVENT_TYPES, "list of strings")
    ),
    MAX_SEND_RETRIES: config_utils.config_field_type(MAX_SEND_RETRIES, int),
    POLLING_ENABLED: config_utils.config_field_type(POLLING_ENABLED, bool),
    defs.PARAMETERS: config_utils.config_field_type(defs.PARAMETERS, list),
}
