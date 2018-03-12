# -*- coding: utf-8 -*-
"""Honeycomb service uninstall command."""

import logging

import click

from honeycomb.defs import SERVICES
from honeycomb.utils import plugin_utils

logger = logging.getLogger(__name__)


@click.command(short_help="Uninstall a service")
@click.pass_context
@click.option("-y", "--yes", is_flag=True, default=False, help="Don't ask for confirmation of uninstall deletions.")
@click.argument("services", nargs=-1)
def uninstall(ctx, yes, services):
    """Uninstall a service."""
    logger.debug("running command %s (%s)", ctx.command.name, ctx.params,
                 extra={"command": ctx.command.name, "params": ctx.params})

    home = ctx.obj["HOME"]

    for service in services:
        service_path = plugin_utils.get_plugin_path(home, SERVICES, service)
        plugin_utils.uninstall_plugin(service_path, yes)
