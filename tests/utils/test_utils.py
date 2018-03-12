# -*- coding: utf-8 -*-
"""Honeycomb service tests."""

from __future__ import absolute_import, unicode_literals

import os
import json

from honeycomb.defs import DEBUG_LOG_FILE


def sanity_check(result=None, home=None, fail=False):
    """Run a generic sanity check for CLI command."""
    if result:
        assert (result.exit_code == 0 if not fail else not 0), "\n{}\n{}".format(result.output, repr(result.exception))
        assert (result.exception != fail), "{}\n\n\n{}".format(result.output, repr(result.exception))
    if home:
        json_log_is_valid(home)


def json_log_is_valid(path):
    """Validate a json file.

    :param path: valid path to json file
    """
    with open(os.path.join(str(path), DEBUG_LOG_FILE), "r") as fh:
        for line in fh.readlines():
                try:
                    json.loads(line)
                except json.decoder.JSONDecodeError:
                    return False
    return True


def search_file_log(filepath, method, args):
    """Search a log file by executing a string method on its lines.

    :param filepath: Valid path to a log file
    :param method: A valid :py:module:`string` method
    :param args: Arguments to above method
    :returns: First matching line in log file
    """
    with open(filepath, "r") as fh:
        for line in fh.readlines():
                cmd = getattr(line, method)
                if cmd(args):
                    return line
        return False


def search_json_log(filepath, key, value):
    """Search json log file for a key=value pair.

    :param filepath: Valid path to a json file
    :param key: key to match
    :param value: value to match
    :returns: First matching line in json log file, parsed by :py:func:`json.loads`
    """
    with open(filepath, "r") as fh:
        for line in fh.readlines():
                log = json.loads(line)
                if key in log and log[key] == value:
                    return log
        return False
