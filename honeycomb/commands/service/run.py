# -*- coding: utf-8 -*-
"""Honeycomb service run command."""

import os
import json
import signal
import logging

import click

from honeycomb.defs import SERVICES, INTEGRATIONS, ARGS_JSON
from honeycomb.utils import plugin_utils, config_utils
from honeycomb.utils.daemon import myRunner
from honeycomb.integrationmanager.tasks import configure_integration
from honeycomb.servicemanager.defs import STDOUTLOG, STDERRLOG, LOGS_DIR
from honeycomb.servicemanager.registration import register_service, get_service_module

logger = logging.getLogger(__name__)


@click.command(short_help="Load and run a specific service")
@click.pass_context
@click.argument("service", nargs=1)
@click.argument("args", nargs=-1)
@click.option("-d", "--daemon", is_flag=True, default=False, help="Run service in daemon mode")
@click.option("-e", "--editable", is_flag=True, default=False,
              help="Load service directly from specified path without installing (mainly for dev)")
@click.option("-a", "--show-args", is_flag=True, default=False, help="Show available service arguments")
@click.option("-i", "--integration", multiple=True, help="Enable an integration")
def run(ctx, service, args, show_args, daemon, editable, integration):
    """Load and run a specific service."""
    home = ctx.obj["HOME"]
    service_path = plugin_utils.get_plugin_path(home, SERVICES, service, editable)
    service_log_path = os.path.join(service_path, LOGS_DIR)

    logger.debug("running command %s (%s)", ctx.command.name, ctx.params,
                 extra={"command": ctx.command.name, "params": ctx.params})

    logger.debug("loading {} ({})".format(service, service_path))
    service = register_service(service_path)

    if show_args:
        return plugin_utils.print_plugin_args(service_path)

    # get our service class instance
    service_module = get_service_module(service_path)
    service_args = plugin_utils.parse_plugin_args(args, config_utils.get_config_parameters(service_path))
    service_obj = service_module.service_class(alert_types=service.alert_types, service_args=service_args)

    if not os.path.exists(service_log_path):
        os.mkdir(service_log_path)

    # prepare runner
    if daemon:
        runner = myRunner(service_obj,
                          pidfile=service_path + ".pid",
                          stdout=open(os.path.join(service_log_path, STDOUTLOG), "ab"),
                          stderr=open(os.path.join(service_log_path, STDERRLOG), "ab"))

        files_preserve = []
        for handler in logging.getLogger().handlers:
            if hasattr(handler, "stream"):
                if hasattr(handler.stream, "fileno"):
                    files_preserve.append(handler.stream.fileno())
            if hasattr(handler, "socket"):
                files_preserve.append(handler.socket.fileno())

        runner.daemon_context.files_preserve = files_preserve
        runner.daemon_context.signal_map.update({
            signal.SIGTERM: service_obj._on_server_shutdown,
            signal.SIGINT: service_obj._on_server_shutdown,
        })
        logger.debug("daemon_context", extra={"daemon_context": vars(runner.daemon_context)})

    for integration_name in integration:
        integration_path = plugin_utils.get_plugin_path(home, INTEGRATIONS, integration_name, editable)
        configure_integration(integration_path)

    click.secho("[+] Launching {} {}".format(service.name, "in daemon mode" if daemon else ""))
    try:
        # save service_args for external reference (see test)
        with open(os.path.join(service_path, ARGS_JSON), "w") as f:
            f.write(json.dumps(service_args))
        runner._start() if daemon else service_obj.run()
    except KeyboardInterrupt:
        service_obj._on_server_shutdown()

    click.secho("[*] {} has stopped".format(service.name))
