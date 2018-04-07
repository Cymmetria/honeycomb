# -*- coding: utf-8 -*-
"""Honeycomb service status command."""

import os
import logging

import click

from honeycomb.defs import SERVICES

logger = logging.getLogger(__name__)


@click.command(short_help="Shows status of installed service(s)")
@click.pass_context
@click.argument("services", nargs=-1)
@click.option("-a", "--show-all", is_flag=True, default=False, help="Show status for all services")
def status(ctx, services, show_all):
    """Show status of installed service(s)."""
    logger.debug("running command %s (%s)", ctx.command.name, ctx.params,
                 extra={"command": ctx.command.name, "params": ctx.params})

    home = ctx.obj["HOME"]
    services_path = os.path.join(home, SERVICES)

    def print_status(service):
        service_dir = os.path.join(services_path, service)
        if os.path.exists(service_dir):
            pidfile = service_dir + ".pid"
            if os.path.exists(pidfile):
                try:
                    with open(pidfile) as fh:
                        pid = int(fh.read().strip())
                    os.kill(pid, 0)
                    status = "running (pid: {})".format(pid)
                except OSError:
                    status = "not running (stale pidfile)"
            else:
                status = "not running"
        else:
            status = "no such service"
        click.secho("{} - {}".format(service, status))

    if show_all:
        for service in next(os.walk(services_path))[1]:
            print_status(service)
    elif services:
        for service in services:
            print_status(service)
    else:
        raise click.UsageError("You must specify a service name or use --show-all")
