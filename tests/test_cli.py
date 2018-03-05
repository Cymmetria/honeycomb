# -*- coding: utf-8 -*-
"""Honeycomb tests."""
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

from honeycomb.cli import cli
from honeycomb.utils.wait import wait_until
from honeycomb.utils.defs import DEBUG_LOG_FILE
from .utils.syslog import runSyslogServer

DEMO_SERVICE = 'simple_http'
DEMO_SERVICE_PORT = '8888/TCP'
DEMO_SERVICE_ALERT = 'simple_http'
RUN_HONEYCOMB = 'coverage run --parallel-mode --module --source=honeycomb honeycomb'.split(' ')
JSON_LOG_FILE = tempfile.mkstemp()[1]
SYSLOG_HOST = '127.0.0.1'
SYSLOG_PORT = 5514
rsession = requests.Session()
rsession.mount('https://', HTTPAdapter(max_retries=3))


@pytest.fixture
def service_installed(tmpdir):
    """Prepare honeycomb home path with DEMO_SERVICE installed."""
    CliRunner().invoke(cli, args=['--iamroot', '--home', str(tmpdir),
                       'install', 'sample_services/{}'.format(DEMO_SERVICE)])
    yield str(tmpdir)
    CliRunner().invoke(cli, args=['--iamroot', '--home', str(tmpdir), 'uninstall', '-y', DEMO_SERVICE])


@pytest.fixture
def running_service(service_installed, request):
    """Provide a running instance with :func:`service_installed`."""
    args = '--verbose --iamroot --home {} run {}'.format(service_installed, DEMO_SERVICE).split(' ')
    cmd = RUN_HONEYCOMB + args + request.param
    env = os.environ.copy()
    env.update({'DEBUG': '1'})
    p = subprocess.Popen(cmd, env=env)
    assert wait_until(search_json_log, filepath=os.path.join(service_installed, DEBUG_LOG_FILE), total_timeout=10,
                      key='message', value='Starting Simple HTTP service on port: 8888')
    yield service_installed
    p.send_signal(signal.SIGINT)
    p.wait()

    try:
        rsession.get('http://localhost:8888')
        assert False, 'Service is still available (make sure to properly kill it before repeating test)'
    except requests.exceptions.ConnectionError:
        assert True


@pytest.fixture
def running_daemon(service_installed, request):
    """Provide a running daemon with :func:`service_installed`."""
    args = '--verbose --iamroot --home {} run -d {}'.format(service_installed, DEMO_SERVICE).split(' ')
    cmd = RUN_HONEYCOMB + args + request.param
    env = os.environ.copy()
    env.update({'DEBUG': '1'})
    p = subprocess.Popen(cmd, env=env)
    p.wait()
    assert p.returncode == 0
    assert wait_until(search_json_log, filepath=os.path.join(service_installed, DEBUG_LOG_FILE), total_timeout=10,
                      key='message', value='Starting Simple HTTP service on port: 8888')

    yield service_installed

    result = CliRunner().invoke(cli, args=['--iamroot', '--home', service_installed, 'stop', DEMO_SERVICE])
    assert result.exit_code == 0
    assert not result.exception

    try:
        rsession.get('http://localhost:8888')
        assert False, 'Service is still available (make sure to properly kill it before repeating test)'
    except requests.exceptions.ConnectionError:
        assert True


@pytest.fixture
def syslog(tmpdir):
    """Provide generic syslog server fixture."""
    logfile = tmpdir.join('syslog.log')
    p = Process(target=runSyslogServer, args=(SYSLOG_HOST, SYSLOG_PORT, logfile))
    p.start()
    yield str(logfile)
    p.terminate()


def json_log_is_valid(path):
    """Validate a json file.

    :param path: valid path to json file
    """
    with open(os.path.join(str(path), 'honeycomb.debug.log'), 'r') as fh:
        for line in fh.readlines():
                try:
                    json.loads(line)
                except json.decoder.JSONDecodeError:
                    return False
    return True


