# -*- coding: utf-8 -*-
"""Honeycomb integration install command."""

import os
import logging

import click

from honeycomb.defs import INTEGRATION, INTEGRATIONS
from honeycomb.utils import plugin_utils
from honeycomb.integrationmanager.registration import register_integration

logger = logging.getLogger(__name__)


@click.command(short_help="Install an integration")
@click.pass_context
@click.argument("integrations", nargs=-1)
def install(ctx, integrations, delete_after_install=False):
    """Install a honeycomb integration from the online library, local path or zipfile."""
    logger.debug("running command %s (%s)", ctx.command.name, ctx.params,
                 extra={"command": ctx.command.name, "params": ctx.params})

    home = ctx.obj["HOME"]
    integrations_path = os.path.join(home, INTEGRATIONS)

    for integration in integrations:
        plugin_utils.install_plugin(integration, INTEGRATION, integrations_path, register_integration)
