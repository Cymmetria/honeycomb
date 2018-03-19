# -*- coding: utf-8 -*-
"""Honeycomb service tests."""

from __future__ import absolute_import

import os
import signal
import requests
import subprocess
from requests.adapters import HTTPAdapter

import pytest
from click.testing import CliRunner

from honeycomb.cli import cli
from honeycomb import defs
from honeycomb.utils.wait import wait_until

from tests.utils.defs import plugins, commands, args
from tests.utils.syslog import runSyslogServer
from tests.utils.test_utils import sanity_check, search_json_log, search_file_log

DEMO_SERVICE = "simple_http"
DEMO_SERVICE_PORT = 8888
DEMO_SERVICE_ARGS = "port={}".format(DEMO_SERVICE_PORT)
DEMO_SERVICE_PORTS = "{}/TCP".format(DEMO_SERVICE_PORT)
DEMO_SERVICE_ALERT = "simple_http"
RUN_HONEYCOMB = "coverage run --parallel-mode --module --source=honeycomb honeycomb".split(" ")

SYSLOG_PORT = 5514
SYSLOG_HOST = "127.0.0.1"
DEMO_INTEGRATION = "syslog"
DEMO_INTEGRATION_ARGS = "protocol=udp address={} port={}".format(SYSLOG_HOST, SYSLOG_PORT)

rsession = requests.Session()
rsession.mount("https://", HTTPAdapter(max_retries=3))


@pytest.fixture
def syslogd(tmpdir):
    """Run a syslog server and provide the logfile."""
    logfile = str(tmpdir.join('syslog.log'))
    syslogd = runSyslogServer(SYSLOG_HOST, SYSLOG_PORT, logfile)
    yield logfile
    syslogd.shutdown()


@pytest.fixture
def service_installed(tmpdir):
    """Prepare honeycomb home path with DEMO_SERVICE installed."""
    home = str(tmpdir)
    result = CliRunner().invoke(cli, args=args.COMMON_ARGS + [home, plugins.SERVICE,
                                commands.INSTALL, os.path.join("sample_services", DEMO_SERVICE)])
    sanity_check(result, home)
    assert os.path.exists(os.path.join(home, plugins.SERVICES, DEMO_SERVICE, "{}_service.py".format(DEMO_SERVICE)))

    yield home

    result = CliRunner().invoke(cli, args=args.COMMON_ARGS + [home, plugins.SERVICE, commands.UNINSTALL,
                                                              args.YES, DEMO_SERVICE])
    sanity_check(result, home)
    assert os.path.exists(os.path.join(home, plugins.SERVICES))
    assert not os.path.exists(os.path.join(home, plugins.SERVICES, DEMO_SERVICE))


@pytest.fixture
def integration_installed(service_installed):
    """Prepare honeycomb home path with DEMO_INTEGRATION installed."""
    home = service_installed
    CliRunner().invoke(cli, args=args.COMMON_ARGS + [integration_installed, plugins.INTEGRATION,
                       commands.CONFIGURE, DEMO_INTEGRATION] + DEMO_INTEGRATION_ARGS.split(" "))
    result = CliRunner().invoke(cli, args=args.COMMON_ARGS + [home, plugins.INTEGRATION,
                                commands.INSTALL, os.path.join("sample_integrations", DEMO_INTEGRATION)])
    sanity_check(result, home)
    assert os.path.exists(os.path.join(home, plugins.INTEGRATIONS, DEMO_INTEGRATION, "integration.py"))

    yield home

    result = CliRunner().invoke(cli, args=args.COMMON_ARGS + [home, plugins.INTEGRATION,
                                commands.UNINSTALL, args.YES, DEMO_INTEGRATION])
    sanity_check(result, home)
    assert os.path.exists(os.path.join(home, plugins.INTEGRATIONS))
    assert not os.path.exists(os.path.join(home, plugins.INTEGRATIONS, DEMO_INTEGRATION))


@pytest.fixture
def running_service(service_installed, request):
    """Provide a running instance with :func:`service_installed`."""
    cmdargs = args.COMMON_ARGS + [service_installed, plugins.SERVICE, commands.RUN, DEMO_SERVICE]
    cmd = RUN_HONEYCOMB + cmdargs + request.param
    env = os.environ.copy()
    env["DEBUG"] = "1"
    p = subprocess.Popen(cmd, env=env)
    sanity_check(home=service_installed)
    assert wait_until(search_json_log, filepath=os.path.join(service_installed, defs.DEBUG_LOG_FILE), total_timeout=10,
                      key="message", value="Starting Simple HTTP service on port: {}".format(DEMO_SERVICE_PORT))
    yield service_installed
    p.send_signal(signal.SIGINT)
    p.wait()

    try:
        rsession.get("http://localhost:{}".format(DEMO_SERVICE_PORT))
        assert False, "Service is still available (make sure to properly kill it before repeating test)"
    except requests.exceptions.ConnectionError:
        assert True


