# -*- coding: utf-8 -*-
"""Honeycomb integration run command."""

import os
import json
import logging

import click

from honeycomb import defs
from honeycomb.utils import plugin_utils, config_utils
from honeycomb.integrationmanager.registration import register_integration

logger = logging.getLogger(__name__)


@click.command(short_help="Configure an integration with default parameters")
@click.pass_context
@click.argument("integration")
@click.argument("args", nargs=-1)
@click.option("-e", "--editable", is_flag=True, default=False,
              help="Load integration directly from unspecified path without installing (mainly for dev)")
@click.option("-a", "--show_args", is_flag=True, default=False, help="Show available integration arguments")
def configure(ctx, integration, args, show_args, editable):
    """Configure an integration with default parameters.

    You can still provide one-off integration arguments to :func:`honeycomb.commands.service.run` if required.
    """
    home = ctx.obj["HOME"]
    integration_path = plugin_utils.get_plugin_path(home, defs.INTEGRATIONS, integration, editable)

    logger.debug("running command %s (%s)", ctx.command.name, ctx.params,
                 extra={"command": ctx.command.name, "params": ctx.params})

    logger.debug("loading {} ({})".format(integration, integration_path))
    integration = register_integration(integration_path)

    if show_args:
        return plugin_utils.print_plugin_args(integration_path)

    # get our integration class instance
    integration_args = plugin_utils.parse_plugin_args(args, config_utils.get_config_parameters(integration_path))

    args_file = os.path.join(integration_path, defs.ARGS_JSON)
    with open(args_file, "w") as f:
        data = json.dumps(integration_args)
        logger.debug("writing %s to %s", data, args_file)
        f.write(json.dumps(integration_args))

    click.secho("[*] {0} has been configured, make sure to test it with `honeycomb integration test {0}`"
                .format(integration.name))