def search_file_log(filepath, method, args):
    """Search a log file by executing a string method on its lines.

    :param filepath: Valid path to a log file
    :param method: A valid :py:module:`string` method
    :param args: Arguments to above method
    :returns: First matching line in log file
    """
    with open(filepath, 'r') as fh:
        for line in fh.readlines():
                cmd = getattr(line, method)
                if cmd(args):
                    return line
        return False


def search_json_log(filepath, key, value):
    """Search json log file for a key=value pair.

    :param filepath: Valid path to a json file
    :param key: key to match
    :param value: value to match
    :returns: First matching line in json log file, parsed by :py:func:`json.loads`
    """
    with open(filepath, 'r') as fh:
        for line in fh.readlines():
                log = json.loads(line)
                if key in log and log[key] == value:
                    return log
        return False


def test_cli_help():
    """Test honeycomb launches without an error (tests :func:`honeycomb.cli`)."""
    result = CliRunner().invoke(cli, args=['--help'])
    assert result.exit_code == 0
    assert not result.exception


@pytest.mark.dependency(name='install_uninstall')
@pytest.mark.parametrize("service", [
    DEMO_SERVICE,  # install from online repo
    'sample_services/{}'.format(DEMO_SERVICE),  # install from local folder
    'sample_services/{}.zip'.format(DEMO_SERVICE),  # install from local zip
])
def test_install_uninstall(tmpdir, service):
    """Test the :func:`honeycomb.cli.install` and :func:`honeycomb.cli.uninstall` commmands."""
    # install
    result = CliRunner().invoke(cli, args=['--iamroot', '--home', str(tmpdir), 'install', service])
    assert result.exit_code == 0
    assert not result.exception

    # uninstall
    result = CliRunner().invoke(cli, input='y', args=['--iamroot', '--home', str(tmpdir), 'uninstall', service])
    assert result.exit_code == 0
    assert not result.exception

    assert json_log_is_valid(tmpdir)


def test_list_nothing_installed(tmpdir):
    """Test the :func:`honeycomb.cli.list` command when nothing is installed."""
    result = CliRunner().invoke(cli, args=['--iamroot', '--home', str(tmpdir), 'list'])
    assert result.exit_code == 0
    assert json_log_is_valid(str(tmpdir))


def test_list_remote(tmpdir):
    """Test the :func:`honeycomb.cli.list` command and also show services from remote repository."""
    result = CliRunner().invoke(cli, args=['--iamroot', '--home', str(tmpdir), 'list', '--remote'])
    assert DEMO_SERVICE in result.output, bytes(result.output)
    assert result.exit_code == 0
    assert not result.exception
    assert json_log_is_valid(tmpdir)


@pytest.mark.dependency(depends=['install_uninstall'])
def test_list_local(service_installed):
    """Test the :func:`honeycomb.cli.list` command with a service installed."""
    result = CliRunner().invoke(cli, args=['--iamroot', '--home', service_installed, 'list'])
    assert '{} ({}) [Alerts: {}]'.format(DEMO_SERVICE, DEMO_SERVICE_PORT,
                                         DEMO_SERVICE_ALERT) in result.output, bytes(result.output)
    assert result.exit_code == 0
    assert not result.exception
    assert json_log_is_valid(service_installed)


def test_show_remote_not_installed(tmpdir):
    """Test the :func:`honeycomb.cli.show` command to show information from remote repository."""
    result = CliRunner().invoke(cli, args=['--iamroot', '--home', str(tmpdir), 'show', DEMO_SERVICE])
    assert 'Installed: False' in result.output, bytes(result.output)
    assert 'Name: {}'.format(DEMO_SERVICE) in result.output, bytes(result.output)
    assert result.exit_code == 0
    assert not result.exception
    assert json_log_is_valid(tmpdir)


