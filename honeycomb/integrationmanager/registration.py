# -*- coding: utf-8 -*-
"""Honeycomb service manager."""

from __future__ import unicode_literals, absolute_import

import os
import sys
import json
import logging
import importlib

import six

from honeycomb.defs import DEPS_DIR, CONFIG_FILE_NAME, INTEGRATION

from honeycomb.exceptions import ConfigFileNotFound
from honeycomb.utils.config_utils import validate_config, validate_config_parameters
from honeycomb.integrationmanager import defs
from honeycomb.integrationmanager.models import Integration
from honeycomb.integrationmanager.exceptions import IntegrationNotFound

logger = logging.getLogger(__name__)


def get_integration_module(integration_path):
    """Add custom paths to sys and import integration module.

    :param integration_path: Path to integration folder
    """
    # add custom paths so imports would work
    paths = [
        os.path.join(__file__, "..", ".."),  # to import integrationmanager
        os.path.join(integration_path, ".."),  # to import integration itself
        os.path.join(integration_path, DEPS_DIR),  # to import integration deps
    ]

    for path in paths:
        path = os.path.realpath(path)
        logger.debug("adding %s to path", path)
        sys.path.insert(0, path)

    # get our integration class instance
    integration_name = os.path.basename(integration_path)
    logger.debug("importing %s", ".".join([integration_name, INTEGRATION]))
    return importlib.import_module(".".join([integration_name, INTEGRATION]))


def register_integration(package_folder):
    """Register a honeycomb integration.

    :param package_folder: Path to folder with integration to load
    :returns: Validated integration object
    :rtype: :func:`honeycomb.utils.defs.Integration`
    """
    logger.debug("registering integration %s", package_folder)
    package_folder = os.path.realpath(package_folder)
    if not os.path.exists(package_folder):
        raise IntegrationNotFound(os.path.basename(package_folder))

    json_config_path = os.path.join(package_folder, CONFIG_FILE_NAME)
    if not os.path.exists(json_config_path):
        raise ConfigFileNotFound(json_config_path)

    with open(json_config_path, "r") as f:
        config_json = json.load(f)

    # Validate integration and alert config
    validate_config(config_json, defs.INTEGRATION_VALIDATE_CONFIG_FIELDS)
    validate_config_parameters(config_json,
                               defs.INTEGRATION_PARAMETERS_ALLOWED_KEYS,
                               defs.INTEGRATION_PARAMETERS_ALLOWED_TYPES)

    integration_type = _create_integration_object(config_json)

    return integration_type


def _create_integration_object(config):
    integration_type_create_kwargs = {
        key: value for key, value in six.iteritems(config)
        if key in defs.INTEGRATION_FIELDS_TO_CREATE_OBJECT
    }

    obj = Integration(**integration_type_create_kwargs)
    if config[defs.POLLING_ENABLED]:
        setattr(obj, defs.POLLING_DURATION, config[defs.POLLING_DURATION])
    return obj
