# -*- coding: utf-8 -*-
"""Honeycomb service install command."""

import os
import logging

import click

from honeycomb.defs import SERVICE, SERVICES
from honeycomb.utils import plugin_utils
from honeycomb.servicemanager.registration import register_service

logger = logging.getLogger(__name__)


@click.command(short_help="Install a service")
@click.pass_context
@click.argument("services", nargs=-1)
def install(ctx, services, delete_after_install=False):
    """Install a honeypot service from the online library, local path or zipfile."""
    logger.debug("running command %s (%s)", ctx.command.name, ctx.params,
                 extra={"command": ctx.command.name, "params": ctx.params})

    home = ctx.obj["HOME"]
    services_path = os.path.join(home, SERVICES)

    for service in services:
        plugin_utils.install_plugin(service, SERVICE, services_path, register_service)
