# -*- coding: utf-8 -*-
from __future__ import absolute_import

import os
import sys
import pip
import signal
import ctypes
import shutil
import socket
import logging
import zipfile
import requests
import tempfile
import importlib

import click
import svn.local
import svn.remote
import svn.exception
from pythonjsonlogger import jsonlogger
from daemon.runner import DaemonRunner, DaemonRunnerStopFailureError

from honeycomb import __version__, honeycomb
from honeycomb.utils.cef_handler import CEFSyslogHandler

hc = honeycomb.Honeycomb()
logger = None
SVN_URL = 'https://github.com/Cymmetria/honeycomb_services/trunk/{service}'
DEPS_DIR = 'venv'
GITHUB_URL = 'https://github.com/Cymmetria/honeycomb_services/tree/master/{service}'
GITHUB_RAW_URL = 'https://raw.githubusercontent.com/Cymmetria/honeycomb_services/master/{service}/{filename}'
PKG_INFO_TEMPLATE = """Name: {name}
Installed: {installed}
Version: {commit_revision} Updated: {commit_date}
Summary: {label}
Location: {location}
Requires: {requirements}"""


class myRunner(DaemonRunner):
    def parse_args(argv):
        """do nothing since we manage the daemon from code"""


@click.group()
@click.pass_context
@click.option('--home', '-h', default=os.path.realpath(os.path.expanduser('~/.honeycomb')),
              help='Path Honeycomb repository', type=click.Path())
@click.option('--iamroot', is_flag=True, default=False, help='Force run as root (NOT RECOMMENDED!)')
@click.option('--verbose', '-v', envvar="DEBUG", is_flag=True, default=False, help='Enable verbose logging')
def main(ctx, home, iamroot, verbose):
    global logger
    """Homeycomb is a honeypot framework"""
    mkhome(home)
    logger = setup_logging(home, verbose)

    logger.debug('Starting up Honeycomb v{}'.format(__version__))
    logger.debug('in command: {}'.format(ctx.command.name))

    try:
        is_admin = os.getuid() == 0
    except AttributeError:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin()

    if is_admin:
        if not iamroot:
            raise click.ClickException('Honeycomb should not run as a privileged user, if you are just '
                                       'trying to bind to a low port try running `setcap "cap_net_bind_service=+ep" '
                                       '$(which honeycomb)` instead. If you insist, use --iamroot')
        logger.warn('running as root!')

    ctx.obj['HOME'] = home

    logger.debug('ctx: {}'.format(ctx.obj))


def validate_ip_or_hostname(ctx, param, value):
    try:
        socket.gethostbyname(value)
        return value
    except socket.error:
        raise click.BadParameter('{} must be a valid IP address or hostname')


