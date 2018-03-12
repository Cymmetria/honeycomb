# -*- coding: utf-8 -*-
"""Honeycomb wait utilities."""

from __future__ import unicode_literals, absolute_import

import time
import json
import logging
import threading
import subprocess

logger = logging.getLogger(__name__)


class TimeoutCommand(object):
    """TimeoutCommand allows running a command line process in a thread.

    :param cmd: command to run (in a :py:func:`subprocess.Popen` shell)
    """

    def __init__(self, cmd):
        """init."""
        self.cmd = cmd
        self.process = None

    def run(self, timeout):
        """Start the specified command in a thread and wait until timeout.

        :param timeout: Timeout in seconds
        """
        def target():
            logger.debug("starting process: {}".format(self.cmd))
            self.process = subprocess.Popen(self.cmd, shell=True)
            self.process.communicate()

        thread = threading.Thread(target=target)
        thread.start()

        thread.join(timeout)
        if thread.is_alive():
            logger.debug("terminating process: {}".format(self.process))
            self.process.terminate()
            thread.join()
            raise TimeoutException


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

    :param check_return_value:
    until total_timeout seconds,
    for interval seconds interval,
    while catching exceptions given in exc_list.
    If it ends in time, it re-returns the return value from the called function.
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
    with open(filepath, "r") as fh:
        for line in fh.readlines():
                log = json.loads(line)
                if key in log and log[key] == value:
                    return log
        return False