@pytest.mark.dependency(depends=['install_uninstall'])
def test_show_local_installed(service_installed):
    """Test the :func:`honeycomb.cli.show` command to show information about locally installe service."""
    result = CliRunner().invoke(cli, args=['--iamroot', '--home', service_installed, 'show', DEMO_SERVICE])
    assert 'Installed: True' in result.output, bytes(result.output)
    assert 'Name: {}'.format(DEMO_SERVICE) in result.output, bytes(result.output)
    assert result.exit_code == 0
    assert not result.exception
    assert json_log_is_valid(service_installed)


def test_show_nonexistent(tmpdir):
    """Test the :func:`honeycomb.cli.test` command to fail on nonexistent service."""
    result = CliRunner().invoke(cli, args=['--iamroot', '--home', str(tmpdir), 'show', 'this_should_never_exist'])
    assert result.exit_code != 0
    assert result.exception
    assert json_log_is_valid(str(tmpdir))


@pytest.mark.dependency(name='arg_missing', depends=['install_uninstall'])
def test_missing_arg(service_installed):
    """Test the :func:`honeycomb.cli.run` command with missing service parameter."""
    result = CliRunner().invoke(cli, args=['--iamroot', '--home', service_installed, 'run', DEMO_SERVICE])
    assert result.exit_code != 0
    assert result.exception
    assert "'port' is missing" in result.output, bytes(result.output)
    assert json_log_is_valid(service_installed)


@pytest.mark.dependency(name='arg_bad_int', depends=['install_uninstall'])
def test_arg_bad_int(service_installed):
    """Test the :func:`honeycomb.cli.run` with invalid int."""
    result = CliRunner().invoke(cli, args=['--iamroot', '--home', service_installed,
                                           'run', DEMO_SERVICE, 'port=notint'])
    assert result.exit_code != 0
    assert result.exception
    assert 'Bad value for port=notint (must be integer)' in result.output, bytes(result.output)
    assert json_log_is_valid(service_installed)


@pytest.mark.dependency(name='arg_bad_bool', depends=['install_uninstall'])
def test_arg_bad_bool(service_installed):
    """Test the :func:`honeycomb.cli.run` with invalid boolean."""
    result = CliRunner().invoke(cli, args=['--iamroot', '--home', service_installed,
                                           'run', DEMO_SERVICE, 'port=8888', 'threading=notbool'])
    assert result.exit_code != 0
    assert result.exception
    assert 'Bad value for threading=notbool (must be boolean)' in result.output, bytes(result.output)
    assert json_log_is_valid(service_installed)


@pytest.mark.dependency(name='run', depends=['arg_missing', 'arg_bad_int', 'arg_bad_bool'])
@pytest.mark.parametrize('running_service', [['port=8888']], indirect=['running_service'])
def test_run(running_service):
    """Test the :func:`honeycomb.cli.run` command and validate the serivce started properly."""
    assert wait_until(search_json_log, filepath=os.path.join(running_service, DEBUG_LOG_FILE), total_timeout=10,
                      key='message', value='Starting Simple HTTP service on port: 8888')

    r = rsession.get('http://localhost:8888')
    assert 'Welcome to nginx!' in r.text


@pytest.mark.dependency(depends=['run'])
@pytest.mark.parametrize('running_service', [['--json-log', JSON_LOG_FILE, 'port=8888']],
                         indirect=['running_service'])
def test_json_log(running_service):
    """Test the :func:`honeycomb.cli.run` command with a JSON alert output."""
    assert wait_until(search_json_log, filepath=os.path.join(running_service, DEBUG_LOG_FILE), total_timeout=10,
                      key='message', value='Starting Simple HTTP service on port: 8888')
    r = rsession.get('http://localhost:8888')
    assert 'Welcome to nginx!' in r.text

    json_log = wait_until(search_json_log, filepath=JSON_LOG_FILE, total_timeout=10,
                          key='event_type', value=DEMO_SERVICE)

    assert json_log['request'] == 'GET /'