@main.command()
@click.pass_context
@click.argument('service')
@click.option('-d', '--daemon', is_flag=True, default=False, help='Run service in daemon mode')
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
def run(ctx, service, daemon, json_log, syslog, syslog_host, syslog_port, syslog_protocol, verbose):
    """load and run a specific service"""

    logger.debug('in command: {}'.format(ctx.command.name))
    logger.debug('loading {}'.format(service))
    click.secho('[+] Loading {}'.format(service), fg='green')
    service = hc.register_custom_service(os.path.join(ctx.obj['HOME'], service))
    if service:
        if syslog:
            click.secho('[+] Adding syslog handler', fg='green')
            socktype = socket.SOCK_DGRAM if syslog_protocol == 'udp' else socket.SOCK_STREAM
            cef_handler = CEFSyslogHandler(address=(syslog_host, syslog_port), socktype=socktype)
            cef_handler.setLevel(logging.CRITICAL)
            logging.getLogger().addHandler(cef_handler)

        if json_log:
            click.secho('[+] Adding JSON handler', fg='green')
            json_handler = logging.handlers.WatchedFileHandler(filename=json_log)
            json_handler.setLevel(logging.CRITICAL)
            json_formatter = jsonlogger.JsonFormatter('%(levelname)s %(asctime)s %(module)s %(filename)s '
                                                      '%(lineno)s %(funcName)s %(message)s')
            json_handler.setFormatter(json_formatter)
            logging.getLogger().addHandler(json_handler)

        # add custom paths so imports would work
        sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
        sys.path.insert(0, os.path.join(ctx.obj['HOME'], service.name, DEPS_DIR))
        sys.path.insert(0, ctx.obj['HOME'])

        # get our service class instance
        service_module = importlib.import_module(".".join([service.name, service.name + '_service']))
        service_obj = service_module.service_class()

        # prepare service_obj for deamon
        # stdout/stderr will be reset if we're not forking
        service_obj.pidfile_path = os.path.join(ctx.obj['HOME'], service.name + '.pid')
        service_obj.stdout_path = os.path.join(ctx.obj['HOME'], service.name, 'stdout.log')
        service_obj.stderr_path = os.path.join(ctx.obj['HOME'], service.name, 'stderr.log')

        # prepare runner
        if daemon:
            runner = myRunner(service_obj)
            runner.daemon_context.signal_map = {signal.SIGTERM: service_obj._on_server_shutdown}
            runner.daemon_context.detach_process = daemon

            files_preserve = []
            for handler in logging.getLogger().handlers:
                if hasattr(handler, 'stream'):
                    files_preserve.append(handler.stream.fileno())
                if hasattr(handler, 'socket'):
                    files_preserve.append(handler.socket.fileno())
            runner.daemon_context.files_preserve = files_preserve
            logger.debug('Daemon Context: {}'.format(vars(runner.daemon_context)))

        click.secho('[+] Launching {} {}'.format(service.name, 'in Background' if daemon else ''), fg='green')
        try:
            runner._start() if daemon else service_obj.run()
        except KeyboardInterrupt:
            service_obj._on_server_shutdown()

        click.secho('[*] {} has stopped'.format(service.name), fg='green')
    else:
        click.secho('[-] Failed to load {}'.format(service), fg='green')
        logger.critical('Failed to load {}'.format(service))


@main.command()
@click.pass_context
@click.argument('service')
def stop(ctx, service):
    logger.debug('in command: {}'.format(ctx.command.name))
    service = hc.register_custom_service(os.path.join(ctx.obj['HOME'], service))
    logger.debug('loading {}'.format(service))
    if service:

        # add custom paths so imports would work
        sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
        sys.path.insert(0, ctx.obj['HOME'])

        # get our service class instance
        service_module = importlib.import_module(".".join([service.name, service.name + '_service']))
        service_obj = service_module.service_class()

        # prepare service_obj for deamon
        service_obj.pidfile_path = os.path.join(ctx.obj['HOME'], service.name + '.pid')
        service_obj.stdout_path = os.path.join(ctx.obj['HOME'], service.name, 'stdout.log')
        service_obj.stderr_path = os.path.join(ctx.obj['HOME'], service.name, 'stderr.log')
        runner = myRunner(service_obj)
        click.secho('[*] Stopping {}'.format(service.name), fg='green')
        try:
            runner._stop()
        except DaemonRunnerStopFailureError:
            raise click.ClickException('{} does not seem to be running'.format(service.name))

    else:
        raise click.ClickException('Failed to load {}'.format(service))


@main.command()
@click.pass_context
@click.option('-r', '--remote', is_flag=True, default=False, help='Include available services from online repository')
def list(ctx, remote):
    """
        shows the contents of the local repository including versions
        optionally also lists all available package in online repository
    """
    logger.debug('in command: {}'.format(ctx.command.name))
    installed_services = []
    click.secho('[*] Installed services:', fg='green')
    service = None
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

        try:
            info = get_local_svn_info(os.path.join(ctx.obj['HOME'], service_dir))
            s += ' (version: {0:d}, updated: {1:%Y}{1:%m}{1:%d})'.format(info['commit_revision'], info['commit_date'])
        except svn.exception.SvnException:
            s += ' (local package)'
        click.secho(s)
    if not service:
        click.secho('[*] You do not have any services installed, try installing one with `{} install`'
                    .format(os.path.basename(__file__)))

    if remote:
        click.secho('\n[*] Additional services from online repository:', fg='green')
        try:
            logger.debug('fetching services from remote repo')
            rsvn = svn.remote.RemoteClient(SVN_URL.format(service=''))
            for sinfo in rsvn.list(extended=True):
                logger.debug(sinfo)
                if sinfo['is_directory'] and sinfo['name'] not in installed_services:
                    click.secho('{0} (version: {1:d}, updated: {2:%Y}{2:%m}{2:%d})'
                                .format(sinfo['name'], sinfo['commit_revision'], sinfo['date']))

        except svn.exception.SvnException:
            click.ClickException('Unable to fetch information from online repository')
    else:
        click.secho('\n[*] try running `honeycomb list -r` to see services available from our repository', fg='green')


