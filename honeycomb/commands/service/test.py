# -*- coding: utf-8 -*-
"""Honeycomb service test command."""

import os
import json
import socket
import logging

import click

from honeycomb.defs import DEBUG_LOG_FILE, SERVICES, ARGS_JSON
from honeycomb.utils import plugin_utils
from honeycomb.utils.wait import wait_until, search_json_log, TimeoutException
from honeycomb.servicemanager.defs import EVENT_TYPE
from honeycomb.servicemanager.registration import register_service, get_service_module

logger = logging.getLogger(__name__)


@click.command(short_help="Test a running service")
@click.pass_context
@click.argument("services", nargs=-1)
@click.option("-f", "--force", is_flag=True, default=False, help="Do not check if service is running before testing")
@click.option("-e", "--editable", is_flag=True, default=False,
              help="Run service directly from specified path (main for dev)")
def test(ctx, services, force, editable):
    """Execute the service's internal test method to verify it's working as intended.

    If there's no such method, honeycomb will attempt to connect to the port listed in config.json
    """
    logger.debug("running command %s (%s)", ctx.command.name, ctx.params,
                 extra={"command": ctx.command.name, "params": ctx.params})

    home = ctx.obj["HOME"]

    for service in services:
        service_path = plugin_utils.get_plugin_path(home, SERVICES, service, editable)

        logger.debug("loading {} ({})".format(service, service_path))
        service = register_service(service_path)
        service_module = get_service_module(service_path)

        if not force:
            if os.path.exists(service_path):
                pidfile = service_path + ".pid"
                if os.path.exists(pidfile):
                    try:
                        with open(pidfile) as fh:
                            pid = int(fh.read().strip())
                        os.kill(pid, 0)
                        logger.debug("service is running (pid: {})".format(pid))
                    except OSError:
                        logger.debug("service is not running (stale pidfile, pid: {})".format(pid), exc_info=True)
                        raise click.ClickException("Unable to test {} because it is not running".format(service.name))
                else:
                    logger.debug("service is not running (no pidfile)")
                    raise click.ClickException("Unable to test {} because it is not running".format(service.name))

        try:
            with open(os.path.join(service_path, ARGS_JSON)) as f:
                service_args = json.loads(f.read())
        except IOError as exc:
            logger.debug(str(exc), exc_info=True)
            raise click.ClickException("Cannot load service args, are you sure server is running?")
        logger.debug("loading service {} with args {}".format(service, service_args))
        service_obj = service_module.service_class(alert_types=service.alert_types, service_args=service_args)
        logger.debug("loaded service {}".format(service_obj))

        if hasattr(service_obj, "test"):
            click.secho("[+] Executing internal test method for service..")
            logger.debug("executing internal test method for service")
            event_types = service_obj.test()
            for event_type in event_types:
                try:
                    wait_until(search_json_log, filepath=os.path.join(home, DEBUG_LOG_FILE),
                               total_timeout=10, key=EVENT_TYPE, value=event_type)
                except TimeoutException:
                    raise click.ClickException("failed to test alert: {}".format(event_type))

                click.secho("{} alert tested successfully".format(event_type))

        elif hasattr(service, "ports") and len(service.ports) > 0:
            click.secho("[+] No internal test method found, only testing ports are open")
            logger.debug("no internal test method found, testing ports: {}".format(service.ports))
            for port in service.ports:
                socktype = socket.SOCK_DGRAM if port["protocol"] == "udp" else socket.SOCK_STREAM
                s = socket.socket(socket.AF_INET, socktype)
                try:
                    s.connect(("127.0.0.1", port["port"]))
                    s.shutdown(2)
                except Exception as exc:
                    logger.debug(str(exc), exc_info=True)
                    raise click.ClickException("Unable to connect to service port {}".format(port["port"]))
