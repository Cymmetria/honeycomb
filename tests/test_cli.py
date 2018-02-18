# -*- coding: utf-8 -*-
from __future__ import absolute_import

import os
import json
import logging
import tempfile
import requests
from multiprocessing import Process
from requests.adapters import HTTPAdapter

import pytest
from click.testing import CliRunner

from honeycomb import cli
from .utils.wait import wait_until
from .utils.syslog import runSyslogServer

JSON_LOG_FILE = tempfile.mkstemp()[1]
DEBUG_LOG_FILE = 'honeycomb.debug.log'
SYSLOG_HOST = '127.0.0.1'
SYSLOG_PORT = 5514
rsession = requests.Session()
rsession.mount('https://', HTTPAdapter(max_retries=3))


@pytest.fixture(autouse=True)
def collect_logs(caplog):
    caplog.set_level(logging.DEBUG, logger='root')


@pytest.fixture
def simple_http_installed(tmpdir):
    """prepared honeycomb home path with simple_http installed"""
    CliRunner().invoke(cli.main, obj={}, args=['--home', str(tmpdir), 'install', 'simple_http'])
    yield str(tmpdir)
    CliRunner().invoke(cli.main, obj={}, args=['--home', str(tmpdir), 'uninstall', '-y', 'simple_http'])


@pytest.fixture
def simple_http_installed_locally(tmpdir):
    """prepared honeycomb home path with simple_http installed"""
    CliRunner().invoke(cli.main, obj={}, args=['--home', str(tmpdir), 'install', 'sample_services/simple_http'])
    yield str(tmpdir)
    CliRunner().invoke(cli.main, obj={}, args=['--home', str(tmpdir), 'uninstall', '-y', 'simple_http'])


@pytest.fixture
def running_service(simple_http_installed, request):
    args = ['--home', simple_http_installed] + request.param
    p = Process(target=CliRunner().invoke, kwargs={'cli': cli.main, 'obj': {},
                                                   'args': args})
    p.daemon = True
    p.start()
    yield simple_http_installed
    p.terminate()


@pytest.fixture
def syslog(tmpdir):
    logfile = tmpdir.join('syslog.log')
    p = Process(target=runSyslogServer, args=(SYSLOG_HOST, SYSLOG_PORT, logfile))
    p.daemon = True
    p.start()
    yield str(logfile)
    p.terminate()


def json_log_is_valid(path):
    with open(os.path.join(str(path), 'honeycomb.debug.log'), 'r') as fh:
        for line in fh.readlines():
                try:
                    json.loads(line)
                except json.decoder.JSONDecodeError:
                    return False
    return True


def search_file_log(filepath, method, args):
    with open(filepath, 'r') as fh:
        for line in fh.readlines():
                cmd = getattr(line, method)
                if cmd(args):
                    return line
        return False


def search_json_log(filepath, key, value):
    with open(filepath, 'r') as fh:
        for line in fh.readlines():
                log = json.loads(line)
                if key in log and log[key] == value:
                    return log
        return False


def test_cli_help():
    result = CliRunner().invoke(cli.main, obj={}, args=['--help'])
    assert result.exit_code == 0
    assert not result.exception


@pytest.mark.dependency(name='install_uninstall')
@pytest.mark.parametrize("service", [
    'simple_http',  # install from online repo
    'sample_services/simple_http',  # install from local folder
    'sample_services/simple_http.zip',  # install from local zip
])
def test_install_uninstall(tmpdir, service):
    # install
    result = CliRunner().invoke(cli.main, obj={}, args=['--home', str(tmpdir), 'install', service])
    assert result.exit_code == 0
    assert not result.exception

    # uninstall
    result = CliRunner().invoke(cli.main, obj={}, input='y', args=['--home', str(tmpdir), 'uninstall', service])
    assert result.exit_code == 0
    assert not result.exception

    assert json_log_is_valid(tmpdir)


def test_list_nothing_installed(tmpdir):
    result = CliRunner().invoke(cli.main, obj={}, args=['--home', str(tmpdir), 'list'])
    assert result.exit_code == 0
    assert json_log_is_valid(str(tmpdir))


