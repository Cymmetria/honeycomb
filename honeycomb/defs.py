# -*- coding: utf-8 -*-
"""Honeycomb defs and constants."""

from __future__ import unicode_literals, absolute_import

import six
from attr import attrs, attrib


@attrs
class BaseNameLabel(object):
    """Generic name/label class."""

    name = attrib()
    label = attrib()


@attrs
class IBaseType(object):
    """Abstract type interface, provides BaseNameLabel collection methods."""

    @classmethod
    def all_names(cls):
        """Return list of all property names."""
        return [v.name for (k, v) in six.iteritems(cls.__dict__) if isinstance(v, BaseNameLabel)]

    @classmethod
    def all_labels(cls):
        """Return list of all property labels."""
        return [v.label for (k, v) in six.iteritems(cls.__dict__) if isinstance(v, BaseNameLabel)]


@attrs
class BaseCollection(object):
    """Abstract type collection mixin, should hold BaseNameLabel attributes."""


@attrs
class ConfigField(object):
    """Config Validator.

    error_message is also a function to calculate the error when we ran the validator_func
    """

    validator_func = attrib()
    get_error_message = attrib()


DEPS_DIR = "venv"
DEBUG_LOG_FILE = "honeycomb.debug.log"

SERVICE = "service"
SERVICES = "{}s".format(SERVICE)
INTEGRATION = "integration"
INTEGRATIONS = "{}s".format(INTEGRATION)

GITHUB_URL = "https://github.com/Cymmetria/honeycomb_plugins/tree/master/{plugin_type}/{plugin}"
GITHUB_RAW = "https://cymmetria.github.io/honeycomb_plugins"
GITHUB_RAW_URL = "https://raw.githubusercontent.com/Cymmetria/honeycomb_plugins/master/" \
                 "{plugin_type}/{plugin}/{filename}"


"""Config constants."""
NAME = "name"
LABEL = "label"
DESCRIPTION = "description"
CONFIG_FILE_NAME = "config.json"


"""Parameters constants."""
PARAMETERS = "parameters"

ARGS_JSON = ".args.json"

MIN = "min"
MAX = "max"
TYPE = "type"
VALUE = "value"
ITEMS = "items"
DEFAULT = "default"
REQUIRED = "required"
HELP_TEXT = "help_text"
VALIDATOR = "validator"
FIELD_LABEL = LABEL

TEXT_TYPE = "text"
STRING_TYPE = "string"
SELECT_TYPE = "select"
BOOLEAN_TYPE = "boolean"
INTEGER_TYPE = "integer"
PASSWORD_TYPE = "password"
FILE_TYPE = "file"