@main.command()
@click.pass_context
@click.argument('pkg')
@click.option('-r', '--remote', is_flag=True, default=False, help='Show information only from remote repository')
def show(ctx, pkg, remote):
    """shows detailed information about a package"""
    logger.debug('in command: {}'.format(ctx.command.name))

    def get_remote_info(pkgname):
        info = {}
        try:
            rinfo = get_remote_svn_info(SVN_URL.format(service=pkg))
            info['commit_date'] = "{0:%Y}{0:%m}{0:%d}".format(rinfo['commit_date'])
            info['commit_revision'] = rinfo['commit_revision']
        except svn.exception.SvnException:
            raise click.ClickException('Cannot connect to online repository')

        return info

    def collect_local_info(pkg, pkgpath):
        logger.debug('loading {} from {}'.format(pkg, pkgpath))
        service = hc.register_custom_service(pkgpath)
        try:
            with open(os.path.join(pkgpath, 'requirements.txt'), 'r') as fh:
                info['requirements'] = ' '.join(fh.readlines())
        except IOError:
            pass
        info['name'] = service.name
        info['label'] = service.label
        info['location'] = pkgpath
        try:
            linfo = get_local_svn_info(os.path.join(ctx.obj['HOME'], pkgpath))
            info['commit_date'] = "{0:%Y}{0:%m}{0:%d}".format(linfo['commit_date'])
            info['commit_revision'] = linfo['commit_revision']
        except svn.exception.SvnException:
            pass

        return info

    def collect_remote_info(pkg):
        info.update(get_remote_info(pkg))
        try:
            r = requests.get(GITHUB_RAW_URL.format(service=pkg, filename='config.json'))
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
            r = requests.get(GITHUB_RAW_URL.format(service=pkg, filename='requirements.txt'))
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


def install_deps(pkgpath):
    if os.path.exists(os.path.join(pkgpath, 'requirements.txt')):
        logger.debug('installing dependencies')
        click.secho('[*] Installing dependencies', fg='green')
        pipargs = ['install', '--target', os.path.join(pkgpath, DEPS_DIR), '--ignore-installed',
                   '-r', os.path.join(pkgpath, 'requirements.txt')]
        logger.debug('running pip {}'.format(pipargs))
        return pip.main(pipargs)
    return 0


def install_dir(ctx, pkgpath, delete_after_install):
    logger.debug('{} is a directory, attempting to validate'.format(pkgpath))
    service = hc.register_custom_service(pkgpath)
    logger.debug('{} looks good, copying to {}'.format(pkgpath, ctx.obj['HOME']))
    try:
        shutil.copytree(pkgpath, os.path.join(ctx.obj['HOME'], service.name))
        if delete_after_install:
            logger.debug('deleting {}'.format(pkgpath))
            shutil.rmtree(pkgpath)
        pkgpath = os.path.join(ctx.obj['HOME'], service.name)
    except OSError as e:
        logger.exception(str(e))
        raise click.ClickException('Sorry, already have a service called {}, try deleting it first.'
                                   .format(service.name))

    return install_deps(pkgpath)


def install_from_file(ctx, pkgpath):
    logger.debug('{} is a file, atttempting to load zip'.format(pkgpath))
    pkgtempdir = tempfile.mkdtemp(prefix='honeycomb_')
    try:
        with zipfile.ZipFile(pkgpath, 'r') as pkgzip:
            pkgzip.extractall(pkgtempdir)
    except zipfile.BadZipfile as e:
        logger.error('{} is not a zip file'.format(pkgpath))
        raise click.ClickException(str(e))
    logger.debug('installing from unzipped folder {}'.format(pkgtempdir))
    return install_dir(ctx, pkgtempdir, delete_after_install=True)


