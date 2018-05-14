# -*- coding: utf-8 -*-
"""Honeycomb Config Utilities."""

from __future__ import unicode_literals, absolute_import

import os
import re
import json
import logging

import six
import yaml

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
    """Validate a JSON file configuration against list of :obj:`honeycomb.defs.ConfigField`."""
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
            raise exceptions.ConfigFieldTypeMismatch(field, value, "one of: {}".format(", ".join(items)))


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


def process_config(ctx, configfile):
    """Process a yaml config with instructions.

    This is a heavy method that loads lots of content, so we only run the imports if its called.
    """
    from honeycomb.commands.service.run import run as service_run
    # from honeycomb.commands.service.logs import logs as service_logs
    from honeycomb.commands.service.install import install as service_install
    from honeycomb.commands.integration.install import install as integration_install
    from honeycomb.commands.integration.configure import configure as integration_configure

    VERSION = "version"
    SERVICES = defs.SERVICES
    INTEGRATIONS = defs.INTEGRATIONS

    required_top_keys = [VERSION, SERVICES]
    supported_versions = [1]

    def validate_yml(config):
        for key in required_top_keys:
            if key not in config:
                raise exceptions.ConfigFieldMissing(key)

        version = config.get(VERSION)
        if version not in supported_versions:
            raise exceptions.ConfigFieldTypeMismatch(VERSION, version,
                                                     "one of: {}".format(repr(supported_versions)))

    def install_plugins(services, integrations):
        for cmd, kwargs in [(service_install, {SERVICES: services}),
                            (integration_install, {INTEGRATIONS: integrations})]:
            try:
                ctx.invoke(cmd, **kwargs)
            except SystemExit:
                # If a plugin is already installed honeycomb will exit abnormally
                pass

    def parameters_to_string(parameters_dict):
        return ["{}={}".format(k, v) for k, v in parameters_dict.items()]

    def configure_integrations(integrations):
        for integration in integrations:
            args_list = parameters_to_string(config[INTEGRATIONS][integration].get(defs.PARAMETERS, dict()))
            ctx.invoke(integration_configure, integration=integration, args=args_list)

    def run_services(services, integrations):
        # TODO: Enable support with multiple services as daemon, and run service.logs afterwards
        #       tricky part is that services launched as daemon are exited with os._exit(0) so you
        #       can't catch it.
        for service in services:
            args_list = parameters_to_string(config[SERVICES][service].get(defs.PARAMETERS, dict()))
            ctx.invoke(service_run, service=service, integration=integrations, args=args_list)

    # TODO: Silence normal stdout and follow honeycomb.debug.json instead
    #       This would make monitoring containers and collecting logs easier
    with open(configfile, "rb") as fh:
        config = yaml.load(fh.read())

    validate_yml(config)
    services = config.get(SERVICES).keys()
    integrations = config.get(INTEGRATIONS).keys() if config.get(INTEGRATIONS) else []

    install_plugins(services, integrations)
    configure_integrations(integrations)
    run_services(services, integrations)
