# -*- coding: utf-8 -*-
"""Honeycomb generic error messages."""

from __future__ import unicode_literals, absolute_import

from honeycomb.defs import CONFIG_FILE_NAME

MISSING_FILE_ERROR = "Missing file {}"
PATH_NOT_FOUND_ERROR = "Cannot find path {}"
MALFORMED_CONFIG_FILE = "{} is not a valid json file".format(CONFIG_FILE_NAME)
CUSTOM_MESSAGE_ERROR_VALIDATION = "Failed to import config. error in field {} with value {}: {}"
FIELD_MISSING = "field {} is missing from config file"

CONFIG_FIELD_TYPE_ERROR = "Config error: '{}' is not a valid {}"
PARAMETERS_FIELD_ERROR = "Parameters: '{}' is not a valid {}"
PARAMETERS_DEFAULT_DOESNT_MATCH_TYPE = "Parameters: Bad value for {}={} (must be {})"
PARAMETERS_REQUIRED_FIELD_MISSING = "Parameters: '{}' is missing (use --show_args to see all parameters)"

PLUGIN_ALREADY_INSTALLED = "{} is already installed"
PLUGIN_NOT_FOUND_IN_ONLINE_REPO = "Cannot find {} in online repository"
PLUGIN_REPO_CONNECTION_ERROR = "Unable to access online repository (check debug logs for detailed info)"
