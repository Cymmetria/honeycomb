# -*- coding: utf-8 -*-
"""Custom Service implementation from MazeRunner."""
from __future__ import unicode_literals, absolute_import


import sys
import logging
from attr import attrs, attrib
from threading import Thread
from multiprocessing import Process

import six
from six.moves.queue import Queue, Full, Empty

from honeycomb.decoymanager.models import Alert
from honeycomb.servicemanager.defs import SERVICE_ALERT_QUEUE_SIZE
from honeycomb.servicemanager.error_messages import INVALID_ALERT_TYPE
from honeycomb.integrationmanager.tasks import send_alert_to_subscribed_integrations


@attrs
class ServerCustomService(Process):
    """Custom Service Class.

    This class provides a basic wrapper for honeycomb and mazerunner services.

    :param service_args: Validated dictionary of service arguments (see: :func:`honeycomb.Honeycomb.parse_service_args`)
    """

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    alert_types = attrib(type=list)
    service_args = attrib(type=dict, default={})

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

        Override this and take care of gracefully shutting down you service (e.g., close files)
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

        while self.thread_server.is_alive():
            try:
                new_alert = self.alerts_queue.get(timeout=1)
                self.emit(**new_alert)
            except Empty:
                continue
            except Exception as exc:
                self.logger.exception(exc)
            except KeyboardInterrupt:
                self.logger.debug("Caught KeyboardInterrupt, shutting service down gracefully")
                self._on_server_shutdown()

    def run(self):
        """Daemon entry point."""
        self.run_service()

    def emit(self, **kwargs):
        """Send alerts to logfile.

        :param **kwargs: Fields to pass to :py:class:`honeycomb.decoymanager.models.Alert`
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
        if (signum):
            sys.stderr.write("Terminating on signal {}".format(signum))
            self.logger.debug("Terminating on signal {}".format(signum))
        self.on_server_shutdown()
        raise SystemExit()
