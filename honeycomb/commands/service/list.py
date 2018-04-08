# -*- coding: utf-8 -*-
"""Honeycomb service list command."""

import os
import logging

import click

from honeycomb.defs import SERVICES
from honeycomb.utils.plugin_utils import list_remote_plugins, list_local_plugins
from honeycomb.servicemanager.registration import register_service

logger = logging.getLogger(__name__)


@click.command(short_help="List available services")
@click.pass_context
@click.option("-r", "--remote", is_flag=True, default=False,
              help="Include available services from online repository")
def list(ctx, remote):
    """List services."""
    logger.debug("running command %s (%s)", ctx.command.name, ctx.params,
                 extra={"command": ctx.command.name, "params": ctx.params})

    click.secho("[*] Installed services:")
    home = ctx.obj["HOME"]
    services_path = os.path.join(home, SERVICES)
    plugin_type = "service"

    def get_service_details(service_name):
        logger.debug("loading {}".format(service_name))
        service = register_service(os.path.join(services_path, service_name))
        if service.ports:
            ports = ", ".join("{}/{}".format(port["port"], port["protocol"]) for port in service.ports)
        else:
            ports = "Undefined"
        return "{:s} (Ports: {}) [Alerts: {}]".format(service.name, ports,
                                                      ", ".join([_.name for _ in service.alert_types]))

    installed_services = list_local_plugins(plugin_type, services_path, get_service_details)

    if remote:
        list_remote_plugins(installed_services, plugin_type)
    else:
        click.secho("\n[*] Try running `honeycomb services list -r` "
                    "to see services available from our repository")
