# -*- coding: utf-8 -*-
"""Honeycomb integration test command."""

import os
import json
import logging

import click

from honeycomb.defs import INTEGRATIONS, ARGS_JSON
from honeycomb.utils import plugin_utils
from honeycomb.integrationmanager.exceptions import IntegrationTestFailed
from honeycomb.integrationmanager.registration import register_integration, get_integration_module

logger = logging.getLogger(__name__)


@click.command(short_help="Test an integration")
@click.pass_context
@click.argument("integrations", nargs=-1)
@click.option("-e", "--editable", is_flag=True, default=False,
              help="Run integration directly from specified path (main for dev)")
def test(ctx, integrations, editable):
    """Execute the integration's internal test method to verify it's working as intended."""
    logger.debug("running command %s (%s)", ctx.command.name, ctx.params,
                 extra={"command": ctx.command.name, "params": ctx.params})

    home = ctx.obj["HOME"]

    for integration in integrations:
        integration_path = plugin_utils.get_plugin_path(home, INTEGRATIONS, integration, editable)

        logger.debug("loading {} ({})".format(integration, integration_path))
        integration = register_integration(integration_path)
        integration_module = get_integration_module(integration_path)

        if not integration.test_connection_enabled:
            raise click.ClickException("Sorry, {} integration does not support testing.".format(integration.name))

        try:
            with open(os.path.join(integration_path, ARGS_JSON)) as f:
                integration_args = json.loads(f.read())
        except IOError:
            raise click.ClickException("Cannot load integration args, please configure it first.")
        logger.debug("testing integration {} with args {}".format(integration, integration_args))
        click.secho("[*] Testing {} with args {}".format(integration.name, integration_args))
        integration_obj = integration_module.IntegrationActionsClass(integration_args)

        success, response = integration_obj.test_connection(integration_args)
        if success:
            click.secho("Integration test: {}, Extra details: {}".format("OK" if success else "FAIL", response))
        else:
            raise IntegrationTestFailed(response)
