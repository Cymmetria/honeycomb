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
from honeycomb import defs, integrationmanager
from honeycomb.utils.wait import wait_until, search_json_log

from tests.utils.defs import commands, args
from tests.utils.syslog import runSyslogServer
from tests.utils.test_utils import sanity_check, search_file_log

DEMO_SERVICE = "simple_http"
DEMO_SERVICE_PORT = 8888
DEMO_SERVICE_ARGS = "port={}".format(DEMO_SERVICE_PORT)
DEMO_SERVICE_PORTS = "Undefined"
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
    logfile = str(tmpdir.join("syslog.log"))
    syslogd = runSyslogServer(SYSLOG_HOST, SYSLOG_PORT, logfile)
    yield logfile
    syslogd.shutdown()


@pytest.fixture
def service_installed(tmpdir):
    """Prepare honeycomb home path with DEMO_SERVICE installed."""
    home = str(tmpdir)
    result = CliRunner().invoke(cli, args=args.COMMON_ARGS + [home, defs.SERVICE,
                                commands.INSTALL, DEMO_SERVICE])
    sanity_check(result, home)
    assert os.path.exists(os.path.join(home, defs.SERVICES, DEMO_SERVICE, "{}_service.py".format(DEMO_SERVICE)))

    yield home

    result = CliRunner().invoke(cli, args=args.COMMON_ARGS + [home, defs.SERVICE, commands.UNINSTALL,
                                                              args.YES, DEMO_SERVICE])
    sanity_check(result, home)
    assert os.path.exists(os.path.join(home, defs.SERVICES))
    assert not os.path.exists(os.path.join(home, defs.SERVICES, DEMO_SERVICE))


@pytest.fixture
def integration_installed(service_installed):
    """Prepare honeycomb home path with DEMO_INTEGRATION installed."""
    home = service_installed

    result = CliRunner().invoke(cli, args=args.COMMON_ARGS + [home, defs.INTEGRATION,
                                commands.INSTALL, DEMO_INTEGRATION])
    sanity_check(result, home)
    result = CliRunner().invoke(cli, args=args.COMMON_ARGS + [home, defs.INTEGRATION,
                                commands.CONFIGURE, DEMO_INTEGRATION] + DEMO_INTEGRATION_ARGS.split(" "))
    sanity_check(result, home)

    installed_integration_path = os.path.join(home, defs.INTEGRATIONS, DEMO_INTEGRATION)
    assert os.path.exists(os.path.join(installed_integration_path, integrationmanager.defs.ACTIONS_FILE_NAME))
    assert os.path.exists(os.path.join(installed_integration_path, defs.ARGS_JSON))

    yield home

    result = CliRunner().invoke(cli, args=args.COMMON_ARGS + [home, defs.INTEGRATION,
                                commands.UNINSTALL, args.YES, DEMO_INTEGRATION])
    sanity_check(result, home)
    assert os.path.exists(os.path.join(home, defs.INTEGRATIONS))
    assert not os.path.exists(os.path.join(home, defs.INTEGRATIONS, DEMO_INTEGRATION))


