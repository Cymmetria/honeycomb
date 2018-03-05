# -*- coding: utf-8 -*-
"""Honeycomb status command."""
from __future__ import absolute_import

import os
import logging

import click


@click.command(short_help='Shows status of installed service(s)')
@click.pass_context
@click.argument('services', nargs=-1)
@click.option('-a', '--show-all', is_flag=True, default=False, help='Show status for all services')
def status(ctx, services, show_all):
    """Show status of installed service(s)."""
    logger = logging.getLogger(__name__)
    logger.debug('in command: {} {}'.format(ctx.command.name, ctx.params))

    def print_status(service):
        service_dir = os.path.join(ctx.obj['HOME'], service)
        if os.path.exists(service_dir):
            pidfile = service_dir + '.pid'
            if os.path.exists(pidfile):
                try:
                    with open(pidfile) as fh:
                        pid = int(fh.read().strip())
                    os.kill(pid, 0)
                    status = 'running (pid: {})'.format(pid)
                except OSError:
                    status = 'not running (stale pidfile)'
            else:
                status = 'not running'
        else:
            status = 'no such service'
        click.secho('{} - {}'.format(service, status))

    if show_all:
        for service_dir in next(os.walk(ctx.obj['HOME']))[1]:
            print_status(service_dir)
    elif services:
        for service in services:
            print_status(service)
    else:
        raise click.ClickException('You must specify a service name')
