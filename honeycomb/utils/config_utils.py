# -*- coding: utf-8 -*-
"""Honeycomb Config Utilities."""

from __future__ import unicode_literals, absolute_import

import os
import re
import json
import logging

import six

from honeycomb import defs, exceptions
from honeycomb.error_messages import CONFIG_FIELD_TYPE_ERROR


logger = logging.getLogger(__name__)


def config_field_type(field, cls):
    """Validate a config field against a type.

    Similar functionality to :func:`validate_field_matches_type` but returns :obj:`honeycomb.defs.ConfigField`
    """
    return defs.ConfigField(lambda _: isinstance(_, cls),
                            lambda: CONFIG_FIELD_TYPE_ERROR.format(field, cls.__name__))


def validate_config(config_json, fields):
    """Validate a JSON file configuration against list of :obj:`honeycomb.defs.ConfigField`s."""
    for field_name, validator_obj in six.iteritems(fields):
        field_value = config_json.get(field_name, None)
        if field_value is None:
            raise exceptions.ConfigFieldMissing(field_name)

        if not validator_obj.validator_func(field_value):
            raise exceptions.ConfigFieldValidationError(field_name, field_value, validator_obj.get_error_message())


def get_config_parameters(plugin_path):
    """Return the parameters section from config.json."""
    json_config_path = os.path.join(plugin_path, defs.CONFIG_FILE_NAME)
    with open(json_config_path, "r") as f:
        config = json.load(f)
    return config.get(defs.PARAMETERS, [])


def validate_config_parameters(config_json, allowed_keys, allowed_types):
    """Validate parameters in config file."""
    custom_fields = config_json.get(defs.PARAMETERS, [])
    for field in custom_fields:
        validate_field(field, allowed_keys, allowed_types)
        default = field.get(defs.DEFAULT)
        field_type = field.get(defs.TYPE)
        if default:
            validate_field_matches_type(field[defs.VALUE], default, field_type)


def validate_field_matches_type(field, value, field_type, select_items=None, _min=None, _max=None):
    """Validate a config field against a specific type."""
    if (field_type == defs.TEXT_TYPE and not isinstance(value, six.string_types)) or \
       (field_type == defs.STRING_TYPE and not isinstance(value, six.string_types)) or \
       (field_type == defs.BOOLEAN_TYPE and not isinstance(value, bool)) or \
       (field_type == defs.INTEGER_TYPE and not isinstance(value, int)):
        raise exceptions.ConfigFieldTypeMismatch(field, value, field_type)

    if field_type == defs.INTEGER_TYPE:
        if _min and value < _min:
            raise exceptions.ConfigFieldTypeMismatch(field, value, "must be higher than {}".format(_min))
        if _max and value > _max:
            raise exceptions.ConfigFieldTypeMismatch(field, value, "must be lower than {}".format(_max))

    if field_type == defs.SELECT_TYPE:
        from honeycomb.utils.plugin_utils import get_select_items
        items = get_select_items(select_items)
        if value not in items:
            raise exceptions.ConfigFieldTypeMismatch(field, value, 'one of: {}'.format(", ".join(items)))


def get_truetype(value):
    """Convert a string to a pythonized parameter."""
    if value in ["true", "True", "y", "Y", "yes"]:
        return True
    if value in ["false", "False", "n", "N", "no"]:
        return False
    if value.isdigit():
        return int(value)
    return str(value)


def validate_field(field, allowed_keys, allowed_types):
    """Validate field is allowed and valid."""
    for key, value in field.items():
        if key not in allowed_keys:
            raise exceptions.ParametersFieldError(key, "property")
        if key == defs.TYPE:
            if value not in allowed_types:
                raise exceptions.ParametersFieldError(value, key)
        if key == defs.VALUE:
            if not is_valid_field_name(value):
                raise exceptions.ParametersFieldError(value, "field name")


def is_valid_field_name(value):
    """Ensure field name is valid."""
    leftovers = re.sub(r"\w", "", value)
    leftovers = re.sub(r"-", "", leftovers)
    if leftovers != "" or value[0].isdigit() or value[0] in ["-", "_"] or " " in value:
        return False
    return True