@pytest.fixture
def running_service_with_integration(integration_installed, request):
    """Provide a running instance with :func:`integration_installed` and DEMO_INTEGRATION."""
    cmdargs = args.COMMON_ARGS + [integration_installed, plugins.SERVICE, commands.RUN, DEMO_SERVICE,
                                  args.INTEGRATION, DEMO_INTEGRATION]
    cmd = RUN_HONEYCOMB + cmdargs + request.param
    env = os.environ.copy()
    env["DEBUG"] = "1"
    print(cmd)
    p = subprocess.Popen(cmd, env=env)
    sanity_check(home=integration_installed)
    assert wait_until(search_json_log, filepath=os.path.join(integration_installed, defs.DEBUG_LOG_FILE), key="message",
                      total_timeout=10, value="Starting Simple HTTP service on port: {}".format(DEMO_SERVICE_PORT))
    yield integration_installed
    p.send_signal(signal.SIGINT)
    p.wait()

    try:
        rsession.get("http://localhost:{}".format(DEMO_SERVICE_PORT))
        assert False, "Service is still available (make sure to properly kill it before repeating test)"
    except requests.exceptions.ConnectionError:
        assert True


@pytest.fixture
def running_daemon(service_installed, request):
    """Provide a running daemon with :func:`service_installed`."""
    cmdargs = args.COMMON_ARGS + [service_installed, plugins.SERVICE, commands.RUN, args.DAEMON, DEMO_SERVICE]
    cmd = RUN_HONEYCOMB + cmdargs + request.param
    env = os.environ.copy()
    env["DEBUG"] = "1"
    p = subprocess.Popen(cmd, env=env)
    p.wait()
    sanity_check(home=service_installed)
    assert p.returncode == 0
    assert wait_until(search_json_log, filepath=os.path.join(service_installed, defs.DEBUG_LOG_FILE), total_timeout=10,
                      key="message", value="Starting Simple HTTP service on port: {}".format(DEMO_SERVICE_PORT))

    assert rsession.get("http://localhost:{}".format(DEMO_SERVICE_PORT))

    yield service_installed

    result = CliRunner().invoke(cli, args=args.COMMON_ARGS + [service_installed, plugins.SERVICE,
                                commands.STOP, DEMO_SERVICE])
    sanity_check(result, service_installed)
    assert wait_until(search_json_log, filepath=os.path.join(service_installed, defs.DEBUG_LOG_FILE), total_timeout=10,
                      key="message", value="Simple HTTP service stopped")

    try:
        rsession.get("http://localhost:{}".format(DEMO_SERVICE_PORT))
        assert False, "Service is still available (make sure to properly kill it before repeating test)"
    except requests.exceptions.ConnectionError:
        assert True


def test_cli_help():
    """Test honeycomb launches without an error (tests :func:`honeycomb.cli`)."""
    result = CliRunner().invoke(cli, args=[plugins.SERVICE, "--help"])
    sanity_check(result)


@pytest.mark.dependency(name="service_install_uninstall")
def test_service_install_uninstall(service_installed):
    """Test the service install and uninstall commmands.

    This is just mock test for :func:`service_installed` fixture
    """
    assert service_installed


def test_service_list_nothing_installed(tmpdir):
    """Test the service list command when nothing is installed."""
    result = CliRunner().invoke(cli, args=args.COMMON_ARGS + [str(tmpdir), plugins.SERVICE, "list"])
    sanity_check(result, str(tmpdir))


def test_service_list_remote(tmpdir):
    """Test the service list command and also show services from remote repository."""
    result = CliRunner().invoke(cli, args=args.COMMON_ARGS + [str(tmpdir), plugins.SERVICE, "list", "--remote"])
    sanity_check(result, str(tmpdir))
    assert DEMO_SERVICE in result.output, result.output


@pytest.mark.dependency(depends=["service_install_uninstall"])
def test_service_list_local(service_installed):
    """Test the service list command with a service installed."""
    result = CliRunner().invoke(cli, args=args.COMMON_ARGS + [service_installed, plugins.SERVICE, "list"])
    sanity_check(result, service_installed)
    assert "{} ({}) [Alerts: {}]".format(DEMO_SERVICE, DEMO_SERVICE_PORTS,
                                         DEMO_SERVICE_ALERT) in result.output, result.output


