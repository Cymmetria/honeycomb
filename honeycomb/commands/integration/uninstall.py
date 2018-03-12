# -*- coding: utf-8 -*-
"""Honeycomb integration uninstall command."""

import logging

import click

from honeycomb.defs import INTEGRATIONS
from honeycomb.utils import plugin_utils

logger = logging.getLogger(__name__)


@click.command(short_help="Uninstall an integration")
@click.pass_context
@click.option("-y", "--yes", is_flag=True, default=False, help="Don't ask for confirmation of uninstall deletions.")
@click.argument("integrations", nargs=-1)
def uninstall(ctx, yes, integrations):
    """Uninstall a integration."""
    logger.debug("running command %s (%s)", ctx.command.name, ctx.params,
                 extra={"command": ctx.command.name, "params": ctx.params})

    home = ctx.obj["HOME"]

    for integration in integrations:
        integration_path = plugin_utils.get_plugin_path(home, INTEGRATIONS, integration)
        plugin_utils.uninstall_plugin(integration_path, yes)
