# -*- coding: utf-8 -*-
"""Honeycomb uninstall command."""
from __future__ import absolute_import

import os
import shutil
import logging

import click


@click.command(short_help='Uninstall a service')
@click.pass_context
@click.option('-y', '--yes', is_flag=True, default=False, help='Don\'t ask for confirmation of uninstall deletions.')
@click.argument('pkgs', nargs=-1)
def uninstall(ctx, yes, pkgs):
    """Uninstall a service."""
    logger = logging.getLogger(__name__)
    logger.debug('in command: {} {}'.format(ctx.command.name, ctx.params))
    home = ctx.obj['HOME']

    for pkgname in pkgs:
        pkgpath = os.path.join(home, pkgname)
        if os.path.exists(pkgpath):
            if not yes:
                click.confirm('[?] Are you sure you want to delete service `{}` from honeycomb?'.format(pkgname),
                              abort=True)
            try:
                shutil.rmtree(pkgpath)
                logger.debug('succesfully uninstalled {}'.format(pkgname))
                click.secho('[*] Uninstalled {}'.format(pkgname))
            except OSError as e:
                logger.exception(str(e))
        else:
            click.secho('[-] doh! I cannot seem to find `{}`, are you sure it\'s installed?'.format(pkgname))
