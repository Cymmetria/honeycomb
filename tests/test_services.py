# -*- coding: utf-8 -*-
"""Honeycomb tests."""

import os
import signal
import tempfile
import requests
import subprocess
from requests.adapters import HTTPAdapter

import pytest
from click.testing import CliRunner

from honeycomb.cli import cli
from honeycomb.defs import DEBUG_LOG_FILE
from honeycomb.utils.wait import wait_until

from .utils.defs import COMMON_ARGS, SERVICES, SERVICE
from .utils.test_utils import sanity_check, search_json_log

DEMO_SERVICE = "simple_http"
DEMO_SERVICE_PORT = "8888/TCP"
DEMO_SERVICE_ALERT = "simple_http"
RUN_HONEYCOMB = "coverage run --parallel-mode --module --source=honeycomb honeycomb".split(" ")
JSON_LOG_FILE = tempfile.mkstemp()[1]
SYSLOG_HOST = "127.0.0.1"
SYSLOG_PORT = 5514
rsession = requests.Session()
rsession.mount("https://", HTTPAdapter(max_retries=3))


@pytest.fixture
def service_installed(tmpdir):
    """Prepare honeycomb home path with DEMO_SERVICE installed."""
    home = str(tmpdir)
    result = CliRunner().invoke(cli, args=COMMON_ARGS + [home, SERVICE,
                                                         "install", "sample_services/{}".format(DEMO_SERVICE)])
    sanity_check(result, home)
    assert os.path.exists(os.path.join(home, SERVICES, DEMO_SERVICE, "{}_service.py".format(DEMO_SERVICE)))

    yield home

    result = CliRunner().invoke(cli, args=COMMON_ARGS + [home, SERVICE, "uninstall", "-y", DEMO_SERVICE])
    sanity_check(result, home)
    assert os.path.exists(os.path.join(home, SERVICES))
    assert not os.path.exists(os.path.join(home, SERVICES, DEMO_SERVICE))


@pytest.fixture
def running_service(service_installed, request):
    """Provide a running instance with :func:`service_installed`."""
    args = COMMON_ARGS + [service_installed, SERVICE, 'run', DEMO_SERVICE]
    cmd = RUN_HONEYCOMB + args + request.param
    env = os.environ.copy()
    env.update({"DEBUG": "1"})
    p = subprocess.Popen(cmd, env=env)
    assert wait_until(search_json_log, filepath=os.path.join(service_installed, DEBUG_LOG_FILE), total_timeout=10,
                      key="message", value="Starting Simple HTTP service on port: 8888")
    yield service_installed
    p.send_signal(signal.SIGINT)
    p.wait()

    try:
        rsession.get("http://localhost:8888")
        assert False, "Service is still available (make sure to properly kill it before repeating test)"
    except requests.exceptions.ConnectionError:
        assert True


@pytest.fixture
def running_daemon(service_installed, request):
    """Provide a running daemon with :func:`service_installed`."""
    args = COMMON_ARGS + [service_installed, SERVICE, 'run', '--daemon', DEMO_SERVICE]
    cmd = RUN_HONEYCOMB + args + request.param
    env = os.environ.copy()
    env.update({"DEBUG": "1"})
    p = subprocess.Popen(cmd, env=env)
    p.wait()
    assert p.returncode == 0
    assert wait_until(search_json_log, filepath=os.path.join(service_installed, DEBUG_LOG_FILE), total_timeout=10,
                      key="message", value="Starting Simple HTTP service on port: 8888")

    assert rsession.get("http://localhost:8888")

    yield service_installed

    result = CliRunner().invoke(cli, args=COMMON_ARGS + [service_installed, SERVICE, "stop", DEMO_SERVICE])
    sanity_check(result, service_installed)
    assert wait_until(search_json_log, filepath=os.path.join(service_installed, DEBUG_LOG_FILE), total_timeout=10,
                      key="message", value="Simple HTTP service stopped")

    try:
        rsession.get("http://localhost:8888")
        assert False, "Service is still available (make sure to properly kill it before repeating test)"
    except requests.exceptions.ConnectionError:
        assert True