def install_from_svn(ctx, pkgname):
    logger.debug('trying to install {} from SVN'.format(pkgname))
    r = svn.remote.RemoteClient(SVN_URL.format(service=pkgname))
    pkgtempdir = tempfile.mkdtemp(prefix='honeycomb_')
    try:
        r.checkout(pkgtempdir)
        return install_dir(ctx, pkgtempdir, delete_after_install=True)
    except svn.exception.SvnException as e:
        logger.debug(str(e))
        click.ClickException('[-] Cannot find {} in online repository'.format(pkgname))


@main.command()
@click.pass_context
@click.argument('pkgs', nargs=-1)
def install(ctx, pkgs, delete_after_install=False):
    """get a particular honeypot from the online library or install from local directory or zipfile"""
    logger.debug('in command: {}'.format(ctx.command.name))
    # TODO:
    # handle package name exists in HOME (upgrade? overwrite?)

    for pkgpath in pkgs:
        if os.path.exists(pkgpath):
            logger.debug('{} exists in filesystem'.format(pkgpath))
            if os.path.isdir(pkgpath):
                pip_status = install_dir(ctx, pkgpath, delete_after_install)
            else:  # pkgpath is file
                pip_status = install_from_file(ctx, pkgpath)
        else:
            click.secho('Collecting {}...'.format(pkgpath))
            logger.debug('cannot find {} locally, checking github repo'.format(pkgpath))
            pip_status = install_from_svn(ctx, pkgpath)

        if pip_status == 0:
            click.secho('[+] Success! now try using `honeycomb run {}`'
                        .format(os.path.basename(pkgpath)), fg='green')
        else:
            click.secho('[-] Service installed but something went wrong with dependency install, please review logs')


@main.command()
@click.pass_context
@click.option('-y', '--yes', is_flag=True, default=False, help='Don\'t ask for confirmation of uninstall deletions.')
@click.argument('pkgs', nargs=-1)
def uninstall(ctx, yes, pkgs):
    """delete a local honeypot"""
    logger.debug('in command: {}'.format(ctx.command.name))

    for pkgname in pkgs:
        pkgpath = os.path.join(ctx.obj['HOME'], pkgname)
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


@main.command()
def upgrade():
    """gets the newest version of a particular honeypot"""


@main.command()
def install_all():
    """gets all the honeypots from the online library"""


@main.command()
def upgrade_all():
    """upgrades all the local honeypots"""


def setup_logging(home, verbose):
    logging.config.dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "console": {
                "format": '%(levelname)-8s [%(asctime)s %(module)s] %(filename)s:%(lineno)s %(funcName)s: %(message)s',
            },
            "json": {
                "()": jsonlogger.JsonFormatter,
                "format": '%(levelname)s %(asctime)s %(module)s %(filename)s %(lineno)s %(funcName)s %(message)s',
            },
        },
        "handlers": {
            "default": {
                "level": "DEBUG" if verbose else "INFO",
                "class": "logging.StreamHandler",
                "formatter": "console",
            },
            "file": {
                "level": "DEBUG",
                "class": "logging.handlers.WatchedFileHandler",
                "filename": os.path.join(home, 'honeycomb.debug.log'),
                "formatter": "json",
            },
        },
        "loggers": {
            "": {
                "handlers": ["default", "file"],
                "level": "DEBUG",
                "propagate": True,
            },
        }
    })

    return logging.getLogger(__name__)


def get_local_svn_info(path):
    logger.debug('loading local SVN info from {}'.format(path))
    lsvn = svn.local.LocalClient(path)
    return lsvn.info()


def get_remote_svn_info(repo_url):
    logger.debug('loading remote SVN info from {}'.format(repo_url))
    rsvn = svn.remote.RemoteClient(repo_url)
    return rsvn.info()


def mkhome(home):
    home = os.path.realpath(home)
    try:
        if not os.path.exists(home):
            os.mkdir(home)
    except OSError as e:
        raise click.ClickException('Unable to create Honeycomb repository {}'.format(str(e)))
