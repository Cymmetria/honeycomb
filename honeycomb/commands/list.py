# -*- coding: utf-8 -*-
"""Honeycomb list command."""
from __future__ import absolute_import

import os
import logging

import click
import requests
from requests.adapters import HTTPAdapter

from ..utils.defs import GITHUB_RAW
from ..honeycomb import Honeycomb


@click.command(short_help='List available services')
@click.pass_context
@click.option('-r', '--remote', is_flag=True, default=False, help='Include available services from online repository')
def list(ctx, remote):
    """Show information about a honeycomb service."""
    logger = logging.getLogger(__name__)
    logger.debug('in command: {} {}'.format(ctx.command.name, ctx.params))
    installed_services = []
    click.secho('[*] Installed services:')
    service = None
    hc = Honeycomb()

    for service_dir in next(os.walk(ctx.obj['HOME']))[1]:
        logger.debug('loading {}'.format(service_dir))
        service = hc.register_custom_service(os.path.join(ctx.obj['HOME'], service_dir))
        logger.debug('loaded service {}'.format(service))
        installed_services.append(service_dir)
        s = "{:s} ({}) [Alerts:".format(service.name, ", ".join("{}/{}".format(port['port'], port['protocol'])
                                                                for port in service.ports))
        for alert in service.alert_types:
            s += " {}".format(alert.name)
        s += "]"
        click.secho(s)
    if not service:
        click.secho('[*] You do not have any services installed, try installing one with `honeycomb install`')

    if remote:
        click.secho('\n[*] Additional services from online repository:')
        try:
            rsession = requests.Session()
            rsession.mount('https://', HTTPAdapter(max_retries=3))

            r = rsession.get(GITHUB_RAW + '/services.txt')
            logger.debug('fetching services from remote repo')
            click.secho(r.text)

        except requests.exceptions.ConnectionError:
            raise click.ClickException('Unable to fetch information from online repository')
    else:
        click.secho('\n[*] try running `honeycomb list -r` to see services available from our repository')
