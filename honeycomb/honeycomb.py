# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os
import re
import json
import logging

import six
import click

from .utils.defs import *


class CustomServiceException(click.ClickException):
    pass


class Honeycomb():
    logger = logging.getLogger(CUSTOM_SERVICES)
    alert_types = list()  # list of AlertType (Used only to make sure there are no duplicate alert names)

    def get_service_folder(self, package_folder, builtin=False):
        return os.path.abspath(package_folder)

    def get_custom_fields(self, package, builtin=False):
        path = os.path.join(self.get_service_folder(package, builtin), CONFIG_FILE_NAME)
        with open(path, b'r') as f:
            config = json.load(f)
        return config.get('parameters', [])

    def register_custom_service(self, package_folder):
        json_config_path = os.path.join(package_folder, CONFIG_FILE_NAME)
        if not os.path.exists(json_config_path):
            self.logger.error(MISSING_FILE_ERROR.format(json_config_path))
            raise CustomServiceException(MISSING_FILE_ERROR.format(json_config_path))

        with open(json_config_path, 'rb') as f:
            config_json = json.load(f)

        # Validate service and alert config
        self._validate_config(config_json, SERVICE_ALERT_VALIDATE_FIELDS)

        self._validate_config(config_json.get(SERVICE_CONFIG_SECTION_KEY, {}), SERVICE_CONFIG_VALIDATE_FIELDS)
        self._validate_alert_configs(config_json)
        self._validate_custom_fields(config_json)

        alert_types = self._create_alert_types_and_policies(config_json)
        service_type = self._create_service_object(config_json, alert_types)

        return service_type

    def get_package_initial_data(self, package_folder):
        json_config_path = os.path.join(package_folder, CONFIG_FILE_NAME)
        if not os.path.exists(json_config_path):
            self.logger.error(MISSING_FILE_ERROR.format(CONFIG_FILE_NAME))
            raise CustomServiceException(MISSING_FILE_ERROR.format(CONFIG_FILE_NAME))

        with open(json_config_path, 'rb') as f:
            try:
                config_json = json.load(f)
            except ValueError:
                self.logger.error(MALFORMED_CONFIG_FILE)
                raise CustomServiceException(MALFORMED_CONFIG_FILE)
            name = config_json.get(SERVICE_CONFIG_SECTION_KEY, {}).get(NAME, "")
            label = config_json.get(SERVICE_CONFIG_SECTION_KEY, {}).get(LABEL, "")
            description = config_json.get(SERVICE_CONFIG_SECTION_KEY, {}).get(DESCRIPTION, "")
            return name, label, description

    def get_service_path(self, service_name, builtin=False):
        return os.path.abspath(service_name)

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
                self._validate_default_matches_type(default, field_type)

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
                self.logger.error(FIELD_DOES_NOT_EXIST.format(field_name))
                raise CustomServiceException(FIELD_DOES_NOT_EXIST.format(field_name))

            if not validator_obj.validator_func(field_value):
                self.logger.error(CUSTOM_MESSAGE_ERROR_VALIDATION.format(
                    field_name, field_value, validator_obj.get_error_message()))
                raise CustomServiceException(
                    CUSTOM_MESSAGE_ERROR_VALIDATION.format(
                        field_name, field_value, validator_obj.get_error_message()))

    def _validate_default_matches_type(self, default, field_type):
        if (field_type == BOOLEAN_TYPE and not isinstance(default, bool)) or \
           (field_type == INTEGER_TYPE and not isinstance(default, int)) or \
           (field_type == TEXT_TYPE and not isinstance(default, six.string_types)):
            self.logger.error(PARAMETERS_DEFAULT_DOESNT_MATCH_TYPE.format(default, field_type))
            raise CustomServiceException(PARAMETERS_DEFAULT_DOESNT_MATCH_TYPE.format(default, field_type))

    def _validate_custom_field(self, field):
        for key, value in field.items():
            if key not in ALLOWED_KEYS:
                self.logger.error(PARAMETERS_FIELD_ERROR.format(key, "property"))
                raise CustomServiceException(PARAMETERS_FIELD_ERROR.format(key, "property"))
            if key == TYPE:
                if value not in ALLOWED_TYPES:
                    self.logger.error(PARAMETERS_FIELD_ERROR.format(value, key))
                    raise CustomServiceException(PARAMETERS_FIELD_ERROR.format(value, key))
            if key == VALUE:
                if not self.is_valid_field_name(value):
                    self.logger.error(PARAMETERS_FIELD_ERROR.format(value, "field name"))
                    raise CustomServiceException(PARAMETERS_FIELD_ERROR.format(value, "field name"))

    def is_valid_field_name(self, value):
        leftovers = re.sub(r'\w', '', value)
        leftovers = re.sub(r'-', '', leftovers)
        if leftovers != '' or value[0].isdigit() or value[0] in ['-', '_'] or " " in value:
            return False
        return True
