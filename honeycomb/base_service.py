# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import logging


class ServerCustomService(object):
    # replace with pluggable logging (but keep logger methods so it interfaces)
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    # daemon properties
    pidfile_path = None
    stdout_path = None
    stderr_path = None
    stdin_path = "/dev/null"
    pidfile_timeout = 3

    def signal_ready(self):
        pass

    def __str__(self):
        return "Honeycomb Service - {}".format(self.__class__)

    def on_server_start(self):
        """
        Server run loop function
        The custom service manager will call this function in a new thread
        Must call self.signal_ready after finishing configuration
        """
        raise NotImplementedError

    def on_server_shutdown(self):
        """
        Shutdown function of the server
        have the same context as the on_server_start
        """
        raise NotImplementedError

    def run_service(self):
        try:
            self._on_server_start()  # should hang by design
        except KeyboardInterrupt:
            self.logger.debug("Caught KeyboardInterrupt, shutting service down gracefully")
            self._on_server_shutdown()
        except Exception:
            self.logger.exception(None)

    def run(self):
        """daemon entry point"""
        self.run_service()

    def emit(self, event_type, **kwargs):
        """
        Send alerts to logfile
        Args:
            event_type: type of the event, defined by system events or custom events that defined in the plugin
            event_description: message to pass
            **kwargs: other fields to pass (see defs.AlertTypes)
        """
        params = {'event_type': event_type}
        params.update(kwargs)
        return self.logger.critical(params)

    def add_alert_to_queue(self, alert_dict):
        self.emit(**alert_dict)

    def _on_server_start(self):
        try:
            self.is_running = True
            self.on_server_start()
        except Exception:
            self.logger.exception(None)

    def _on_server_shutdown(self, signum=None, frame=None):
        self.is_running = False
        if isinstance(signum, int):
            raise SystemExit("Terminating on signal {}".format(signum))
        self.on_server_shutdown()  # TODO: this is never actually reached