def test_service_show_remote_not_installed(tmpdir):
    """Test the service show command to show information from remote repository."""
    result = CliRunner().invoke(cli, args=args.COMMON_ARGS + [str(tmpdir), plugins.SERVICE, commands.SHOW,
                                DEMO_SERVICE])
    sanity_check(result, str(tmpdir))
    assert "Installed: False" in result.output, result.output
    assert "Name: {}".format(DEMO_SERVICE) in result.output, result.output


@pytest.mark.dependency(depends=["service_install_uninstall"])
def test_service_show_local_installed(service_installed):
    """Test the service show command to show information about locally installe service."""
    result = CliRunner().invoke(cli, args=args.COMMON_ARGS + [service_installed, plugins.SERVICE,
                                commands.SHOW, DEMO_SERVICE])
    sanity_check(result, service_installed)
    assert "Installed: True" in result.output, result.output
    assert "Name: {}".format(DEMO_SERVICE) in result.output, result.output


def test_service_show_nonexistent(tmpdir):
    """Test the service test command to fail on nonexistent service."""
    result = CliRunner().invoke(cli, args=args.COMMON_ARGS + [str(tmpdir), plugins.SERVICE, commands.SHOW,
                                "this_should_never_exist"])
    sanity_check(result, str(tmpdir), fail=True)


@pytest.mark.dependency(depends=["service_install_uninstall"])
def test_service_show_args(service_installed):
    """Test the service run command show-args."""
    result = CliRunner().invoke(cli, args=args.COMMON_ARGS + [service_installed, plugins.SERVICE, commands.RUN,
                                DEMO_SERVICE, "--show-args"])
    sanity_check(result, service_installed, fail=True)
    args_format = "{:20} {:10} {:^15} {:^10} {:25}"
    title = args_format.format(defs.NAME.upper(), defs.TYPE.upper(), defs.DEFAULT.upper(),
                               defs.REQUIRED.upper(), defs.DESCRIPTION.upper())

    assert title in result.output, result.output


@pytest.mark.dependency(name="service_arg_missing", depends=["service_install_uninstall"])
def test_service_missing_arg(service_installed):
    """Test the service run command with missing service parameter."""
    result = CliRunner().invoke(cli, args=args.COMMON_ARGS + [service_installed, plugins.SERVICE,
                                commands.RUN, DEMO_SERVICE])
    sanity_check(result, service_installed, fail=True)
    assert "'port' is missing" in result.output, result.output


@pytest.mark.dependency(name="service_arg_bad_int", depends=["service_install_uninstall"])
def test_service_arg_bad_int(service_installed):
    """Test the service run with invalid int."""
    result = CliRunner().invoke(cli, args=args.COMMON_ARGS + [service_installed, plugins.SERVICE,
                                commands.RUN, DEMO_SERVICE, "port=noint"])
    sanity_check(result, service_installed, fail=True)
    assert "Bad value for port=noint (must be integer)" in result.output, result.output


@pytest.mark.dependency(name="service_arg_bad_bool", depends=["service_install_uninstall"])
def test_service_arg_bad_bool(service_installed):
    """Test the service run with invalid boolean."""
    result = CliRunner().invoke(cli, args=args.COMMON_ARGS + [service_installed, plugins.SERVICE,
                                commands.RUN, DEMO_SERVICE, DEMO_SERVICE_ARGS, "threading=notbool"])
    sanity_check(result, service_installed, fail=True)
    assert "Bad value for threading=notbool (must be boolean)" in result.output, result.output


@pytest.mark.dependency(name="service_run",
                        depends=["service_arg_missing", "service_arg_bad_int", "service_arg_bad_bool"])
@pytest.mark.parametrize("running_service", [[DEMO_SERVICE_ARGS]], indirect=["running_service"])
def test_service_run(running_service):
    """Test the service run command and validate the serivce started properly."""
    assert wait_until(search_json_log, filepath=os.path.join(running_service, defs.DEBUG_LOG_FILE), total_timeout=10,
                      key="message", value="Starting Simple HTTP service on port: {}".format(DEMO_SERVICE_PORT))

    r = rsession.get("http://localhost:{}".format(DEMO_SERVICE_PORT))
    assert "Welcome to nginx!" in r.text


@pytest.mark.dependency(name="service_daemon", depends=["service_run"])
@pytest.mark.parametrize("running_daemon", [[DEMO_SERVICE_ARGS]], indirect=["running_daemon"])
def test_service_daemon(running_daemon):
    """Test the service run command in daemon mode."""
    r = rsession.get("http://localhost:{}".format(DEMO_SERVICE_PORT))
    assert "Welcome to nginx!" in r.text


