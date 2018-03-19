# -*- coding: utf-8 -*-
"""Honeycomb test constants."""


class commands():
    """Plugin commands."""

    RUN = "run"
    SHOW = "show"
    TEST = "test"
    STOP = "stop"
    LIST = "list"
    STATUS = "status"
    INSTALL = "install"
    UNINSTALL = "uninstall"
    CONFIGURE = "configure"


class plugins():
    """Plugins."""

    SERVICE = "service"
    SERVICES = "{}s".format(SERVICE)

    INTEGRATION = "integration"
    INTEGRATIONS = "{}s".format(INTEGRATION)


class args():
    """Plugin arguments."""

    YES = "--yes"
    HOME = "--home"
    DAEMON = "--daemon"
    VERBOSE = "--verbose"
    IAMROOT = "--iamroot"
    SHOW_ALL = "--show-all"
    INTEGRATION = "--integration"
    COMMON_ARGS = [VERBOSE, IAMROOT, HOME]
