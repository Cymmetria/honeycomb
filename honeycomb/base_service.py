# -*- coding: utf-8 -*-
"""Custom Service implementation from MazeRunner."""
import sys
import logging
from multiprocessing import Process


class ServerCustomService(Process):
    """Custom Service Class.

    This class provides a basic wrapper for honeycomb and mazerunner services.

    :param service_args: Validated dictionary of service arguments (see: :func:`honeycomb.Honeycomb.parse_service_args`)
    """

    # replace with pluggable logging (but keep logger methods so it interfaces)
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    service_args = None
    ready = False

    def __init__(self, service_args=None, *args, **kwargs):
        """Initialize the service object with optional arguments."""
        super(ServerCustomService, self).__init__(*args, **kwargs)
        self.service_args = service_args

    def signal_ready(self):
        """Signal the service manager this service is ready for incoming connections."""
        self.ready = True
        self.logger.debug('service is ready')

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
        """Run the service in a conrolled manner.

        .. seealso:: Use :func:`on_server_start` and :func:`on_server_shutdown` for starting and shutting down
                     your service
        """
        try:
            self._on_server_start()  # should hang by design
        except KeyboardInterrupt:
            self.logger.debug("Caught KeyboardInterrupt, shutting service down gracefully")
            self._on_server_shutdown()
        except Exception:
            self.logger.exception(None)

    def run(self):
        """Daemon entry point."""
        self.run_service()

    def emit(self, event_type, **kwargs):
        """Send alerts to logfile.

        :param event_type: type of the event, defined by system events or custom events that defined in the plugin
        :param event_description: message to pass
        :param kwargs: other fields to pass (see defs.AlertTypes)
        """
        params = {'event_type': event_type}
        params.update(kwargs)
        return self.logger.critical(params)

    def add_alert_to_queue(self, alert_dict):
        """Add alert to queue."""
        self.emit(**alert_dict)

    def _on_server_start(self):
        try:
            self.is_running = True
            self.on_server_start()
        except Exception:
            self.logger.exception(None)

    def _on_server_shutdown(self, signum=None, frame=None):
        self.is_running = False
        if (signum):
            sys.stderr.write('Terminating on signal {}'.format(signum))
            self.logger.debug('Terminating on signal {}'.format(signum))
        self.on_server_shutdown()
        raise SystemExit()
