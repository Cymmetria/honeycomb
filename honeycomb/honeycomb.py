# -*- coding: utf-8 -*-
"""Honeycomb Service Manager."""
from __future__ import unicode_literals

import os
import re
import json
import logging

import six
import click

from .utils.defs import *


class Honeycomb():
    """Honeycomb serivce manager.

    Honeycomb will parse the service config file and validate its contents.
    """

    logger = logging.getLogger(CUSTOM_SERVICES)
    alert_types = list()  # list of AlertType (Used only to make sure there are no duplicate alert names)

    def _get_parameters(self, package_folder):
        json_config_path = os.path.join(package_folder, CONFIG_FILE_NAME)
        with open(json_config_path, 'r') as f:
            config = json.load(f)
        return config.get(PARAMETERS, [])

    def register_custom_service(self, package_folder):
        """Register a honeycomb service.

        :param package_folder: Path to folder with service to load
        :returns: Validated service object
        :rtype: :func:`honeycomb.utils.defs.ServiceType`
        """
        json_config_path = os.path.join(package_folder, CONFIG_FILE_NAME)
        if not os.path.exists(json_config_path):
            self.logger.debug(MISSING_FILE_ERROR.format(json_config_path))
            raise click.ClickException('Cannot find service ' + os.path.basename(package_folder))

        with open(json_config_path, 'r') as f:
            config_json = json.load(f)

        # Validate service and alert config
        self._validate_config(config_json, SERVICE_ALERT_VALIDATE_FIELDS)

        self._validate_config(config_json.get(SERVICE_CONFIG_SECTION_KEY, {}), SERVICE_CONFIG_VALIDATE_FIELDS)
        self._validate_alert_configs(config_json)
        self._validate_custom_fields(config_json)

        alert_types = self._create_alert_types_and_policies(config_json)
        service_type = self._create_service_object(config_json, alert_types)

        return service_type

    def _validate_alert_configs(self, config_json):
        alert_types = config_json[ALERT_CONFIG_SECTION_KEY]
        for alert_type in alert_types:
            self._validate_config(alert_type, ALERT_CONFIG_VALIDATE_FIELDS)

    def _validate_custom_fields(self, config_json):
        custom_fields = config_json.get(PARAMETERS, [])
        for field in custom_fields:
            self._validate_custom_field(field)
            default = field.get(DEFAULT)
            field_type = field.get(TYPE)
            if default:
                self._validate_field_matches_type(field, default, field_type)

    def _create_alert_types_and_policies(self, config_json):

        alert_types = []
        for alert_type in config_json.get(ALERT_CONFIG_SECTION_KEY, []):
            _alert_type = AlertType(name=alert_type[NAME],
                                    label=alert_type[LABEL],
                                    aggregatable=False, system_alert=False)
            alert_types.append(_alert_type)
        return alert_types

    def _create_service_object(self, config_json, alert_types):
        service_config = config_json[SERVICE_CONFIG_SECTION_KEY]

        service_type_create_kwargs = {
            key: value for key, value in six.iteritems(service_config)
            if key in SERVICE_FIELDS_TO_CREATE_OBJECT
        }

        obj = ServiceType(alert_types=alert_types, **service_type_create_kwargs)
        return obj

    def _validate_config(self, config_json, fields):
        for field_name, validator_obj in six.iteritems(fields):
            field_value = config_json.get(field_name, None)
            if field_value is None:
                self.logger.debug(FIELD_DOES_NOT_EXIST.format(field_name))
                raise click.ClickException(FIELD_DOES_NOT_EXIST.format(field_name))

            if not validator_obj.validator_func(field_value):
                self.logger.debug(CUSTOM_MESSAGE_ERROR_VALIDATION.format(
                    field_name, field_value, validator_obj.get_error_message()))
                raise click.ClickException(
                    CUSTOM_MESSAGE_ERROR_VALIDATION.format(
                        field_name, field_value, validator_obj.get_error_message()))

    def _validate_field_matches_type(self, field, value, field_type):
        if (field_type == BOOLEAN_TYPE and not isinstance(value, bool)) or \
           (field_type == INTEGER_TYPE and not isinstance(value, int)) or \
           (field_type == TEXT_TYPE and not isinstance(value, six.string_types)):
            self.logger.debug(PARAMETERS_DEFAULT_DOESNT_MATCH_TYPE.format(field, value, field_type))
            raise click.ClickException(PARAMETERS_DEFAULT_DOESNT_MATCH_TYPE.format(field, value, field_type))

    def _validate_custom_field(self, field):
        for key, value in field.items():
            if key not in ALLOWED_KEYS:
                self.logger.debug(PARAMETERS_FIELD_ERROR.format(key, "property"))
                raise click.ClickException(PARAMETERS_FIELD_ERROR.format(key, "property"))
            if key == TYPE:
                if value not in ALLOWED_TYPES:
                    self.logger.debug(PARAMETERS_FIELD_ERROR.format(value, key))
                    raise click.ClickException(PARAMETERS_FIELD_ERROR.format(value, key))
            if key == VALUE:
                if not self._is_valid_field_name(value):
                    self.logger.debug(PARAMETERS_FIELD_ERROR.format(value, "field name"))
                    raise click.ClickException(PARAMETERS_FIELD_ERROR.format(value, "field name"))

    def _get_truetype(self, value):
        if value in ['true', 'True', 'y', 'Y', 'yes']:
            return True
        if value in ['false', 'False', 'n', 'N', 'no']:
            return False
        if value.isdigit():
            return int(value)
        return str(value)

    def parse_service_args(self, cmdargs, service_args):
        """Parse command line arguments based on the service's parameters config.

        :param cmdargs: Command line arguments as provided by the user in `key=value` format.
        :param service_args: Service parameters parsed from config.json.

        :returns: Validated dictionary of parameters that will be passed to
                  :class:`honeycomb.base_service.ServerCustomService`
        """
        args = dict()
        for cmdarg in cmdargs:
            kv = cmdarg.split('=')
            args[kv[0]] = self._get_truetype(kv[1])
        for arg in service_args:
            field = arg[VALUE]
            field_type = arg[TYPE]
            if field in args:
                self._validate_field_matches_type(field, args[field], field_type)
            elif arg[REQUIRED] and DEFAULT not in arg:
                """parameter was not supplied by user, but it's required and has no default value"""
                raise click.ClickException(PARAMETERS_REQUIRED_FIELD_MISSING.format(field))
        return args

    def _is_valid_field_name(self, value):
        leftovers = re.sub(r'\w', '', value)
        leftovers = re.sub(r'-', '', leftovers)
        if leftovers != '' or value[0].isdigit() or value[0] in ['-', '_'] or " " in value:
            return False
        return True
