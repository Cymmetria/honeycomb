# -*- coding: utf-8 -*-
"""Honeycomb integration error messages."""

from __future__ import unicode_literals, absolute_import

from honeycomb.integrationmanager.defs import ACTIONS_FILE_NAME

REQUIRED_FIELD = "This field may not be blank"

TEST_CONNECTION_REQUIRED = "This field is required for the connection test"
TEST_CONNECTION_NOT_SUPPORTED = "Test connection is not supported"
TEST_CONNECTION_GENERAL_ERROR = "An error occurred while testing connection"

INVALID_INTEGRATIONS_ACTIONS_FILE = "Invalid {} file".format(ACTIONS_FILE_NAME)
INVALID_INTEGER = "Value must be an integer"

ERROR_SENDING_PREFIX = "Sending alert data to '{}' failed"

INTEGRATION_NOT_FOUND_ERROR = "Cannot find integration named {}, try installing it?"

INTEGRATION_TEST_FAILED = "Integration test failed, details: {}"

INTEGRATION_SEND_EVENT_ERROR = "Error sending integration event: {}"