def test_list_remote(tmpdir):
    result = CliRunner().invoke(cli.main, obj={}, args=['--home', str(tmpdir), 'list', '--remote'])
    assert 'simple_http' in result.output
    assert result.exit_code == 0
    assert not result.exception
    assert json_log_is_valid(tmpdir)


@pytest.mark.dependency(depends=['install_uninstall'])
def test_list_local(simple_http_installed_locally):
    result = CliRunner().invoke(cli.main, obj={}, args=['--home', simple_http_installed_locally, 'list'])
    assert 'simple_http (8888/TCP) [Alerts: simple_http]' in result.output
    assert result.exit_code == 0
    assert not result.exception
    assert json_log_is_valid(simple_http_installed_locally)


def test_show_remote_not_installed(tmpdir):
    result = CliRunner().invoke(cli.main, obj={}, args=['--home', str(tmpdir), 'show', 'simple_http'])
    assert 'Installed: False' in result.output
    assert 'Name: simple_http' in result.output
    assert result.exit_code == 0
    assert not result.exception
    assert json_log_is_valid(tmpdir)


@pytest.mark.dependency(depends=['install_uninstall'])
def test_show_local_installed(simple_http_installed_locally):
    result = CliRunner().invoke(cli.main, obj={}, args=['--home', simple_http_installed_locally, 'show', 'simple_http'])
    assert 'Installed: True' in result.output
    assert 'Name: simple_http' in result.output
    assert result.exit_code == 0
    assert not result.exception
    assert json_log_is_valid(simple_http_installed_locally)


def test_show_nonexistent(tmpdir):
    result = CliRunner().invoke(cli.main, obj={}, args=['--home', str(tmpdir), 'show', 'this_should_never_exist'])
    assert result.exit_code != 0
    assert result.exception
    assert json_log_is_valid(str(tmpdir))


@pytest.mark.dependency(name='run', depends=['install_uninstall'])
@pytest.mark.parametrize('running_service', [['run', 'simple_http']], indirect=['running_service'])
def test_run(running_service):
    assert wait_until(search_json_log, filepath=os.path.join(running_service, DEBUG_LOG_FILE), total_timeout=10,
                      key='message', value='Starting Simple HTTP service on port: 8888')

    r = rsession.get('http://localhost:8888')
    assert 'Welcome to nginx!' in r.text


@pytest.mark.dependency(depends=['run', 'install_uninstall'])
@pytest.mark.parametrize('running_service', [['run', 'simple_http', '-j', JSON_LOG_FILE,
                                              '--syslog', '--syslog-host', SYSLOG_HOST,
                                              '--syslog-port', SYSLOG_PORT]], indirect=['running_service'])
def test_json_log(running_service):
    assert wait_until(search_json_log, filepath=os.path.join(running_service, DEBUG_LOG_FILE), total_timeout=10,
                      key='message', value='Starting Simple HTTP service on port: 8888')
    r = rsession.get('http://localhost:8888')
    assert 'Welcome to nginx!' in r.text

    json_log = wait_until(search_json_log, filepath=JSON_LOG_FILE, total_timeout=10,
                          key='event_type', value='simple_http')

    assert json_log['request'] == 'GET /'


@pytest.mark.dependency(depends=['run', 'install_uninstall'])
@pytest.mark.parametrize('running_service', [['run', 'simple_http', '--syslog',
                                              '--syslog-host', SYSLOG_HOST,
                                              '--syslog-port', SYSLOG_PORT]], indirect=['running_service'])
def test_syslog(running_service, syslog):
    assert wait_until(search_json_log, filepath=os.path.join(running_service, DEBUG_LOG_FILE), total_timeout=10,
                      key='message', value='Starting Simple HTTP service on port: 8888')
    r = rsession.get('http://localhost:8888')
    assert 'Welcome to nginx!' in r.text

    assert wait_until(search_file_log, filepath=syslog, total_timeout=10,
                      method='find', args='act=simple_http')

    assert wait_until(search_file_log, filepath=syslog, total_timeout=10,
                      method='find', args='request=GET /')

    assert wait_until(search_file_log, filepath=syslog, total_timeout=10,
                      method='find', args='src=127.0.0.1')
