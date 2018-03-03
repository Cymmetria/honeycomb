# -*- coding: utf-8 -*-
from __future__ import absolute_import

import os
import sys
import pip
import json
import ctypes
import shutil
import socket
import logging
import zipfile
import requests
import tempfile
import importlib
from requests.adapters import HTTPAdapter

import click
import daemon.runner
import daemon.daemon
from pythonjsonlogger import jsonlogger

import honeycomb.honeycomb
from honeycomb import __version__
from honeycomb.utils import defs
from honeycomb.utils.wait import wait_until
from honeycomb.utils.cef_handler import CEFSyslogHandler

hc = honeycomb.honeycomb.Honeycomb()
logger = None
DEPS_DIR = 'venv'
GITHUB_URL = 'https://github.com/Cymmetria/honeycomb_services/tree/master/{service}'
GITHUB_RAW = 'https://cymmetria.github.io/honeycomb_services/'
GITHUB_RAW_URL = 'https://raw.githubusercontent.com/Cymmetria/honeycomb_services/master/{service}/{filename}'
PKG_INFO_TEMPLATE = """Name: {name}
Installed: {installed}
Version: {commit_revision} Updated: {commit_date}
Summary: {label}
Location: {location}
Requires: {requirements}"""
rsession = requests.Session()
rsession.mount('https://', HTTPAdapter(max_retries=3))
CONTEXT_SETTINGS = dict(
    obj={},
    auto_envvar_prefix="HC",  # all parameters will be taken from HC_PARAMETER first
    max_content_width=120,
)


class myRunner(daemon.runner.DaemonRunner):
    """overriding default runner behaviour to be simpler"""
    def __init__(self, app, pidfile=None, stdout=sys.stdout, stderr=sys.stderr, stdin=open('/dev/null', 'rt')):
        self.app = app
        self.daemon_context = daemon.daemon.DaemonContext()
        self.daemon_context.stdin = stdin
        self.daemon_context.stdout = stdout
        self.daemon_context.stderr = stderr
        self.app.pidfile_path = pidfile
        self.pidfile = None
        if self.app.pidfile_path is not None:
            self.pidfile = daemon.runner.make_pidlockfile(self.app.pidfile_path, 3)
        self.daemon_context.pidfile = self.pidfile


@click.group(context_settings=CONTEXT_SETTINGS)
@click.pass_context
@click.option('--home', '-h', default=os.path.realpath(os.path.expanduser('~/.honeycomb')),
              help='Path Honeycomb repository', type=click.Path())
@click.option('--iamroot', is_flag=True, default=False, help='Force run as root (NOT RECOMMENDED!)')
@click.option('--verbose', '-v', envvar="DEBUG", is_flag=True, default=False, help='Enable verbose logging')
def main(ctx, home, iamroot, verbose):
    """Homeycomb is a honeypot framework"""
    global logger
    mkhome(home)
    logger = setup_logging(home, verbose)

    logger.debug('Starting up Honeycomb v{}'.format(__version__))
    logger.debug('in command: {} {}'.format(ctx.command.name, ctx.params))

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


@main.command(short_help='Load and run a specific service')
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
    """load and run a specific service"""
    home = ctx.obj['HOME']
    if editable:
        service_path = os.path.realpath(service)
    else:
        service_path = os.path.join(home, service)
    service_log_path = os.path.join(service_path, 'logs')

    def print_args(service):
        args = hc.get_parameters(service_path)
        args_format = '{:15} {:10} {:^15} {:^10} {:25}'
        title = args_format.format(defs.NAME.upper(), defs.TYPE.upper(), defs.DEFAULT.upper(),
                                   defs.REQUIRED.upper(), defs.DESCRIPTION.upper())
        click.secho(title)
        click.secho("-" * len(title))
        for arg in args:
            help_text = " ({}}".format(arg[defs.HELP_TEXT]) if defs.HELP_TEXT in arg else ''
            click.secho(args_format.format(arg[defs.VALUE], arg[defs.TYPE], str(arg.get(defs.DEFAULT, None)),
                                           str(arg.get(defs.REQUIRED, False)), arg[defs.LABEL] + help_text))

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
    service_module = get_service_module(service_path, service.name)
    service_args = hc.parse_service_args(arg, hc.get_parameters(service_path))
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


@main.command(short_help='Stop a running service daemon')
@click.pass_context
@click.argument('service')
def stop(ctx, service):
    """stop a running service daemon"""
    logger.debug('in command: {} {}'.format(ctx.command.name, ctx.params))
    home = ctx.obj['HOME']

    logger.debug('loading {}'.format(service))
    service = hc.register_custom_service(os.path.join(home, service))

    # get our service class instance
    service_module = get_service_module(home, service.name)
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


