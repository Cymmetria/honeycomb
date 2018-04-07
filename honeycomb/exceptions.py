# -*- coding: utf-8 -*-
"""Honeycomb Exceptions."""

from __future__ import unicode_literals, absolute_import

import os
import sys
import logging
import traceback

import click

from honeycomb import error_messages


class BaseHoneycombException(click.ClickException):
    """Base Exception."""

    msg_format = None

    def __init__(self, *args, **kwargs):
        """Raise ClickException and log msg with relevant debugging info from the frame that raised the exception."""
        try:
            raise ZeroDivisionError
        except ZeroDivisionError:
            exception_frame = sys.exc_info()[2].tb_frame.f_back.f_back

        exception_stack = traceback.extract_stack(exception_frame, limit=1)[0]
        filename, lineno, funcName, tb_msg = exception_stack

        extra = {"filename": os.path.basename(filename), "lineno": lineno, "funcName": funcName}
        msg = self.msg_format.format(*args)
        logging.getLogger(__name__).debug(msg, extra=extra)
        if kwargs.get("exc_info") or os.environ.get("DEBUG", False):
            traceback.print_stack(exception_frame)
        super(BaseHoneycombException, self).__init__(click.style("[-] {}".format(msg), fg="red"))


class PathNotFound(BaseHoneycombException):
    """Specified path was not found."""

    msg_format = error_messages.PATH_NOT_FOUND_ERROR


class PluginError(BaseHoneycombException):
    """Base Plugin Exception."""


class ConfigFileNotFound(PluginError):
    """Config file not found."""

    msg_format = error_messages.MISSING_FILE_ERROR


class RequiredFieldMissing(PluginError):
    """Required parameter is missing."""

    msg_format = error_messages.PARAMETERS_REQUIRED_FIELD_MISSING


class PluginAlreadyInstalled(PluginError):
    """Plugin already installed."""

    msg_format = error_messages.PLUGIN_ALREADY_INSTALLED


class PluginNotFoundInOnlineRepo(PluginError):
    """Plugin not found in online repo."""

    msg_format = error_messages.PLUGIN_NOT_FOUND_IN_ONLINE_REPO


class PluginRepoConnectionError(PluginError):
    """Connection error when trying to connect to plugin repo."""

    msg_format = error_messages.PLUGIN_REPO_CONNECTION_ERROR


class ConfigValidationError(BaseHoneycombException):
    """Base config validation error."""


class ConfigFieldMissing(ConfigValidationError):
    """Field is missing from config file."""

    msg_format = error_messages.FIELD_MISSING


class ConfigFieldTypeMismatch(ConfigValidationError):
    """Config field does not match specified type."""

    msg_format = error_messages.PARAMETERS_DEFAULT_DOESNT_MATCH_TYPE


class ConfigFieldValidationError(ConfigValidationError):
    """Error validating config field."""

    msg_format = error_messages.CUSTOM_MESSAGE_ERROR_VALIDATION


class ParametersFieldError(ConfigValidationError):
    """Error validating parameter."""

    msg_format = error_messages.PARAMETERS_FIELD_ERROR
