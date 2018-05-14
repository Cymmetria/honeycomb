# -*- coding: utf-8 -*-
"""Honeycomb generic validators."""
from __future__ import unicode_literals, absolute_import

import socket
import logging


logger = logging.getLogger(__name__)


def validate_ip_or_hostname(value):
    """IP/Host parameter validator."""
    try:
        socket.gethostbyname(value)
        return value
    except socket.error as exc:
        logger.debug(str(exc), exc_info=True)
        return False


def validate_port(value):
    """Validate port is in standard range."""
    try:
        val = int(value)
        if 0 < val < 2**16:
            return val
    except ValueError:
        pass
    finally:
        return False
