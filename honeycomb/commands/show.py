# -*- coding: utf-8 -*-
"""Honeycomb stop command."""
from __future__ import absolute_import

import os
import logging

import click
import requests
from requests.adapters import HTTPAdapter

from ..utils.defs import GITHUB_URL, GITHUB_RAW_URL
from ..honeycomb import Honeycomb

PKG_INFO_TEMPLATE = """Name: {name}
Installed: {installed}
Version: {commit_revision} Updated: {commit_date}
Summary: {label}
Location: {location}
Requires: {requirements}"""


@click.command(short_help='Show detailed information about a service')
@click.pass_context
@click.argument('pkg')
@click.option('-r', '--remote', is_flag=True, default=False, help='Show information only from remote repository')
def show(ctx, pkg, remote):
    """Show detailed information about a package."""
    logger = logging.getLogger(__name__)
    logger.debug('in command: {} {}'.format(ctx.command.name, ctx.params))

    def collect_local_info(pkg, pkgpath):
        logger.debug('loading {} from {}'.format(pkg, pkgpath))
        hc = Honeycomb()
        service = hc.register_custom_service(pkgpath)
        try:
            with open(os.path.join(pkgpath, 'requirements.txt'), 'r') as fh:
                info['requirements'] = ' '.join(fh.readlines())
        except IOError:
            pass
        info['name'] = service.name
        info['label'] = service.label
        info['location'] = pkgpath

        return info

    def collect_remote_info(pkg):
        rsession = requests.Session()
        rsession.mount('https://', HTTPAdapter(max_retries=3))

        try:
            r = rsession.get(GITHUB_RAW_URL.format(service=pkg, filename='config.json'))
            service = r.json()
            info['name'] = service['service']['name']
            info['label'] = service['service']['label']
            info['location'] = GITHUB_URL.format(service=pkg)
        except requests.exceptions.HTTPError as e:
            logger.debug(str(e))
            raise click.ClickException('Cannot find package {}'.format(pkg))
        except requests.exceptions.ConnectionError as e:
            logger.debug(str(e))
            raise click.ClickException('Unable to reach remote repository {}'.format(pkg))

        try:
            r = rsession.get(GITHUB_RAW_URL.format(service=pkg, filename='requirements.txt'))
            info['requirements'] = ' '.join(r.text.split('\n'))
        except requests.exceptions.HTTPError as e:
            logger.debug(str(e))
            info['requirements'] = None
        except requests.exceptions.ConnectionError as e:
            logger.debug(str(e))
            raise click.ClickException('Unable to reach remote repository {}'.format(pkg))

        return info

    info = {'commit_revision': 'N/A', 'commit_date': 'N/A', 'requirements': 'None'}

    pkgpath = os.path.join(ctx.obj['HOME'], pkg)
    if os.path.exists(pkgpath):
        info['installed'] = True
        if remote:
            click.secho('[*] Fetching info from online repository')
            info.update(collect_remote_info(pkg))
        else:
            info.update(collect_local_info(pkg, pkgpath))
    else:
        logger.debug('cannot find {} locally'.format(pkg))
        if not remote:
            click.secho('[*] Cannot find service locally, checking online repository')
        info['installed'] = False
        info.update(collect_remote_info(pkg))
    logger.debug(info)
    click.secho(PKG_INFO_TEMPLATE.format(**info))
