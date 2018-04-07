# -*- coding: utf-8 -*-
"""Honeycomb test constants."""


class commands():
    """Plugin commands."""

    RUN = "run"
    LOGS = "logs"
    SHOW = "show"
    TEST = "test"
    STOP = "stop"
    LIST = "list"
    STATUS = "status"
    INSTALL = "install"
    UNINSTALL = "uninstall"
    CONFIGURE = "configure"


class args():
    """Plugin arguments."""

    YES = "--yes"
    NUM = "--num"
    HOME = "--home"
    HELP = "--help"
    CONFIG = "--config"
    FOLLOW = "--follow"
    DAEMON = "--daemon"
    VERBOSE = "--verbose"
    IAMROOT = "--iamroot"
    SHOW_ALL = "--show-all"
    INTEGRATION = "--integration"
    COMMON_ARGS = [VERBOSE, IAMROOT, HOME]