@pytest.fixture
def running_service(service_installed, request):
    """Provide a running instance with :func:`service_installed`."""
    cmdargs = args.COMMON_ARGS + [service_installed, defs.SERVICE, commands.RUN, DEMO_SERVICE]
    cmd = RUN_HONEYCOMB + cmdargs + request.param
    p = subprocess.Popen(cmd, env=os.environ)
    assert wait_until(search_json_log, filepath=os.path.join(service_installed, defs.DEBUG_LOG_FILE), total_timeout=10,
                      key="message", value="Starting Simple HTTP service on port: {}".format(DEMO_SERVICE_PORT))
    assert sanity_check(home=service_installed)

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
    cmdargs = args.COMMON_ARGS + [integration_installed, defs.SERVICE, commands.RUN, DEMO_SERVICE,
                                  args.INTEGRATION, DEMO_INTEGRATION]
    cmd = RUN_HONEYCOMB + cmdargs + request.param
    p = subprocess.Popen(cmd, env=os.environ)
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
    cmdargs = args.COMMON_ARGS + [service_installed, defs.SERVICE, commands.RUN, args.DAEMON, DEMO_SERVICE]
    cmd = RUN_HONEYCOMB + cmdargs + request.param
    p = subprocess.Popen(cmd, env=os.environ)
    p.wait()
    sanity_check(home=service_installed)
    assert p.returncode == 0
    assert wait_until(search_json_log, filepath=os.path.join(service_installed, defs.DEBUG_LOG_FILE), total_timeout=10,
                      key="message", value="Starting Simple HTTP service on port: {}".format(DEMO_SERVICE_PORT))

    assert rsession.get("http://localhost:{}".format(DEMO_SERVICE_PORT))

    yield service_installed

    result = CliRunner().invoke(cli, args=args.COMMON_ARGS + [service_installed, defs.SERVICE,
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
    result = CliRunner().invoke(cli, args=[args.HELP])
    sanity_check(result)


def test_service_command():
    """Test honeycomb service command."""
    result = CliRunner().invoke(cli, args=[defs.SERVICE, args.HELP])
    sanity_check(result)


def test_integration_command():
    """Test honeycomb integration command."""
    result = CliRunner().invoke(cli, args=[defs.INTEGRATION, args.HELP])
    sanity_check(result)


def test_invalid_command():
    """Test honeycomb invalud command."""
    result = CliRunner().invoke(cli, args=["nosuchcommand", args.HELP])
    sanity_check(result, fail=True)


def test_invalid_subcommand():
    """Test honeycomb invalud command."""
    result = CliRunner().invoke(cli, args=[defs.SERVICE, "nosuchsubcommand", args.HELP])
    sanity_check(result, fail=True)


@pytest.mark.dependency(name="service_install_uninstall")
def test_service_install_uninstall(service_installed):
    """Test the service install and uninstall commmands.

    This is just mock test for :func:`service_installed` fixture
    """
    assert service_installed


def test_service_list_nothing_installed(tmpdir):
    """Test the service list command when nothing is installed."""
    result = CliRunner().invoke(cli, args=args.COMMON_ARGS + [str(tmpdir), defs.SERVICE, "list"])
    sanity_check(result, str(tmpdir))


def test_service_list_remote(tmpdir):
    """Test the service list command and also show services from remote repository."""
    result = CliRunner().invoke(cli, args=args.COMMON_ARGS + [str(tmpdir), defs.SERVICE, "list", "--remote"])
    sanity_check(result, str(tmpdir))
    assert DEMO_SERVICE in result.output, result.output


@pytest.mark.dependency(depends=["service_install_uninstall"])
def test_service_list_local(service_installed):
    """Test the service list command with a service installed."""
    result = CliRunner().invoke(cli, args=args.COMMON_ARGS + [service_installed, defs.SERVICE, "list"])
    sanity_check(result, service_installed)
    assert "{} (Ports: {}) [Alerts: {}]".format(DEMO_SERVICE, DEMO_SERVICE_PORTS,
                                                DEMO_SERVICE_ALERT) in result.output, result.output


def test_service_show_remote_not_installed(tmpdir):
    """Test the service show command to show information from remote repository."""
    result = CliRunner().invoke(cli, args=args.COMMON_ARGS + [str(tmpdir), defs.SERVICE, commands.SHOW,
                                DEMO_SERVICE])
    sanity_check(result, str(tmpdir))
    assert "Installed: False" in result.output, result.output
    assert "Name: {}".format(DEMO_SERVICE) in result.output, result.output


@pytest.mark.dependency(depends=["service_install_uninstall"])
def test_service_show_local_installed(service_installed):
    """Test the service show command to show information about locally installe service."""
    result = CliRunner().invoke(cli, args=args.COMMON_ARGS + [service_installed, defs.SERVICE,
                                commands.SHOW, DEMO_SERVICE])
    sanity_check(result, service_installed)
    assert "Installed: True" in result.output, result.output
    assert "Name: {}".format(DEMO_SERVICE) in result.output, result.output


def test_service_show_nonexistent(tmpdir):
    """Test the service test command to fail on nonexistent service."""
    result = CliRunner().invoke(cli, args=args.COMMON_ARGS + [str(tmpdir), defs.SERVICE, commands.SHOW,
                                "this_should_never_exist"])
    sanity_check(result, str(tmpdir), fail=True)


@pytest.mark.dependency(depends=["service_install_uninstall"])
def test_service_show_args(service_installed):
    """Test the service run command show-args."""
    result = CliRunner().invoke(cli, args=args.COMMON_ARGS + [service_installed, defs.SERVICE, commands.RUN,
                                DEMO_SERVICE, "--show-args"])
    sanity_check(result, service_installed, fail=True)
    args_format = "{:20} {:10} {:^15} {:^10} {:25}"
    title = args_format.format(defs.NAME.upper(), defs.TYPE.upper(), defs.DEFAULT.upper(),
                               defs.REQUIRED.upper(), defs.DESCRIPTION.upper())

    assert title in result.output, result.output


@pytest.mark.dependency(name="service_arg_missing", depends=["service_install_uninstall"])
def test_service_missing_arg(service_installed):
    """Test the service run command with missing service parameter."""
    result = CliRunner().invoke(cli, args=args.COMMON_ARGS + [service_installed, defs.SERVICE,
                                commands.RUN, DEMO_SERVICE])
    sanity_check(result, service_installed, fail=True)
    assert "'port' is missing" in result.output, result.output


@pytest.mark.dependency(name="service_arg_bad_int", depends=["service_install_uninstall"])
def test_service_arg_bad_int(service_installed):
    """Test the service run with invalid int."""
    result = CliRunner().invoke(cli, args=args.COMMON_ARGS + [service_installed, defs.SERVICE,
                                commands.RUN, DEMO_SERVICE, "port=noint"])
    sanity_check(result, service_installed, fail=True)
    assert "Bad value for port=noint (must be integer)" in result.output, result.output


@pytest.mark.dependency(name="service_arg_bad_bool", depends=["service_install_uninstall"])
def test_service_arg_bad_bool(service_installed):
    """Test the service run with invalid boolean."""
    result = CliRunner().invoke(cli, args=args.COMMON_ARGS + [service_installed, defs.SERVICE,
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
    result = CliRunner().invoke(cli, args=args.COMMON_ARGS + [running_daemon, defs.SERVICE, commands.STATUS,
                                DEMO_SERVICE])
    sanity_check(result, running_daemon)
    assert "{} - running".format(DEMO_SERVICE) in result.output, result.output


@pytest.mark.dependency(depends=["service_daemon"])
@pytest.mark.parametrize("running_daemon", [[DEMO_SERVICE_ARGS]], indirect=["running_daemon"])
def test_service_status_all(running_daemon):
    """Test the service status command on all running services."""
    result = CliRunner().invoke(cli, args=args.COMMON_ARGS + [running_daemon, defs.SERVICE, commands.STATUS,
                                args.SHOW_ALL])
    sanity_check(result, running_daemon)
    assert "{} - running".format(DEMO_SERVICE) in result.output, result.output


def test_service_status_nonexistent(tmpdir):
    """Test the service status command on a nonexistent service."""
    result = CliRunner().invoke(cli, args=args.COMMON_ARGS + [str(tmpdir), defs.SERVICE, commands.STATUS,
                                "nosuchservice"])
    sanity_check(result, str(tmpdir), fail=True)
    assert "nosuchservice - no such service" in result.output, result.output


def test_service_status_no_service(tmpdir):
    """Test the service status command without a serivce name."""
    result = CliRunner().invoke(cli, args=args.COMMON_ARGS + [str(tmpdir), defs.SERVICE, commands.STATUS])
    sanity_check(result, str(tmpdir), fail=True)
    assert "You must specify a service name" in result.output, result.output


@pytest.mark.dependency(depends=["service_daemon"])
@pytest.mark.parametrize("running_daemon", [[DEMO_SERVICE_ARGS]], indirect=["running_daemon"])
def test_service_test(running_daemon):
    """Test the service test command."""
    result = CliRunner().invoke(cli, args=args.COMMON_ARGS + [running_daemon, defs.SERVICE, commands.TEST,
                                DEMO_SERVICE])
    sanity_check(result, running_daemon)
    assert "alert tested succesfully" in result.output, result.output


@pytest.mark.dependency(name="integration_install_uninstall", depends=["service_install_uninstall"])
def test_integration_install_uninstall(integration_installed):
    """Test the integration install and uninstall commmands.

    This is just mock test for :func:`integration_installed` fixture
    """
    assert integration_installed


def test_integration_list_nothing_installed(tmpdir):
    """Test the integration list command when nothing is installed."""
    result = CliRunner().invoke(cli, args=args.COMMON_ARGS + [str(tmpdir), defs.INTEGRATION, "list"])
    sanity_check(result, str(tmpdir))


def test_integration_list_remote(tmpdir):
    """Test the integration list command and also show integrations from remote repository."""
    result = CliRunner().invoke(cli, args=args.COMMON_ARGS + [str(tmpdir), defs.INTEGRATION, "list", "--remote"])
    sanity_check(result, str(tmpdir))
    assert DEMO_INTEGRATION in result.output, result.output


@pytest.mark.dependency(depends=["integration_install_uninstall"])
def test_integration_list_local(integration_installed):
    """Test the integration list command with a integration installed."""
    result = CliRunner().invoke(cli, args=args.COMMON_ARGS + [integration_installed, defs.INTEGRATION, "list"])
    sanity_check(result, integration_installed)
    assert DEMO_INTEGRATION in result.output, result.output


def test_integration_show_remote_not_installed(tmpdir):
    """Test the integration show command to show information from remote repository."""
    result = CliRunner().invoke(cli, args=args.COMMON_ARGS + [str(tmpdir), defs.INTEGRATION, commands.SHOW,
                                DEMO_INTEGRATION])
    sanity_check(result, str(tmpdir))
    assert "Installed: False" in result.output, result.output
    assert "Name: {}".format(DEMO_INTEGRATION.capitalize()) in result.output, result.output


@pytest.mark.dependency(depends=["integration_install_uninstall"])
def test_integration_show_local_installed(integration_installed):
    """Test the integration show command to show information about locally installe integration."""
    result = CliRunner().invoke(cli, args=args.COMMON_ARGS + [integration_installed, defs.INTEGRATION,
                                commands.SHOW, DEMO_INTEGRATION])
    sanity_check(result, integration_installed)
    assert "Installed: True" in result.output, result.output
    assert "Name: {}".format(DEMO_INTEGRATION) in result.output, result.output


def test_integration_show_nonexistent(tmpdir):
    """Test the integration test command to fail on nonexistent integration."""
    result = CliRunner().invoke(cli, args=args.COMMON_ARGS + [str(tmpdir), defs.INTEGRATION, commands.SHOW,
                                "this_should_never_exist"])
    sanity_check(result, str(tmpdir), fail=True)


@pytest.mark.dependency(name="integration_configured", depends=["integration_install_uninstall"])
def test_integration_configure(integration_installed):
    """Test the integration configure command."""
    result = CliRunner().invoke(cli, args=args.COMMON_ARGS + [integration_installed, defs.INTEGRATION,
                                commands.CONFIGURE, DEMO_INTEGRATION] + DEMO_INTEGRATION_ARGS.split(" "))
    sanity_check(result, integration_installed)
    assert "has been configured, make sure to test it with" in result.output, result.output


@pytest.mark.dependency(depends=["integration_configured"])
def test_integration_test(integration_installed):
    """Test the integration test command."""
    CliRunner().invoke(cli, args=args.COMMON_ARGS + [integration_installed, defs.INTEGRATION,
                       commands.CONFIGURE, DEMO_INTEGRATION] + DEMO_INTEGRATION_ARGS.split(" "))
    result = CliRunner().invoke(cli, args=args.COMMON_ARGS + [integration_installed, defs.INTEGRATION,
                                commands.TEST, DEMO_INTEGRATION])
    sanity_check(result, integration_installed, fail=True)  # TODO: consider replacing with an integration has a test
    # assert "alert tested succesfully" in result.output, result.output


@pytest.mark.dependency(name="integration_run", depends=["integration_configured", "service_run"])
@pytest.mark.parametrize("running_service_with_integration", [[DEMO_SERVICE_ARGS]],
                         indirect=["running_service_with_integration"])
def test_integration_run(running_service_with_integration, syslogd):
    """Test the integration test command."""
    assert running_service_with_integration
    rsession.get("http://localhost:{}".format(DEMO_SERVICE_PORT))
    assert wait_until(search_file_log, filepath=str(syslogd), method="find", args="GET /", total_timeout=3)


@pytest.mark.dependency(depends=["service_daemon"])
@pytest.mark.parametrize("running_daemon", [[DEMO_SERVICE_ARGS]], indirect=["running_daemon"])
def test_service_logs(running_daemon):
    """Test the service logs command."""
    teststring = "__LOGS_TEST__"
    nlines = 5

    # generate lots of logs
    for i in range(nlines * 2):
        rsession.get("http://localhost:{}/{}".format(DEMO_SERVICE_PORT, teststring))

    args_no_verbose = list(args.COMMON_ARGS)
    args_no_verbose.remove(args.VERBOSE)
    result = CliRunner().invoke(cli, args=args_no_verbose + [running_daemon, defs.SERVICE, commands.LOGS,
                                args.NUM, nlines, DEMO_SERVICE])
    sanity_check(result, running_daemon)
    assert teststring in result.output, "\n{}\n{}".format(result.output, repr(result.exception))
    # when honeycomb exits after printing the logs there's an additional empty line, we exclude it
    log_rows = len(result.output.split("\n")) - 1
    # if we are running as root the output will have an additional line of warning
    assert log_rows == nlines or log_rows == nlines + 1, "\n{}\n{}".format(result.output, repr(result.exception))


@pytest.mark.dependency(depends=["service_daemon"])
@pytest.mark.parametrize("running_daemon", [[DEMO_SERVICE_ARGS]], indirect=["running_daemon"])
def test_service_logs_follow(running_daemon):
    """Test the service logs command with follow."""
    # TODO: Test service logs -f
    # Consider https://stackoverflow.com/questions/375427/non-blocking-read-on-a-subprocess-pipe-in-python
    assert True
    """
    def wait_for_output(p, needle):
            i = 0
            output = ""
            success = False
            while i < 10:  # wait 5 seconds
                output += p.stdout.read()
                if "Starting Simple HTTP service" in output:
                    success = True
                    break
                time.sleep(0.5)
                i += 1
            assert success, output

        teststring = "__LOGS_TEST__"
        args_no_verbose = list(args.COMMON_ARGS)
        args_no_verbose.remove(args.VERBOSE)
        cmdargs = args_no_verbose + [running_daemon, defs.SERVICE, commands.LOGS, args.FOLLOW, DEMO_SERVICE]
        p = subprocess.Popen(RUN_HONEYCOMB + cmdargs, env=os.environ, stdout=subprocess.PIPE)
        wait_for_output(p, "Starting Simple HTTP service")

        rsession.get("http://localhost:{}/{}".format(DEMO_SERVICE_PORT, teststring))
        wait_for_output(p, teststring)

        p.send_signal(signal.SIGINT)
        assert wait_until(p.wait)
    """


@pytest.mark.dependency(depends=["service_run", "integration_run"])
def test_service_config(tmpdir):
    """Test honeycomb with a yml config."""
    home = str(tmpdir)
    configfile = tmpdir.join("honeycomb.yml")

    sampleconfig = """
---
version: 1

services:
  simple_http:
    parameters:
      port: 8888

integrations:
  syslog:
    parameters:
      address: "127.0.0.1"
      port: 5514
      protocol: tcp
    """

    configfile.write(sampleconfig)
    cmdargs = args.COMMON_ARGS + [home, args.CONFIG, str(configfile)]
    p = subprocess.Popen(RUN_HONEYCOMB + cmdargs, env=os.environ, stdout=subprocess.PIPE)
    assert wait_until(search_json_log, filepath=os.path.join(home, defs.DEBUG_LOG_FILE), total_timeout=20,
                      key="message", value="Starting Simple HTTP service on port: {}".format(DEMO_SERVICE_PORT))
    p.send_signal(signal.SIGINT)
    sanity_check(home=home)
    output = str(p.stdout.read())
    assert "Launching simple_http" in output
    assert "Adding integration syslog" in output
    assert "syslog has been configured" in output
