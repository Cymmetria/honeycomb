# -*- coding: utf-8 -*-
from __future__ import absolute_import

import os
import json
import signal
import tempfile
import requests
import subprocess
from multiprocessing import Process
from requests.adapters import HTTPAdapter

import pytest
from click.testing import CliRunner

from honeycomb import cli
from .utils.wait import wait_until
from .utils.syslog import runSyslogServer

RUN_HONEYCOMB = 'coverage run --parallel-mode --module --source=honeycomb honeycomb'
JSON_LOG_FILE = tempfile.mkstemp()[1]
DEBUG_LOG_FILE = 'honeycomb.debug.log'
SYSLOG_HOST = '127.0.0.1'
SYSLOG_PORT = 5514
rsession = requests.Session()
rsession.mount('https://', HTTPAdapter(max_retries=3))


@pytest.fixture
def simple_http_installed(tmpdir):
    """prepared honeycomb home path with simple_http installed"""
    CliRunner().invoke(cli.main, args=['--iamroot', '--home', str(tmpdir), 'install', 'sample_services/simple_http'])
    yield str(tmpdir)
    CliRunner().invoke(cli.main, args=['--iamroot', '--home', str(tmpdir), 'uninstall', '-y', 'simple_http'])


@pytest.fixture
def running_service(simple_http_installed, request):
    cmd = [RUN_HONEYCOMB, '--iamroot', '--home', simple_http_installed] + request.param
    p = subprocess.Popen(' '.join(cmd), shell=True, env=os.environ.copy())
    yield simple_http_installed
    p.send_signal(signal.SIGINT)
    p.wait()


@pytest.fixture
def syslog(tmpdir):
    logfile = tmpdir.join('syslog.log')
    p = Process(target=runSyslogServer, args=(SYSLOG_HOST, SYSLOG_PORT, logfile))
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
    result = CliRunner().invoke(cli.main, args=['--help'])
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
    result = CliRunner().invoke(cli.main, args=['--iamroot', '--home', str(tmpdir), 'install', service])
    assert result.exit_code == 0
    assert not result.exception

    # uninstall
    result = CliRunner().invoke(cli.main, input='y', args=['--iamroot', '--home', str(tmpdir), 'uninstall', service])
    assert result.exit_code == 0
    assert not result.exception

    assert json_log_is_valid(tmpdir)


def test_list_nothing_installed(tmpdir):
    result = CliRunner().invoke(cli.main, args=['--iamroot', '--home', str(tmpdir), 'list'])
    assert result.exit_code == 0
    assert json_log_is_valid(str(tmpdir))


def test_list_remote(tmpdir):
    result = CliRunner().invoke(cli.main, args=['--iamroot', '--home', str(tmpdir), 'list', '--remote'])
    assert 'simple_http' in result.output
    assert result.exit_code == 0
    assert not result.exception
    assert json_log_is_valid(tmpdir)


@pytest.mark.dependency(depends=['install_uninstall'])
def test_list_local(simple_http_installed):
    result = CliRunner().invoke(cli.main, args=['--iamroot', '--home', simple_http_installed, 'list'])
    assert 'simple_http (8888/TCP) [Alerts: simple_http]' in result.output
    assert result.exit_code == 0
    assert not result.exception
    assert json_log_is_valid(simple_http_installed)


def test_show_remote_not_installed(tmpdir):
    result = CliRunner().invoke(cli.main, args=['--iamroot', '--home', str(tmpdir), 'show', 'simple_http'])
    assert 'Installed: False' in result.output
    assert 'Name: simple_http' in result.output
    assert result.exit_code == 0
    assert not result.exception
    assert json_log_is_valid(tmpdir)


@pytest.mark.dependency(depends=['install_uninstall'])
def test_show_local_installed(simple_http_installed):
    result = CliRunner().invoke(cli.main, args=['--iamroot', '--home', simple_http_installed, 'show', 'simple_http'])
    assert 'Installed: True' in result.output
    assert 'Name: simple_http' in result.output
    assert result.exit_code == 0
    assert not result.exception
    assert json_log_is_valid(simple_http_installed)


def test_show_nonexistent(tmpdir):
    result = CliRunner().invoke(cli.main, args=['--iamroot', '--home', str(tmpdir), 'show', 'this_should_never_exist'])
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
@pytest.mark.parametrize('running_service', [['run', 'simple_http', '-j', JSON_LOG_FILE]], indirect=['running_service'])
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
                                              '--syslog-port', str(SYSLOG_PORT)]], indirect=['running_service'])
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


@pytest.mark.dependency(depends=['run', 'install_uninstall'])
def test_daemon(simple_http_installed):
    cmd = [RUN_HONEYCOMB, '--iamroot', '--home', simple_http_installed, 'run', '--daemon', 'simple_http']
    p = subprocess.Popen(' '.join(cmd), shell=True, env=os.environ.copy())
    p.wait()
    assert p.returncode == 0
    assert wait_until(search_json_log, filepath=os.path.join(simple_http_installed, DEBUG_LOG_FILE), total_timeout=10,
                      key='message', value='Starting Simple HTTP service on port: 8888')

    r = rsession.get('http://localhost:8888')
    assert 'Welcome to nginx!' in r.text

    result = CliRunner().invoke(cli.main, args=['--iamroot', '--home', simple_http_installed, 'stop', 'simple_http'])
    assert result.exit_code == 0
    assert not result.exception

    try:
        r = rsession.get('http://localhost:8888')
        assert False, 'Service is still available (make sure to properly kill it before testing again)'
    except requests.exceptions.ConnectionError:
        assert True
