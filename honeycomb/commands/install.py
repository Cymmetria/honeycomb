# -*- coding: utf-8 -*-
"""Honeycomb install command."""
from __future__ import absolute_import

import os
import pip
import shutil
import zipfile
import logging
import tempfile

import click
import requests
from requests.adapters import HTTPAdapter

from ..utils.defs import DEPS_DIR, GITHUB_RAW
from ..honeycomb import Honeycomb


@click.command(short_help='Install a service')
@click.pass_context
@click.argument('pkgs', nargs=-1)
def install(ctx, pkgs, delete_after_install=False):
    """Install a honeypot service from the online library, local path or zipfile."""
    logger = logging.getLogger(__name__)
    logger.debug('in command: {} {}'.format(ctx.command.name, ctx.params))
    home = ctx.obj['HOME']
    # TODO:
    # handle package name exists in HOME (upgrade? overwrite?)

    def install_deps(pkgpath):
        if os.path.exists(os.path.join(pkgpath, 'requirements.txt')):
            logger.debug('installing dependencies')
            click.secho('[*] Installing dependencies')
            pipargs = ['install', '--target', os.path.join(pkgpath, DEPS_DIR), '--ignore-installed',
                       '-r', os.path.join(pkgpath, 'requirements.txt')]
            logger.debug('running pip {}'.format(pipargs))
            return pip.main(pipargs)
        return 0

    def install_dir(ctx, pkgpath, delete_after_install):
        logger.debug('{} is a directory, attempting to validate'.format(pkgpath))
        hc = Honeycomb()
        service = hc.register_custom_service(pkgpath)
        logger.debug('{} looks good, copying to {}'.format(pkgpath, home))
        try:
            shutil.copytree(pkgpath, os.path.join(home, service.name))
            if delete_after_install:
                logger.debug('deleting {}'.format(pkgpath))
                shutil.rmtree(pkgpath)
            pkgpath = os.path.join(home, service.name)
        except OSError as e:
            logger.exception(str(e))
            raise click.ClickException('Sorry, already have a service called {}, try deleting it first.'
                                       .format(service.name))

        return install_deps(pkgpath)

    def install_from_zip(ctx, pkgpath, delete_after_install=False):
        logger.debug('{} is a file, atttempting to load zip'.format(pkgpath))
        pkgtempdir = tempfile.mkdtemp(prefix='honeycomb_')
        try:
            with zipfile.ZipFile(pkgpath) as pkgzip:
                pkgzip.extractall(pkgtempdir)
        except zipfile.BadZipfile as e:
            logger.error('{} is not a zip file'.format(pkgpath))
            raise click.ClickException(str(e))
        if delete_after_install:
            logger.debug('deleting {}'.format(pkgpath))
            os.remove(pkgpath)
        logger.debug('installing from unzipped folder {}'.format(pkgtempdir))
        return install_dir(ctx, pkgtempdir, delete_after_install=True)

    def install_from_repo(ctx, pkgname):
        rsession = requests.Session()
        rsession.mount('https://', HTTPAdapter(max_retries=3))

        logger.debug('trying to install {} from online repo'.format(pkgname))
        pkgurl = '{}/{}.zip'.format(GITHUB_RAW, pkgname)
        try:
            r = rsession.head(pkgurl)
            r.raise_for_status()
            total_size = int(r.headers.get('content-length', 0))
            pkgsize = _sizeof_fmt(total_size)
            with click.progressbar(length=total_size, label='Downloading {} ({})..'.format(pkgname, pkgsize)) as bar:
                r = rsession.get(pkgurl, stream=True)
                with tempfile.NamedTemporaryFile(delete=False) as f:
                    downloaded = 0
                    for chunk in r.iter_content(chunk_size=1):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            bar.update(downloaded)
            return install_from_zip(ctx, f.name, delete_after_install=True)
        except requests.exceptions.HTTPError as e:
            logger.debug(str(e))
            raise click.ClickException('[-] Cannot find {} in online repository'.format(pkgname))
        except requests.exceptions.ConnectionError as e:
            logger.debug(str(e))
            raise click.ClickException('[-] Unable to access online repository'.format(pkgname))

    for pkgpath in pkgs:
        if os.path.exists(pkgpath):
            logger.debug('{} exists in filesystem'.format(pkgpath))
            if os.path.isdir(pkgpath):
                pip_status = install_dir(ctx, pkgpath, delete_after_install)
            else:  # pkgpath is file
                pip_status = install_from_zip(ctx, pkgpath)
        else:
            click.secho('Collecting {}..'.format(pkgpath))
            logger.debug('cannot find {} locally, checking github repo'.format(pkgpath))
            pip_status = install_from_repo(ctx, pkgpath)

        if pip_status == 0:
            click.secho('[+] Success! now try using `honeycomb run {}`'
                        .format(os.path.basename(pkgpath)))
        else:
            click.secho('[-] Service installed but something went wrong with dependency install, please review logs')


def _sizeof_fmt(num, suffix='B'):
    if not num:
        return 'unknown size'
    for unit in ['', 'K', 'M', 'G', 'T', 'P', 'E', 'Z']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s".format(num, 'Yi', suffix)
