# -*- coding: utf-8 -*-
"""Custom Service implementation from MazeRunner."""
from __future__ import unicode_literals, absolute_import

import os
import sys
import time
import logging
from threading import Thread
from multiprocessing import Process

import six
import docker
from attr import attrs, attrib
from six.moves.queue import Queue, Full, Empty

from honeycomb.decoymanager.models import Alert
from honeycomb.servicemanager.defs import SERVICE_ALERT_QUEUE_SIZE
from honeycomb.servicemanager.error_messages import INVALID_ALERT_TYPE
from honeycomb.integrationmanager.tasks import send_alert_to_subscribed_integrations


@attrs
class ServerCustomService(Process):
    """Custom Service Class.

    This class provides a basic wrapper for honeycomb (and mazerunner) services.
    """

    alerts_queue = None
    thread_server = None

    logger = logging.getLogger(__name__)
    """Logger to be used by plugins and collected by main logger."""

    alert_types = attrib(type=list)
    """List of alert types, parsed from config.json"""

    service_args = attrib(type=dict, default={})
    """Validated dictionary of service arguments (see: :func:`honeycomb.utils.plugin_utils.parse_plugin_args`)"""

    logger.setLevel(logging.DEBUG)

    def signal_ready(self):
        """Signal the service manager this service is ready for incoming connections."""
        self.logger.debug("service is ready")

    def on_server_start(self):
        """Service run loop function.

        The service manager will call this function in a new thread.

        .. note:: Must call :func:`signal_ready` after finishing configuration
        """
        raise NotImplementedError

    def on_server_shutdown(self):
        """Shutdown function of the server.

        Override this and take care to gracefully shut down your service (e.g., close files)
        """
        raise NotImplementedError

    def run_service(self):
        """Run the service and start an alert processing queue.

        .. seealso:: Use :func:`on_server_start` and :func:`on_server_shutdown` for starting and shutting down
                     your service
        """
        self.alerts_queue = Queue(maxsize=SERVICE_ALERT_QUEUE_SIZE)
        self.thread_server = Thread(target=self._on_server_start)
        # self.thread_server.daemon = True
        self.thread_server.start()

        try:
            while self.thread_server.is_alive():
                try:
                    new_alert = self.alerts_queue.get(timeout=1)
                    self.emit(**new_alert)
                except Empty:
                    continue
                except KeyboardInterrupt:
                    self.logger.debug("Caught KeyboardInterrupt, shutting service down gracefully")
                    raise
                except Exception as exc:
                    self.logger.exception(exc)
        finally:
            self._on_server_shutdown()

    def run(self):
        """Daemon entry point."""
        self.run_service()

    def emit(self, **kwargs):
        """Send alerts to logfile.

        :param kwargs: Fields to pass to :py:class:`honeycomb.decoymanager.models.Alert`
        """
        try:
            alert_type = next(_ for _ in self.alert_types if _.name == kwargs["event_type"])
        except StopIteration:
            self.logger.error(INVALID_ALERT_TYPE, kwargs["event_type"])
            return

        self.logger.critical(kwargs)

        alert = Alert(alert_type)
        for key, value in six.iteritems(kwargs):
            setattr(alert, key, value)

        send_alert_to_subscribed_integrations(alert)

    def add_alert_to_queue(self, alert_dict):
        """Log alert and send to integrations."""
        try:
            self.alerts_queue.put(alert_dict, block=False)
        except Full:
            self.logger.warning("Queue (size=%d) is full and can't process messages", SERVICE_ALERT_QUEUE_SIZE)
        except Exception as exc:
            self.logger.exception(exc)

    def _on_server_start(self):
        try:
            self.on_server_start()
        except Exception as exc:
            self.logger.exception(exc)

    def _on_server_shutdown(self, signum=None, frame=None):
        if signum:
            sys.stderr.write("Terminating on signal {}".format(signum))
            self.logger.debug("Terminating on signal %s", signum)
        self.on_server_shutdown()
        raise SystemExit()


class DockerService(ServerCustomService):
    """Provides an ability to run a Docker container that will be monitored for events."""

    def __init__(self, *args, **kwargs):
        super(DockerService, self).__init__(*args, **kwargs)
        self._container = None
        self._docker_client = docker.from_env()

    @property
    def docker_params(self):
        """Return a dictionary of docker run parameters.

        .. seealso::
            Docker run: https://docs.docker.com/engine/reference/run/

        :return: Dictionary, e.g., :code:`dict(ports={80: 80})`
        """
        return {}

    @property
    def docker_image_name(self):
        """Return docker image name."""
        raise NotImplementedError

    def parse_line(self, line):
        """Parse line and return dictionary if its an alert, else None / {}."""
        raise NotImplementedError

    def get_lines(self):
        """Fetch log lines from the docker service.

        :return: A blocking logs generator
        """
        return self._container.logs(stream=True)

    def read_lines(self, file_path, empty_lines=False, signal_ready=True):
        """Fetch lines from file.

        In case the file handler changes (logrotate), reopen the file.

        :param file_path: Path to file
        :param empty_lines: Return empty lines
        :param signal_ready: Report signal ready on start
        """
        file_handler, file_id = self._get_file(file_path)
        file_handler.seek(0, os.SEEK_END)

        if signal_ready:
            self.signal_ready()

        while self.thread_server.is_alive():
            line = six.text_type(file_handler.readline(), "utf-8")
            if line:
                yield line
                continue
            elif empty_lines:
                yield line

            time.sleep(0.1)

            if file_id != self._get_file_id(os.stat(file_path)) and os.path.isfile(file_path):
                file_handler, file_id = self._get_file(file_path)

    @staticmethod
    def _get_file_id(file_stat):
        if os.name == "posix":
            # st_dev: Device inode resides on.
            # st_ino: Inode number.
            return "%xg%x" % (file_stat.st_dev, file_stat.st_ino)
        return "%f" % file_stat.st_ctime

    def _get_file(self, file_path):
        file_handler = open(file_path, "rb")
        file_id = self._get_file_id(os.fstat(file_handler.fileno()))
        return file_handler, file_id

    def on_server_start(self):
        """Service run loop function.

        Run the desired docker container with parameters and start parsing the monitored file for alerts.
        """
        self._container = self._docker_client.containers.run(self.docker_image_name, detach=True, **self.docker_params)
        self.signal_ready()

        for log_line in self.get_lines():
            try:
                alert_dict = self.parse_line(log_line)
                if alert_dict:
                    self.add_alert_to_queue(alert_dict)
            except Exception:
                self.logger.exception(None)

    def on_server_shutdown(self):
        """Stop the container before shutting down."""
        if not self._container:
            return
        self._container.stop()
        self._container.remove(v=True, force=True)
