# -*- coding: utf-8 -*-
"""Honeycomb test command."""
from __future__ import absolute_import

import os
import json
import socket
import logging

import click

from ..honeycomb import Honeycomb
from ..utils.defs import DEBUG_LOG_FILE, EVENT_TYPE, _get_service_module
from ..utils.wait import wait_until, search_json_log


@click.command(short_help='Test a running service')
@click.pass_context
@click.argument('services', nargs=-1)
@click.option('-f', '--force', is_flag=True, default=False, help='Do not check if service is running before testing')
@click.option('-e', '--editable', is_flag=True, default=False,
              help='Run service directly from spefified path (main for dev)')
def test(ctx, services, force, editable):
    """Execute the service's internal test method to verify it's working as intended.

    If there's no such method, honeycomb will attempt to connect to the port listed in config.json
    """
    logger = logging.getLogger(__name__)
    logger.debug('in command: {} {}'.format(ctx.command.name, ctx.params))
    home = ctx.obj['HOME']

    for service in services:
        if editable:
            service_path = os.path.realpath(service)
        else:
            service_path = os.path.join(home, service)

        hc = Honeycomb()
        logger.debug('loading {} ({})'.format(service, service_path))
        click.secho('[+] Loading {}'.format(service))
        service = hc.register_custom_service(service_path)
        service_module = _get_service_module(service_path, service.name)

        if not force:
            if os.path.exists(service_path):
                pidfile = service_path + '.pid'
                if os.path.exists(pidfile):
                    try:
                        with open(pidfile) as fh:
                            pid = int(fh.read().strip())
                        os.kill(pid, 0)
                        logger.debug('service is running (pid: {})'.format(pid))
                    except OSError:
                        logger.debug('service is not running (stale pidfile, pid: {})'.format(pid))
                        raise click.ClickException('Unable to test {} because it is not running'.format(service.name))
                else:
                    logger.debug('service is not running (no pidfile)')
                    raise click.ClickException('Unable to test {} because it is not running'.format(service.name))

        try:
            with open(os.path.join(home, service.name + '.args.json')) as f:
                service_args = json.loads(f.read())
        except IOError:
            raise click.ClickException('Cannot load service args, are you sure server is running?')
        logger.debug('loading service {} with args {}'.format(service, service_args))
        service_obj = service_module.service_class(service_args=service_args)
        logger.debug('loaded service {}'.format(service_obj))

        if hasattr(service_obj, 'test'):
            click.secho('[+] Executing internal test method for service')
            logger.debug('executing internal test method for service')
            event_types = service_obj.test()
            for event_type in event_types:
                assert wait_until(search_json_log, filepath=os.path.join(home, DEBUG_LOG_FILE),
                                  total_timeout=10, key=EVENT_TYPE, value=event_type), ''
                'failed to test alert: {}'.format(event_type)

                click.secho('{} alert tested succesfully'.format(event_type))

        elif hasattr(service, 'ports') and len(service.ports) > 0:
            click.secho('[+] No internal test method found, only testing ports are open')
            logger.debug('no internal test method found, testing ports: {}'.format(service.ports))
            for port in service.ports:
                socktype = socket.SOCK_DGRAM if port['protocol'] == 'udp' else socket.SOCK_STREAM
                s = socket.socket(socket.AF_INET, socktype)
                try:
                    s.connect(('127.0.0.1', port['port']))
                    s.shutdown(2)
                except Exception as e:
                    logger.debug(str(e), exc_info=e)
                    raise click.ClickException('Unable to connect to service port {}'.format(port['port']))
