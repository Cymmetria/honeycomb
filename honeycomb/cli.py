# -*- coding: utf-8 -*-
"""Honeycomb Command Line Interface."""
from __future__ import absolute_import

import os
import ctypes
import logging.config

import six
import click
from pythonjsonlogger import jsonlogger

from honeycomb import __version__
from honeycomb.defs import DEBUG_LOG_FILE, INTEGRATIONS, SERVICES
from honeycomb.commands import commands_list
from honeycomb.utils.config_utils import process_config


CONTEXT_SETTINGS = dict(
    obj={},
    auto_envvar_prefix="HC",  # all parameters will be taken from HC_PARAMETER first
    max_content_width=120,
    help_option_names=["-h", "--help"],
)

logger = logging.getLogger(__name__)


@click.group(commands=commands_list, context_settings=CONTEXT_SETTINGS, invoke_without_command=True,
             no_args_is_help=True)
@click.option("--home", "-H", default=click.get_app_dir("honeycomb"),
              help="Honeycomb home path", type=click.Path(), show_default=True)
@click.option("--iamroot", is_flag=True, default=False, help="Force run as root (NOT RECOMMENDED!)")
# TODO: --config help needs rephrasing
@click.option("--config", "-c", type=click.Path(exists=True, dir_okay=False, resolve_path=True),
              help="Path to a honeycomb.yml file that provides instructions")
@click.option("--verbose", "-v", envvar="DEBUG", is_flag=True, default=False, help="Enable verbose logging")
@click.pass_context
@click.version_option(version=__version__, message="Honeycomb, version %(version)s")
def cli(ctx, home, iamroot, config, verbose):
    """Honeycomb is a honeypot framework."""
    _mkhome(home)
    setup_logging(home, verbose)

    logger.debug("Honeycomb v%s", __version__, extra={"version": __version__})
    logger.debug("running command %s (%s)", ctx.command.name, ctx.params,
                 extra={"command": ctx.command.name, "params": ctx.params})

    try:
        is_admin = os.getuid() == 0
    except AttributeError:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin()

    if is_admin:
        if not iamroot:
            raise click.ClickException("Honeycomb should not run as a privileged user, if you are just "
                                       "trying to bind to a low port try running `setcap 'cap_net_bind_service=+ep' "
                                       "$(which honeycomb)` instead. If you insist, use --iamroot")
        logger.warn("running as root!")

    ctx.obj["HOME"] = home

    logger.debug("ctx: {}".format(ctx.obj))

    if config:
        return process_config(ctx, config)


class MyLogger(logging.Logger):
    """Custom Logger."""

    def makeRecord(self, name, level, fn, lno, msg, args, exc_info, func=None, extra=None, sinfo=None):
        """Override default logger to allow overriding of internal attributes."""
        # See below commented section for a simple example of what the docstring refers to
        if six.PY2:
            rv = logging.LogRecord(name, level, fn, lno, msg, args, exc_info, func)
        else:
            rv = logging.LogRecord(name, level, fn, lno, msg, args, exc_info, func, sinfo)

        if extra is None:
            extra = dict()
        extra.update({"pid": os.getpid(), "uid": os.getuid(), "gid": os.getgid(), "ppid": os.getppid()})

        for key in extra:
            # if (key in ["message", "asctime"]) or (key in rv.__dict__):
            #     raise KeyError("Attempt to overwrite %r in LogRecord" % key)
            rv.__dict__[key] = extra[key]
        return rv


def setup_logging(home, verbose):
    """Configure logging for honeycomb."""
    logging.setLoggerClass(MyLogger)
    logging.config.dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "console": {
                "format": "%(levelname)-8s [%(asctime)s %(name)s] %(filename)s:%(lineno)s %(funcName)s: %(message)s",
            },
            "json": {
                "()": jsonlogger.JsonFormatter,
                "format": "%(levelname)s %(asctime)s %(name)s %(filename)s %(lineno)s %(funcName)s %(message)s",
            },
        },
        "handlers": {
            "default": {
                "level": "DEBUG" if verbose else "INFO",
                "class": "logging.StreamHandler",
                "formatter": "console",
            },
            "file": {
                "level": "DEBUG",
                "class": "logging.handlers.WatchedFileHandler",
                "filename": os.path.join(home, DEBUG_LOG_FILE),
                "formatter": "json",
            },
        },
        "loggers": {
            "": {
                "handlers": ["default", "file"],
                "level": "DEBUG",
                "propagate": True,
            },
        }
    })


def _mkhome(home):
    def mkdir_if_not_exists(path):
        try:
            if not os.path.exists(path):
                os.makedirs(path)
        except OSError as exc:
            logging.exception(exc)
            raise click.ClickException("Unable to create Honeycomb home dirs")

    home = os.path.realpath(home)
    for path in [home,
                 os.path.join(home, SERVICES),
                 os.path.join(home, INTEGRATIONS)]:
        mkdir_if_not_exists(path)
