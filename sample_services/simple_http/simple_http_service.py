# -*- coding: utf-8 -*-
import os

from base_service import ServerCustomService

from six.moves.BaseHTTPServer import HTTPServer
from six.moves.SimpleHTTPServer import SimpleHTTPRequestHandler


HTTPD_PORT = 8888
EVENT_TYPE_FIELD_NAME = 'event_type'
SIMPLE_HTTP_ALERT_TYPE_NAME = 'simple_http'
ORIGINATING_IP_FIELD_NAME = 'originating_ip'
ORIGINATING_PORT_FIELD_NAME = 'originating_port'
REQUEST_FIELD_NAME = 'request'


class HoneyHTTPRequestHandler(SimpleHTTPRequestHandler, object):
    def version_string(self):
        return 'nginx'

    def send_head(self, *args, **kwargs):
        self.alert(self)
        return super(HoneyHTTPRequestHandler, self).send_head(*args, **kwargs)

    def alert(self, request):
        pass

    def log_error(self, msg, *args):
        self.log_message('error', msg, *args)

    def log_request(self, code='-', size='-'):
        self.log_message('debug', '"{:s}" {:s} {:s}'.format(self.requestline, str(code), str(size)))

    def log_message(self, level, msg, *args):
        getattr(self.logger, level)("{:s} - - [{:s}] {:s}".format(self.client_address[0], self.log_date_time_string(),
                                                                  msg % args))


class SimpleHTTPService(ServerCustomService):
    def __init__(self, *args, **kwargs):
        super(SimpleHTTPService, self).__init__(*args, **kwargs)
        self.httpd = None

    def alert(self, request):
        params = {
            EVENT_TYPE_FIELD_NAME: SIMPLE_HTTP_ALERT_TYPE_NAME,
            ORIGINATING_IP_FIELD_NAME: request.client_address[0],
            ORIGINATING_PORT_FIELD_NAME: request.client_address[1],
            REQUEST_FIELD_NAME: ' '.join([request.command, request.path]),
        }
        self.add_alert_to_queue(params)

    def on_server_start(self):

        os.chdir(os.path.join(os.path.dirname(__file__), 'www'))
        requestHandler = HoneyHTTPRequestHandler
        requestHandler.alert = self.alert
        requestHandler.logger = self.logger

        self.httpd = HTTPServer(('', HTTPD_PORT), requestHandler)

        self.signal_ready()
        self.logger.info("Starting Simple HTTP service on port: %d", HTTPD_PORT)
        self.httpd.serve_forever()

    def on_server_shutdown(self):
        if self.httpd:
            self.httpd.shutdown()
            self.logger.info("Simple HTTP service stopped")

    def __str__(self):
        return "Simple HTTP"


service_class = SimpleHTTPService