def test_cli_help():
    """Test honeycomb launches without an error (tests :func:`honeycomb.cli`)."""
    result = CliRunner().invoke(cli, args=[SERVICE, "--help"])
    sanity_check(result)


@pytest.mark.dependency(name="install_uninstall")
def test_install_uninstall(service_installed):
    """Test the :func:`honeycomb.cli.install` and :func:`honeycomb.cli.uninstall` commmands.

    This is just mock test for :func:`service_installed` fixture
    """
    assert service_installed


def test_list_nothing_installed(tmpdir):
    """Test the :func:`honeycomb.cli.list` command when nothing is installed."""
    result = CliRunner().invoke(cli, args=COMMON_ARGS + [str(tmpdir), SERVICE, "list"])
    sanity_check(result, str(tmpdir))


def test_list_remote(tmpdir):
    """Test the :func:`honeycomb.cli.list` command and also show services from remote repository."""
    result = CliRunner().invoke(cli, args=COMMON_ARGS + [str(tmpdir), SERVICE, "list", "--remote"])
    sanity_check(result, str(tmpdir))
    assert DEMO_SERVICE in result.output, result.output


@pytest.mark.dependency(depends=["install_uninstall"])
def test_list_local(service_installed):
    """Test the :func:`honeycomb.cli.list` command with a service installed."""
    result = CliRunner().invoke(cli, args=COMMON_ARGS + [service_installed, SERVICE, "list"])
    sanity_check(result, service_installed)
    assert "{} ({}) [Alerts: {}]".format(DEMO_SERVICE, DEMO_SERVICE_PORT,
                                         DEMO_SERVICE_ALERT) in result.output, result.output


def test_show_remote_not_installed(tmpdir):
    """Test the :func:`honeycomb.cli.show` command to show information from remote repository."""
    result = CliRunner().invoke(cli, args=COMMON_ARGS + [str(tmpdir), SERVICE, "show", DEMO_SERVICE])
    sanity_check(result, str(tmpdir))
    assert "Installed: False" in result.output, result.output
    assert "Name: {}".format(DEMO_SERVICE) in result.output, result.output


@pytest.mark.dependency(depends=["install_uninstall"])
def test_show_local_installed(service_installed):
    """Test the :func:`honeycomb.cli.show` command to show information about locally installe service."""
    result = CliRunner().invoke(cli, args=COMMON_ARGS + [service_installed, SERVICE, "show", DEMO_SERVICE])
    sanity_check(result, service_installed)
    assert "Installed: True" in result.output, result.output
    assert "Name: {}".format(DEMO_SERVICE) in result.output, result.output


def test_show_nonexistent(tmpdir):
    """Test the :func:`honeycomb.cli.test` command to fail on nonexistent service."""
    result = CliRunner().invoke(cli, args=COMMON_ARGS + [str(tmpdir), SERVICE, "show", "this_should_never_exist"])
    sanity_check(result, str(tmpdir), fail=True)


@pytest.mark.dependency(name="arg_missing", depends=["install_uninstall"])
def test_missing_arg(service_installed):
    """Test the :func:`honeycomb.cli.run` command with missing service parameter."""
    result = CliRunner().invoke(cli, args=COMMON_ARGS + [service_installed, SERVICE, "run", DEMO_SERVICE])
    sanity_check(result, service_installed, fail=True)
    assert "'port' is missing" in result.output, result.output


@pytest.mark.dependency(name="arg_bad_int", depends=["install_uninstall"])
def test_arg_bad_int(service_installed):
    """Test the :func:`honeycomb.cli.run` with invalid int."""
    result = CliRunner().invoke(cli, args=COMMON_ARGS + [service_installed, SERVICE, "run", DEMO_SERVICE, "port=noint"])
    sanity_check(result, service_installed, fail=True)
    assert "Bad value for port=noint (must be integer)" in result.output, result.output


