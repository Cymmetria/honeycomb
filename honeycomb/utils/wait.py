# -*- coding: utf-8 -*-
"""Honeycomb wait utilities."""

from __future__ import unicode_literals, absolute_import

import time
import json
import logging

logger = logging.getLogger(__name__)


class TimeoutException(Exception):
    """Exception to be raised on timeout."""

    pass


def wait_until(func,
               check_return_value=True,
               total_timeout=60,
               interval=0.5,
               exc_list=None,
               error_message="",
               *args,
               **kwargs):
    """Run a command in a loop until desired result or timeout occurs.

    :param func: Function to call and wait for
    :param bool check_return_value: Examine return value
    :param int total_timeout: Wait timeout,
    :param float interval: Sleep interval between retries
    :param list exc_list: Acceptable exception list
    :param str error_message: Default error messages
    :param args: args to pass to func
    :param kwargs: lwargs to pass to fun
    """
    start_function = time.time()
    while time.time() - start_function < total_timeout:

        try:
            logger.debug("executing {} with args {} {}".format(func, args, kwargs))
            return_value = func(*args, **kwargs)
            if not check_return_value or (check_return_value and return_value):
                return return_value

        except Exception as exc:
            if exc_list and any([isinstance(exc, x) for x in exc_list]):
                pass
            else:
                raise

        time.sleep(interval)

    raise TimeoutException(error_message)


def search_json_log(filepath, key, value):
    """Search json log file for a key=value pair.

    :param filepath: Valid path to a json file
    :param key: key to match
    :param value: value to match
    :returns: First matching line in json log file, parsed by :py:func:`json.loads`
    """
    try:
        with open(filepath, "r") as fh:
            for line in fh.readlines():
                    log = json.loads(line)
                    if key in log and log[key] == value:
                        return log
    except IOError:
        pass
    return False