@pytest.mark.dependency(depends=['run'])
@pytest.mark.parametrize('running_service', [['--syslog', '--syslog-host', SYSLOG_HOST,
                                              '--syslog-port', str(SYSLOG_PORT), 'port=8888']],
                         indirect=['running_service'])
def test_syslog(running_service, syslog):
    """Test the :func:`honeycomb.cli.run` command with a syslog alert outout."""
    assert wait_until(search_json_log, filepath=os.path.join(running_service, DEBUG_LOG_FILE), total_timeout=10,
                      key='message', value='Starting Simple HTTP service on port: 8888')
    r = rsession.get('http://localhost:8888')
    assert 'Welcome to nginx!' in r.text

    assert wait_until(search_file_log, filepath=syslog, total_timeout=10,
                      method='find', args='act={}'.format(DEMO_SERVICE_ALERT))

    assert wait_until(search_file_log, filepath=syslog, total_timeout=10,
                      method='find', args='request=GET /')

    assert wait_until(search_file_log, filepath=syslog, total_timeout=10,
                      method='find', args='src=127.0.0.1')


@pytest.mark.dependency(name='daemon', depends=['run'])
@pytest.mark.parametrize('running_daemon', [['port=8888']], indirect=['running_daemon'])
def test_daemon(running_daemon):
    """Test the :func:`honeycomb.cli.run` command in daemon mode."""
    r = rsession.get('http://localhost:8888')
    assert 'Welcome to nginx!' in r.text


@pytest.mark.dependency(depends=['daemon'])
@pytest.mark.parametrize('running_daemon', [['port=8888']], indirect=['running_daemon'])
def test_status(running_daemon):
    """Test the :func:`honeycomb.cli.status` command on a running daemon."""
    result = CliRunner().invoke(cli, args=['--home', running_daemon, 'status', DEMO_SERVICE])
    assert result.exit_code == 0
    assert not result.exception
    assert '{} - running'.format(DEMO_SERVICE) in result.output, bytes(result.output)
    assert json_log_is_valid(running_daemon)


@pytest.mark.dependency(depends=['daemon'])
@pytest.mark.parametrize('running_daemon', [['port=8888']], indirect=['running_daemon'])
def test_status_all(running_daemon):
    """Test the :func:`honeycomb.cli.status` command on all running services."""
    result = CliRunner().invoke(cli, args=['--home', running_daemon, 'status', '--show-all'])
    assert result.exit_code == 0
    assert not result.exception
    assert '{} - running'.format(DEMO_SERVICE) in result.output, bytes(result.output)
    assert json_log_is_valid(running_daemon)


@pytest.mark.dependency(depends=['daemon'])
@pytest.mark.parametrize('running_daemon', [['port=8888']], indirect=['running_daemon'])
def test_status_nonexistent(running_daemon):
    """Test the :func:`honeycomb.cli.status` command on a nonexistent service."""
    result = CliRunner().invoke(cli, args=['--home', running_daemon, 'status', 'nosuchservice'])
    assert result.exit_code == 0
    assert not result.exception
    assert 'nosuchservice - no such service' in result.output, bytes(result.output)
    assert json_log_is_valid(running_daemon)


def test_status_no_service(tmpdir):
    """Test the :func:`honeycomb.cli.status` without a serivce name."""
    result = CliRunner().invoke(cli, args=['--home', str(tmpdir), 'status'])
    assert result.exit_code != 0
    assert result.exception
    assert 'You must specify a service name' in result.output, bytes(result.output)
    assert json_log_is_valid(str(tmpdir))


@pytest.mark.dependency(depends=['daemon'])
@pytest.mark.parametrize('running_daemon', [['port=8888']], indirect=['running_daemon'])
def test_test(running_daemon):
    """Test the :func:`honeycomb.cli.test` command."""
    result = CliRunner().invoke(cli, args=['--home', running_daemon, 'test', DEMO_SERVICE])
    assert result.exit_code == 0
    assert not result.exception
    assert 'alert tested succesfully' in result.output, bytes(result.output)
    assert json_log_is_valid(running_daemon)