@pytest.mark.dependency(name="arg_bad_bool", depends=["install_uninstall"])
def test_arg_bad_bool(service_installed):
    """Test the :func:`honeycomb.cli.run` with invalid boolean."""
    result = CliRunner().invoke(cli, args=COMMON_ARGS + [service_installed, SERVICE,
                                                         "run", DEMO_SERVICE, "port=8888", "threading=notbool"])
    sanity_check(result, service_installed, fail=True)
    assert "Bad value for threading=notbool (must be boolean)" in result.output, result.output


@pytest.mark.dependency(name="run", depends=["arg_missing", "arg_bad_int", "arg_bad_bool"])
@pytest.mark.parametrize("running_service", [["port=8888"]], indirect=["running_service"])
def test_run(running_service):
    """Test the :func:`honeycomb.cli.run` command and validate the serivce started properly."""
    assert wait_until(search_json_log, filepath=os.path.join(running_service, DEBUG_LOG_FILE), total_timeout=10,
                      key="message", value="Starting Simple HTTP service on port: 8888")

    r = rsession.get("http://localhost:8888")
    assert "Welcome to nginx!" in r.text


@pytest.mark.dependency(name="daemon", depends=["run"])
@pytest.mark.parametrize("running_daemon", [["port=8888"]], indirect=["running_daemon"])
def test_daemon(running_daemon):
    """Test the :func:`honeycomb.cli.run` command in daemon mode."""
    r = rsession.get("http://localhost:8888")
    assert "Welcome to nginx!" in r.text


@pytest.mark.dependency(depends=["daemon"])
@pytest.mark.parametrize("running_daemon", [["port=8888"]], indirect=["running_daemon"])
def test_status(running_daemon):
    """Test the :func:`honeycomb.cli.status` command on a running daemon."""
    result = CliRunner().invoke(cli, args=COMMON_ARGS + [running_daemon, SERVICE, "status", DEMO_SERVICE])
    sanity_check(result, running_daemon)
    assert "{} - running".format(DEMO_SERVICE) in result.output, result.output


@pytest.mark.dependency(depends=["daemon"])
@pytest.mark.parametrize("running_daemon", [["port=8888"]], indirect=["running_daemon"])
def test_status_all(running_daemon):
    """Test the :func:`honeycomb.cli.status` command on all running services."""
    result = CliRunner().invoke(cli, args=COMMON_ARGS + [running_daemon, SERVICE, "status", "--show-all"])
    sanity_check(result, running_daemon)
    assert "{} - running".format(DEMO_SERVICE) in result.output, result.output


def test_status_nonexistent(tmpdir):
    """Test the :func:`honeycomb.cli.status` command on a nonexistent service."""
    result = CliRunner().invoke(cli, args=COMMON_ARGS + [str(tmpdir), SERVICE, "status", "nosuchservice"])
    sanity_check(result, str(tmpdir), fail=True)
    assert "nosuchservice - no such service" in result.output, result.output


def test_status_no_service(tmpdir):
    """Test the :func:`honeycomb.cli.status` command without a serivce name."""
    result = CliRunner().invoke(cli, args=COMMON_ARGS + [str(tmpdir), SERVICE, "status"])
    sanity_check(result, str(tmpdir), fail=True)
    assert "You must specify a service name" in result.output, result.output


@pytest.mark.dependency(depends=["daemon"])
@pytest.mark.parametrize("running_daemon", [["port=8888"]], indirect=["running_daemon"])
def test_test(running_daemon):
    """Test the :func:`honeycomb.cli.test` command."""
    result = CliRunner().invoke(cli, args=COMMON_ARGS + [running_daemon, SERVICE, "test", DEMO_SERVICE])
    sanity_check(result, running_daemon)
    assert "alert tested succesfully" in result.output, result.output
