# -*- coding: utf-8 -*-
"""Honeycomb service stop command."""

import os
import json
import logging

import click
import daemon.runner

from honeycomb.defs import SERVICES, ARGS_JSON
from honeycomb.utils import plugin_utils
from honeycomb.utils.daemon import myRunner
from honeycomb.servicemanager.registration import get_service_module, register_service

logger = logging.getLogger(__name__)


@click.command(short_help="Stop a running service daemon")
@click.argument("service")
@click.option("-e", "--editable", is_flag=True, default=False,
              help="Load service directly from specified path without installing (mainly for dev)")
@click.pass_context
def stop(ctx, service, editable):
    """Stop a running service daemon."""
    logger.debug("running command %s (%s)", ctx.command.name, ctx.params,
                 extra={"command": ctx.command.name, "params": ctx.params})

    home = ctx.obj["HOME"]
    service_path = plugin_utils.get_plugin_path(home, SERVICES, service, editable)

    logger.debug("loading {}".format(service))
    service = register_service(service_path)

    try:
        with open(os.path.join(service_path, ARGS_JSON)) as f:
            service_args = json.loads(f.read())
    except IOError as exc:
        logger.debug(str(exc), exc_info=True)
        raise click.ClickException("Cannot load service args, are you sure server is running?")

    # get our service class instance
    service_module = get_service_module(service_path)
    service_obj = service_module.service_class(alert_types=service.alert_types, service_args=service_args)

    # prepare runner
    runner = myRunner(service_obj,
                      pidfile=service_path + ".pid",
                      stdout=open(os.path.join(service_path, "stdout.log"), "ab"),
                      stderr=open(os.path.join(service_path, "stderr.log"), "ab"))

    click.secho("[*] Stopping {}".format(service.name))
    try:
        runner._stop()
    except daemon.runner.DaemonRunnerStopFailureError as exc:
        logger.debug(str(exc), exc_info=True)
        raise click.ClickException("Unable to stop service, are you sure it is running?")
