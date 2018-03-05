# -*- coding: utf-8 -*-
"""Honeycomb stop command."""
from __future__ import absolute_import

import os
import sys
import logging

import click
import importlib
import daemon.runner

from ..utils.defs import DEPS_DIR
from ..honeycomb import Honeycomb
from ..utils.daemon import myRunner


def _get_service_module(service_path, service_name):
    # add custom paths so imports would work
    sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
    sys.path.insert(0, os.path.join(service_path, DEPS_DIR))
    sys.path.insert(0, os.path.join(service_path, '..'))

    # get our service class instance
    return importlib.import_module(".".join([service_name, service_name + '_service']))


@click.command(short_help='Stop a running service daemon')
@click.pass_context
@click.argument('service')
def stop(ctx, service):
    """Stop a running service daemon."""
    logger = logging.getLogger(__name__)
    logger.debug('in command: {} {}'.format(ctx.command.name, ctx.params))
    home = ctx.obj['HOME']

    hc = Honeycomb()
    logger.debug('loading {}'.format(service))
    service = hc.register_custom_service(os.path.join(home, service))

    # get our service class instance
    service_module = _get_service_module(home, service.name)
    service_obj = service_module.service_class()

    # prepare runner
    runner = myRunner(service_obj,
                      pidfile=os.path.join(home, service.name + '.pid'),
                      stdout=open(os.path.join(home, service.name, 'stdout.log'), 'ab'),
                      stderr=open(os.path.join(home, service.name, 'stderr.log'), 'ab'))

    click.secho('[*] Stopping {}'.format(service.name))
    try:
        runner._stop()
    except daemon.runner.DaemonRunnerStopFailureError as e:
        logger.debug(str(e))
        raise click.ClickException('Unable to stop service, are you sure it is running?')