@main.command(short_help='List available services')
@click.pass_context
@click.option('-r', '--remote', is_flag=True, default=False, help='Include available services from online repository')
def list(ctx, remote):
    """
        shows the contents of the local repository including versions
        optionally also lists all available package in online repository
    """
    logger.debug('in command: {} {}'.format(ctx.command.name, ctx.params))
    installed_services = []
    click.secho('[*] Installed services:')
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
        click.secho(s)
    if not service:
        click.secho('[*] You do not have any services installed, try installing one with `honeycomb install`')

    if remote:
        click.secho('\n[*] Additional services from online repository:')
        try:
            r = rsession.get(GITHUB_RAW + '/services.txt')
            logger.debug('fetching services from remote repo')
            click.secho(r.text)

        except requests.exceptions.ConnectionError:
            raise click.ClickException('Unable to fetch information from online repository')
    else:
        click.secho('\n[*] try running `honeycomb list -r` to see services available from our repository')


@main.command(short_help='Shows status of installed service(s)')
@click.pass_context
@click.argument('services', nargs=-1)
@click.option('-a', '--show-all', is_flag=True, default=False, help='Show status for all services')
def status(ctx, services, show_all):
    """shows status of installed service(s)"""
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


@main.command(short_help='Show detailed information about a service')
@click.pass_context
@click.argument('pkg')
@click.option('-r', '--remote', is_flag=True, default=False, help='Show information only from remote repository')
def show(ctx, pkg, remote):
    """shows detailed information about a package"""
    logger.debug('in command: {} {}'.format(ctx.command.name, ctx.params))

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

        return info

    def collect_remote_info(pkg):
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


@main.command(short_help='Install a service')
@click.pass_context
@click.argument('pkgs', nargs=-1)
def install(ctx, pkgs, delete_after_install=False):
    """get a particular honeypot from the online library or install from local directory or zipfile"""
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
        logger.debug('trying to install {} from online repo'.format(pkgname))
        pkgurl = '{}/{}.zip'.format(GITHUB_RAW, pkgname)
        try:
            r = rsession.head(pkgurl)
            r.raise_for_status()
            total_size = int(r.headers.get('content-length', 0))
            pkgsize = sizeof_fmt(total_size)
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


@main.command(short_help='Uninstall a service')
@click.pass_context
@click.option('-y', '--yes', is_flag=True, default=False, help='Don\'t ask for confirmation of uninstall deletions.')
@click.argument('pkgs', nargs=-1)
def uninstall(ctx, yes, pkgs):
    """Uninstall a service"""
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


@main.command(short_help='Test a running service')
@click.pass_context
@click.argument('services', nargs=-1)
@click.option('-f', '--force', is_flag=True, default=False, help='Do not check if service is running before testing')
@click.option('-e', '--editable', is_flag=True, default=False,
              help='Run service directly from spefified path (main for dev)')
def test(ctx, services, force, editable):
    """
    execute the service's internal test method to verify it's working as intended
    if there's no such method, honeycomb will attempt to connect to the port listed in config.json
    """
    logger.debug('in command: {} {}'.format(ctx.command.name, ctx.params))
    home = ctx.obj['HOME']

    for service in services:
        if editable:
            service_path = os.path.realpath(service)
        else:
            service_path = os.path.join(home, service)

        logger.debug('loading {} ({})'.format(service, service_path))
        click.secho('[+] Loading {}'.format(service))
        service = hc.register_custom_service(service_path)
        service_module = get_service_module(service_path, service.name)

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
                assert wait_until(search_json_log, filepath=os.path.join(home, defs.DEBUG_LOG_FILE),
                                  total_timeout=10, key=defs.EVENT_TYPE, value=event_type), ''
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
                "filename": os.path.join(home, defs.DEBUG_LOG_FILE),
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


def mkhome(home):
    home = os.path.realpath(home)
    try:
        if not os.path.exists(home):
            os.mkdir(home)
    except OSError as e:
        raise click.ClickException('Unable to create Honeycomb repository {}'.format(str(e)))


def sizeof_fmt(num, suffix='B'):
    if not num:
        return 'unknown size'
    for unit in ['', 'K', 'M', 'G', 'T', 'P', 'E', 'Z']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s".format(num, 'Yi', suffix)


def get_service_module(service_path, service_name):
    # add custom paths so imports would work
    sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
    sys.path.insert(0, os.path.join(service_path, DEPS_DIR))
    sys.path.insert(0, os.path.join(service_path, '..'))

    # get our service class instance
    return importlib.import_module(".".join([service_name, service_name + '_service']))


def search_json_log(filepath, key, value):
    with open(filepath, 'r') as fh:
        for line in fh.readlines():
                log = json.loads(line)
                if key in log and log[key] == value:
                    return log
        return False