@pytest.mark.dependency(depends=["service_daemon"])
@pytest.mark.parametrize("running_daemon", [[DEMO_SERVICE_ARGS]], indirect=["running_daemon"])
def test_service_status(running_daemon):
    """Test the service status command on a running daemon."""
    result = CliRunner().invoke(cli, args=args.COMMON_ARGS + [running_daemon, plugins.SERVICE, commands.STATUS,
                                DEMO_SERVICE])
    sanity_check(result, running_daemon)
    assert "{} - running".format(DEMO_SERVICE) in result.output, result.output


@pytest.mark.dependency(depends=["service_daemon"])
@pytest.mark.parametrize("running_daemon", [[DEMO_SERVICE_ARGS]], indirect=["running_daemon"])
def test_service_status_all(running_daemon):
    """Test the service status command on all running services."""
    result = CliRunner().invoke(cli, args=args.COMMON_ARGS + [running_daemon, plugins.SERVICE, commands.STATUS,
                                args.SHOW_ALL])
    sanity_check(result, running_daemon)
    assert "{} - running".format(DEMO_SERVICE) in result.output, result.output


def test_service_status_nonexistent(tmpdir):
    """Test the service status command on a nonexistent service."""
    result = CliRunner().invoke(cli, args=args.COMMON_ARGS + [str(tmpdir), plugins.SERVICE, commands.STATUS,
                                "nosuchservice"])
    sanity_check(result, str(tmpdir), fail=True)
    assert "nosuchservice - no such service" in result.output, result.output


def test_service_status_no_service(tmpdir):
    """Test the service status command without a serivce name."""
    result = CliRunner().invoke(cli, args=args.COMMON_ARGS + [str(tmpdir), plugins.SERVICE, commands.STATUS])
    sanity_check(result, str(tmpdir), fail=True)
    assert "You must specify a service name" in result.output, result.output


@pytest.mark.dependency(depends=["service_daemon"])
@pytest.mark.parametrize("running_daemon", [[DEMO_SERVICE_ARGS]], indirect=["running_daemon"])
def test_service_test(running_daemon):
    """Test the service test command."""
    result = CliRunner().invoke(cli, args=args.COMMON_ARGS + [running_daemon, plugins.SERVICE, commands.TEST,
                                DEMO_SERVICE])
    sanity_check(result, running_daemon)
    assert "alert tested succesfully" in result.output, result.output


@pytest.mark.dependency(depends=["service_install_uninstall"])
def test_integration_install_uninstall(integration_installed):
    """Test the integration install and uninstall commmands.

    This is just mock test for :func:`integration_installed` fixture
    """
    assert integration_installed


@pytest.mark.dependency(name="integration_configured", depends=["service_install_uninstall"])
def test_integration_configure(integration_installed):
    """Test the integration configure command."""
    result = CliRunner().invoke(cli, args=args.COMMON_ARGS + [integration_installed, plugins.INTEGRATION,
                                commands.CONFIGURE, DEMO_INTEGRATION] + DEMO_INTEGRATION_ARGS.split(" "))
    sanity_check(result, integration_installed)
    assert "has been configured, make sure to test it with" in result.output, result.output


@pytest.mark.dependency(depends=["integration_configured"])
def test_integration_test(integration_installed):
    """Test the integration test command."""
    CliRunner().invoke(cli, args=args.COMMON_ARGS + [integration_installed, plugins.INTEGRATION,
                       commands.CONFIGURE, DEMO_INTEGRATION] + DEMO_INTEGRATION_ARGS.split(" "))
    result = CliRunner().invoke(cli, args=args.COMMON_ARGS + [integration_installed, plugins.INTEGRATION,
                                commands.TEST, DEMO_INTEGRATION])
    sanity_check(result, integration_installed, fail=True)  # TODO: consider replacing with an integration has a test
    # assert "alert tested succesfully" in result.output, result.output


@pytest.mark.dependency(depends=["integration_configured", "service_run"])
@pytest.mark.parametrize("running_service_with_integration", [[DEMO_SERVICE_ARGS]],
                         indirect=["running_service_with_integration"])
def test_integration_run(running_service_with_integration, syslogd):
    """Test the integration test command."""
    assert running_service_with_integration
    rsession.get("http://localhost:{}".format(DEMO_SERVICE_PORT))
    assert wait_until(search_file_log, filepath=str(syslogd), method="find", args="GET /", total_timeout=3)
