# -*- coding: utf-8 -*-
"""Honeycomb Command Line Interface."""
from __future__ import absolute_import

import os
import ctypes
import logging

import click
from pythonjsonlogger import jsonlogger

from honeycomb import __version__
from honeycomb.utils import defs
from honeycomb.commands import commands_list


CONTEXT_SETTINGS = dict(
    obj={},
    auto_envvar_prefix="HC",  # all parameters will be taken from HC_PARAMETER first
    max_content_width=120,
)


@click.group(context_settings=CONTEXT_SETTINGS)
@click.pass_context
@click.option('--home', '-h', default=os.path.realpath(os.path.expanduser('~/.honeycomb')),
              help='Path Honeycomb repository', type=click.Path())
@click.option('--iamroot', is_flag=True, default=False, help='Force run as root (NOT RECOMMENDED!)')
@click.option('--verbose', '-v', envvar="DEBUG", is_flag=True, default=False, help='Enable verbose logging')
def cli(ctx, home, iamroot, verbose):
    """Homeycomb is a honeypot framework."""
    _mkhome(home)
    setup_logging(home, verbose)

    logger = logging.getLogger(__name__)

    logger.debug('Starting up Honeycomb v{}'.format(__version__))
    logger.debug('in command: {} {}'.format(ctx.command.name, ctx.params))

    try:
        is_admin = os.getuid() == 0
    except AttributeError:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin()

    if is_admin:
        if not iamroot:
            raise click.ClickException('Honeycomb should not run as a privileged user, if you are just '
                                       'trying to bind to a low port try running `setcap "cap_net_bind_service=+ep" '
                                       '$(which honeycomb)` instead. If you insist, use --iamroot')
        logger.warn('running as root!')

    ctx.obj['HOME'] = home

    logger.debug('ctx: {}'.format(ctx.obj))


def setup_logging(home, verbose):
    """Configure logging for honeycomb."""
    logging.config.dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "console": {
                "format": '%(levelname)-8s [%(asctime)s %(module)s] %(filename)s:%(lineno)s %(funcName)s: %(message)s',
            },
            "json": {
                "()": jsonlogger.JsonFormatter,
                "format": '%(levelname)s %(asctime)s %(module)s %(filename)s %(lineno)s %(funcName)s %(message)s',
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
                "filename": os.path.join(home, defs.DEBUG_LOG_FILE),
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
    home = os.path.realpath(home)
    try:
        if not os.path.exists(home):
            os.mkdir(home)
    except OSError as e:
        raise click.ClickException('Unable to create Honeycomb repository {}'.format(str(e)))


for command in commands_list:
    cli.add_command(command)
