# -*- coding: utf-8 -*-
"""Honeycomb integration list command."""

import os
import logging

import click

from honeycomb.defs import INTEGRATIONS
from honeycomb.utils.plugin_utils import list_remote_plugins, list_local_plugins
from honeycomb.integrationmanager.registration import register_integration

logger = logging.getLogger(__name__)


@click.command(short_help="List available integrations")
@click.pass_context
@click.option("-r", "--remote", is_flag=True, default=False,
              help="Include available integrations from online repository")
def list(ctx, remote):
    """List integrations."""
    logger.debug("running command %s (%s)", ctx.command.name, ctx.params,
                 extra={"command": ctx.command.name, "params": ctx.params})

    click.secho("[*] Installed integrations:")
    home = ctx.obj["HOME"]
    integrations_path = os.path.join(home, INTEGRATIONS)
    plugin_type = "integration"

    def get_integration_details(integration_name):
        logger.debug("loading {}".format(integration_name))
        integration = register_integration(os.path.join(integrations_path, integration_name))
        supported_event_types = integration.supported_event_types
        if not supported_event_types:
            supported_event_types = "All"

        return "{:s} ({:s}) [Supported event types: {}]".format(integration.name, integration.description,
                                                                supported_event_types)

    installed_integrations = list_local_plugins(plugin_type, integrations_path, get_integration_details)

    if remote:
        list_remote_plugins(installed_integrations, plugin_type)
    else:
        click.secho("\n[*] Try running `honeycomb integrations list -r` "
                    "to see integrations available from our repository")
