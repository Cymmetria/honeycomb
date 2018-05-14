# -*- coding: utf-8 -*-
"""Honeycomb service manager."""

from __future__ import unicode_literals, absolute_import

import os
import sys
import json
import logging
import platform
import importlib

import six

from honeycomb.defs import NAME, LABEL, CONFIG_FILE_NAME, DEPS_DIR
from honeycomb.utils import config_utils
from honeycomb.exceptions import ConfigFileNotFound
from honeycomb.decoymanager.models import AlertType
from honeycomb.servicemanager import defs
from honeycomb.servicemanager.models import ServiceType, OSFamilies
from honeycomb.servicemanager.exceptions import ServiceNotFound, UnsupportedOS

logger = logging.getLogger(__name__)


def get_service_module(service_path):
    """Add custom paths to sys and import service module.

    :param service_path: Path to service folder
    """
    # add custom paths so imports would work
    paths = [
        os.path.dirname(__file__),  # this folder, to catch base_service
        os.path.realpath(os.path.join(service_path, "..")),  # service's parent folder for import
        os.path.realpath(os.path.join(service_path)),  # service's folder for local imports
        os.path.realpath(os.path.join(service_path, DEPS_DIR)),  # deps dir
    ]

    for path in paths:
        path = os.path.realpath(path)
        logger.debug("adding %s to path", path)
        sys.path.insert(0, path)

    # get our service class instance
    service_name = os.path.basename(service_path)
    module = ".".join([service_name, service_name + "_service"])
    logger.debug("importing %s", module)
    return importlib.import_module(module)


def register_service(package_folder):
    """Register a honeycomb service.

    :param package_folder: Path to folder with service to load
    :returns: Validated service object
    :rtype: :func:`honeycomb.utils.defs.ServiceType`
    """
    logger.debug("registering service %s", package_folder)
    package_folder = os.path.realpath(package_folder)
    if not os.path.exists(package_folder):
        raise ServiceNotFound(os.path.basename(package_folder))

    json_config_path = os.path.join(package_folder, CONFIG_FILE_NAME)
    if not os.path.exists(json_config_path):
        raise ConfigFileNotFound(json_config_path)

    with open(json_config_path, "r") as f:
        config_json = json.load(f)

    # Validate service and alert config
    config_utils.validate_config(config_json, defs.SERVICE_ALERT_VALIDATE_FIELDS)

    config_utils.validate_config(config_json.get(defs.SERVICE_CONFIG_SECTION_KEY, {}),
                                 defs.SERVICE_CONFIG_VALIDATE_FIELDS)
    _validate_supported_platform(config_json)
    _validate_alert_configs(config_json)
    config_utils.validate_config_parameters(config_json,
                                            defs.SERVICE_ALLOWED_PARAMTER_KEYS,
                                            defs.SERVICE_ALLOWED_PARAMTER_TYPES)

    service_type = _create_service_object(config_json)
    service_type.alert_types = _create_alert_types(config_json, service_type)

    return service_type


def _validate_supported_platform(config_json):
    current_platform = platform.system()
    supported_platform = config_json[defs.SERVICE_CONFIG_SECTION_KEY][defs.SUPPORTED_OS_FAMILIES]

    if supported_platform == OSFamilies.ALL.name:
        return current_platform
    elif supported_platform == OSFamilies.LINUX.name and \
            current_platform in [OSFamilies.LINUX.name, OSFamilies.MACOS.name]:
        return current_platform
    elif supported_platform == OSFamilies.WINDOWS.name == current_platform:
        return current_platform

    raise UnsupportedOS(supported_platform, current_platform)


def _validate_alert_configs(config_json):
    alert_types = config_json[defs.ALERT_CONFIG_SECTION_KEY]
    for alert_type in alert_types:
        config_utils.validate_config(alert_type, defs.ALERT_CONFIG_VALIDATE_FIELDS)


def _create_service_object(config_json):
    service_config = config_json[defs.SERVICE_CONFIG_SECTION_KEY]

    service_type_create_kwargs = {
        key: value for key, value in six.iteritems(service_config)
        if key in defs.SERVICE_FIELDS_TO_CREATE_OBJECT
    }

    obj = ServiceType(**service_type_create_kwargs)
    return obj


def _create_alert_types(config_json, service_type):
    alert_types = []
    for alert_type in config_json.get(defs.ALERT_CONFIG_SECTION_KEY, []):
        _alert_type = AlertType(name=alert_type[NAME], label=alert_type[LABEL], service_type=service_type)
        alert_types.append(_alert_type)
    return alert_types
