# -*- coding: utf-8 -*-
"""Honeycomb run command."""
from __future__ import absolute_import

import os
import json
import socket
import logging

import click
from pythonjsonlogger import jsonlogger

from ..utils import defs
from ..honeycomb import Honeycomb
from ..utils.defs import _get_service_module
from ..utils.daemon import myRunner
from ..utils.cef_handler import CEFSyslogHandler


def validate_ip_or_hostname(ctx, param, value):
    """IP/Host parameter validator."""
    try:
        socket.gethostbyname(value)
        return value
    except socket.error:
        raise click.BadParameter('{} must be a valid IP address or hostname')


@click.command(short_help='Load and run a specific service')
@click.pass_context
@click.argument('service', nargs=1)
@click.argument('arg', nargs=-1)
@click.option('-d', '--daemon', is_flag=True, default=False, help='Run service in daemon mode')
@click.option('-e', '--editable', is_flag=True, default=False,
              help='Run service directly from spefified path (main for dev)')
@click.option('-a', '--args', is_flag=True, default=False, help='Show available service arguments')
@click.option('-j', '--json-log', type=click.Path(exists=False, dir_okay=False, writable=True, resolve_path=True),
              help='Log alerts in JSON to provided path')
@click.option('-s', '--syslog', is_flag=True, default=False, help='Enable syslog (CEF) logging for service')
@click.option('-h', '--syslog-host', default='127.0.0.1', callback=validate_ip_or_hostname,
              help='Host/IP for syslog server (default: 127.0.0.1)')
@click.option('-p', '--syslog-port', default='514', type=click.IntRange(0, 65535),
              help='Host/IP for syslog server (default: 514)')
@click.option('-P', '--syslog-protocol', default='udp', type=click.Choice(['tcp', 'udp']),
              help='Syslog protocol (default: udp)')
@click.option('-v', '--verbose', is_flag=True, default=False, help='Enable verbose logging for service')
def run(ctx, service, arg, args, daemon, editable, json_log,
        syslog, syslog_host, syslog_port, syslog_protocol, verbose):
    """Load and run a specific service."""
    home = ctx.obj['HOME']
    hc = Honeycomb()

    if editable:
        service_path = os.path.realpath(service)
    else:
        service_path = os.path.join(home, service)
    service_log_path = os.path.join(service_path, 'logs')

    def print_args(service):
        args = hc._get_parameters(service_path)
        args_format = '{:15} {:10} {:^15} {:^10} {:25}'
        title = args_format.format(defs.NAME.upper(), defs.TYPE.upper(), defs.DEFAULT.upper(),
                                   defs.REQUIRED.upper(), defs.DESCRIPTION.upper())
        click.secho(title)
        click.secho("-" * len(title))
        for arg in args:
            help_text = " ({}}".format(arg[defs.HELP_TEXT]) if defs.HELP_TEXT in arg else ''
            click.secho(args_format.format(arg[defs.VALUE], arg[defs.TYPE], str(arg.get(defs.DEFAULT, None)),
                                           str(arg.get(defs.REQUIRED, False)), arg[defs.LABEL] + help_text))

    logger = logging.getLogger(__name__)
    logger.debug('in command: {} {}'.format(ctx.command.name, ctx.params))
    logger.debug('loading {} ({})'.format(service, service_path))
    click.secho('[+] Loading {}'.format(service))
    service = hc.register_custom_service(service_path)

    if args:
        return print_args(service)

    if syslog:
        click.secho('[+] Adding syslog handler')
        socktype = socket.SOCK_DGRAM if syslog_protocol == 'udp' else socket.SOCK_STREAM
        cef_handler = CEFSyslogHandler(address=(syslog_host, syslog_port), socktype=socktype)
        cef_handler.setLevel(logging.CRITICAL)
        logging.getLogger().addHandler(cef_handler)

    if json_log:
        click.secho('[+] Adding JSON handler')
        json_handler = logging.handlers.WatchedFileHandler(filename=json_log)
        json_handler.setLevel(logging.CRITICAL)
        json_formatter = jsonlogger.JsonFormatter('%(levelname)s %(asctime)s %(module)s %(filename)s '
                                                  '%(lineno)s %(funcName)s %(message)s')
        json_handler.setFormatter(json_formatter)
        logging.getLogger().addHandler(json_handler)

    # get our service class instance
    service_module = _get_service_module(service_path, service.name)
    service_args = hc.parse_service_args(arg, hc._get_parameters(service_path))
    service_obj = service_module.service_class(service_args=service_args)

    if not os.path.exists(service_log_path):
        os.mkdir(service_log_path)

    # prepare runner
    if daemon:
        runner = myRunner(service_obj,
                          pidfile=service_path + '.pid',
                          stdout=open(os.path.join(service_log_path, 'stdout.log'), 'ab'),
                          stderr=open(os.path.join(service_log_path, 'stderr.log'), 'ab'))

        files_preserve = []
        for handler in logging.getLogger().handlers:
            if hasattr(handler, 'stream'):
                if hasattr(handler.stream, 'fileno'):
                    files_preserve.append(handler.stream.fileno())
            if hasattr(handler, 'socket'):
                files_preserve.append(handler.socket.fileno())
        runner.daemon_context.files_preserve = files_preserve
        logger.debug('Daemon Context: {}'.format(vars(runner.daemon_context)))

    click.secho('[+] Launching {} {}'.format(service.name, 'in daemon mode' if daemon else ''))
    try:
        # save service_args for external reference (see test)
        with open(os.path.join(home, service.name + '.args.json'), 'w') as f:
            f.write(json.dumps(service_args))
        runner._start() if daemon else service_obj.run()
    except KeyboardInterrupt:
        service_obj._on_server_shutdown()

    click.secho('[*] {} has stopped'.format(service.name))
